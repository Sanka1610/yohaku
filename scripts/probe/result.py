"""Executable schema for Phase 1 metadata records (no runtime gate verdicts)."""

import json
import re
from datetime import datetime

SCHEMA_VERSION = 1
CASE_IDS = [f"{gate}{n:02}" for gate, count in (("A", 8), ("B", 6), ("C", 6))
            for n in range(1, count + 1)]
OBSERVATIONS = {"environment", "codex_version", "features", "config", "source"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names, label):
    require(type(value) is dict and set(value) == set(names.split()), label)


def text(value):
    return type(value) is str and bool(value.strip())


def timestamp(value):
    require(text(value) and value.endswith("+00:00"), "UTC timestamp required")
    datetime.fromisoformat(value)


def validate_value(name, value):
    if name == "environment":
        fields(value, "python python_executable os kernel machine distro wsl shell_environment cwd codex_home codex_home_source", "environment fields")
        for key in ("python", "python_executable", "os", "kernel", "machine", "cwd", "codex_home"):
            require(text(value[key]), f"environment {key}")
        require(type(value["wsl"]) is bool, "wsl flag")
        require(value["shell_environment"] is None or text(value["shell_environment"]), "shell")
        require(value["codex_home_source"] in ("default", "environment"), "home source")
        require(type(value["distro"]) is dict and set(value["distro"]) <= {"ID", "VERSION_ID"}
                and all(text(v) for v in value["distro"].values()), "distro")
    elif name == "codex_version":
        fields(value, "executable resolved_executable version", "codex fields")
        require(all(text(v) for v in value.values()), "codex values")
        require(re.fullmatch(r"codex-cli [0-9]+\.[0-9]+\.[0-9]+(?:[-+.][A-Za-z0-9.-]+)?", value["version"]), "codex version")
    elif name == "features":
        require(type(value) is dict and bool(value), "features")
        for key, feature in value.items():
            require(re.fullmatch(r"[a-z][a-z0-9_.]*", key), "feature name")
            fields(feature, "stage enabled", "feature fields")
            require(type(feature["enabled"]) is bool and feature["stage"] in
                    ("stable", "experimental", "under development", "deprecated", "removed"), "feature value")
    elif name == "config":
        require(type(value) is list and bool(value), "config sources")
        for entry in value:
            fields(entry, "path state selected", "config entry")
            require(text(entry["path"]) and entry["state"] in
                    ("absent", "read", "unavailable", "too_large", "unreadable_or_invalid"), "config state")
            selected = entry["selected"]
            require(type(selected) is dict and set(selected) <=
                    {"approval_policy", "sandbox_mode", "features", "plugins"}, "selected config")
            require(entry["state"] == "read" or not selected, "unread config values")
            for key, choices in (("approval_policy", ("untrusted", "on-failure", "on-request", "never")),
                                 ("sandbox_mode", ("read-only", "workspace-write", "danger-full-access"))):
                require(key not in selected or selected[key] in choices, "config enum")
            for key in ("features", "plugins"):
                values = selected.get(key, {})
                require(type(values) is dict, "config mapping")
                for identifier, item in values.items():
                    if key == "features":
                        require(re.fullmatch(r"[a-z][a-z0-9_.]*", identifier) and type(item) is bool, "declared feature")
                    else:
                        require(re.fullmatch(r"[A-Za-z0-9_.@/-]{1,200}", identifier), "plugin identifier")
                        fields(item, "enabled", "plugin declaration")
                        require(type(item["enabled"]) is bool, "plugin enabled")
    elif name == "source":
        fields(value, "root git_head dirty sha256", "source fields")
        require(text(value["root"]), "source root")
        require(value["git_head"] is None or (text(value["git_head"]) and
                re.fullmatch(r"[0-9a-f]{40,64}", value["git_head"])), "git revision")
        require(value["dirty"] is None or type(value["dirty"]) is bool, "dirty flag")
        require(type(value["sha256"]) is dict and bool(value["sha256"]), "source hashes")
        for path, digest in value["sha256"].items():
            require(text(path) and text(digest) and re.fullmatch(r"[0-9a-f]{64}", digest), "source hash")


def validate(record):
    fields(record, "schema_version run_id created_at kind runtime invocation observations cases limitations", "record fields")
    require(type(record["schema_version"]) is int and record["schema_version"] == SCHEMA_VERSION, "schema version")
    require(text(record["run_id"]) and re.fullmatch(r"[0-9a-f]{32}", record["run_id"]), "run ID")
    timestamp(record["created_at"])
    require(record["kind"] in ("metadata-only", "synthetic"), "record kind")
    require(record["runtime"] == "codex-cli-wsl", "runtime")
    require(type(record["invocation"]) is list and bool(record["invocation"])
            and all(text(s) for s in record["invocation"]), "invocation")
    require(type(record["limitations"]) is list and bool(record["limitations"])
            and all(text(s) for s in record["limitations"]), "limitations")
    observations = record["observations"]
    fields(observations, " ".join(sorted(OBSERVATIONS)), "observation names")
    for name, item in observations.items():
        fields(item, "status value reason evidence", f"{name}: fields")
        require(item["status"] in ("OBSERVED", "PARTIAL", "UNAVAILABLE"), "observation status")
        require(text(item["reason"]), "observation reason")
        fields(item["evidence"], "claim source authority scope freshness coverage", "evidence fields")
        evidence = item["evidence"]
        for key in ("claim", "source", "scope"):
            require(text(evidence[key]), f"evidence {key}")
        timestamp(evidence["freshness"])
        require(evidence["authority"] in ("authoritative", "observed", "inferred", "unknown"), "authority")
        require(evidence["coverage"] in ("complete_for_declared_scope", "partial", "not_observed", "out_of_scope", "unknown"), "coverage")
        if item["status"] == "UNAVAILABLE":
            require(item["value"] is None and evidence["authority"] == "unknown"
                    and evidence["coverage"] == "not_observed", "unavailable evidence")
        else:
            require(item["value"] is not None and evidence["authority"] != "unknown", "observed evidence")
            validate_value(name, item["value"])
            require(evidence["coverage"] == ("partial" if item["status"] == "PARTIAL"
                    else "complete_for_declared_scope"), "observation coverage")
    require(type(record["cases"]) is list and len(record["cases"]) == len(CASE_IDS), "case count")
    for case, case_id in zip(record["cases"], CASE_IDS):
        fields(case, "id gate status reason evidence hook_failure_behavior", "case fields")
        require(case["id"] == case_id and case["gate"] == case_id[0], "case identity")
        require(case["status"] == "NOT_RUN", "Phase 1 accepts only NOT_RUN gates")
        require(text(case["reason"]) and case["evidence"] == []
                and case["hook_failure_behavior"] is None, "unexecuted case evidence")
    json.dumps(record, allow_nan=False)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def read_record(path):
    require(path.stat().st_size <= 2 * 1024 * 1024, "result too large")
    with path.open(encoding="utf-8") as stream:
        content = stream.read(2 * 1024 * 1024 + 1)
    require(len(content) <= 2 * 1024 * 1024, "result too large")
    record = json.loads(content, object_pairs_hook=no_duplicates)
    validate(record)
    return record
