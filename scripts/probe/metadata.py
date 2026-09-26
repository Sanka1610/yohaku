"""Read local CLI metadata without starting a model session."""

import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def observation(value, source, scope, reason, partial=False):
    status = "UNAVAILABLE" if value is None else "PARTIAL" if partial else "OBSERVED"
    return {
        "status": status, "value": value, "reason": reason,
        "evidence": {
            "claim": reason, "source": source,
            "authority": "unknown" if value is None else "observed",
            "scope": scope, "freshness": now(),
            "coverage": "not_observed" if value is None else "partial" if partial
                        else "complete_for_declared_scope",
        },
    }


def command(argv, cwd):
    try:
        completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                   encoding="utf-8", errors="strict", timeout=10,
                                   stdin=subprocess.DEVNULL, check=False)
    except subprocess.TimeoutExpired:
        return None, "command_timeout"
    except (OSError, UnicodeError):
        return None, "command_unavailable"
    if completed.returncode:
        return None, f"command_exit_{completed.returncode}"
    if len(completed.stdout) > 1024 * 1024:
        return None, "command_output_too_large"
    # Diagnostic output can contain configuration or credentials; never persist it.
    return completed.stdout, "command_completed"


def parse_features(output):
    features = {}
    for line in output.splitlines():
        match = re.fullmatch(r"([a-z][a-z0-9_.]*)\s+(stable|experimental|under development|deprecated|removed)\s+(true|false)\s*", line)
        if not match or match[1] in features:
            raise ValueError("unrecognized feature output")
        features[match[1]] = {"stage": match[2], "enabled": match[3] == "true"}
    if not features:
        raise ValueError("empty feature output")
    return features


def config_summary(paths):
    result = []
    for path in dict.fromkeys(paths):
        entry = {"path": str(path), "state": "unavailable", "selected": {}}
        try:
            if path.stat().st_size > 1024 * 1024:
                entry["state"] = "too_large"
                result.append(entry)
                continue
            with path.open("rb") as stream:
                data = stream.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                entry["state"] = "too_large"
                result.append(entry)
                continue
            config = tomllib.loads(data.decode("utf-8"))
        except FileNotFoundError:
            entry["state"] = "absent"
        except (OSError, ValueError):
            entry["state"] = "unreadable_or_invalid"
        else:
            entry["state"] = "read"
            selected = entry["selected"]
            allowed = {
                "sandbox_mode": ("read-only", "workspace-write", "danger-full-access"),
                "approval_policy": ("untrusted", "on-failure", "on-request", "never"),
            }
            for key, choices in allowed.items():
                if type(config.get(key)) is str and config[key] in choices:
                    selected[key] = config[key]
            features = config.get("features", {})
            if type(features) is dict:
                selected["features"] = {k: v for k, v in features.items()
                                        if re.fullmatch(r"[a-z][a-z0-9_.]*", k) and type(v) is bool}
            plugins = config.get("plugins", {})
            if type(plugins) is dict:
                selected["plugins"] = {k: {"enabled": v["enabled"]}
                    for k, v in plugins.items()
                    if re.fullmatch(r"[A-Za-z0-9_.@/-]{1,200}", k)
                    and type(v) is dict and type(v.get("enabled")) is bool}
        result.append(entry)
    return result


def source_metadata(root):
    revision, revision_reason = command(["git", "rev-parse", "HEAD"], root)
    status, status_reason = command(["git", "status", "--porcelain=v1", "--untracked-files=all"], root)
    hashes = {}
    paths = sorted((root / "scripts/probe").glob("*.py"))
    paths += [root / ".python-version", root / ".gitignore", root / "README.md"]
    try:
        for path in paths:
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return observation(None, "local_source", "Probe source identity", "source_read_failed")
    head = revision.strip() if revision and re.fullmatch(r"[0-9a-f]{40,64}\s*", revision) else None
    return observation({"root": str(root), "git_head": head,
                        "dirty": None if status is None else bool(status), "sha256": hashes},
                       "git_and_source_files", "Probe code and selected foundation files",
                       f"git_revision={revision_reason}; git_status={status_reason}",
                       partial=head is None or status is None)


def collect(root, codex):
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().absolute()
    try:
        release = platform.freedesktop_os_release()
        distro = {key: release[key] for key in ("ID", "VERSION_ID") if key in release}
    except OSError:
        distro = {}
    environment = {"python": platform.python_version(), "python_executable": sys.executable,
                   "os": platform.system(), "kernel": platform.release(), "machine": platform.machine(),
                   "distro": distro, "wsl": "microsoft" in platform.release().lower(),
                   "shell_environment": os.environ.get("SHELL"), "cwd": str(root),
                   "codex_home": str(home), "codex_home_source": "environment" if "CODEX_HOME" in os.environ else "default"}
    found = shutil.which(codex)
    executable = str(Path(found).absolute()) if found else None
    version_output, version_reason = command([executable, "--version"], root) if executable else (None, "executable_not_found")
    version = version_output.strip() if version_output else ""
    version_valid = bool(re.fullmatch(r"codex-cli [0-9]+\.[0-9]+\.[0-9]+(?:[-+.][A-Za-z0-9.-]+)?", version))
    codex_version = observation(
        {"executable": executable, "resolved_executable": str(Path(executable).resolve()), "version": version} if version_valid else None,
        "codex --version", "Selected CLI executable only",
        "CLI version observed" if version_valid else version_reason if not version_output else "unrecognized_version_output")
    feature_output, feature_reason = command([executable, "features", "list"], root) if version_valid else (None, "version_unavailable")
    feature_value = None
    if feature_output is not None:
        try:
            feature_value = parse_features(feature_output)
            feature_reason = "Effective flags reported by this standalone CLI invocation; not app session state"
        except ValueError:
            feature_reason = "unrecognized_feature_output"
    paths = [Path("/etc/codex/config.toml"), home / "config.toml"]
    paths += [parent / ".codex/config.toml" for parent in reversed((root, *root.parents))]
    return {
        "environment": observation(environment, "python_platform_and_selected_environment", "Current process environment", "Local process environment observed"),
        "codex_version": codex_version,
        "features": observation(feature_value, "codex features list", "Flags of the metadata command, without CLI overrides", feature_reason),
        "config": observation(config_summary(paths), "selected_local_TOML_files",
                              "Declared settings only; candidate ancestors are not proof of loaded layers",
                              "Allowlisted declarations; profiles, managed policy, effective merge and plugin loading are not observed", partial=True),
        "source": source_metadata(root),
    }
