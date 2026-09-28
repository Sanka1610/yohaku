"""Runtime-specific allowlist checks without starting Codex or inference."""

import unittest
from pathlib import Path
import tempfile

from yohaku.document_review import READ_TOOL, WRITE_TOOL
from yohaku.document_review_runtime import DocumentReviewRuntime
from yohaku import operational as op


class DocumentReviewRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime = object.__new__(DocumentReviewRuntime)
        self.runtime.violation = None
        self.runtime.host = None

    def test_task_dynamic_tools_are_exactly_allowed_by_hook(self):
        for name in (READ_TOOL, WRITE_TOOL):
            with self.subTest(name=name):
                self.assertEqual(self.runtime.deny_or_deliver(
                    {"hook_event_name": "PreToolUse", "tool_name": name}), {})
                self.assertEqual(self.runtime.deny_or_deliver(
                    {"hook_event_name": "PostToolUse", "tool_name": name}), {})
                self.assertIsNone(self.runtime.violation)

    def test_every_other_tool_is_denied(self):
        result = self.runtime.deny_or_deliver(
            {"hook_event_name": "PreToolUse", "tool_name": "Bash"})
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.runtime.violation, "BUILTIN_TOOL_ATTEMPT_REFUSED")

    def test_task_state_is_single_use_but_can_be_disabled_after_success(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            workspace = root / "workspace"
            workspace.mkdir(mode=0o700)
            workspace.chmod(0o700)
            source = workspace / "input.md"
            source.write_text("# Input\n")
            source.chmod(0o600)
            credentials = root / "credentials"
            credentials.mkdir(mode=0o700)
            (credentials / "auth.json").write_text("{}")
            path = root / "config.json"
            config = op.OperationalConfig(
                "codex-document-review-report-v1", str(Path("/usr/bin/false").resolve()),
                str(workspace), str(root / "state"), True, True,
                task_inputs=(str(source),), task_output=str(workspace / "report.md"),
                task_instruction="Review the input.", credential_home=str(credentials))
            op.configure(path, config)
            op.set_enabled(path, True)
            config = op.load(path)
            self.assertTrue(op.recovery(config)["fresh_start_allowed"])
            op.write_json(Path(config.state_dir) / "last-run.json", {
                "schema": 1, "config_digest": op.config_digest(config), "run_id": "done",
                "state": "STOPPED"})
            self.assertFalse(op.recovery(config)["fresh_start_allowed"])
            op.set_enabled(path, False)
            self.assertFalse(op.load(path).enabled)


if __name__ == "__main__":
    unittest.main()
