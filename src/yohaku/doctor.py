"""Local inspection only; never preflight, attach to, or repair a runtime."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version

from . import operational as op
from .dsh_adapter import DSH_RECEIPT_PROFILE, DSH_VERSION
from .hermes import HERMES_SOURCE
from .opencode import OPENCODE_VERSION
from .profiles import PROFILES, profile
from .supervisor import SupervisorError, failure_guidance


def _query(args):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=3, env={'PATH': os.environ.get('PATH', os.defpath), 'LANG': 'C.UTF-8'})
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None


def _package_version(executable):
    # Only the published @opencode/cli bin layout. Do not search parent trees or
    # execute OpenCode: its CLI initializes logging/configuration before parsing.
    try:
        binary = Path(executable).resolve()
        package = binary.parent.parent / 'package.json'
        with package.open('rb') as stream:
            data = json.loads(stream.read(65537))
        entry = data.get('bin', {}).get('opencode')
        value = data.get('version')
        if (data.get('name') == '@opencode/cli' and isinstance(entry, str)
                and (package.parent / entry).resolve() == binary
                and isinstance(value, str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?', value)):
            return value
    except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
        pass
    return None


def render(config_path=None, *, supervisor=None):
    """Return human-readable observations, without acquiring any owner lock."""
    warnings = []
    config = None
    if config_path is not None:
        try:
            config = op.load(config_path)
        except (op.OperationError, OSError, ValueError):
            warnings.append('Selected config could not be validated. Check its private paths, profile and binding.')
    try:
        installed = version('yohaku')
    except PackageNotFoundError:
        installed = 'unknown (package metadata unavailable)'
    lines = ['Yohaku', f'  Version: {installed}', f'  Python: {sys.version.split()[0]}',
        '  State/storage root: ' + ('configured (path omitted)' if config else 'not checked (no validated config selected)'),
        '  Context Assist Stage 1: available (deterministic / model-free)',
        '  Context Assist Stage 2 / 3: Deferred', '', 'Runtime profiles']
    supported = qualified = 0
    for runtime, label in (('codex', 'Codex'), ('hermes', 'Hermes'), ('dsh', 'DSH'),
                           ('opencode', 'OpenCode'), ('orca', 'Orca'), ('claude', 'Claude Code CLI')):
        entries = [profile(name) for name, p in PROFILES.items() if p['runtime'] == runtime]
        selected = config is not None and profile(config.profile)['runtime'] == runtime
        executable = shutil.which(runtime)
        if selected and runtime != 'hermes':
            executable = config.runtime_path if os.path.isfile(config.runtime_path) and os.access(config.runtime_path, os.X_OK) else None
        detected = executable is not None
        if selected and runtime == 'hermes':
            detected = (Path(config.runtime_path) / 'cli.py').is_file()
        source = 'selected config' if selected else 'PATH'
        lines += [f'  {label}', f'    Detected: {"yes" if detected else "not detected"} ({source})']
        actual = None
        if detected and runtime in ('codex', 'dsh'):
            raw = _query([executable, '--version'])
            pattern = r'codex-cli ([0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?)' if runtime == 'codex' else r'([0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?)'
            match = re.fullmatch(pattern, raw or '')
            actual = match.group(1) if match else None
            if actual is None:
                warnings.append(f'{label} version query did not return a recognized version; compatibility is unknown.')
        elif detected and runtime == 'opencode':
            actual = _package_version(executable)
            if actual is None:
                warnings.append('OpenCode package version is unknown; the CLI was not executed. Check the installed version manually.')
        queryable = detected and runtime in ('codex', 'dsh', 'opencode')
        lines.append('    Version: ' + (actual if actual else 'unknown' if queryable else 'not checked'))
        if runtime == 'orca':
            lines += ['    Probe status: validated (bounded structured Codex profile)',
                      '    Production integration: not available',
                      '    Session ownership / trigger authority: not checked']
            continue
        if runtime == 'claude':
            lines.append('    Beta support: Experimental (bounded profiles only)')
            for entry in entries:
                lines.append(f'    Profile: {entry["id"]}; profile maturity: {entry["status"]}; expected version: {entry["runtime_version"]}')
            lines += ['    Static / live qualification: not checked', '    Production CLI launcher: not available']
            continue
        if runtime in ('codex', 'hermes'):
            supported += int(detected)
            lines.append('    Beta support: Supported (existing bounded workflows only)')
            for entry in entries:
                lines.append(f'    Profile: {entry["id"]}; profile maturity: {entry["status"]}; expected version: {entry["runtime_version"]}')
            current = profile(config.profile) if selected else next(p for p in entries if p['launch_supported'])
            lines.append(f'    Comparison profile: {current["id"]}')
            if runtime == 'hermes':
                pin = _query(['git', '--no-optional-locks', '-C', config.runtime_path, 'rev-parse', 'HEAD']) if selected and detected else None
                compatible = 'compatible (source pin only)' if pin == HERMES_SOURCE else 'mismatch' if pin and re.fullmatch(r'[0-9a-f]{40}', pin) else 'unknown' if selected and detected else 'not checked'
                lines += [f'    Static qualification: {compatible}',
                          '    Clean source / native host venv: not checked']
                if compatible == 'mismatch':
                    warnings.append('Hermes source pin does not match the selected profile. Check the pinned source before launch.')
            else:
                compatible = 'compatible (version only)' if actual == current['runtime_version'] else 'mismatch' if actual else 'unknown' if detected else 'not checked'
                lines.append(f'    Static qualification: {compatible}')
                if compatible == 'mismatch':
                    warnings.append('Codex version does not match the comparison profile. Check the executable and selected profile before launch.')
            lines += ['    Live session qualification: not checked',
                      '    Important limitations: lifecycle profiles do not run tasks or transitions; restart unsupported']
        else:
            qualified += int(detected)
            expected = DSH_VERSION if runtime == 'dsh' else OPENCODE_VERSION
            compatible = 'compatible (version only)' if actual == expected else 'mismatch' if actual else 'unknown' if detected else 'not checked'
            if runtime == 'opencode' and actual == expected:
                compatible = 'compatible (package version only; server version not checked)'
            lines += ['    Beta support: Supported on qualified profile', f'    Qualified version: {expected}',
                      f'    Static qualification: {compatible}', '    Live session qualification: not checked']
            if actual is not None and actual != expected:
                warnings.append(f'{label} version is outside the Beta-qualified profile. Check the qualified version before execution.')
            if runtime == 'dsh':
                lines += [f'    Receipt profile: {DSH_RECEIPT_PROFILE} (activation not checked)',
                          '    Runtime-only conditions: official DeepSeek Messages adapter; headless fresh Session;',
                          '      plain text; single Agent / owner; no additional extension fields; known gate ordering; retry disabled']
            else:
                lines += ['    Runtime-only conditions: Linux; known terminal http.request hook graph; no later mutator;',
                          '      native deny-all receipt tools; fresh owned Session; retry disabled']
            lines.append('    Important limitations: retry unsupported; restart unsupported; no public CLI launcher')
    if supervisor is not None:
        lines += ['', 'Supervisor sessions (provided facts only)',
                  '  Process-local; restart recovery: NOT_SUPPORTED']
        for session in supervisor.sessions:
            lines += ['  Session', f'    Harness: {session.harness}']
            try:
                trigger = supervisor.resolve(session)
                observers = supervisor.observers(session)
                lines += [f'    Trigger authority: {trigger.name}',
                          '    Observers: ' + (', '.join(item.name for item in observers) or 'none'),
                          '    Ownership facts: supplied by embedding host']
            except SupervisorError as exc:
                lines.append('    Trigger authority: unresolved')
                lines.extend('    ' + line for line in failure_guidance(str(exc)).splitlines())
                warnings.append('A supplied Supervisor session could not be resolved safely.')
    lines += ['', 'Environment', f'  Platform: {sys.platform}',
              '  Operational launcher requires Linux / local POSIX storage; filesystem suitability: not checked']
    if config:
        lines += [f'  Selected profile: {config.profile}', f'  Enabled: {str(config.enabled).lower()}']
        if not Path(config.workspace).is_dir():
            warnings.append('Selected workspace directory is missing. Check the configured workspace path.')
        if not config.dedicated_session or not config.single_owner:
            warnings.append('Selected config requires a dedicated session and single owner. Confirm the configuration before launch.')
        if not profile(config.profile)['launch_supported']:
            warnings.append('Selected profile has no operational launcher. Check yohaku profiles for a launch-supported profile.')
    lines += ['', 'Limitations / warnings',
              '  Executable presence and version compatibility do not prove transition or resume readiness.',
              '  For not detected runtimes, check PATH; use --config to inspect an existing operational configuration.',
              '  Verify runtime-only qualification at execution time; see docs/runtime-support.md.',
              ('  Ownership, trigger authority, other observers and external writers: not checked.'
               if supervisor is None else
               '  Supervisor routing uses provided facts only; live ownership and external writers: not checked.'),
              '  No config/provider/state changes, repairs, runtime sessions or network requests are performed.']
    lines += [f'  Warning: {warning}' for warning in warnings]
    lines += ['', 'Summary', f'  Supported runtimes detected (presence only): {supported}',
              f'  Qualified-profile runtimes detected (presence only): {qualified}', f'  Warnings: {len(warnings)}']
    return '\n'.join(lines)
