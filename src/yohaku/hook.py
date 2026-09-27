"""Synchronous work admission and SessionStart recovery from the live owner."""

import argparse
import json
import socket
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise ValueError("oversized Hook input")
        payload = json.loads(raw)
        response = {}
        event = payload.get("hook_event_name")
        if (event in ("PreToolUse", "PostToolUse", "PreCompact")
                or (event == "SessionStart" and payload.get("source") == "compact")):
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(5)
                client.connect(args.socket)
                client.sendall(json.dumps(payload).encode() + b"\n")
                with client.makefile("rb") as stream:
                    wire = stream.readline(262145)
                if len(wire) > 262144 or not wire.endswith(b"\n"):
                    raise ValueError("invalid owner response")
                response = json.loads(wire)
        print(json.dumps(response))
    except (OSError, ValueError, AttributeError):
        # No payload/credentials in errors. Failure never authorizes resume.
        print("{}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
