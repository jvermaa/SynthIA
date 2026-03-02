"""
agent.py — Main agentic orchestration loop for SynthIA.

Connects to Ableton, feeds session state + user message to Claude (with tool
use), executes any tool calls, and loops until the model returns a final
text response.

Run directly for an interactive CLI:
    python src/backend/agent.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import anthropic
from dotenv import load_dotenv

from ableton_connection import AbletonConnection, DEFAULT_HOST, DEFAULT_PORT
from session_state import describe_session, get_session_state
from system_prompt import build_system_prompt
from tools import BROWSER_TOOLS, CORE_TOOLS, MIXING_TOOLS

load_dotenv()

# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------
# Sonnet handles the first call (musical reasoning, planning).
# Haiku handles subsequent tool-result round trips (execution only) —
# cheaper, faster, and has a higher token-per-minute rate limit.
MODEL_REASONING = "claude-sonnet-4-20250514"
MODEL_EXECUTION = "claude-haiku-4-5-20251001"

MAX_AGENT_TURNS = 20   # Safety cap on agentic loop turns
MAX_TOOL_CALLS  = 10   # Cap total tool executions per request; force summary after

# ---------------------------------------------------------------------------
# Keyword sets for dynamic tool + session-state selection
# ---------------------------------------------------------------------------

# Controls whether BROWSER_TOOLS are appended to the tool list.
# Common instruments/effects now have known URIs in the system prompt, so the agent
# can load them directly without browsing.  Only add browser tools when the user
# explicitly wants to explore/search, or is asking for a preset by name.
_BROWSER_TOOL_KEYWORDS = {
    "browse", "find", "search", "preset",
}

# Controls whether MIXING_TOOLS are appended to the tool list.
_MIXING_TOOL_KEYWORDS = {
    "mix", "eq", "compress", "reverb", "delay", "volume", "pan",
    "effect", "gain", "filter", "send",
}

# Broader set — controls whether device parameters appear in session state.
_DEVICE_PARAM_KEYWORDS = {
    "mix", "volume", "vol", "pan", "panning", "reverb", "delay", "eq",
    "equalizer", "compress", "compressor", "effect", "plugin", "device",
    "parameter", "param", "cutoff", "filter", "gain", "frequency",
    "attack", "release", "ratio", "threshold", "send", "return", "master",
    "fader", "db", "decibel", "saturate", "distort", "chorus", "flanger",
}


def _words(message: str) -> set[str]:
    return set(message.lower().split())


def select_tools(message: str) -> list[dict]:
    """
    Return the minimal tool list needed for this request.

    Always starts with CORE_TOOLS, then conditionally appends:
      - BROWSER_TOOLS when the message references instruments/sounds/loading
      - MIXING_TOOLS  when the message references mixing/effects/devices
    """
    w = _words(message)
    tools = list(CORE_TOOLS)
    if w & _BROWSER_TOOL_KEYWORDS:
        tools.extend(BROWSER_TOOLS)
    if w & _MIXING_TOOL_KEYWORDS:
        tools.extend(MIXING_TOOLS)
    return tools


# ---------------------------------------------------------------------------
# Core agent function
# ---------------------------------------------------------------------------

def run_agent(user_message: str, connection: AbletonConnection) -> str:
    """
    Run a single user request through the SynthIA agentic loop.

    Steps:
      1. Fetch current session state from Ableton.
      2. Select tool subset and build system prompt.
      3. Call Claude (Sonnet) for the first turn — musical reasoning.
      4. If the model returns tool_use blocks, execute each command against
         Ableton and feed the results back as tool_result blocks.
      5. Subsequent turns use Haiku — just executing the established plan.
      6. After MAX_TOOL_CALLS total executions, force a summary response.
      7. Repeat until the model returns a text-only response.
      8. Return the final text to the caller.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # 1. Session state — include device params only for mixing/effects requests
    include_device_params = bool(_words(user_message) & _DEVICE_PARAM_KEYWORDS)
    try:
        state = get_session_state(connection)
        session_desc = describe_session(state, include_device_params=include_device_params)
    except Exception as exc:
        session_desc = "Could not retrieve session state: {}".format(exc)

    # 2. Select tools and build (cached) system prompt
    tools = select_tools(user_message)
    print("  [tools] {} selected ({} core + {} extra)".format(
        len(tools),
        len(CORE_TOOLS),
        len(tools) - len(CORE_TOOLS),
    ))

    # Wrap system prompt with cache_control so it is cached after the first call.
    # The system prompt + tools are stable across all turns in a request.
    system = [
        {
            "type": "text",
            "text": build_system_prompt(session_desc),
            "cache_control": {"type": "ephemeral"},
        }
    ]

    # 3. Initial messages
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_message},
    ]

    total_tool_calls = 0  # Running count across all turns

    for call_count in range(MAX_AGENT_TURNS):
        # First call: Sonnet for deep musical reasoning.
        # Subsequent calls: Haiku for cheap, fast tool-execution steps.
        model = MODEL_REASONING if call_count == 0 else MODEL_EXECUTION

        # 4. Call Claude (prompt-caching beta header keeps system + tools cached)
        response = client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=4096,
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        )

        # Log token usage so we can verify cache hits
        usage = response.usage
        cache_read   = getattr(usage, "cache_read_input_tokens",   0) or 0
        cache_write  = getattr(usage, "cache_creation_input_tokens", 0) or 0
        print("  [tokens] input={} cache_read={} cache_write={} output={} model={}".format(
            usage.input_tokens,
            cache_read,
            cache_write,
            usage.output_tokens,
            model,
        ))

        # Collect tool_use blocks
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        # If no tool calls — the model is done; extract and return text
        if not tool_use_blocks:
            text_parts = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_parts).strip()

        # Append the assistant turn
        messages.append({"role": "assistant", "content": response.content})

        # 5. Execute each tool call and collect results
        tool_results = []
        for block in tool_use_blocks:
            tool_name: str = block.name
            tool_args: dict[str, Any] = block.input  # already a dict

            print("  [tool] {} {}".format(tool_name, json.dumps(tool_args)))

            try:
                result = connection.send_command(tool_name, tool_args)
                tool_result_content = json.dumps({"result": result})
            except Exception as exc:
                error_msg = "Error executing {}: {}".format(tool_name, exc)
                print("  [tool error] {}".format(error_msg))
                tool_result_content = json.dumps({"error": error_msg})

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": tool_result_content,
            })

        total_tool_calls += len(tool_use_blocks)

        # Feed all tool results back in a single user turn
        messages.append({"role": "user", "content": tool_results})

        # 6. Tool call cap — force a summary response instead of continuing
        if total_tool_calls >= MAX_TOOL_CALLS:
            print("  [cap] {} tool calls reached — forcing summary response".format(
                total_tool_calls
            ))
            messages.append({
                "role": "user",
                "content": (
                    "[Tool cap reached: {used}/{max}] "
                    "Stop using tools. Summarise what has been completed so far "
                    "and what steps would remain to fully satisfy the original request."
                ).format(used=total_tool_calls, max=MAX_TOOL_CALLS),
            })
            final = client.messages.create(
                model=model,
                system=system,
                messages=messages,
                max_tokens=2048,
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
            )
            text_parts = [b.text for b in final.content if b.type == "text"]
            return "\n".join(text_parts).strip()

        # Brief pause to avoid bursting Anthropic rate limits on multi-step chains
        time.sleep(1.0)

    # Safety fallback if we somehow exhaust turns
    return "[SynthIA] Reached maximum agent turns without a final response."


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Interactive command-line loop for testing SynthIA."""
    print("SynthIA — Ableton AI Producer")
    print("=" * 40)
    print("Connecting to Ableton at {}:{}...".format(DEFAULT_HOST, DEFAULT_PORT))

    connection = AbletonConnection(host=DEFAULT_HOST, port=DEFAULT_PORT)
    if not connection.connect():
        print(
            "ERROR: Could not connect to Ableton. "
            "Make sure the remote script is loaded and Live is running."
        )
        sys.exit(1)

    print("Connected.  Type your request and press Enter.  Ctrl+C to quit.\n")

    try:
        while True:
            try:
                user_input = input("> ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            print("\nThinking...\n")
            try:
                response = run_agent(user_input, connection)
                print(response)
            except Exception as exc:
                print("Agent error: {}".format(exc))
            print()

    except KeyboardInterrupt:
        print("\nGoodbye.")
    finally:
        connection.disconnect()


if __name__ == "__main__":
    main()
