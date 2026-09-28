"""Startup activation must not silently enable an embedded owner."""

from pathlib import Path
import tempfile
import unittest

from yohaku.config import HostConfig, activate, load_config


class ConfigTests(unittest.TestCase):
    def load(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'yohaku.toml'
            path.write_text(text)
            return load_config(path)

    def test_disabled_by_default_never_constructs_owner(self):
        for runtime in ('codex', 'hermes-h-cli-01'):
            config = self.load(f'[yohaku]\nruntime = "{runtime}"\n')
            self.assertIsNone(activate(config, runtime=runtime,
                create=lambda: self.fail('disabled factory was called')))

    def test_enable_then_disable_on_next_start(self):
        for runtime in ('codex', 'hermes-h-cli-01'):
            calls = []
            config = self.load(f'[yohaku]\nruntime = "{runtime}"\nenabled = true\n')
            self.assertEqual(activate(config, runtime=runtime, create=lambda: calls.append(1) or 'owner'), 'owner')
            config = self.load(f'[yohaku]\nruntime = "{runtime}"\nenabled = false\n')
            self.assertIsNone(activate(config, runtime=runtime, create=lambda: calls.append(2)))
            self.assertEqual(calls, [1])

    def test_invalid_config_is_rejected(self):
        cases = ('', '[other]\nenabled = true', '[yohaku]\nenabled = true',
                 '[yohaku]\nruntime = "unknown"', '[yohaku]\nruntime = "codex"\nenabled = "false"',
                 '[yohaku]\nruntime = "codex"\nenabled = 1', '[yohaku]\nruntime = "codex"\nauto = true',
                 'yohaku = true', '[yohaku]\nruntime = "codex"\n[other]')
        for text in cases:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.load(text)

    def test_wrong_runtime_cannot_create_owner(self):
        with self.assertRaises(ValueError):
            activate(HostConfig('codex', True), runtime='hermes-h-cli-01',
                     create=lambda: self.fail('wrong runtime factory'))

    def test_missing_file_is_not_a_default_enabled_config(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(FileNotFoundError):
            load_config(Path(directory) / 'missing.toml')


if __name__ == '__main__':
    unittest.main()
