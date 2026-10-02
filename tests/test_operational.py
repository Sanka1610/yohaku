"""Operational failure boundaries; injected hosts here are synthetic evidence only."""

from contextlib import ExitStack, redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from yohaku import operational as op
from yohaku.cli import main
from yohaku.operational_hosts import CodexOperationalHost, deny_task


class DelayedHost:
    """Controlled local stop timeout, without a model or Runtime process."""
    def open(self, config, run):
        self.allow = Path(config.workspace) / 'allow-stop'
        self.closing = False
    def details(self):
        return {'runtime_running': True}
    def poll(self):
        pass
    def begin_stop(self):
        self.closing = True
    def stopped(self):
        return self.closing and self.allow.exists()
    def close(self):
        pass
    def clean_stop(self):
        return True


def serve_delayed(path):
    config = op.load(path)
    with patch('yohaku.operational_hosts.CodexOperationalHost', DelayedHost), redirect_stdout(io.StringIO()):
        with op.owner_lock(config):
            op._serve(config, {'profile': {'runtime': 'codex'}, 'observed_runtime': 'synthetic'})


class OperationalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workspace = self.base / 'workspace'
        self.workspace.mkdir()
        self.path = self.base / 'config.json'
        self.config = op.OperationalConfig('codex-operational-0.158', str(Path('/usr/bin/false').resolve()),
            str(self.workspace), str(self.base / 'state'), True, True, stop_timeout=.1)
        op.configure(self.path, self.config)

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([*args, '--config', str(self.path)])
        return code, json.loads(out.getvalue() or err.getvalue())

    def test_disabled_start_does_not_construct_native_host(self):
        with patch('yohaku.operational_hosts.CodexOperationalHost') as host:
            code, result = self.cli('start')
        self.assertEqual(code, 2)
        self.assertEqual(result['error'], 'DISABLED')
        host.assert_not_called()
        self.assertFalse((Path(self.config.state_dir) / 'runs').exists())

    def test_top_level_help_distinguishes_lifecycle_and_fixed_task_run(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as stopped:
            main(['--help'])
        self.assertEqual(stopped.exception.code, 0)
        help_text = ' '.join(out.getvalue().split())
        self.assertIn('lifecycle-only profiles', help_text)
        self.assertIn('fixed Task Profile runs', help_text)
        self.assertIn('general transitions are not supported', help_text)

    def test_unknown_fields_config_binding_and_copy_rejected(self):
        data = json.loads(self.path.read_text())
        data['auto_transition'] = True
        op.write_json(self.path, data)
        with self.assertRaises(op.OperationError):
            op.load(self.path)
        data.pop('auto_transition')
        data['workspace'] = str(self.base / 'elsewhere')
        op.write_json(self.path, data)
        with self.assertRaisesRegex(op.OperationError, 'BINDING'):
            op.load(self.path)
        other = self.base / 'copy.json'
        op.write_json(other, op.asdict(self.config))
        with self.assertRaisesRegex(op.OperationError, 'BINDING'):
            op.load(other)

    def test_configure_never_adopts_existing_data(self):
        with self.assertRaisesRegex(op.OperationError, 'EXISTS'):
            op.configure(self.base / 'other.json', self.config)
        with self.assertRaises(op.OperationError):
            replace(self.config, state_dir=str(self.workspace / 'nested'))

    def test_cli_configure_enforces_owner_conditions_without_ack_flags(self):
        path = self.base / 'cli-config.json'
        with redirect_stdout(io.StringIO()):
            code = main(['configure', '--config', str(path),
                '--profile', self.config.profile, '--runtime-path', self.config.runtime_path,
                '--workspace', str(self.workspace), '--state-dir', str(self.base / 'cli-state')])
        self.assertEqual(code, 0)
        config = op.load(path)
        self.assertTrue(config.dedicated_session)
        self.assertTrue(config.single_owner)
        self.assertFalse(config.enabled)

    def test_schema_one_lifecycle_config_without_task_fields_still_loads(self):
        data = json.loads(self.path.read_text())
        for key in ('task_inputs', 'task_output', 'task_instruction', 'credential_home'):
            data.pop(key)
        op.write_json(self.path, data)
        self.assertEqual(op.load(self.path), self.config)

    def test_preflight_allows_untested_linux_and_python_patch(self):
        with patch('platform.release', return_value='6.8.0-generic'), \
                patch('sys.version_info', (3, 12, 7, 'final', 0)), \
                patch('yohaku.operational.command_output', return_value='codex-cli 0.158.0-alpha.2.1'):
            report = op.preflight(self.config)
        self.assertEqual(report['errors'], [])
        self.assertFalse(report['transition_ready'])

    def test_preflight_keeps_python_floor_and_linux_requirement(self):
        with patch('sys.version_info', (3, 10, 0, 'final', 0)), \
                patch('yohaku.operational.Path.exists', return_value=False), \
                patch('yohaku.operational.command_output', return_value='codex-cli 0.158.0-alpha.2.1'):
            report = op.preflight(self.config)
        self.assertIn('PYTHON_3_11_REQUIRED', report['errors'])
        self.assertIn('LINUX_REQUIRED', report['errors'])

    def test_removed_noop_cli_surfaces_are_rejected(self):
        configure = ['configure', '--profile', self.config.profile,
                     '--runtime-path', self.config.runtime_path,
                     '--workspace', str(self.workspace), '--state-dir', str(self.base / 'new-state')]
        cases = (['transition'], ['recover', '--inspect'], ['status', '--json'],
                 [*configure, '--single-owner'], [*configure, '--dedicated-session'])
        for args in cases:
            with self.subTest(args=args), redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as stopped:
                main([*args, '--config', str(self.path)])
            self.assertEqual(stopped.exception.code, 2)

    def test_symlink_and_insecure_config_rejected(self):
        link = self.base / 'link.json'
        link.symlink_to(self.path)
        with self.assertRaisesRegex(op.OperationError, 'SYMLINK'):
            op.load(link)
        self.path.chmod(0o644)
        with self.assertRaisesRegex(op.OperationError, 'PRIVATE'):
            op.load(self.path)

    def test_version_mismatch_does_not_launch(self):
        with patch('yohaku.operational.command_output', return_value='codex-cli 0.155.0-alpha.16.4'):
            report = op.preflight(self.config)
            self.assertIn('RUNTIME_VERSION_MISMATCH', report['errors'])
            op.set_enabled(self.path, True)
            with patch('yohaku.operational_hosts.CodexOperationalHost') as host:
                self.assertEqual(self.cli('start')[0], 2)
                host.assert_not_called()

    def test_unsupported_and_missing_owner_assumptions(self):
        c = replace(self.config, profile='codex-reference-0.155', single_owner=False)
        with patch('yohaku.operational.command_output', return_value='codex-cli 0.155.0-alpha.16.4'):
            r = op.preflight(c)
        self.assertIn('OPERATIONAL_PROFILE_UNSUPPORTED', r['errors'])
        self.assertIn('DEDICATED_SESSION_AND_SINGLE_OWNER_REQUIRED', r['errors'])

    def test_second_owner_and_disable_cannot_race_live_owner(self):
        with op.owner_lock(self.config):
            with self.assertRaisesRegex(op.OperationError, 'OWNER_BUSY'):
                with op.owner_lock(self.config):
                    self.fail()
            self.assertEqual(self.cli('disable')[0], 2)
            s = op.status(self.config)
            self.assertEqual(s['operational']['state'], 'OWNER_UNREACHABLE')

    def test_missing_observer_rejects_every_transition_route(self):
        with self.assertRaisesRegex(op.OperationError, 'TASK_PROFILE_REQUIRED'):
            deny_task()
        host = CodexOperationalHost()
        for method in ('turn/start', 'thread/compact/start', 'thread/resume'):
            with self.assertRaisesRegex(op.OperationError, 'TASK_PROFILE_REQUIRED'):
                host.send({'method': method})
        self.assertFalse(self.cli('status')[1]['recovery']['resume_supported'])

    def test_stale_owner_not_inferred_stopped_from_pid_or_socket(self):
        op.write_json(Path(self.config.state_dir) / 'last-run.json', {
            'schema': 1, 'config_digest': op.config_digest(self.config), 'state': 'RUNNING',
            'run_id': 'stale', 'owner_pid': 99999999, 'socket': '/tmp/nonexistent/control.sock'})
        s = op.status(self.config)
        self.assertEqual(s['operational']['state'], 'RECOVERY_REQUIRED')
        self.assertFalse(s['recovery']['fresh_start_allowed'])
        with self.assertRaises(op.OperationError):
            op.set_enabled(self.path, False)
        self.assertEqual(self.cli('stop')[0], 2)

    def test_corrupt_lifecycle_never_becomes_fresh_start(self):
        op.write_json(Path(self.config.state_dir) / 'last-run.json', {'state': 'STOPPED'})
        with self.assertRaisesRegex(op.OperationError, 'INVALID_LIFECYCLE'):
            op.recovery(self.config)

    def test_disable_preserves_saved_payload_bytes(self):
        root = Path(self.config.state_dir)
        protected = []
        for name in ('checkpoints', 'handoffs', 'archive', 'journal', 'hermes-events'):
            p = root / name
            p.mkdir()
            f = p / 'preserved.json'
            f.write_bytes(b'untouched retained evidence\n')
            protected.append((f, f.read_bytes()))
        op.set_enabled(self.path, True)
        op.set_enabled(self.path, False)
        for f, expected in protected:
            self.assertEqual(f.read_bytes(), expected)

    def test_stop_timeout_retains_owner_until_terminal(self):
        proc = multiprocessing.get_context('fork').Process(target=serve_delayed, args=(str(self.path),))
        proc.start()
        try:
            end = time.monotonic() + 5
            while time.monotonic() < end:
                try:
                    if op.status(self.config)['owner_live']:
                        break
                except op.OperationError:
                    pass
                time.sleep(.02)
            else:
                self.fail('test host startup timed out')
            with self.assertRaisesRegex(op.OperationError, 'STOP_TIMEOUT'):
                op.stop(self.config)
            s = op.status(self.config)
            self.assertTrue(s['owner_lock_busy'])
            self.assertEqual(s['operational']['state'], 'STOP_INCOMPLETE')
            self.assertEqual(self.cli('disable')[0], 2)
            (self.workspace / 'allow-stop').touch()
            proc.join(5)
            self.assertEqual(proc.exitcode, 0)
            self.assertEqual(op.status(self.config)['operational']['state'], 'STOPPED')
            self.assertTrue(op.recovery(self.config)['fresh_start_allowed'])
        finally:
            (self.workspace / 'allow-stop').touch()
            proc.join(2)
            if proc.is_alive():
                proc.kill()
                proc.join()


class CredentialAndStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workspace = self.base / 'workspace'
        self.workspace.mkdir(mode=0o700)
        self.source = self.workspace / 'input.md'
        self.source.write_text('# Input\n')
        self.source.chmod(0o600)
        self.credentials = self.base / 'credentials'
        self.credentials.mkdir(mode=0o700)
        self.auth = self.credentials / 'auth.json'
        self.auth.write_text('{}')
        self.auth.chmod(0o600)
        self.path = self.base / 'config.json'
        self.config = op.OperationalConfig(
            'codex-document-review-report-v1', str(Path('/usr/bin/false').resolve()),
            str(self.workspace), str(self.base / 'state'), True, True,
            task_inputs=(str(self.source),), task_output=str(self.workspace / 'report.md'),
            task_instruction='Review the input.', credential_home=str(self.credentials))

    def configure(self, *, enabled=False):
        op.configure(self.path, self.config)
        if enabled:
            op.set_enabled(self.path, True)
        return op.load(self.path)

    def runtime_patches(self, output='codex-cli 0.158.0-alpha.2.1'):
        stack = ExitStack()
        stack.enter_context(patch('yohaku.operational.command_output', return_value=output))
        return stack

    def lifecycle(self, config, state):
        op.write_json(Path(config.state_dir) / 'last-run.json', {
            'schema': 1, 'config_digest': op.config_digest(config),
            'run_id': state.lower(), 'state': state})

    def test_valid_private_credential_home_and_auth(self):
        identity = op.credential_identity(self.config)
        self.assertEqual(identity, op.credential_identity(self.config, identity))

    def test_credential_home_symlink_rejected(self):
        real = self.base / 'credentials-real'
        self.credentials.rename(real)
        self.credentials.symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(op.OperationError, 'SYMLINK'):
            op.credential_identity(self.config)

    def test_auth_symlink_rejected(self):
        replacement = self.base / 'other-auth.json'
        replacement.write_text('{}')
        replacement.chmod(0o600)
        self.auth.unlink()
        self.auth.symlink_to(replacement)
        with self.assertRaisesRegex(op.OperationError, 'SYMLINK'):
            op.credential_identity(self.config)

    def test_wrong_owner_is_exercised_at_unit_boundary(self):
        with patch('yohaku.operational.os.getuid', return_value=os.getuid() + 1):
            with self.assertRaisesRegex(op.OperationError, 'PRIVATE_PATH_REQUIRED'):
                op.credential_identity(self.config)

    def test_wrong_auth_owner_is_exercised_at_unit_boundary(self):
        owner = os.getuid()
        with patch('yohaku.operational.os.getuid',
                   side_effect=(owner, owner, owner + 1)):
            with self.assertRaisesRegex(op.OperationError, 'PRIVATE_PATH_REQUIRED'):
                op.credential_identity(self.config)

    def test_insecure_credential_directory_mode_rejected(self):
        self.credentials.chmod(0o770)
        with self.assertRaisesRegex(op.OperationError, 'PRIVATE_PATH_REQUIRED'):
            op.credential_identity(self.config)

    def test_insecure_auth_mode_rejected(self):
        self.auth.chmod(0o640)
        with self.assertRaisesRegex(op.OperationError, 'PRIVATE_PATH_REQUIRED'):
            op.credential_identity(self.config)

    def test_non_regular_auth_rejected(self):
        self.auth.unlink()
        self.auth.mkdir(mode=0o700)
        with self.assertRaisesRegex(op.OperationError, 'WRONG_PATH_TYPE'):
            op.credential_identity(self.config)

    def test_missing_auth_rejected(self):
        self.auth.unlink()
        with self.assertRaisesRegex(op.OperationError, 'CODEX_AUTH_MISSING'):
            op.credential_identity(self.config)

    def test_replacement_after_preflight_is_rejected_before_runtime_runner(self):
        self.configure(enabled=True)
        original = op._preflight

        def replace_after_preflight(config):
            report, identity = original(config)
            self.auth.unlink()
            self.auth.write_text('{"replacement": true}')
            self.auth.chmod(0o600)
            return report, identity

        with self.runtime_patches(), \
                patch('yohaku.operational._preflight', side_effect=replace_after_preflight), \
                patch('yohaku.document_review_runtime.run_document_review') as runner:
            with self.assertRaisesRegex(op.OperationError, 'CODEX_CREDENTIAL_STATE_CHANGED'):
                op.run(self.path)
        runner.assert_not_called()

    def test_status_semantics_for_lifecycle_fresh_disabled_and_preflight_failure(self):
        lifecycle_path = self.base / 'lifecycle.json'
        lifecycle = op.OperationalConfig(
            'codex-operational-0.158', str(Path('/usr/bin/false').resolve()),
            str(self.workspace), str(self.base / 'lifecycle-state'), True, True)
        op.configure(lifecycle_path, lifecycle)
        with self.runtime_patches():
            status = op.status(op.load(lifecycle_path))
        self.assertFalse(status['task_profile_registered'])
        self.assertFalse(status['profile']['task_profile_registered'])
        self.assertNotIn('transition_available', status['profile'])
        self.assertFalse(status['transition_ready'])
        self.assertTrue(status['recovery']['fresh_start_allowed'])
        self.assertFalse(status['recovery']['resume_supported'])

        config = self.configure()
        with self.runtime_patches():
            status = op.status(config)
        self.assertTrue(status['task_profile_registered'])
        self.assertFalse(status['transition_ready'])
        self.assertEqual(status['transition_reason'], 'DISABLED')

        op.set_enabled(self.path, True)
        config = op.load(self.path)
        with self.runtime_patches():
            status = op.status(config)
        self.assertTrue(status['task_profile_registered'])
        self.assertTrue(status['transition_ready'])
        self.assertTrue(status['transition_available'])
        self.assertTrue(status['recovery']['fresh_start_allowed'])
        self.assertFalse(status['recovery']['resume_supported'])

        with self.runtime_patches('codex-cli 0.0.0'):
            status = op.status(config)
        self.assertFalse(status['transition_ready'])
        self.assertFalse(status['transition_available'])
        self.assertIn('RUNTIME_VERSION_MISMATCH', status['transition_reason'])

    def test_task_registration_and_current_readiness_are_distinct(self):
        candidate = op.profile('codex-document-review-report-v1')
        self.assertTrue(candidate['task_profile_registered'])
        self.assertNotIn('transition_available', candidate)
        excluded = op.profile('hermes-operational-h-cli-01')
        self.assertIn('transition_available', excluded)
        self.assertNotIn('task_profile_registered', excluded)
        path = self.base / 'excluded.json'
        config = op.OperationalConfig(
            'codex-reference-0.155', str(Path('/usr/bin/false').resolve()),
            str(self.workspace), str(self.base / 'excluded-state'), True, True)
        op.configure(path, config)
        status = op.status(op.load(path))
        self.assertFalse(status['transition_available'])
        self.assertNotIn('task_profile_registered', status)
        self.assertNotIn('transition_ready', status)

    def test_completed_recovery_required_and_ambiguous_are_not_transition_ready(self):
        config = self.configure(enabled=True)
        with self.runtime_patches():
            for state in ('STOPPED', 'RUNNING', 'AMBIGUOUS'):
                with self.subTest(state=state):
                    self.lifecycle(config, state)
                    status = op.status(config)
                    self.assertTrue(status['task_profile_registered'])
                    self.assertFalse(status['transition_ready'])
                    self.assertFalse(status['transition_available'])
                    self.assertFalse(status['recovery']['fresh_start_allowed'])
                    self.assertFalse(status['recovery']['resume_supported'])
                    if state != 'STOPPED':
                        self.assertEqual(status['operational']['state'], 'RECOVERY_REQUIRED')


if __name__ == '__main__':
    unittest.main()
