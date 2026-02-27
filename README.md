# SynthIA

**Claude Code for music production** — an agentic AI assistant that runs inside Ableton Live.

SynthIA connects to Ableton via a Python Remote Script (TCP socket on port 9877), reads the entire session state, and uses Claude with extended thinking + tool use to understand and modify your Live set in response to natural language requests.

---

## Architecture

```
┌─────────────────────────────────────────┐
│              Ableton Live               │
│                                         │
│  src/remote_script/__init__.py          │
│  (Python Remote Script — TCP :9877)     │
└────────────────┬────────────────────────┘
                 │  TCP socket (JSON)
                 ▼
┌─────────────────────────────────────────┐
│           src/backend/                  │
│                                         │
│  ableton_connection.py  ← socket client │
│  session_state.py       ← state reader  │
│  tools.py               ← tool schemas  │
│  system_prompt.py       ← prompt builder│
│  agent.py               ← agentic loop  │
└─────────────────────────────────────────┘
                 │  Anthropic API
                 ▼
         Claude (claude-sonnet-4-*)
         extended thinking + tool use
```

---

## Setup

### 1. Install the Remote Script in Ableton

1. Find your Ableton MIDI Remote Scripts folder:
   - **macOS**: `/Applications/Ableton Live X.app/Contents/App-Resources/MIDI Remote Scripts/`
   - **Windows**: `C:\ProgramData\Ableton\Live X\Resources\MIDI Remote Scripts\`

2. Copy `src/remote_script/` into that folder and name it `SynthIA`:
   ```bash
   cp -r src/remote_script "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/MIDI Remote Scripts/SynthIA"
   ```

3. In Ableton: **Preferences → Link / Tempo / MIDI → Control Surface** — select **SynthIA** from the dropdown. You should see "AbletonMCP: Listening for commands on port 9877" in the status bar.

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

Or with uv:
```bash
uv pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

---

## Running

### Test the connection

Make sure Ableton is running with the remote script loaded, then:

```bash
python src/backend/test_connection.py
```

This prints the full session state as JSON and a human-readable summary.

### Start the AI agent

```bash
python src/backend/agent.py
```

Type your request at the `>` prompt. Examples:

```
> Set the tempo to 128 BPM and create a 4-bar kick pattern on track 0
> Add a reverb to the piano track and set the decay to 3 seconds
> Write a chord progression in C minor across 4 bars on track 1
> Mix everything: pull the bass up, bring the hi-hats down a bit, center the kick
> Mute all tracks except the drums
```

---

## How It Works

1. **Session snapshot** — On each request, SynthIA calls `get_session_state` which returns your entire Live set: every track, every device with every parameter, every clip with every MIDI note. This is injected into Claude's system prompt so the model "sees" your session.

2. **Extended thinking** — Claude uses up to 10,000 thinking tokens to reason about the request before deciding what to do.

3. **Tool loop** — Claude calls tools (e.g. `set_tempo`, `set_clip_notes`, `set_device_parameter`) which are executed against the remote script. Results are fed back to Claude. This repeats until Claude is done.

4. **Final response** — Claude returns a summary of what was done.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `get_session_state` | Full session snapshot |
| `set_tempo` | Set BPM |
| `set_time_signature` | Set time signature |
| `start_playback` / `stop_playback` | Transport control |
| `create_midi_track` | New MIDI track |
| `create_audio_track` | New audio track |
| `create_return_track` | New return track |
| `delete_track` | Delete a track |
| `set_track_name` | Rename a track |
| `set_track_volume` | Fader (0.0–0.85 = 0 dB) |
| `set_track_pan` | Panning (-1.0 to 1.0) |
| `arm_track` / `mute_track` / `solo_track` | Track states |
| `set_device_parameter` | Set any device knob/slider |
| `load_instrument_or_effect` | Load from browser by URI |
| `create_clip` | Create empty MIDI clip |
| `set_clip_name` | Rename a clip |
| `set_clip_notes` | Write MIDI notes (replaces all) |
| `add_notes_to_clip` | Add notes without clearing |
| `get_clip_notes` | Read MIDI notes from a clip |
| `fire_clip` / `stop_clip` | Clip playback |
| `create_scene` | New scene |
| `fire_scene` | Launch a scene |
| `get_browser_tree` | Browse available instruments |
| `get_browser_items_at_path` | Browse a specific path |

---

## Project Structure

```
src/
  remote_script/
    __init__.py          Ableton Remote Script (TCP server, LOM access)
  backend/
    __init__.py
    ableton_connection.py  Socket client
    session_state.py       State fetcher + describer
    tools.py               Claude API tool schemas
    system_prompt.py       Prompt template
    agent.py               Agentic loop + CLI
    test_connection.py     Connection smoke-test
upstream-reference/        Original AbletonMCP for reference
requirements.txt
.env.example
README.md
```

---

## Credits

Built on top of [AbletonMCP](https://github.com/ahujasid/ableton-mcp) by Sid Ahuja.
Powered by [Claude](https://anthropic.com) with extended thinking.
