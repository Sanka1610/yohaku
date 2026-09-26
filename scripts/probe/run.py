#!/usr/bin/env python3
"""Collect v2 metadata or prepare isolated probes without model dispatch."""

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from metadata import collect, now
from result import CASE_IDS, SCHEMA_VERSION, read_record, validate
from result_v2 import summarize

ROOT = Path(__file__).resolve().parents[2]


def make_record(codex, invocation):
    return {
        "schema_version": SCHEMA_VERSION,
        "run": {"id": uuid4().hex, "timestamp": now(), "kind": "metadata-only",
                "runtime": "codex-cli-wsl", "invocation": invocation},
        "metadata": collect(ROOT, codex), "environment": None,
        "scope": [{"id": case, "subject": subject(case)} for case in CASE_IDS],
        "cases": [unexecuted_case(case, subject(case)) for case in CASE_IDS],
        "limitations": [
            "Metadata is a sequence of local observations, not an atomic runtime snapshot.",
            "Config declarations do not establish effective app settings or plugin load success.",
            "No model request, hook, rollover, handoff or Gate A/B/C was executed.",
            "Output storage is not the Phase 8 durable checkpoint adapter.",
        ],
    }


def subject(case):
    return {"kind": "tool" if case.startswith("A") else "backend", "name": "unselected"}


def unexecuted_case(case_id, target):
    return {"id": case_id, "gate": case_id[0], "subject": target,
            "trigger": {"description": "No runtime trigger selected", "command_or_prompt": "NOT_RUN"},
            "preconditions": ["Select a subject and fix the probe environment before execution"],
            "expected": ["Collect evidence before assigning a runtime verdict"],
            "model_calls": {"allowed": False, "model": None, "max_requests": 0, "max_tokens": 0,
                            "max_duration_sec": 0, "synthetic_input": True},
            "observations": [], "evidence": [],
            "coverage": {"authority": "unknown", "scope": target["name"], "completeness": "not_observed"},
            "verdict": {"status": "NOT_RUN", "reason": "No runtime gate was executed"},
            "failure_behavior": None, "unavailable": None}


def save_record(record, output, files=None):
    if record.get("schema_version") != 2:
        raise ValueError("writing v1 is not supported")
    validate(record)
    output.mkdir(parents=True, exist_ok=True)
    run_dir = output / record["run"]["id"]
    run_dir.mkdir(mode=0o700, exist_ok=False)
    for name, content in (files or {}).items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != name or name in (
                "result.json", "result.pending.json"):
            raise ValueError("unsafe artifact path")
        path = run_dir / relative
        for parent in reversed(path.parents):
            if parent != run_dir and parent.is_relative_to(run_dir):
                parent.mkdir(mode=0o700, exist_ok=True)
        with path.open("xb") as stream:
            os.chmod(path, 0o600)
            stream.write(content)
    # The final filename appears only after validation and round-trip readback.
    pending = run_dir / "result.pending.json"
    with pending.open("x", encoding="utf-8") as stream:
        os.chmod(pending, 0o600)
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    if read_record(pending) != record:
        raise ValueError("result readback mismatch")
    final = run_dir / "result.json"
    pending.rename(final)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("collect", help="Collect local metadata without running gates")
    capture.add_argument("--codex", default="codex", help="Trusted Codex executable path or PATH name")
    capture.add_argument("--output", type=Path, default=ROOT / "probe-results")
    prepare = commands.add_parser("prepare-a01", help="Prepare an isolated A01 fixture; never start Codex")
    prepare.add_argument("--codex", default="codex")
    prepare.add_argument("--output", type=Path, default=ROOT / "probe-results")
    prepare.add_argument("--subject", choices=("Bash", "apply_patch"), default="Bash")
    check = commands.add_parser("validate", help="Read and validate a v1 or v2 result")
    check.add_argument("result", type=Path)
    report = commands.add_parser("report", help="Summarize a v2 scope without promoting fixture checks")
    report.add_argument("result", type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        parser.error("Probe runner requires Python 3.14.x")
    try:
        if args.command == "validate":
            record = read_record(args.result)
            run = record["run"] if record["schema_version"] == 2 else {
                "id": record["run_id"], "kind": record["kind"]}
            print(f"VALID {run['id']} schema={record['schema_version']} kind={run['kind']}")
            return 0
        if args.command == "report":
            print(json.dumps(summarize(read_record(args.result)), ensure_ascii=False, indent=2))
            return 0
        invocation = [sys.executable, str(Path(__file__).resolve()), "collect",
                      "--codex", args.codex, "--output", str(args.output.absolute())]
        record = make_record(args.codex, invocation)
        files = None
        if args.command == "prepare-a01":
            from environment import prepare_a01
            record["run"]["invocation"] = [sys.executable, str(Path(__file__).resolve()),
                "prepare-a01", "--codex", args.codex, "--output", str(args.output.absolute()),
                "--subject", args.subject]
            files = prepare_a01(record, args.output.absolute(), args.subject)
        result = save_record(record, args.output.absolute(), files)
        missing = [name for name, item in record["metadata"].items() if item["status"] == "UNAVAILABLE"]
        print(f"SAVED {result}")
        print(f"gates=NOT_RUN; unavailable={','.join(missing) or 'none'}; config_coverage=partial")
        return 2 if missing else 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        # Do not echo malformed JSON, config values or subprocess stderr.
        print("ERROR: invalid input or result storage failure; no success claimed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
