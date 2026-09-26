#!/usr/bin/env python3
"""Collect Phase 1 metadata; never execute Gate A/B/C."""

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from metadata import collect, now
from result import CASE_IDS, SCHEMA_VERSION, read_record, validate

ROOT = Path(__file__).resolve().parents[2]


def make_record(codex, invocation):
    return {
        "schema_version": SCHEMA_VERSION, "run_id": uuid4().hex, "created_at": now(),
        "kind": "metadata-only", "runtime": "codex-cli-wsl", "invocation": invocation,
        "observations": collect(ROOT, codex),
        "cases": [{"id": case, "gate": case[0], "status": "NOT_RUN",
                   "reason": "Phase 1 collects metadata only; no runtime gate was executed",
                   "evidence": [], "hook_failure_behavior": None} for case in CASE_IDS],
        "limitations": [
            "Metadata is a sequence of local observations, not an atomic runtime snapshot.",
            "Config declarations do not establish effective app settings or plugin load success.",
            "No model request, hook, rollover, handoff or Gate A/B/C was executed.",
            "Output storage is not the Phase 8 durable checkpoint adapter.",
        ],
    }


def save_record(record, output):
    validate(record)
    output.mkdir(parents=True, exist_ok=True)
    run_dir = output / record["run_id"]
    run_dir.mkdir(mode=0o700, exist_ok=False)
    # The final filename appears only after validation and round-trip readback.
    pending = run_dir / "result.pending.json"
    with pending.open("x", encoding="utf-8") as stream:
        os.chmod(pending, 0o600)
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    if read_record(pending) != record:
        raise ValueError("result readback mismatch")
    fixture = run_dir / "fixture"
    fixture.mkdir(mode=0o700)
    (fixture / "marker.txt").write_text("Yohaku synthetic fixture; no runtime probe executed.\n", encoding="utf-8")
    final = run_dir / "result.json"
    pending.rename(final)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("collect", help="Collect local metadata without running gates")
    capture.add_argument("--codex", default="codex", help="Trusted Codex executable path or PATH name")
    capture.add_argument("--output", type=Path, default=ROOT / "probe-results")
    check = commands.add_parser("validate", help="Validate one Phase 1 result file")
    check.add_argument("result", type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        parser.error("Phase 1 requires Python 3.14.x")
    try:
        if args.command == "validate":
            record = read_record(args.result)
            print(f"VALID {record['run_id']} kind={record['kind']} gates=NOT_RUN")
            return 0
        invocation = [sys.executable, str(Path(__file__).resolve()), "collect",
                      "--codex", args.codex, "--output", str(args.output.absolute())]
        record = make_record(args.codex, invocation)
        result = save_record(record, args.output.absolute())
        missing = [name for name, item in record["observations"].items() if item["status"] == "UNAVAILABLE"]
        print(f"SAVED {result}")
        print(f"gates=NOT_RUN; unavailable={','.join(missing) or 'none'}; config_coverage=partial")
        return 2 if missing else 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        # Do not echo malformed JSON, config values or subprocess stderr.
        print("ERROR: invalid input or result storage failure; no success claimed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
