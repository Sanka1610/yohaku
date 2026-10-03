"""Local fixture inspection; no live runtime, network or transition acceptance."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from yohaku import doctor, operational as op
from yohaku.cli import main
from yohaku.profiles import PROFILES


class DoctorTests(unittest.TestCase):
    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(['doctor', *args])
        return code, out.getvalue(), err.getvalue()

    def test_no_runtime_detected_completes(self):
        with patch('yohaku.doctor.shutil.which', return_value=None), patch('yohaku.doctor._query') as query:
            code, output, error = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(error, '')
        self.assertIn('Supported runtimes detected (presence only): 0', output)
        self.assertIn('Context Assist Stage 1: available', output)
        self.assertIn('Stage 2 / 3: Deferred', output)
        self.assertIn('not detected (PATH)', output)
        self.assertIn('Version: not checked', output)
        self.assertIn('Beta support: Experimental', output)
        self.assertIn('Profile: claude-c-cli', output)
        query.assert_not_called()

    def test_supported_runtime_keeps_maturity_separate(self):
        with patch('yohaku.doctor.shutil.which', side_effect=lambda name: '/fixture/codex' if name == 'codex' else None), \
                patch('yohaku.doctor._query', return_value='codex-cli ' + PROFILES['codex-operational-0.158']['runtime_version']):
            code, output, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertIn('Beta support: Supported (existing bounded workflows only)', output)
        self.assertIn('profile maturity: alpha', output)
        self.assertIn('Static qualification: compatible (version only)', output)
        self.assertIn('Supported runtimes detected (presence only): 1', output)
        self.assertIn('Live session qualification: not checked', output)

    def test_version_mismatch_is_inspection_success(self):
        with patch('yohaku.doctor.shutil.which', side_effect=lambda name: '/fixture/dsh' if name == 'dsh' else None), \
                patch('yohaku.doctor._query', return_value='9.0.0'):
            code, output, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertIn('Static qualification: mismatch', output)
        self.assertIn('outside the Beta-qualified profile', output)
        self.assertNotIn('Static qualification: compatible', output)

    def test_dsh_static_compatibility_is_not_live_qualification(self):
        with patch('yohaku.doctor.shutil.which', side_effect=lambda name: '/fixture/dsh' if name == 'dsh' else None), \
                patch('yohaku.doctor._query', return_value=doctor.DSH_VERSION) as query:
            code, output, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertIn('Static qualification: compatible (version only)', output)
        self.assertIn('Live session qualification: not checked', output)
        self.assertIn('official DeepSeek Messages adapter', output)
        self.assertIn('activation not checked', output)
        self.assertIn('retry unsupported; restart unsupported', output)
        query.assert_called_once_with(['/fixture/dsh', '--version'])

    def test_opencode_reads_only_bound_package_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'bin' / 'opencode.cjs'
            binary.parent.mkdir()
            binary.write_text('fixture')
            (root / 'package.json').write_text(json.dumps({'name': '@opencode/cli',
                'version': doctor.OPENCODE_VERSION, 'bin': {'opencode': './bin/opencode.cjs'}}))
            with patch('yohaku.doctor.shutil.which', side_effect=lambda name: str(binary) if name == 'opencode' else None), \
                    patch('yohaku.doctor._query') as query:
                code, output, _ = self.invoke()
            query.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn('compatible (package version only; server version not checked)', output)
        self.assertIn('known terminal http.request hook graph; no later mutator', output)
        self.assertIn('native deny-all receipt tools', output)
        self.assertIn('Live session qualification: not checked', output)

    def test_foreign_or_unbound_package_does_not_qualify_opencode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'bin' / 'opencode.cjs'
            binary.parent.mkdir()
            binary.write_text('fixture')
            for name, entry in (('foreign', './bin/opencode.cjs'), ('@opencode/cli', './another.cjs')):
                with self.subTest(name=name, entry=entry):
                    (root / 'package.json').write_text(json.dumps({'name': name,
                        'version': doctor.OPENCODE_VERSION, 'bin': {'opencode': entry}}))
                    self.assertIsNone(doctor._package_version(binary))

    def test_orca_detection_does_not_execute_or_claim_production_support(self):
        with patch('yohaku.doctor.shutil.which', side_effect=lambda name: '/fixture/orca' if name == 'orca' else None), \
                patch('yohaku.doctor._query') as query:
            code, output, _ = self.invoke()
        self.assertEqual(code, 0)
        orca = output.split('  Orca\n')[1].split('\nEnvironment')[0]
        self.assertIn('Detected: yes', orca)
        self.assertIn('Version: not checked', orca)
        self.assertIn('Probe status: validated', orca)
        self.assertIn('Production integration: prototype — transition-only', orca)
        self.assertNotIn('Supported', orca)
        self.assertIn('Supported runtimes detected (presence only): 0', output)
        query.assert_not_called()

    def test_detector_failure_does_not_crash_other_detection(self):
        def query(args):
            return None if 'codex' in args[0] else doctor.DSH_VERSION
        with patch('yohaku.doctor.shutil.which', side_effect=lambda name: '/fixture/' + name if name in ('codex', 'dsh') else None), \
                patch('yohaku.doctor._query', side_effect=query):
            code, output, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertIn('Version: unknown', output)
        self.assertIn('Static qualification: unknown', output)
        self.assertIn('Static qualification: compatible (version only)', output)

    def test_unrecognized_version_output_is_not_printed_or_guessed(self):
        with patch('yohaku.doctor.shutil.which', side_effect=lambda name: '/fixture/dsh' if name == 'dsh' else None), \
                patch('yohaku.doctor._query', return_value='token=SECRET 0.2.0-rc.2'):
            code, output, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertIn('Static qualification: unknown', output)
        self.assertNotIn('SECRET', output)
        self.assertNotIn('Static qualification: compatible', output)

    def test_query_is_bounded_and_uses_no_shell_or_credentials(self):
        with patch.dict(os.environ, {'SECRET_TOKEN': 'SECRET'}), \
                patch('yohaku.doctor.subprocess.run', side_effect=subprocess.TimeoutExpired('fixture', 3)) as run:
            self.assertIsNone(doctor._query(['/fixture/dsh', '--version']))
        self.assertEqual(run.call_args.args[0], ['/fixture/dsh', '--version'])
        self.assertEqual(run.call_args.kwargs['timeout'], 3)
        self.assertNotIn('shell', run.call_args.kwargs)
        self.assertNotIn('SECRET_TOKEN', run.call_args.kwargs['env'])
        self.assertEqual(run.call_args.kwargs['stderr'], subprocess.DEVNULL)
        for failure in (OSError('SECRET'), UnicodeError('SECRET')):
            with patch('yohaku.doctor.subprocess.run', side_effect=failure):
                self.assertIsNone(doctor._query(['/fixture/dsh', '--version']))

    def test_config_inspection_does_not_mutate_files_or_acquire_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o700)
            workspace = root / 'workspace'
            workspace.mkdir()
            path = root / 'config.json'
            config = op.OperationalConfig('codex-operational-0.158', str(Path('/usr/bin/false').resolve()),
                str(workspace), str(root / 'state'), True, True)
            op.configure(path, config)
            def snapshot():
                return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None,
                    p.stat().st_mode, p.stat().st_mtime_ns) for p in root.rglob('*')}
            before = snapshot()
            with patch('yohaku.doctor.shutil.which', return_value=None), \
                    patch('yohaku.doctor._query', return_value='codex-cli ' + PROFILES[config.profile]['runtime_version']) as query, \
                    patch('yohaku.operational.owner_lock') as lock, patch('yohaku.operational.preflight') as preflight, \
                    patch('yohaku.operational.write_json') as write, patch('yohaku.operational.start') as start:
                code, output, _ = self.invoke('--config', str(path))
            self.assertEqual(code, 0)
            self.assertEqual(before, snapshot())
            self.assertNotIn(str(root), output)
            self.assertIn('Selected profile: codex-operational-0.158', output)
            self.assertIn('State/storage root: configured (path omitted)', output)
            query.assert_called_once_with([config.runtime_path, '--version'])
            for mocked in (lock, preflight, write, start):
                mocked.assert_not_called()

    def test_invalid_config_is_warning_without_leaking_contents(self):
        with patch('yohaku.doctor.op.load', side_effect=ValueError('SECRET')), \
                patch('yohaku.doctor.shutil.which', return_value=None):
            code, output, _ = self.invoke('--config', '/fixture/config')
        self.assertEqual(code, 0)
        self.assertIn('Selected config could not be validated', output)
        self.assertNotIn('SECRET', output)

    def test_missing_workspace_and_unsupported_launcher_are_warnings(self):
        config = op.OperationalConfig('codex-reference-0.155', '/fixture/codex',
            '/fixture/workspace', '/fixture/state', False, False)
        with patch('yohaku.doctor.op.load', return_value=config), \
                patch('yohaku.doctor.shutil.which', return_value=None):
            code, output, _ = self.invoke('--config', '/fixture/config')
        self.assertEqual(code, 0)
        self.assertIn('Selected workspace directory is missing', output)
        self.assertIn('Selected profile has no operational launcher', output)
        self.assertIn('dedicated session and single owner', output)

    def test_hermes_does_not_infer_version_from_executable_presence(self):
        with patch('yohaku.doctor.shutil.which', side_effect=lambda name: '/fixture/hermes' if name == 'hermes' else None), \
                patch('yohaku.doctor._query') as query:
            _, output, _ = self.invoke()
        hermes = output.split('  Hermes\n')[1].split('  DSH\n')[0]
        self.assertIn('Version: not checked', hermes)
        self.assertIn('Static qualification: not checked', hermes)
        self.assertIn('expected version: 0.21.0', hermes)
        query.assert_not_called()

    def test_configured_hermes_checks_only_source_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'cli.py').write_text('fixture')
            config = op.OperationalConfig('hermes-operational-h-cli-01', str(root),
                '/fixture/workspace', '/fixture/state', True, True)
            for pin, expected in ((doctor.HERMES_SOURCE, 'compatible (source pin only)'),
                                  ('0' * 40, 'mismatch'), (None, 'unknown')):
                with self.subTest(pin=pin), patch('yohaku.doctor.op.load', return_value=config), \
                        patch('yohaku.doctor.shutil.which', return_value=None), \
                        patch('yohaku.doctor._query', return_value=pin) as query:
                    code, output, _ = self.invoke('--config', '/fixture/config')
                self.assertEqual(code, 0)
                self.assertIn('Static qualification: ' + expected, output)
                self.assertIn('Clean source / native host venv: not checked', output)
                self.assertIn('Version: not checked', output)
                query.assert_called_once_with(['git', '--no-optional-locks', '-C', str(root), 'rev-parse', 'HEAD'])

    def test_doctor_itself_failure_uses_existing_failure_exit_code(self):
        with patch('yohaku.doctor.render', side_effect=RuntimeError('SECRET')):
            code, output, error = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(output, '')
        self.assertIn('Doctor could not complete', error)
        self.assertNotIn('SECRET', error)

    def test_missing_package_metadata_remains_unknown(self):
        from importlib.metadata import PackageNotFoundError
        with patch('yohaku.cli.version', side_effect=PackageNotFoundError), \
                patch('yohaku.doctor.version', side_effect=PackageNotFoundError), \
                patch('yohaku.doctor.shutil.which', return_value=None):
            code, output, _ = self.invoke()
        self.assertEqual(code, 0)
        self.assertIn('Version: unknown (package metadata unavailable)', output)

    def test_json_surface_is_not_added(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
            main(['doctor', '--json'])
        self.assertEqual(stopped.exception.code, 2)
