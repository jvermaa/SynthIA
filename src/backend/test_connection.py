"""
test_connection.py — Quick smoke-test for the Ableton connection.

Usage:
    python src/backend/test_connection.py

Connects to Ableton, retrieves the full session state, prints it as JSON,
then prints the human-readable describe_session summary.
"""
from __future__ import annotations

import json
import sys

from ableton_connection import AbletonConnection, DEFAULT_HOST, DEFAULT_PORT
from session_state import describe_session, get_session_state


def main() -> None:
    print("Connecting to Ableton at {}:{}...".format(DEFAULT_HOST, DEFAULT_PORT))

    conn = AbletonConnection(host=DEFAULT_HOST, port=DEFAULT_PORT)
    if not conn.connect():
        print("ERROR: Could not connect. Is the remote script running?")
        sys.exit(1)

    print("Connected.\n")

    try:
        print("Fetching session state...")
        state = get_session_state(conn)

        print("\n--- RAW JSON ---")
        print(json.dumps(state, indent=2))

        print("\n--- DESCRIBE SESSION ---")
        print(describe_session(state))

    except Exception as exc:
        print("Error: {}".format(exc))
        sys.exit(1)
    finally:
        conn.disconnect()
        print("\nDisconnected.")


if __name__ == "__main__":
    main()
