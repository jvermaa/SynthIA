"""
tools.py — Gemini function declaration schemas for all SynthIA / AbletonMCP commands.

ALL_TOOLS is a list of dicts in Gemini FunctionDeclaration format:
  {"name": str, "description": str, "parameters": <JSON schema>}

agent.py wraps these in types.Tool(function_declarations=[types.FunctionDeclaration(**t) ...]).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _tool(name: str, description: str, properties: dict, required: list) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


# ---------------------------------------------------------------------------
# 1. Session / Playback
# ---------------------------------------------------------------------------

GET_SESSION_STATE = _tool(
    name="get_session_state",
    description=(
        "Return a complete snapshot of the current Ableton Live session: "
        "tempo, time signature, playback state, all tracks with their devices "
        "(including every parameter name/value/min/max), and all clip slots "
        "including MIDI notes. Use this whenever you need an up-to-date view "
        "of the session."
    ),
    properties={},
    required=[],
)

SET_TEMPO = _tool(
    name="set_tempo",
    description="Set the session tempo in BPM.",
    properties={
        "tempo": {"type": "number", "description": "New tempo in BPM (e.g. 120.0)."}
    },
    required=["tempo"],
)

SET_TIME_SIGNATURE = _tool(
    name="set_time_signature",
    description="Set the song time signature.",
    properties={
        "numerator": {
            "type": "integer",
            "description": "Beats per bar (e.g. 4 for 4/4).",
        },
        "denominator": {
            "type": "integer",
            "description": "Beat unit (e.g. 4 for quarter notes).",
        },
    },
    required=["numerator", "denominator"],
)

START_PLAYBACK = _tool(
    name="start_playback",
    description="Start playing the Ableton session from the current position.",
    properties={},
    required=[],
)

STOP_PLAYBACK = _tool(
    name="stop_playback",
    description="Stop session playback.",
    properties={},
    required=[],
)

# ---------------------------------------------------------------------------
# 2. Track management
# ---------------------------------------------------------------------------

CREATE_MIDI_TRACK = _tool(
    name="create_midi_track",
    description="Create a new MIDI track in the session.",
    properties={
        "index": {
            "type": "integer",
            "description": "Position to insert the track (-1 = end of list).",
        }
    },
    required=[],
)

CREATE_AUDIO_TRACK = _tool(
    name="create_audio_track",
    description="Create a new audio track in the session.",
    properties={
        "index": {
            "type": "integer",
            "description": "Position to insert the track (-1 = end of list).",
        }
    },
    required=[],
)

CREATE_RETURN_TRACK = _tool(
    name="create_return_track",
    description=(
        "Create a new return (send) track. Ableton always appends return tracks "
        "at the end of the return track list."
    ),
    properties={},
    required=[],
)

DELETE_TRACK = _tool(
    name="delete_track",
    description="Delete the track at the given index. This is irreversible.",
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based index of the track to delete.",
        }
    },
    required=["track_index"],
)

SET_TRACK_NAME = _tool(
    name="set_track_name",
    description="Rename a track.",
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based index of the track.",
        },
        "name": {"type": "string", "description": "New track name."},
    },
    required=["track_index", "name"],
)

# ---------------------------------------------------------------------------
# 3. Track mixing
# ---------------------------------------------------------------------------

SET_TRACK_VOLUME = _tool(
    name="set_track_volume",
    description=(
        "Set a track's fader volume. "
        "Ableton LOM volume range is 0.0 (silence) to 0.85 (0 dB, unity gain). "
        "Values above 0.85 boost above unity."
    ),
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based track index.",
        },
        "value": {
            "type": "number",
            "description": "Volume level (0.0–0.85 for 0 dB, max ~1.0).",
        },
    },
    required=["track_index", "value"],
)

SET_TRACK_PAN = _tool(
    name="set_track_pan",
    description="Set a track's panning. -1.0 = full left, 0.0 = centre, 1.0 = full right.",
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based track index.",
        },
        "value": {
            "type": "number",
            "description": "Panning value from -1.0 to 1.0.",
        },
    },
    required=["track_index", "value"],
)

ARM_TRACK = _tool(
    name="arm_track",
    description="Arm or disarm a track for recording.",
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based track index.",
        },
        "arm": {"type": "boolean", "description": "true to arm, false to disarm."},
    },
    required=["track_index", "arm"],
)

MUTE_TRACK = _tool(
    name="mute_track",
    description="Mute or unmute a track.",
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based track index.",
        },
        "mute": {"type": "boolean", "description": "true to mute, false to unmute."},
    },
    required=["track_index", "mute"],
)

SOLO_TRACK = _tool(
    name="solo_track",
    description="Solo or unsolo a track.",
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based track index.",
        },
        "solo": {"type": "boolean", "description": "true to solo, false to unsolo."},
    },
    required=["track_index", "solo"],
)

# ---------------------------------------------------------------------------
# 4. Devices / Parameters
# ---------------------------------------------------------------------------

SET_DEVICE_PARAMETER = _tool(
    name="set_device_parameter",
    description=(
        "Set a single parameter on a device. Use get_session_state to find "
        "track_index, device_index, parameter_index, and the parameter's min/max "
        "range before calling this. Critical for mixing and sound design."
    ),
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based track index.",
        },
        "device_index": {
            "type": "integer",
            "description": "Zero-based device index within the track.",
        },
        "parameter_index": {
            "type": "integer",
            "description": "Zero-based parameter index within the device.",
        },
        "value": {
            "type": "number",
            "description": "New parameter value (must be within the parameter's min/max range).",
        },
    },
    required=["track_index", "device_index", "parameter_index", "value"],
)

LOAD_INSTRUMENT_OR_EFFECT = _tool(
    name="load_instrument_or_effect",
    description=(
        "Load an instrument or audio/MIDI effect onto a track using its browser URI. "
        "Use get_browser_tree / get_browser_items_at_path to discover URIs first."
    ),
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based track index.",
        },
        "uri": {
            "type": "string",
            "description": (
                "Browser URI of the instrument or effect, "
                "e.g. 'query:Synths#Instrument%20Rack:Bass:FileId_5116'."
            ),
        },
    },
    required=["track_index", "uri"],
)

# ---------------------------------------------------------------------------
# 5. Clips
# ---------------------------------------------------------------------------

CREATE_CLIP = _tool(
    name="create_clip",
    description="Create an empty MIDI clip in a track's clip slot.",
    properties={
        "track_index": {
            "type": "integer",
            "description": "Zero-based track index.",
        },
        "clip_index": {
            "type": "integer",
            "description": "Zero-based clip slot index.",
        },
        "length": {
            "type": "number",
            "description": "Clip length in beats (default 4.0).",
        },
    },
    required=["track_index", "clip_index"],
)

SET_CLIP_NAME = _tool(
    name="set_clip_name",
    description="Rename a clip.",
    properties={
        "track_index": {"type": "integer", "description": "Zero-based track index."},
        "clip_index": {"type": "integer", "description": "Zero-based clip slot index."},
        "name": {"type": "string", "description": "New clip name."},
    },
    required=["track_index", "clip_index", "name"],
)

FIRE_CLIP = _tool(
    name="fire_clip",
    description="Start playing a clip.",
    properties={
        "track_index": {"type": "integer", "description": "Zero-based track index."},
        "clip_index": {"type": "integer", "description": "Zero-based clip slot index."},
    },
    required=["track_index", "clip_index"],
)

STOP_CLIP = _tool(
    name="stop_clip",
    description="Stop playing a clip.",
    properties={
        "track_index": {"type": "integer", "description": "Zero-based track index."},
        "clip_index": {"type": "integer", "description": "Zero-based clip slot index."},
    },
    required=["track_index", "clip_index"],
)

GET_CLIP_NOTES = _tool(
    name="get_clip_notes",
    description=(
        "Retrieve all MIDI notes from a specific clip. Returns a list of notes with "
        "pitch (MIDI 0–127), start_time (in beats), duration (in beats), velocity (0–127), "
        "and mute flag."
    ),
    properties={
        "track_index": {"type": "integer", "description": "Zero-based track index."},
        "clip_index": {"type": "integer", "description": "Zero-based clip slot index."},
    },
    required=["track_index", "clip_index"],
)

SET_CLIP_NOTES = _tool(
    name="set_clip_notes",
    description=(
        "Replace ALL notes in a MIDI clip with the provided list. "
        "This is the primary way to write MIDI — first create_clip, then set_clip_notes. "
        "Pitch is a MIDI number (60 = C4). Times and durations are in beats. "
        "Velocity is 0–127. The existing notes are cleared before writing."
    ),
    properties={
        "track_index": {"type": "integer", "description": "Zero-based track index."},
        "clip_index": {"type": "integer", "description": "Zero-based clip slot index."},
        "notes": {
            "type": "array",
            "description": "List of note objects.",
            "items": {
                "type": "object",
                "properties": {
                    "pitch": {
                        "type": "integer",
                        "description": "MIDI pitch (0–127, 60=C4).",
                    },
                    "start_time": {
                        "type": "number",
                        "description": "Start position in beats.",
                    },
                    "duration": {
                        "type": "number",
                        "description": "Note duration in beats.",
                    },
                    "velocity": {
                        "type": "integer",
                        "description": "Velocity (0–127).",
                    },
                    "mute": {
                        "type": "boolean",
                        "description": "Whether the note is muted (default false).",
                    },
                },
                "required": ["pitch", "start_time", "duration", "velocity"],
            },
        },
    },
    required=["track_index", "clip_index", "notes"],
)

ADD_NOTES_TO_CLIP = _tool(
    name="add_notes_to_clip",
    description=(
        "Add MIDI notes to an existing clip without removing existing ones. "
        "Use set_clip_notes if you want a clean replacement."
    ),
    properties={
        "track_index": {"type": "integer", "description": "Zero-based track index."},
        "clip_index": {"type": "integer", "description": "Zero-based clip slot index."},
        "notes": {
            "type": "array",
            "description": "List of note objects to add.",
            "items": {
                "type": "object",
                "properties": {
                    "pitch": {"type": "integer", "description": "MIDI pitch (0–127)."},
                    "start_time": {"type": "number", "description": "Start in beats."},
                    "duration": {"type": "number", "description": "Duration in beats."},
                    "velocity": {"type": "integer", "description": "Velocity (0–127)."},
                    "mute": {"type": "boolean", "description": "Muted? Default false."},
                },
                "required": ["pitch", "start_time", "duration", "velocity"],
            },
        },
    },
    required=["track_index", "clip_index", "notes"],
)

# ---------------------------------------------------------------------------
# 6. Scenes
# ---------------------------------------------------------------------------

CREATE_SCENE = _tool(
    name="create_scene",
    description="Create a new scene at the end of the scene list.",
    properties={},
    required=[],
)

FIRE_SCENE = _tool(
    name="fire_scene",
    description="Launch all clips in a scene simultaneously.",
    properties={
        "scene_index": {
            "type": "integer",
            "description": "Zero-based scene index.",
        }
    },
    required=["scene_index"],
)

# ---------------------------------------------------------------------------
# 7. Browser (read-only, useful for discovery)
# ---------------------------------------------------------------------------

GET_BROWSER_TREE = _tool(
    name="get_browser_tree",
    description=(
        "Get a hierarchical tree of Ableton's browser categories "
        "(instruments, sounds, drums, audio_effects, midi_effects). "
        "Use this to discover available plugins and sounds."
    ),
    properties={
        "category_type": {
            "type": "string",
            "description": (
                "Category to browse: 'all', 'instruments', 'sounds', 'drums', "
                "'audio_effects', 'midi_effects'."
            ),
        }
    },
    required=[],
)

GET_BROWSER_ITEMS_AT_PATH = _tool(
    name="get_browser_items_at_path",
    description=(
        "Get browser items at a specific path, e.g. 'instruments/Synths'. "
        "Returns child items with names and URIs for loading."
    ),
    properties={
        "path": {
            "type": "string",
            "description": "Browser path in 'category/folder/subfolder' format.",
        }
    },
    required=["path"],
)

# ---------------------------------------------------------------------------
# Master list
# ---------------------------------------------------------------------------

ALL_TOOLS: list[dict] = [
    # Session / playback
    GET_SESSION_STATE,
    SET_TEMPO,
    SET_TIME_SIGNATURE,
    START_PLAYBACK,
    STOP_PLAYBACK,
    # Track management
    CREATE_MIDI_TRACK,
    CREATE_AUDIO_TRACK,
    CREATE_RETURN_TRACK,
    DELETE_TRACK,
    SET_TRACK_NAME,
    # Mixing
    SET_TRACK_VOLUME,
    SET_TRACK_PAN,
    ARM_TRACK,
    MUTE_TRACK,
    SOLO_TRACK,
    # Devices
    SET_DEVICE_PARAMETER,
    LOAD_INSTRUMENT_OR_EFFECT,
    # Clips
    CREATE_CLIP,
    SET_CLIP_NAME,
    FIRE_CLIP,
    STOP_CLIP,
    GET_CLIP_NOTES,
    SET_CLIP_NOTES,
    ADD_NOTES_TO_CLIP,
    # Scenes
    CREATE_SCENE,
    FIRE_SCENE,
    # Browser
    GET_BROWSER_TREE,
    GET_BROWSER_ITEMS_AT_PATH,
]
