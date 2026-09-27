"""Prepare a no-dispatch A01 environment. Authentication is never copied."""

import hashlib
import json
import re
import shlex
import sys
from pathlib import Path


def prepare_a01(record, output, subject):
    # Import here because the CLI also imports this module during preparation.
    from run import unexecuted_case

    cli = record["metadata"]["codex_version"]["value"]
    if cli is None:
        raise ValueError("CLI identity is required")
    base = (output / record["run"]["id"]).resolve()
    workspace = base / "workspace"
    command = "printf 'YOH_A01_TOOL_OK\\n' > tool-marker.txt"
    if subject == "apply_patch":
        command = "*** Begin Patch\n*** Add File: tool-marker.txt\n+YOH_A01_TOOL_OK\n*** End Patch"
    prompt = (f"Synthetic A01 capability probe. Use {subject} exactly once with the following "
              f"input, then finish. Do not substitute another tool or repeat the operation.\n{command}")
    target = {"kind": "tool", "name": subject}
    case = unexecuted_case("A01", target)
    case["trigger"] = {"description": "Observe PreToolUse/PostToolUse and the tool's own marker",
                       "command_or_prompt": prompt}
    case["preconditions"] = ["Dedicated new session and workspace", "Project and hook trust reviewed",
                             "Barrier inactive", "tool-marker.txt absent", "Model budget fixed and enforced"]
    case["expected"] = ["PreToolUse payload received", "PostToolUse correlated by tool_use_id",
                        "tool-marker.txt contains YOH_A01_TOOL_OK"]
    record["run"]["kind"] = "runtime-probe"
    record["scope"] = [{"id": "A01", "subject": target}]
    record["cases"] = [case]
    overrides = ["features.hooks=true", "analytics.enabled=false", "feedback.enabled=false"]
    argv = [cli["executable"], "exec", "--ephemeral", "--skip-git-repo-check",
            "--ignore-user-config", "--sandbox", "workspace-write", "--json", "--cd", str(workspace)]
    for override in overrides:
        argv += ["-c", override]
    argv.append("-")
    record["environment"] = {
        "cli_command": argv, "codex_home": str(base / "codex-home"),
        "working_directory": str(workspace), "config_profile": None, "config_overrides": overrides,
        "project_trust": "unreviewed", "hook_trust_state": "unreviewed", "model": None,
        "provider_auth": {"provider": None, "mode": "none"}, "network_use": "none",
        "max_requests": 0, "max_tokens": 0, "max_duration_sec": 0, "budget_enforcement": "no-dispatch",
        "isolation": {"workspace": str(workspace), "session": "new-session-only",
                      "project_config": str(workspace / ".codex"), "probe_output": str(base),
                      "temporary_files": str(base / "tmp"), "yohaku_state": str(base / "yohaku-state")},
        "evidence_refs": [],
    }
    script = base / "hook.py"
    settings = base / "hook-settings.json"
    hook_command = shlex.join([sys.executable, str(script), str(settings)])
    hooks = {"hooks": {event: [{"matcher": "^" + re.escape(subject) + "$", "hooks": [{
        "type": "command", "command": hook_command, "timeout": 5}]}]
        for event in ("PreToolUse", "PostToolUse")}}
    values = {"run_id": record["run"]["id"], "subject": subject, "workspace": str(workspace),
              "events": str(base / "hook-events"), "expected_command_sha256": hashlib.sha256(command.encode()).hexdigest()}
    encode = lambda obj: (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode()
    record["limitations"] += [
        "Prepared only. CLI command is a review candidate, not an executable authorization.",
        "Source metadata describes the collector environment, not this unstarted probe session.",
        "Authentication is absent. No model/provider is selected; all call budgets are zero.",
        "Project/hook trust and effective configuration are unverified; no trust bypass is configured.",
        "No live dispatcher or provider request/token budget enforcement is implemented.",
        "Direct hook invocation is synthetic evidence and cannot establish A01 runtime PASS.",
    ]
    return {"workspace/.codex/hooks.json": encode(hooks),
            "workspace/.codex/config.toml": b"[features]\nhooks = true\n",
            "hook.py": Path(__file__).with_name("hook.py").read_bytes(),
            "hook-settings.json": encode(values), "prompt.txt": prompt.encode(),
            "codex-home/.keep": b"", "tmp/.keep": b"", "yohaku-state/.keep": b"",
            "hook-events/.keep": b""}
