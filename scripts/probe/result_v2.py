"""Phase 2 case records, evidence integrity, and scoped completion summary."""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from result import CASE_IDS, fields, require, text, timestamp, validate_metadata

STATUSES = ("PASS", "PARTIAL", "FAIL", "UNSUPPORTED", "NOT_RUN")
AUTHORITIES = ("authoritative", "observed", "inferred", "unknown")
COMPLETENESS = ("complete_for_case", "partial", "not_observed", "out_of_scope", "unknown")


def strings(value, label, empty=False):
    require(type(value) is list and (empty or bool(value)) and all(text(x) for x in value), label)


def case_key(value):
    require(value["id"] in CASE_IDS, "case ID")
    fields(value["subject"], "kind name", "subject")
    subject = value["subject"]
    require(subject["kind"] == ("tool" if value["id"].startswith("A") else "backend"), "subject kind")
    require(text(subject["name"]) and re.fullmatch(r"[A-Za-z0-9_./:-]{1,160}", subject["name"]), "subject name")
    return value["id"], subject["kind"], subject["name"]


def verdict(value):
    fields(value, "status reason", "verdict")
    require(value["status"] in STATUSES and text(value["reason"]), "verdict status/reason")


def budget(value):
    fields(value, "allowed model max_requests max_tokens max_duration_sec synthetic_input", "model calls")
    require(type(value["allowed"]) is bool and value["synthetic_input"] is True, "synthetic model calls")
    for key in ("max_requests", "max_tokens", "max_duration_sec"):
        require(type(value[key]) is int and value[key] >= 0, "budget integer")
    if value["allowed"]:
        require(text(value["model"]) and all(value[k] > 0 for k in
                ("max_requests", "max_tokens", "max_duration_sec")), "positive live budget")
    else:
        require(value["model"] is None and all(value[k] == 0 for k in
                ("max_requests", "max_tokens", "max_duration_sec")), "disabled model calls")


def validate_environment(env):
    fields(env, "cli_command codex_home working_directory config_profile config_overrides "
           "project_trust hook_trust_state model provider_auth network_use max_requests "
           "max_tokens max_duration_sec budget_enforcement isolation evidence_refs", "environment contract")
    strings(env["cli_command"], "CLI command")
    require(all(text(env[k]) and Path(env[k]).is_absolute() for k in
                ("codex_home", "working_directory")), "environment paths")
    require(env["config_profile"] is None or text(env["config_profile"]), "config profile")
    require(type(env["config_overrides"]) is list, "overrides")
    # A closed set avoids copying arbitrary provider credentials/configuration.
    require(all(x in ("features.hooks=true", "analytics.enabled=false", "feedback.enabled=false")
                for x in env["config_overrides"]), "safe overrides")
    require(env["project_trust"] in ("unreviewed", "trusted", "untrusted", "unknown"), "project trust")
    require(env["hook_trust_state"] in ("unreviewed", "trusted", "untrusted", "bypassed", "unknown"), "hook trust")
    require(env["model"] is None or text(env["model"]), "environment model")
    fields(env["provider_auth"], "provider mode", "provider/auth")
    require(env["provider_auth"]["provider"] is None or text(env["provider_auth"]["provider"]), "provider")
    require(env["provider_auth"]["mode"] in ("none", "existing-cli-auth", "environment", "local"), "auth mode")
    require(env["network_use"] in ("none", "provider-only"), "network use")
    for key in ("max_requests", "max_tokens", "max_duration_sec"):
        require(type(env[key]) is int and env[key] >= 0, "environment budget")
    require(env["budget_enforcement"] in ("no-dispatch", "unverified", "verified"), "budget enforcement")
    fields(env["isolation"], "workspace session project_config probe_output temporary_files yohaku_state", "isolation")
    require(env["isolation"]["session"] == "new-session-only", "session isolation")
    for key, value in env["isolation"].items():
        require(key == "session" or (text(value) and Path(value).is_absolute()), "isolation path")
    require(env["working_directory"] == env["isolation"]["workspace"], "workspace identity")
    require(env["isolation"]["project_config"] == str(Path(env["working_directory"]) / ".codex"), "project config identity")
    strings(env["evidence_refs"], "environment evidence", empty=True)
    if env["project_trust"] == "trusted" or env["hook_trust_state"] in ("trusted", "bypassed"):
        require(bool(env["evidence_refs"]), "trust requires evidence")
    if env["budget_enforcement"] == "no-dispatch":
        require(env["model"] is None and env["provider_auth"] == {"provider": None, "mode": "none"}
                and env["network_use"] == "none" and all(env[k] == 0 for k in
                ("max_requests", "max_tokens", "max_duration_sec")), "no-dispatch environment")
    if env["budget_enforcement"] == "verified":
        require(bool(env["evidence_refs"]), "budget enforcement requires evidence")


