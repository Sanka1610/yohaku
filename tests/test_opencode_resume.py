"""Final verification with native-shaped API, real SQLite and durable records."""
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import test_opencode_continuation as continuation
from yohaku.codec import encode
from yohaku.controller import TransitionError
from yohaku.model import ResumeVerification, State
from yohaku.persistence import _read


class ResumeVerificationTests(unittest.TestCase):
    setUp = continuation.LateContinuationTests.setUp
    offer = continuation.LateContinuationTests.offer
    observation = continuation.LateContinuationTests.observation
    held = continuation.LateContinuationTests.held
    seal = continuation.LateContinuationTests.seal
    received = continuation.LateContinuationTests.received
    assess = continuation.LateContinuationTests.assess
    qualified = continuation.LateContinuationTests.qualified
    task_observation = continuation.LateContinuationTests.task_observation
    held_task = continuation.LateContinuationTests.held_task
    seal_task = continuation.LateContinuationTests.seal_task
    settle_task = continuation.LateContinuationTests.settle_task

    def completed(self):
        _, future, identity = self.held_task()
        self.assertTrue(self.a.authorize_continuation(identity))
        self.assertEqual(future.result(timeout=1)["action"], "allow")
        self.assertEqual(self.seal_task(identity)["action"], "allow")
        self.settle_task()
        with closing(sqlite3.connect(self.f.db)) as db, db:
            db.execute("insert into session_message values (?, ?, ?, ?, ?, ?)",
                ("msg_stage_one", "ses_test", "assistant", 1, 10,
                 json.dumps(dict(content=[dict(type="text", text="STAGE_ONE_DONE")]))))
        self.a.complete_continuation()
        self.current = replace(self.current, execution_revision=1,
            workspace=replace(self.current.workspace, mutation_epoch=1, workspace_stamp="final"))
        self.a.final_observation()
        self.task_file = Path(self.f.tmp.name) / "task.json"
        self.task_file.write_text(json.dumps(encode(self.current)))
        c = self.a.task_candidate
        self.provider_attempts = [dict(native_id=self.a.task_input_id,
            host_local_attempt_id=c["id"], body_sha256=c["body_sha256"])]

    def assessment(self, document, current, state):
        with closing(sqlite3.connect(self.f.db)) as db:
            rows = db.execute("select data from session_message where session_id=? and type='assistant'",
                              (self.a.core.snapshot.thread_id,)).fetchall()
        parts = [p for row in rows for p in json.loads(row[0]).get("content", [])]
        texts = [p.get("text") for p in parts if p["type"] == "text"]
        task = json.loads(self.task_file.read_text())
        return dict(status="PASS", current=task, task_input_id=self.a.task_input_id,
            terminal_id=state["context"][-2]["id"], provider_attempts=deepcopy(self.provider_attempts),
            task_observation_ref=str(self.task_file), stage_one_count=texts.count("STAGE_ONE_DONE"),
            receipt_count=texts.count("RECEIPT_ONLY"), stage_two_count=texts.count("STAGE_TWO_DONE"),
            tool_execution_count=sum(p["type"] == "tool" for p in parts))

    def rejected(self, assess=None):
        with patch.object(self.a.core, "verify_resume", wraps=self.a.core.verify_resume) as verify:
            with self.assertRaises((TransitionError, OSError)):
                self.a.verify_resume(assess=assess or self.assessment)
            verify.assert_not_called()
        self.assertNotEqual(self.a.core.snapshot.state, State.RESUME_VERIFIED)
        self.assertFalse(hasattr(self.a, "resume_verification"))

    def test_existing_core_verifies_persisted_actual_task_and_second_verify_rejected(self):
        self.completed()
        self.a._lost.set()  # Final authority is independent of SSE.
        original = self.a.core.verify_resume
        def verify(evidence):
            self.assertIsInstance(evidence, ResumeVerification)
            record = _read(Path(evidence.evidence_ref))["payload"]
            self.assertEqual(record["kind"], "runtime_resume_verification")
            self.assertEqual(record["task_input_id"], evidence.continuation_turn_id)
            self.assertNotEqual(record["receipt_input_id"], evidence.continuation_turn_id)
            self.assertEqual(record["current"], encode(self.current))
            original(evidence)
        with patch.object(self.a.core, "verify_resume", side_effect=verify) as call:
            result = self.a.verify_resume(assess=self.assessment)
            call.assert_called_once_with(result)
        self.assertEqual(self.a.core.snapshot.state, State.RESUME_VERIFIED)
        before = self.a.core.snapshot
        with self.assertRaises(TransitionError):
            self.a.verify_resume(assess=self.assessment)
        with self.assertRaises(TransitionError):
            self.a.core.verify_resume(result)
        self.assertEqual(self.a.core.snapshot, before)
        self.assertEqual(self.task_sends, 1)

    def test_receipt_completion_record_reuse_rejected(self):
        self.completed()
        self.a.task_completion = self.a.core.snapshot.receipt_evidence
        self.rejected()

    def test_receipt_authorization_reuse_rejected(self):
        self.completed()
        self.a.task_candidate["authorization_ref"] = self.a.candidate["authorization_ref"]
        self.rejected()

    def test_receipt_provider_attempt_reuse_rejected(self):
        self.completed()
        self.provider_attempts = [dict(native_id=self.a.native_id,
            host_local_attempt_id=self.a.candidate["id"], body_sha256=self.a.candidate["body_sha256"])]
        self.rejected()

    def test_wrong_actual_input_rejected(self):
        self.completed()
        self.a.task_input_id = "wrong"
        self.rejected()

    def test_foreign_session_rejected(self):
        self.completed()
        self.resume_state["session"]["id"] = "foreign"
        self.rejected()

    def test_stale_api_observation_rejected(self):
        self.completed()
        self.resume_state["context"][-2]["content"][0]["text"] = "old"
        self.rejected()

    def test_stale_sqlite_observation_rejected(self):
        self.completed()
        with closing(sqlite3.connect(self.f.db)) as db, db:
            db.execute("update session_message set time_updated=99 where id='msg_stage_two'")
        self.rejected()

    def test_failed_terminal_rejected_even_with_task_marker(self):
        self.completed()
        self.resume_state["context"][-2]["finish"] = "error"
        with closing(sqlite3.connect(self.f.db)) as db, db:
            m = self.resume_state["context"][-2]
            db.execute("update session_message set data=? where id=?",
                (json.dumps({k:v for k,v in m.items() if k not in ("id", "type")}), m["id"]))
        self.rejected()

    def test_incomplete_continuation_rejected(self):
        self.completed()
        self.resume_state["active"] = {"ses_test": {"type": "running"}}
        self.rejected()

    def test_pending_work_rejected(self):
        self.completed()
        with closing(sqlite3.connect(self.f.db)) as db, db:
            db.execute("insert into session_pending values ('later', 'ses_test')")
        self.rejected()

    def test_send_uncertainty_cannot_verify(self):
        self.qualified()
        self.uncertain_send = True
        with self.assertRaises(TimeoutError):
            self.a.continue_task("stage two")
        self.rejected(lambda *args: True)

    def test_completion_uncertainty_cannot_verify(self):
        _, future, identity = self.held_task()
        self.a.authorize_continuation(identity)
        future.result(timeout=1)
        self.seal_task(identity)
        self.uncertain_completion = True
        with self.assertRaises(TimeoutError):
            self.a.complete_continuation()
        self.rejected(lambda *args: True)

    def test_duplicate_completion_rejected(self):
        self.completed()
        self.resume_state["context"].extend(deepcopy(self.resume_state["context"][-2:]))
        self.rejected()

    def test_duplicate_provider_execution_rejected(self):
        self.completed()
        self.provider_attempts *= 2
        self.rejected()

    def test_final_revision_mismatch_rejected(self):
        self.completed()
        self.current = replace(self.current, execution_revision=2)
        self.rejected()

    def test_bounded_assessment_wrong_revision_rejected(self):
        self.completed()
        self.task_file.write_text(json.dumps(encode(replace(self.current, execution_revision=0))))
        self.rejected()

    def test_model_self_report_only_rejected(self):
        self.completed()
        self.rejected(lambda *args: dict(status="PASS", text="STAGE_TWO_DONE"))

    def test_stage_one_repeated_in_transcript_rejected(self):
        self.completed()
        with closing(sqlite3.connect(self.f.db)) as db, db:
            db.execute("insert into session_message select 'repeat',session_id,type,2,11,data "
                       "from session_message where id='msg_stage_one'")
        self.rejected()

    def test_runtime_record_save_failure_never_calls_core(self):
        self.completed()
        write = self.a.store._write
        def fail(path, payload):
            if payload["kind"] == "runtime_resume_verification":
                raise OSError("save failure")
            return write(path, payload)
        with patch.object(self.a.store, "_write", side_effect=fail):
            self.rejected()
        self.assertTrue(self.a.stopped)

    def test_external_mutation_after_record_save_prevents_core_call(self):
        self.completed()
        record = self.a._record
        def mutate(kind, **data):
            ref = record(kind, **data)
            if kind == "runtime_resume_verification":
                self.current = replace(self.current, execution_revision=2)
            return ref
        with patch.object(self.a, "_record", side_effect=mutate):
            self.rejected()

    def test_provider_count_changes_after_record_save_prevents_core_call(self):
        self.completed()
        record = self.a._record
        def mutate(kind, **data):
            ref = record(kind, **data)
            if kind == "runtime_resume_verification":
                self.provider_attempts *= 2
            return ref
        with patch.object(self.a, "_record", side_effect=mutate):
            self.rejected()

    def test_core_rejection_never_repairs_state_or_retries(self):
        self.completed()
        before = self.a.core.snapshot
        with patch.object(self.a.core, "verify_resume", side_effect=TransitionError("rejected")) as call:
            with self.assertRaisesRegex(TransitionError, "rejected"):
                self.a.verify_resume(assess=self.assessment)
            call.assert_called_once()
            with self.assertRaises(TransitionError):
                self.a.verify_resume(assess=self.assessment)
            call.assert_called_once()
        self.assertEqual(self.a.core.snapshot, before)
        self.assertTrue(self.a.stopped)

    def test_success_record_save_failure_stops_owner(self):
        self.completed()
        write = self.a.store._write
        def fail(path, payload):
            if payload["kind"] == "resume_verified":
                raise OSError("success write uncertain")
            return write(path, payload)
        with patch.object(self.a.store, "_write", side_effect=fail):
            with self.assertRaises(OSError):
                self.a.verify_resume(assess=self.assessment)
        self.assertTrue(self.a.stopped)
        self.assertFalse(hasattr(self.a, "resume_verification"))
        with self.assertRaises(TransitionError):
            self.a.continue_task("stage two")
