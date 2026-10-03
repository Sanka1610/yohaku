"""Operational lifecycle and the fixed document-review command line."""

import argparse
import json
import sys
from importlib.metadata import PackageNotFoundError, version

from . import operational as op
from .profiles import PROFILES, profile


def _failure_guidance(reason):
    codes = reason.split('; ')
    if any(code in ('RUNTIME_VERSION_MISMATCH', 'SOURCE_VERSION_MISMATCH',
                    'OPERATIONAL_PROFILE_UNSUPPORTED', 'INVALID_CONFIG_OR_PROFILE') for code in codes):
        return ('The selected runtime/configuration does not match this launcher profile. '
                'No runtime was launched by this command. '
                'Run yohaku doctor --config <absolute-path> and check the selected profile and runtime version.')
    if reason.startswith('RECOVERY_REQUIRED'):
        return ('The previous owner did not prove a clean stop. Yohaku retained the saved state and blocked a fresh start. '
                'Preserve the config, workspace and runtime storage; use yohaku status --config <absolute-path> '
                'and reconcile the previous operation before starting another task. Do not blindly rerun it.')
    if reason.startswith(('STOP_TIMEOUT', 'STOP_INCOMPLETE', 'OWNER_UNREACHABLE', 'RUNTIME_STOP_UNCONFIRMED')):
        return ('A clean runtime stop could not be confirmed; the runtime may still be running. '
                'Yohaku does not treat this as a clean stop. Preserve state and inspect the owner/runtime before another start.')
    if reason.startswith(('OWNER_BUSY', 'TASK_WORKSPACE_BUSY')):
        return ('Another cooperating owner holds the lock. This command did not acquire ownership. '
                'Check the current owner and task before starting another operation.')
    if reason.startswith(('CONFIG_BINDING_MISMATCH', 'OWNER_IDENTITY_MISMATCH', 'CODEX_CREDENTIAL_STATE_CHANGED')):
        return ('The saved binding or current identity changed. Yohaku rejected the operation using that identity. '
                'Preserve state and check the original config, owner and credential paths before proceeding.')
    if reason.startswith('AMBIGUOUS'):
        return ('The operation may have executed, but its outcome is uncertain. Yohaku does not retry automatically. '
                'Preserve the checkpoint, journal and runtime storage; reconcile actual effects before any new transition.')
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=(
        'Yohaku operational CLI for lifecycle-only profiles and fixed Task Profile runs; '
        'general transitions are not supported'))
    try:
        installed_version = version('yohaku')
    except PackageNotFoundError:
        installed_version = 'unknown (package metadata unavailable)'
    parser.add_argument('--version', action='version', version=installed_version)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('profiles')
    doctor = commands.add_parser('doctor', help='inspect local runtimes and Beta qualification without changes')
    doctor.add_argument('--config', help='optional existing operational config (absolute path); read only')
    cfg = commands.add_parser('configure')
    cfg.add_argument('--config', required=True)
    cfg.add_argument('--profile', required=True, choices=PROFILES)
    cfg.add_argument('--runtime-path', required=True, help='Codex executable or pinned Hermes source root')
    cfg.add_argument('--workspace', required=True)
    cfg.add_argument('--state-dir', required=True, help='new private directory, separate from workspace')
    cfg.add_argument('--stop-timeout', type=float, default=10)
    cfg.add_argument('--input', action='append', default=[], help='declared document-review input; repeatable')
    cfg.add_argument('--output', help='fixed create-only document-review report path')
    cfg.add_argument('--instruction', help='fixed document-review instruction')
    cfg.add_argument('--credential-home', help='existing Codex home containing auth.json; never copied')
    command_help = {
        'start': 'start a lifecycle-only operational profile',
        'run': 'run a fixed registered Task Profile',
    }
    for name in ('preflight', 'enable', 'start', 'run', 'status', 'stop', 'disable'):
        sub = commands.add_parser(name, help=command_help.get(name))
        sub.add_argument('--config', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            from .doctor import render
            print(render(args.config))
            return 0
        elif args.command == 'profiles':
            result = {'profiles': [profile(name) for name in PROFILES]}
        elif args.command == 'configure':
            config = op.OperationalConfig(args.profile, args.runtime_path, args.workspace, args.state_dir,
                True, True, stop_timeout=args.stop_timeout,
                task_inputs=tuple(args.input), task_output=args.output,
                task_instruction=args.instruction, credential_home=args.credential_home)
            op.configure(args.config, config)
            result = {'configured': args.config, 'enabled': False, 'profile': profile(args.profile)}
        elif args.command == 'start':
            return op.start(args.config)
        elif args.command == 'run':
            result = op.run(args.config)
        else:
            config = op.load(args.config)
            if args.command == 'preflight':
                result = op.preflight(config)
            elif args.command == 'status':
                result = op.status(config)
            elif args.command in ('enable', 'disable'):
                result = op.set_enabled(args.config, args.command == 'enable')
            elif args.command == 'stop':
                result = op.stop(config)
        reason = ('; '.join(result.get('errors', [])) if result.get('errors') else
                  'AMBIGUOUS' if result.get('verdict') == 'AMBIGUOUS' else result.get('reason') or '')
        guidance = _failure_guidance(reason)
        if guidance:
            result = dict(result, guidance=guidance)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2 if result.get('verdict') == 'FAIL' else 0
    except Exception as exc:
        # Runtime stderr and arbitrary exception text may contain credentials.
        reason = str(exc) if isinstance(exc, op.OperationError) else type(exc).__name__
        if args.command == 'doctor':
            print('Doctor could not complete local inspection. Check the installation and selected config.', file=sys.stderr)
        else:
            result = {'error': reason, 'transition_ready': False, 'transition_available': False}
            guidance = _failure_guidance(reason)
            if guidance:
                result['guidance'] = guidance
            print(json.dumps(result), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
