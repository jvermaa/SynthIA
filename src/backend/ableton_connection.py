"""
ableton_connection.py — Clean socket client for the Ableton Remote Script.

Stripped from the upstream AbletonMCP server.py — no MCP/FastMCP dependency.
"""
from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AbletonConnection")

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9877

# Commands that modify Live's state — these get a longer timeout and extra delay.
MODIFYING_COMMANDS = {
    # Existing
    "create_midi_track",
    "set_track_name",
    "create_clip",
    "add_notes_to_clip",
    "set_clip_name",
    "set_tempo",
    "fire_clip",
    "stop_clip",
    "set_device_parameter",
    "start_playback",
    "stop_playback",
    "load_instrument_or_effect",
    "load_browser_item",
    # New SynthIA commands
    "create_audio_track",
    "create_return_track",
    "delete_track",
    "set_track_volume",
    "set_track_pan",
    "arm_track",
    "mute_track",
    "solo_track",
    "set_time_signature",
    "create_scene",
    "fire_scene",
    "set_clip_notes",
}


@dataclass
class AbletonConnection:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    sock: Optional[socket.socket] = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Open a TCP connection to the Ableton Remote Script."""
        if self.sock:
            return True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info("Connected to Ableton at %s:%d", self.host, self.port)
            return True
        except Exception as exc:
            logger.error("Failed to connect to Ableton: %s", exc)
            self.sock = None
            return False

    def disconnect(self) -> None:
        """Close the TCP connection."""
        if self.sock:
            try:
                self.sock.close()
            except Exception as exc:
                logger.error("Error disconnecting from Ableton: %s", exc)
            finally:
                self.sock = None

    def is_connected(self) -> bool:
        return self.sock is not None

    # ------------------------------------------------------------------
    # Low-level I/O
    # ------------------------------------------------------------------

    def _receive_full_response(self, buffer_size: int = 8192) -> bytes:
        """Accumulate chunks until a complete JSON object is received."""
        chunks: list[bytes] = []
        self.sock.settimeout(15.0)

        try:
            while True:
                try:
                    chunk = self.sock.recv(buffer_size)
                    if not chunk:
                        if not chunks:
                            raise ConnectionError(
                                "Connection closed before receiving any data"
                            )
                        break

                    chunks.append(chunk)

                    # Try to parse; break as soon as we have valid JSON.
                    data = b"".join(chunks)
                    try:
                        json.loads(data.decode("utf-8"))
                        logger.debug("Complete response received (%d bytes)", len(data))
                        return data
                    except json.JSONDecodeError:
                        continue  # Incomplete — keep reading

                except socket.timeout:
                    logger.warning("Socket timeout during chunked receive")
                    break
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as exc:
                    logger.error("Socket error during receive: %s", exc)
                    raise

        except Exception:
            raise

        # Fell through timeout — try to return whatever we have.
        if chunks:
            data = b"".join(chunks)
            try:
                json.loads(data.decode("utf-8"))
                return data
            except json.JSONDecodeError:
                raise Exception("Incomplete JSON response received")
        raise Exception("No data received from Ableton")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_command(
        self, command_type: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a command to Ableton and return the parsed result dict.

        Raises on error (connection lost, Ableton error, timeout, bad JSON).
        """
        if not self.sock and not self.connect():
            raise ConnectionError("Not connected to Ableton")

        is_modifying = command_type in MODIFYING_COMMANDS

        command = {"type": command_type, "params": params or {}}

        try:
            logger.info("Sending command: %s  params=%s", command_type, params)
            self.sock.sendall(json.dumps(command).encode("utf-8"))
            logger.debug("Command sent, waiting for response...")

            if is_modifying:
                time.sleep(0.1)  # Give Ableton a moment to schedule the task

            self.sock.settimeout(15.0 if is_modifying else 10.0)

            response_data = self._receive_full_response()
            response = json.loads(response_data.decode("utf-8"))
            logger.info("Response status: %s", response.get("status", "unknown"))

            if response.get("status") == "error":
                raise Exception(
                    response.get("message", "Unknown error from Ableton")
                )

            if is_modifying:
                time.sleep(0.1)  # Extra settle time after state change

            return response.get("result", {})

        except socket.timeout:
            logger.error("Timeout waiting for Ableton response")
            self.sock = None
            raise Exception("Timeout waiting for Ableton response")

        except (ConnectionError, BrokenPipeError, ConnectionResetError) as exc:
            logger.error("Socket error: %s", exc)
            self.sock = None
            raise Exception("Connection to Ableton lost: {}".format(exc))

        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON from Ableton: %s", exc)
            self.sock = None
            raise Exception("Invalid response from Ableton: {}".format(exc))

        except Exception as exc:
            logger.error("Communication error with Ableton: %s", exc)
            self.sock = None
            raise
