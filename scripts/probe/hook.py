"""A01 hook fixture: record a bounded payload projection, never raw input/output."""

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from uuid import uuid4


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def observe(settings, payload):
    if type(payload) is not dict or payload.get("hook_event_name") not in ("PreToolUse", "PostToolUse"):
        raise ValueError("unsupported event")
    if payload.get("cwd") != settings["workspace"] or payload.get("tool_name") != settings["subject"]:
        raise ValueError("wrong fixture")
    ids = {}
    for key in ("session_id", "turn_id", "tool_use_id"):
        value = payload.get(key)
        if value is not None and (type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_:-]{1,160}", value)):
            raise ValueError("invalid identity")
        ids[key] = value
    command = payload.get("tool_input", {})
    command = command.get("command") if type(command) is dict else None
    match = (type(command) is str and
             hashlib.sha256(command.encode()).hexdigest() == settings["expected_command_sha256"])
    event = {"run_id": settings["run_id"], "case_id": "A01", "subject": settings["subject"],
             "event": payload["hook_event_name"], "monotonic_ns": time.monotonic_ns(),
             "identity": ids, "payload_received": True, "expected_command_matches": match,
             "tool_response_present": "tool_response" in payload,
             "evidence_limit": "Hook invocation source must be established by the external runtime trace"}
    if "tool_response" in payload:
        response = payload["tool_response"]
        rendered = json.dumps(response, ensure_ascii=False)
        exit_match = re.search(r'(?:Process exited with code |"exit_code"\s*:\s*)(-?\d+)', rendered)
        event["tool_result"] = {
            "response_type": type(response).__name__,
            "response_keys": sorted(response) if type(response) is dict else [],
            "exit_code": int(exit_match[1]) if exit_match else None,
            "bwrap_unavailable": "bubblewrap is unavailable" in rendered,
            "read_only_filesystem": "Read-only file system" in rendered,
            "response_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        }
    directory = Path(settings["events"])
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("invalid event directory")
    path = directory / f"{uuid4().hex}.json"
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump(event, stream, allow_nan=False)
        stream.write("\n")
    # The tool creates tool-marker.txt; a hook invocation alone cannot produce it.
    return event


def main():
    try:
        data = sys.stdin.buffer.read(65537)
        if len(data) > 65536:
            raise ValueError("payload size")
        settings = json.loads(Path(sys.argv[1]).read_text(), object_pairs_hook=unique)
        payload = json.loads(data, object_pairs_hook=unique)
        observe(settings, payload)
        print("{}")
        return 0
    except (OSError, ValueError, TypeError, KeyError, IndexError, RecursionError):
        print("Yohaku A01 fixture rejected input", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
