"""Late task binding predicates, using native-shaped API and real SQLite/store."""
import base64
from contextlib import closing
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
import unittest

import test_opencode_receipt as receipt
from yohaku.controller import TransitionError
from yohaku.model import State
from yohaku.persistence import _read


class LateContinuationTests(unittest.TestCase):
    setUp = receipt.OpenCodeReceiptTests.setUp
    offer = receipt.OpenCodeReceiptTests.offer
    observation = receipt.OpenCodeReceiptTests.observation
    held = receipt.OpenCodeReceiptTests.held
    seal = receipt.OpenCodeReceiptTests.seal
    received = receipt.OpenCodeReceiptTests.received
    assess = receipt.OpenCodeReceiptTests.assess
    def qualified(self):
        self.received()
        self.a.qualify_resume(reassess=self.assess)

    def task_observation(self):
        raw = json.dumps({"model": self.f.message["model"]["id"], "messages": [
            {"role": "user", "content": self.a.payload},
            {"role": "user", "content": self.a.task_text}]}).encode()
        return dict(id="test-epoch:2", sessionID="ses_test", agent="build",
            model=self.f.message["model"], kind="primary", method="POST",
            url=self.a.provider_request_url, body_base64=base64.b64encode(raw).decode(),
            body_sha256=sha256(raw).hexdigest())

    def held_task(self):
        self.qualified()
        admission = self.a.continue_task("stage two", ttl=2)
        future = self.pool.submit(self.host.call, "/observe", self.task_observation())
        self.assertTrue(self.a.task_observed.wait(0.5))
        self.assertFalse(future.done())
        return admission, future, self.a.task_candidate["id"]

    def seal_task(self, identity):
        return self.host.call("/seal", dict(id=identity, body_sha256=self.a.task_candidate["body_sha256"]))

    def settle_task(self):
        self.resume_state["context"] = list(self.resume_state["context"]) + [
            dict(id="msg_stage_two", type="assistant", finish="stop",
                 content=[{"type": "text", "text": "STAGE_TWO_DONE"}]),
            dict(id="msg_task_idle", type="idle", outcome="succeeded")]
        self.resume_state["active"] = {}
        with closing(sqlite3.connect(self.f.db)) as db, db:
            for seq, m in enumerate(self.resume_state["context"][-2:], 11):
                db.execute("insert into session_message values (?, ?, ?, ?, ?, ?)",
                    (m["id"], "ses_test", m["type"], seq, 70,
                     json.dumps({k: v for k, v in m.items() if k not in ("id", "type")})))

    def test_late_unbound_receipt_duplicate_consumes_no_permit(self):
        self.received()
        s = self.a.core.snapshot
        self.assertIsNone(s.continuation_request_id)
        self.assertEqual(s.handoff.continuation_turn_id, "")
        self.assertFalse(self.a.core.receive_handoff(s.handoff,
            injection_evidence=s.injection_evidence, receipt_evidence=s.receipt_evidence))
        self.assertEqual(self.a.core.snapshot, s)
        self.assertIsNone(self.a.receipt_policy.delivery)

    def test_late_claim_requires_fresh_unresolved_work(self):
        self.received()
        with self.assertRaises(TransitionError):
            self.a.continue_task("stage two")
        self.a.qualify_resume(reassess=lambda *args: None)
        with self.assertRaises(TransitionError):
            self.a.continue_task("stage two")
        self.assertEqual(self.task_sends, 0)
        self.assertIsNone(self.a.core.snapshot.continuation_request_id)

    def test_late_actual_bind_saved_before_effect_and_final_reads(self):
        admission, future, identity = self.held_task()
        self.assertEqual(self.a.core.snapshot.handoff.continuation_turn_id, "")
        claim = _read(sorted(self.a.records.iterdir())[-3])["payload"]
        self.assertEqual(claim["kind"], "continuation_claimed")
        self.assertTrue(self.a.authorize_continuation(identity))
        self.assertEqual(future.result(timeout=1)["action"], "allow")
        bound = _read(Path(self.a.task_candidate["binding_ref"]))["payload"]
        self.assertEqual(bound["binding"]["turn_id"], admission["id"])
        self.assertNotEqual(admission["id"], self.a.native_id)
        self.assertNotEqual(identity, self.a.candidate["id"])
        self.assertNotEqual(self.a.task_candidate["body_sha256"], self.a.candidate["body_sha256"])
        self.assertEqual(self.seal_task(identity)["action"], "allow")
        self.settle_task()
        self.a.complete_continuation()
        self.a.final_observation()
        self.assertEqual(self.a.core.snapshot.handoff.continuation_turn_id, admission["id"])
        self.assertEqual(self.a.core.snapshot.state, State.HANDOFF_RECEIVED)
        self.assertEqual(self.task_sends, 1)

    def test_late_stale_revision_before_claim_no_send(self):
        self.qualified()
        self.current = replace(self.current, execution_revision=1)
        with self.assertRaises(TransitionError):
            self.a.continue_task("stage two")
        self.assertIsNone(self.a.core.snapshot.continuation_request_id)
        self.assertEqual(self.task_sends, 0)

    def test_late_stale_revision_before_binding_denied(self):
        admission, future, identity = self.held_task()
        self.current = replace(self.current, execution_revision=1)
        self.assertFalse(self.a.authorize_continuation(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")
        self.assertTrue(self.a.core.snapshot.continuation_request_id)
        self.assertEqual(self.a.core.snapshot.handoff.continuation_turn_id, "")

    def test_late_stale_revision_after_binding_before_release_denied(self):
        admission, future, identity = self.held_task()
        record = self.a._record
        def record_and_change(kind, **data):
            ref = record(kind, **data)
            if kind == "continuation_bound":
                self.current = replace(self.current, execution_revision=1)
            return ref
        with patch.object(self.a, "_record", record_and_change):
            self.assertFalse(self.a.authorize_continuation(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")
        self.assertEqual(self.a.core.snapshot.handoff.continuation_turn_id, admission["id"])

    def test_late_duplicate_claim_and_bind_rejected(self):
        admission, future, identity = self.held_task()
        with self.assertRaises(TransitionError):
            self.a.continue_task("stage two")
        self.assertTrue(self.a.authorize_continuation(identity))
        self.assertEqual(future.result(timeout=1)["action"], "allow")
        s = self.a.core.snapshot
        with self.assertRaises(TransitionError):
            self.a.core.claim_continuation(expected_snapshot=s)
        with self.assertRaises(TransitionError):
            self.a.core.bind_continuation(self.a.receipt_policy.delivery, expected_snapshot=s)
        self.assertEqual(self.a.core.snapshot, s)
        self.assertEqual(self.task_sends, 1)

    def test_late_receipt_input_cannot_be_task_identity(self):
        admission, future, identity = self.held_task()
        self.a.task_input_id = self.a.native_id
        self.assertFalse(self.a.authorize_continuation(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")

    def test_late_foreign_sqlite_input_denied(self):
        admission, future, identity = self.held_task()
        with closing(sqlite3.connect(self.f.db)) as db, db:
            db.execute("update session_message set session_id='foreign' where id=?", (admission["id"],))
        self.assertFalse(self.a.authorize_continuation(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")

    def test_late_foreign_hook_session_denied(self):
        self.qualified()
        self.a.continue_task("stage two")
        data = self.task_observation()
        data["sessionID"] = "foreign"
        self.assertEqual(self.host.call("/observe", data)["action"], "deny")

    def test_late_duplicate_completion_event_no_new_effect(self):
        admission, future, identity = self.held_task()
        self.assertTrue(self.a.authorize_continuation(identity))
        future.result(timeout=1)
        self.seal_task(identity)
        self.settle_task()
        self.a.complete_continuation()
        before = self.a.core.snapshot
        self.assertFalse(self.a.core.observe_completion(before.completions[0]))
        with self.assertRaises(TransitionError):
            self.a.complete_continuation()
        self.assertEqual(self.a.core.snapshot, before)
        self.assertEqual(self.task_sends, 1)

    def test_late_callback_cannot_dispatch_again(self):
        admission, future, identity = self.held_task()
        self.assertTrue(self.a.authorize_continuation(identity))
        future.result(timeout=1)
        self.assertEqual(self.seal_task(identity)["action"], "allow")
        self.assertEqual(self.seal_task(identity)["action"], "deny")
        data = self.task_observation()
        data["id"] = "test-epoch:3"
        self.assertEqual(self.host.call("/observe", data)["action"], "deny")
        self.assertEqual(self.task_sends, 1)

    def test_late_send_uncertainty_keeps_claim_no_retry(self):
        self.qualified()
        self.uncertain_send = True
        with self.assertRaises(TimeoutError):
            self.a.continue_task("stage two")
        self.assertTrue(self.a.core.snapshot.continuation_request_id)
        self.assertEqual(self.a.core.snapshot.state, State.RECOVERY_REQUIRED)
        with self.assertRaises(TransitionError):
            self.a.continue_task("stage two")
        self.assertEqual(self.task_sends, 1)

    def test_late_completion_uncertainty_keeps_binding_no_retry(self):
        admission, future, identity = self.held_task()
        self.assertTrue(self.a.authorize_continuation(identity))
        future.result(timeout=1)
        self.assertEqual(self.seal_task(identity)["action"], "allow")
        self.uncertain_completion = True
        with self.assertRaises(TimeoutError):
            self.a.complete_continuation()
        self.assertEqual(self.a.core.snapshot.handoff.continuation_turn_id, admission["id"])
        self.assertEqual(self.a.core.snapshot.state, State.RECOVERY_REQUIRED)
        with self.assertRaises(TransitionError):
            self.a.continue_task("stage two")
        self.assertEqual(self.task_sends, 1)

    def test_late_unsafe_native_permissions_denied(self):
        self.received()
        self.unsafe_permissions = True
        with self.assertRaises(TransitionError):
            self.a.qualify_resume(reassess=self.assess)

    def test_late_binding_write_failure_never_releases_effect(self):
        admission, future, identity = self.held_task()
        write = self.a.store._write
        def fail_binding(path, payload):
            if payload["kind"] == "continuation_bound":
                raise OSError("durable binding write uncertain")
            return write(path, payload)
        with patch.object(self.a.store, "_write", fail_binding):
            self.assertFalse(self.a.authorize_continuation(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")
        self.assertFalse(self.a.task_candidate["sealed"])
        self.assertEqual(self.a.core.snapshot.handoff.continuation_turn_id, admission["id"])
        self.assertEqual(self.a.core.snapshot.state, State.RECOVERY_REQUIRED)

    def test_late_tool_definitions_deny_before_provider_dispatch(self):
        self.offer()
        data = self.observation()
        body = json.loads(base64.b64decode(data["body_base64"]))
        body["tools"] = [{"type": "function", "function": {"name": "execute"}}]
        raw = json.dumps(body).encode()
        data.update(body_base64=base64.b64encode(raw).decode(), body_sha256=sha256(raw).hexdigest())
        self.assertEqual(self.host.call("/observe", data)["action"], "deny")
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)
