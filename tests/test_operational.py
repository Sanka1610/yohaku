"""Operational failure boundaries; injected hosts here are synthetic evidence only."""

from contextlib import redirect_stdout, redirect_stderr
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
        self.assertIn('DEDICATED_SESSION_AND_SINGLE_OWNER_ACK_REQUIRED', r['errors'])

    def test_second_owner_and_disable_cannot_race_live_owner(self):
        with op.owner_lock(self.config):
            with self.assertRaisesRegex(op.OperationError, 'OWNER_BUSY'):
                with op.owner_lock(self.config):
                    self.fail()
            self.assertEqual(self.cli('disable')[0], 2)
            s = op.status(self.config)
            self.assertEqual(s['operational']['state'], 'OWNER_UNREACHABLE')

    def test_missing_observer_rejects_every_transition_route(self):
        self.assertEqual(self.cli('transition')[0], 2)
        with self.assertRaisesRegex(op.OperationError, 'TASK_PROFILE_REQUIRED'):
            deny_task()
        host = CodexOperationalHost()
        for method in ('turn/start', 'thread/compact/start', 'thread/resume'):
            with self.assertRaisesRegex(op.OperationError, 'TASK_PROFILE_REQUIRED'):
                host.send({'method': method})
        self.assertEqual(self.cli('recover')[0], 2)
        self.assertFalse(self.cli('recover', '--inspect')[1]['recovery']['resume_supported'])

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


if __name__ == '__main__':
    unittest.main()
