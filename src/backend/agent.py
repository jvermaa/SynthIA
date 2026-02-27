"""
agent.py — Main agentic orchestration loop for SynthIA.

Connects to Ableton, feeds session state + user message to Gemini (with function
calling), executes any tool calls, and loops until the model returns a final
text response.

Run directly for an interactive CLI:
    python src/backend/agent.py
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from google import genai
from google.genai import types
from dotenv import load_dotenv

from ableton_connection import AbletonConnection, DEFAULT_HOST, DEFAULT_PORT
from session_state import describe_session, get_session_state
from system_prompt import build_system_prompt
from tools import ALL_TOOLS

load_dotenv()

# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------
MODEL = "gemini-2.5-flash"
MAX_AGENT_TURNS = 20  # Safety cap on the agentic loop

# Build the Gemini Tool object once at import time — it's stateless.
_GEMINI_TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t["parameters"] if t["parameters"]["properties"] else None,
            )
            for t in ALL_TOOLS
        ]
    )
]


# ---------------------------------------------------------------------------
# Core agent function
# ---------------------------------------------------------------------------

def run_agent(user_message: str, connection: AbletonConnection) -> str:
    """
    Run a single user request through the SynthIA agentic loop.

    Steps:
      1. Fetch current session state from Ableton.
      2. Build the Gemini request with system instruction + session state.
      3. Call Gemini with function calling enabled.
      4. If the model returns function_call parts, execute each command against
         Ableton and feed the results back as function_response parts.
      5. Repeat until the model returns a text-only response.
      6. Return the final text to the caller.
    """
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    # 1. Session state
    try:
        state = get_session_state(connection)
        session_desc = describe_session(state)
    except Exception as exc:
        session_desc = "Could not retrieve session state: {}".format(exc)

    system = build_system_prompt(session_desc)

    # 2. Initial contents — just the user message
    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)],
        )
    ]

    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=_GEMINI_TOOLS,
    )

    for _turn in range(MAX_AGENT_TURNS):
        # 3. Call Gemini
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0]
        model_content = candidate.content  # types.Content with role="model"

        # Append the model's turn to the conversation
        contents.append(model_content)

        # 4. Collect any function calls from this response
        function_calls = [
            part.function_call
            for part in model_content.parts
            if part.function_call is not None
        ]

        # If no function calls — the model is done; extract and return text
        if not function_calls:
            text_parts = [
                part.text
                for part in model_content.parts
                if part.text
            ]
            return "\n".join(text_parts).strip()

        # 5. Execute each function call and build function_response parts
        response_parts: list[types.Part] = []
        for fn_call in function_calls:
            tool_name: str = fn_call.name
            tool_args: dict[str, Any] = dict(fn_call.args) if fn_call.args else {}

            print("  [tool] {} {}".format(tool_name, json.dumps(tool_args)))

            try:
                result = connection.send_command(tool_name, tool_args)
                fn_response = {"result": result}
            except Exception as exc:
                error_msg = "Error executing {}: {}".format(tool_name, exc)
                print("  [tool error] {}".format(error_msg))
                fn_response = {"error": error_msg}

            response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response=fn_response,
                )
            )

        # Feed all function responses back in a single user turn
        contents.append(
            types.Content(role="user", parts=response_parts)
        )

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
