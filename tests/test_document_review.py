"""Task-specific contract tests; no model or Runtime process is used here."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from yohaku.document_review import (
    DocumentReviewContract, DocumentReviewRefusal, DocumentReviewTask,
    READ_TOOL, WRITE_TOOL, document_review_tools,
)
from yohaku.model import Request, Revisions
from yohaku.recovery import HandoffDocument, RecoveredData


class DocumentReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.workspace = self.base / "workspace"
        self.workspace.mkdir(mode=0o700)
        self.workspace.chmod(0o700)
        self.first = self.workspace / "first.md"
        self.second = self.workspace / "second.md"
        self.first.write_text("# First\n\nCurrent value A.\n")
        self.second.write_text("# Second\n\nCurrent value B.\n")
        self.first.chmod(0o600)
        self.second.chmod(0o600)
        self.output = self.workspace / "review.md"
        self.state = self.base / "state"
        self.state.mkdir(mode=0o700)
        self.contract = DocumentReviewContract.create(
            workspace=str(self.workspace), inputs=(str(self.first), str(self.second)),
            output=str(self.output), instruction="Review contradictions and risks.")
        self.task = DocumentReviewTask(self.contract, self.state)
        self.next_id = 0

    def call(self, tool, arguments):
        self.next_id += 1
        ident = "call-" + str(self.next_id)
        result = self.task.handle_call({"id": self.next_id, "method": "item/tool/call", "params": {
            "threadId": "thread", "turnId": "turn", "callId": ident,
            "namespace": None, "tool": tool, "arguments": arguments}})
        self.assertTrue(result["result"]["success"])
        item = {"id": ident, "type": "dynamicToolCall", "tool": tool,
                "status": "completed", "success": True, "arguments": arguments}
        self.assertTrue(self.task.incorporate(item))
        return item, json.loads(result["result"]["contentItems"][0]["text"])

    def document(self):
        observation = self.task.observe()
        request = Request("request", "thread", "transition", "boundary", "checkpoint",
                          "lease", 1)
        recovered = RecoveredData(
            self.contract.logical_task_id, ("input documents read",),
            "Create the specified Markdown review report from current inputs.",
            ("report is not written",), "fresh read, then publish the one report",
            tuple(["profile=document-review-report-v1",
                   "instruction_sha256=" + self.contract.instruction_sha256]
                  + ["input=" + item.path + ":" + item.sha256
                     for item in self.contract.initial_inputs]))
        return HandoffDocument("handoff", request, Revisions(), observation.workspace,
                               str(self.workspace), recovered)

    def test_exact_tools_and_one_write_complete_mechanical_assessment(self):
        self.assertEqual([tool["name"] for tool in document_review_tools()],
                         [READ_TOOL, WRITE_TOOL])
        _, first = self.call(READ_TOOL, {})
        self.assertEqual(len(first["documents"]), 2)
        self.assertEqual(first["quality_verdict"], "NOT_ASSESSED")
        self.task.begin_continuation()
        document = self.document()
        read, _ = self.call(READ_TOOL, {})
        write, result = self.call(WRITE_TOOL, {"markdown": "# Review\n\nNo contradiction found."})
        proof = self.task.assessor(document, (read, write))
        self.assertEqual(proof.read_item_ids, (read["id"],))
        self.assertEqual(proof.action_item_ids, (write["id"],))
        self.assertEqual(result["quality_verdict"], "NOT_ASSESSED")
        self.assertEqual(self.task.result()["mechanical_task_completion"], "PASS")
        self.assertEqual(self.task.result()["writing_quality"], "NOT_ASSESSED")
        report = self.output.read_text()
        self.assertIn(self.contract.instruction_sha256, report)
        self.assertIn(self.contract.initial_inputs[0].sha256, report)
        self.assertEqual(self.task.events.count("write_started"), 1)
        with self.assertRaisesRegex(DocumentReviewRefusal, "WRITE_NOT_PENDING"):
            self.task.handle_call({"id": 99, "params": {"callId": "again", "namespace": None,
                "tool": WRITE_TOOL, "arguments": {"markdown": "# Again"}}})

    def test_stale_input_after_checkpoint_refuses_fresh_read(self):
        self.call(READ_TOOL, {})
        self.task.begin_continuation()
        self.first.write_text("# First\n\nChanged after checkpoint.\n")
        with self.assertRaisesRegex(DocumentReviewRefusal, "INPUT_REVISION_CHANGED"):
            self.task.handle_call({"id": 2, "params": {"callId": "fresh", "namespace": None,
                "tool": READ_TOOL, "arguments": {}}})
        self.assertEqual(self.task.phase, "AMBIGUOUS")
        self.assertFalse(self.output.exists())

    def test_stale_output_and_undeclared_workspace_files_fail_contract(self):
        self.output.write_text("old")
        with self.assertRaisesRegex(DocumentReviewRefusal, "STALE_OUTPUT_PRESENT"):
            DocumentReviewContract.create(workspace=str(self.workspace),
                inputs=(str(self.first), str(self.second)), output=str(self.output),
                instruction="Review current inputs.")
        self.output.unlink()
        (self.workspace / "unrelated.txt").write_text("not declared")
        with self.assertRaisesRegex(DocumentReviewRefusal, "UNDECLARED_FILES"):
            DocumentReviewContract.create(workspace=str(self.workspace),
                inputs=(str(self.first), str(self.second)), output=str(self.output),
                instruction="Review current inputs.")

    def test_write_uncertainty_never_retries(self):
        self.call(READ_TOOL, {})
        self.task.begin_continuation()
        self.call(READ_TOOL, {})
        with patch.object(self.task, "_publish_bytes", side_effect=OSError):
            with self.assertRaisesRegex(DocumentReviewRefusal, "NO_RETRY"):
                self.task.handle_call({"id": 3, "params": {"callId": "write", "namespace": None,
                    "tool": WRITE_TOOL, "arguments": {"markdown": "# Review"}}})
        self.assertTrue(self.task.write_started)
        self.assertEqual(self.task.events.count("write_started"), 1)
        with self.assertRaises(DocumentReviewRefusal):
            self.task.handle_call({"id": 4, "params": {"callId": "retry", "namespace": None,
                "tool": WRITE_TOOL, "arguments": {"markdown": "# Retry"}}})
        self.assertEqual(self.task.events.count("write_started"), 1)

    def test_unrelated_tool_and_failed_result_refuse(self):
        with self.assertRaisesRegex(DocumentReviewRefusal, "UNRELATED_TOOL"):
            self.task.handle_call({"id": 1, "params": {"callId": "shell", "namespace": None,
                "tool": "shell", "arguments": {}}})
        other_state = self.base / "other-state"
        other_state.mkdir(mode=0o700)
        task = DocumentReviewTask(self.contract, other_state)
        task.handle_call({"id": 2, "params": {"callId": "read", "namespace": None,
            "tool": READ_TOOL, "arguments": {}}})
        with self.assertRaisesRegex(DocumentReviewRefusal, "NOT_INCORPORATED"):
            task.incorporate({"id": "read", "type": "dynamicToolCall", "tool": READ_TOOL,
                              "status": "failed", "success": False})


if __name__ == "__main__":
    unittest.main()
