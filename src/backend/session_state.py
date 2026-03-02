"""
session_state.py — Fetch and describe the current Ableton session state.
"""
from __future__ import annotations

from typing import Any, Dict

from ableton_connection import AbletonConnection


def get_session_state(connection: AbletonConnection) -> Dict[str, Any]:
    """
    Call `get_session_state` on the remote script and return the parsed dict.

    The returned dict contains:
      - tempo, time_signature, is_playing
      - tracks: list of track dicts (name, type, mute, solo, arm, volume, panning,
                devices with parameters, clip_slots with MIDI notes)
      - return_tracks: same structure, no arm field
      - master_track: volume, panning, devices
    """
    return connection.send_command("get_session_state")


def describe_session(
    state: Dict[str, Any],
    include_device_params: bool = False,
) -> str:
    """
    Produce a concise human-readable summary of the session for injection into
    the Claude system prompt.  Keeps it dense but legible.

    Args:
        state: Raw session state dict from get_session_state().
        include_device_params: When True, list device parameters (first 6 per
            device) for all tracks.  Defaults to False to save tokens; pass
            True when the user's request involves mixing or effects.
    """
    lines: list[str] = []

    ts = state.get("time_signature", {})
    lines.append(
        "Tempo: {tempo} BPM  |  Time sig: {num}/{den}  |  Playing: {playing}".format(
            tempo=state.get("tempo", "?"),
            num=ts.get("numerator", "?"),
            den=ts.get("denominator", "?"),
            playing=state.get("is_playing", False),
        )
    )
    lines.append(
        "Tracks: {tc}  |  Return tracks: {rc}".format(
            tc=state.get("track_count", 0),
            rc=state.get("return_track_count", 0),
        )
    )

    def _format_devices(devices: list) -> list[str]:
        device_lines = []
        for device in devices:
            if include_device_params:
                params = device.get("parameters", [])
                params_summary = ", ".join(
                    "{n}={v:.3f}".format(n=p.get("name", "?"), v=p.get("value", 0.0))
                    for p in params[:6]
                )
                more = " ..." if len(params) > 6 else ""
                device_lines.append(
                    "  Device [{di}] {dn}  |  {ps}{more}".format(
                        di=device.get("index", "?"),
                        dn=device.get("name", "?"),
                        ps=params_summary,
                        more=more,
                    )
                )
            else:
                device_lines.append(
                    "  Device [{di}] {dn}".format(
                        di=device.get("index", "?"),
                        dn=device.get("name", "?"),
                    )
                )
        return device_lines

    # ---- Regular tracks ----
    lines.append("\n=== Tracks ===")
    for track in state.get("tracks", []):
        flags: list[str] = []
        if track.get("mute"):
            flags.append("MUTED")
        if track.get("solo"):
            flags.append("SOLO")
        if track.get("arm"):
            flags.append("ARMED")

        lines.append(
            "[{idx}] {name}  ({type})  vol={vol:.3f}  pan={pan:.3f}  {flags}".format(
                idx=track.get("index", "?"),
                name=track.get("name", "Untitled"),
                type=track.get("type", "?"),
                vol=track.get("volume", 0.0),
                pan=track.get("panning", 0.0),
                flags="  ".join(flags) if flags else "",
            )
        )

        lines.extend(_format_devices(track.get("devices", [])))

        # Clip slots — empty slots omitted entirely
        for slot in track.get("clip_slots", []):
            if not (slot.get("has_clip") and slot.get("clip")):
                continue
            clip = slot["clip"]
            lines.append(
                "  Slot [{si}] clip='{cn}'  len={cl}  notes={nc}{playing}".format(
                    si=slot.get("index", "?"),
                    cn=clip.get("name", ""),
                    cl=clip.get("length", 0.0),
                    nc=len(clip.get("notes", [])),
                    playing="  PLAYING" if clip.get("is_playing") else "",
                )
            )

    # ---- Return tracks ----
    if state.get("return_tracks"):
        lines.append("\n=== Return Tracks ===")
        for track in state.get("return_tracks", []):
            lines.append(
                "[{idx}] {name}  vol={vol:.3f}  pan={pan:.3f}".format(
                    idx=track.get("index", "?"),
                    name=track.get("name", "Untitled"),
                    vol=track.get("volume", 0.0),
                    pan=track.get("panning", 0.0),
                )
            )
            lines.extend(_format_devices(track.get("devices", [])))

    # ---- Master track ----
    master = state.get("master_track", {})
    lines.append("\n=== Master Track ===")
    lines.append(
        "vol={vol:.3f}  pan={pan:.3f}".format(
            vol=master.get("volume", 0.0),
            pan=master.get("panning", 0.0),
        )
    )
    lines.extend(_format_devices(master.get("devices", [])))

    return "\n".join(lines)