def reference(value):
    require(text(value) and "\\" not in value, "evidence path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and path.as_posix() == value
            and value.startswith("evidence/"), "run-relative evidence")


def validate_case(item, kind):
    fields(item, "id gate subject trigger preconditions expected model_calls observations evidence "
           "coverage verdict failure_behavior unavailable", "case fields")
    key = case_key(item)
    require(item["gate"] == item["id"][0], "gate")
    fields(item["trigger"], "description command_or_prompt", "trigger")
    require(all(text(v) for v in item["trigger"].values()), "trigger text")
    strings(item["preconditions"], "preconditions")
    strings(item["expected"], "expected")
    budget(item["model_calls"])
    require(type(item["evidence"]) is list, "evidence list")
    refs = set()
    for ev in item["evidence"]:
        fields(ev, "ref sha256 claim source authority scope freshness coverage", "evidence")
        reference(ev["ref"])
        require(ev["ref"] not in refs, "duplicate evidence")
        refs.add(ev["ref"])
        require(text(ev["sha256"]) and re.fullmatch(r"[0-9a-f]{64}", ev["sha256"]), "evidence hash")
        for k in ("claim", "source", "scope"):
            require(text(ev[k]), "evidence text")
        require(ev["authority"] in AUTHORITIES and ev["coverage"] in COMPLETENESS, "evidence coverage")
        timestamp(ev["freshness"])
    require(type(item["observations"]) is list, "observations")
    for obs in item["observations"]:
        fields(obs, "type result evidence_refs", "observation")
        require(text(obs["type"]) and text(obs["result"]), "observation text")
        strings(obs["evidence_refs"], "observation refs")
        require(set(obs["evidence_refs"]) <= refs, "observation evidence missing")
    coverage = item["coverage"]
    fields(coverage, "authority scope completeness", "coverage")
    require(coverage["authority"] in AUTHORITIES and text(coverage["scope"])
            and coverage["completeness"] in COMPLETENESS, "case coverage")
    verdict(item["verdict"])
    status = item["verdict"]["status"]
    if status in ("PASS", "PARTIAL", "FAIL"):
        require(bool(item["observations"]) and bool(refs), "measured verdict requires observations/evidence")
        require(coverage["authority"] in ("observed", "authoritative"), "measured authority")
        require(any(ev["authority"] in ("observed", "authoritative") for ev in item["evidence"]), "observed evidence required")
    if status == "PASS":
        require(coverage["completeness"] == "complete_for_case", "PASS coverage")
    if status == "PARTIAL":
        require(coverage["completeness"] == "partial", "PARTIAL coverage")
    unavailable = item["unavailable"]
    if unavailable is not None:
        fields(unavailable, "reason evidence_refs", "unavailable")
        require(status in ("UNSUPPORTED", "NOT_RUN") and text(unavailable["reason"]), "unavailable verdict")
        strings(unavailable["evidence_refs"], "unavailable evidence")
        require(set(unavailable["evidence_refs"]) <= refs, "unavailable evidence missing")
    require(status != "UNSUPPORTED" or unavailable is not None, "unsupported requires grounds")
    failure = item["failure_behavior"]
    if item["id"] in ("A05", "A06", "A07", "A08") and status in ("PASS", "PARTIAL", "FAIL"):
        require(failure is not None, "failure axes required")
    if failure is not None:
        require(item["id"] in ("A05", "A06", "A07", "A08"), "failure case")
        fields(failure, "reproduction barrier_preserved behavior", "failure behavior")
        verdict(failure["reproduction"])
        verdict(failure["barrier_preserved"])
        require(failure["behavior"] in ("FAIL_OPEN", "FAIL_CLOSED", "UNKNOWN"), "failure outcome")
        if failure["behavior"] == "FAIL_OPEN":
            require(failure["barrier_preserved"]["status"] == "FAIL", "fail-open is not protected")
        if failure["barrier_preserved"]["status"] == "PASS":
            require(failure["reproduction"]["status"] == "PASS" and failure["behavior"] == "FAIL_CLOSED", "protected failure")
        if status == "PASS":
            require(failure["reproduction"]["status"] == "PASS", "failure observation PASS")
    if kind == "metadata-only":
        require(status == "NOT_RUN" and not item["observations"] and not refs
                and failure is None and unavailable is None and not item["model_calls"]["allowed"], "metadata-only verdict")
    return key


