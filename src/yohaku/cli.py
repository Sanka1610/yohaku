"""Yohaku Operational Alpha Foundation command line."""

import argparse
import json
import sys
from importlib.metadata import version

from . import operational as op
from .profiles import MISSING_TASK, PROFILES, profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=(
        'Yohaku operational CLI for lifecycle-only profiles and fixed Task Profile runs; '
        'general transitions are not supported'))
    parser.add_argument('--version', action='version', version=version('yohaku'))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('profiles')
    cfg = commands.add_parser('configure')
    cfg.add_argument('--config', required=True)
    cfg.add_argument('--profile', required=True, choices=PROFILES)
    cfg.add_argument('--runtime-path', required=True, help='Codex executable or pinned Hermes source root')
    cfg.add_argument('--workspace', required=True)
    cfg.add_argument('--state-dir', required=True, help='new private directory, separate from workspace')
    cfg.add_argument('--dedicated-session', action='store_true')
    cfg.add_argument('--single-owner', action='store_true')
    cfg.add_argument('--stop-timeout', type=float, default=10)
    cfg.add_argument('--input', action='append', default=[], help='declared document-review input; repeatable')
    cfg.add_argument('--output', help='fixed create-only document-review report path')
    cfg.add_argument('--instruction', help='fixed document-review instruction')
    cfg.add_argument('--credential-home', help='existing Codex home containing auth.json; never copied')
    command_help = {
        'start': 'start a lifecycle-only operational profile',
        'run': 'run a fixed registered Task Profile',
        'transition': 'unsupported general transition command',
    }
    for name in ('preflight', 'enable', 'start', 'run', 'status', 'stop', 'disable', 'recover', 'transition'):
        sub = commands.add_parser(name, help=command_help.get(name))
        sub.add_argument('--config', required=True)
        sub.add_argument('--json', action='store_true', help='output is always structured JSON')
        if name == 'recover':
            sub.add_argument('--inspect', action='store_true', help='read-only recovery decision; never resend')
    args = parser.parse_args(argv)
    try:
        if args.command == 'profiles':
            result = {'profiles': [profile(name) for name in PROFILES]}
        elif args.command == 'configure':
            config = op.OperationalConfig(args.profile, args.runtime_path, args.workspace, args.state_dir,
                args.dedicated_session, args.single_owner, stop_timeout=args.stop_timeout,
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
            elif args.command == 'recover':
                result = op.status(config)
                if not args.inspect:
                    raise op.OperationError('UNSUPPORTED_RECOVERY; use recover --inspect; ' + MISSING_TASK)
            else:
                raise op.OperationError(MISSING_TASK)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2 if result.get('verdict') == 'FAIL' else 0
    except Exception as exc:
        # Runtime stderr and arbitrary exception text may contain credentials.
        reason = str(exc) if isinstance(exc, op.OperationError) else type(exc).__name__
        print(json.dumps({'error': reason, 'transition_ready': False,
                          'transition_available': False}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