def validate_v2(record):
    fields(record, "schema_version run metadata environment scope cases limitations", "v2 fields")
    require(type(record["schema_version"]) is int and record["schema_version"] == 2, "v2 version")
    run = record["run"]
    fields(run, "id runtime timestamp kind invocation", "run")
    require(text(run["id"]) and re.fullmatch(r"[0-9a-f]{32}", run["id"]), "run ID")
    timestamp(run["timestamp"])
    require(run["runtime"] == "codex-cli-wsl" and run["kind"] in
            ("metadata-only", "runtime-probe", "synthetic"), "run kind/runtime")
    strings(run["invocation"], "runner invocation")
    validate_metadata(record["metadata"])
    strings(record["limitations"], "limitations")
    if record["environment"] is not None:
        validate_environment(record["environment"])
    require(run["kind"] != "runtime-probe" or record["environment"] is not None, "runtime contract required")
    require(type(record["scope"]) is list and bool(record["scope"]), "scope")
    scope = []
    for entry in record["scope"]:
        fields(entry, "id subject", "scope entry")
        scope.append(case_key(entry))
    require(len(set(scope)) == len(scope), "duplicate scoped case")
    require(type(record["cases"]) is list, "cases")
    keys = [validate_case(item, run["kind"]) for item in record["cases"]]
    require(len(keys) == len(set(keys)) and set(keys) == set(scope), "scope/cases mismatch")
    if run["kind"] == "runtime-probe":
        require(all(key[2] != "unselected" for key in keys), "runtime subject must be selected")
    env = record["environment"]
    if env is not None:
        refs = {ev["ref"] for item in record["cases"] for ev in item["evidence"]}
        require(set(env["evidence_refs"]) <= refs, "environment evidence missing")
        for item in record["cases"]:
            if run["kind"] == "runtime-probe" and item["verdict"]["status"] in ("PASS", "PARTIAL", "FAIL"):
                require(env["budget_enforcement"] == "verified", "measured runtime needs verified execution bounds")
            calls = item["model_calls"]
            if calls["allowed"]:
                require(calls["model"] == env["model"] and all(calls[k] <= env[k] for k in
                        ("max_requests", "max_tokens", "max_duration_sec")), "case exceeds environment budget")
    json.dumps(record, allow_nan=False)


def verify_artifacts(record, root):
    root = root.resolve()
    for item in record["cases"]:
        for ev in item["evidence"]:
            path = root / ev["ref"]
            require(path.resolve().is_relative_to(root), "evidence escapes run")
            require(not any(p.is_symlink() for p in (path, *path.parents) if p != root and p.is_relative_to(root)), "evidence symlink")
            require(path.is_file() and path.stat().st_size <= 2 * 1024 * 1024, "evidence file/size")
            require(hashlib.sha256(path.read_bytes()).hexdigest() == ev["sha256"], "evidence integrity")


def summarize(record):
    validate_v2(record)
    claims, cannot, fail_open, unknown, coverage = [], [], [], [], []
    accounted = True
    for item in record["cases"]:
        key = "/".join(case_key(item))
        status = item["verdict"]["status"]
        failure = item["failure_behavior"]
        if status == "NOT_RUN" and item["unavailable"] is None:
            accounted = False
        if failure and failure["behavior"] == "FAIL_OPEN":
            fail_open.append(key)
        protected = not failure or failure["barrier_preserved"]["status"] == "PASS"
        reason = item["verdict"]["reason"] if protected else failure["barrier_preserved"]["reason"]
        (claims if status == "PASS" and protected else cannot).append({"case": key, "reason": reason})
        if (status == "NOT_RUN" or item["coverage"]["completeness"] in ("unknown", "not_observed")
                or (failure and failure["behavior"] == "UNKNOWN")):
            unknown.append(key)
        coverage.append({"case": key, "verdict": status, "coverage": item["coverage"], "failure_behavior": failure})
    runtime = record["run"]["kind"] == "runtime-probe"
    observed = any(item["observations"] and item["verdict"]["status"] in ("PASS", "PARTIAL", "FAIL")
                   for item in record["cases"])
    return {"run": record["run"], "codex_version": record["metadata"]["codex_version"],
            "scope_accounted_for": accounted, "runtime_evidence": runtime and observed,
            "probe_work_complete_for_scope": runtime and accounted,
            "completion_note": "Scope accounting alone does not establish completion of the agreed Phase 2 scope.",
            "what_can_be_claimed": claims if runtime else [], "what_cannot_be_claimed": cannot if runtime else ["Runtime capabilities"],
            "known_fail_open_paths": fail_open if runtime else [], "known_unknowns": unknown,
            "coverage_profile_draft": coverage}
