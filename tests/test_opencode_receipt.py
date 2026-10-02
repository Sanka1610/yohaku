"""R4 production predicates with independent SQLite and durable handoff storage."""

import base64
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import json
import sqlite3
import time
import unittest
from unittest.mock import patch

import test_opencode_adapter as r3
from yohaku.controller import TransitionError
from yohaku.model import State
from yohaku.opencode_adapter import OpenCodeAdapter
from yohaku.opencode_receipt import (BUILTINS, HOOK, PLUGIN_ID,
    OpenCodeReceiptAdapter, OpenCodeReceiptHost)
from yohaku.recovery import CurrentContext, HandoffDocument, RecoveredData


class OpenCodeReceiptTests(unittest.TestCase):
    def setUp(self):
        f = self.f = r3.OpenCodeAdapterTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.a.close()
        # Reuse native fixture construction with a new attachment/store record set.
        for record in f.a.records.iterdir():
            record.unlink()
        self.plugin = f.db.with_name("receipt.mjs")
        self.plugin.write_bytes(HOOK.read_bytes())
        self.host = OpenCodeReceiptHost(directory=f.tmp.name, plugin_path=self.plugin)
        self.addCleanup(self.host.close)
        self.host.epoch = "test-epoch"
        self.pending = None
        self.promoted = False
        self.wrong_payload = False
        self.owned = True
        self.foreign_graph = False
        self.current = CurrentContext("task", 0, 0, f.workspace)
        self.pool = ThreadPoolExecutor()
        self.addCleanup(self.pool.shutdown)
        base_api = OpenCodeAdapter._api

        def api(a, method, path, body=None):
            if path.startswith("/api/plugin?"):
                catalog = [dict(id=p, source={"type": "builtin"}, state={"status": "active"})
                           for p in BUILTINS]
                catalog.append(dict(id=PLUGIN_ID, source={"type": "local", "path": str(self.plugin)},
                                    state={"status": "active"}))
                if self.foreign_graph:
                    catalog.append(dict(id="foreign"))
                return {"data": catalog}
            if path.endswith("/prompt") and body.get("id"):
                payload = "wrong" if self.wrong_payload else body["text"]
                admitted = dict(id=body["id"], sessionID="ses_test", type="user", payload={"text": payload})
                self.pending = admitted
                with closing(sqlite3.connect(f.db)) as db, db:
                    if body.get("resume") is False:
                        db.execute("insert into session_inbox values (?, ?, ?, ?)",
                            (body["id"], "ses_test", "user", json.dumps({"text": payload})))
                    else:
                        self.promoted = True
                        db.execute("delete from session_inbox")
                        db.execute("insert into session_message values (?, ?, ?, ?, ?, ?)",
                            (body["id"], "ses_test", "user", 7, 40, json.dumps({"text": payload})))
                return {"data": admitted}
            if self.pending:
                if path.endswith("/inbox"):
                    return {"data": [] if self.promoted else [self.pending]}
                if path == "/api/session/active":
                    return {"data": {"ses_test": {"type": "running"}} if self.promoted else {}}
                if path.endswith("/context") and self.promoted:
                    return {"data": f.context() + [dict(id=self.pending["id"], type="user",
                                                        text=self.pending["payload"]["text"])]}
            result = base_api(a, method, path, body)
            if path == "/api/session/ses_test":
                result["data"]["model"] = f.message["model"]
            return result

        p = patch.object(OpenCodeReceiptAdapter, "_api", api)
        p.start()
        self.addCleanup(p.stop)
        with patch.object(OpenCodeAdapter, "_read_events", lambda a: a._connected.set()):
            self.a = OpenCodeReceiptAdapter(f.store, server_url="http://127.0.0.1:1", session_id="ses_test",
                db_path=f.db, exclusive_fresh_session=True, timeout=0.1, receipt_host=self.host,
                known_terminal_graph=True, provider_request_url="http://127.0.0.1:2/v1/chat/completions",
                observe_current=lambda: self.current, owner_alive=lambda: self.owned)
        self.addCleanup(self.a.close)
        f.a = self.a
        with closing(sqlite3.connect(f.db)) as db, db:
            db.execute("create table session_inbox(id text, session_id text, type text, payload text)")
        f.checkpoint()
        f.compact()
        s = self.a.core.snapshot
        self.doc = HandoffDocument("h1", s.request, s.checkpoint.revisions, s.workspace, f.tmp.name,
            RecoveredData("task", ("stage one done",), "bounded task", (), "inspect receipt",
                          (f.tmp.name,)))

    def offer(self):
        self.a.offer_receipt(self.doc)
        self.assertEqual(self.a.core.snapshot.state, State.HANDOFF_OFFERED)
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)
        self.a.promote_receipt(ttl=1)

    def observation(self, **overrides):
        raw = json.dumps({"model": self.f.message["model"]["id"],
                          "messages": [{"role": "user", "content": self.a.payload}]}).encode()
        return dict(id="test-epoch:1", sessionID="ses_test", agent="build",
            model=self.f.message["model"], kind="primary", method="POST",
            url=self.a.provider_request_url, body_base64=base64.b64encode(raw).decode(),
            body_sha256=sha256(raw).hexdigest(), **overrides)

    def held(self):
        self.offer()
        future = self.pool.submit(self.host.call, "/observe", self.observation())
        self.assertTrue(self.a.observed.wait(0.5))
        self.assertFalse(future.done())
        return future, self.a.candidate["id"]

    def seal(self, identity, **changes):
        data = dict(id=identity, body_sha256=self.a.candidate["body_sha256"])
        data.update(changes)
        return self.host.call("/seal", data)

    def test_receipt_endpoint_independent_of_sse_and_no_next_prompt(self):
        future, identity = self.held()
        self.a._lost.set()
        self.assertTrue(self.a.authorize_receipt(identity))
        self.assertEqual(future.result(timeout=1)["action"], "allow")
        self.assertEqual(self.seal(identity)["action"], "allow")
        self.assertEqual(self.a.core.snapshot.state, State.HANDOFF_RECEIVED)
        before = self.a.core.snapshot
        self.assertFalse(self.a.core.receive_handoff(before.handoff,
            injection_evidence=before.injection_evidence, receipt_evidence=before.receipt_evidence))
        self.assertEqual(before, self.a.core.snapshot)
        with self.assertRaises(TransitionError):
            self.a.continue_task("continue")

    def test_payload_readback_mismatch_has_no_offer(self):
        self.wrong_payload = True
        with self.assertRaises(TransitionError):
            self.a.offer_receipt(self.doc)
        self.assertIsNone(self.a.core.snapshot.handoff)
        self.assertIsNone(self.a.candidate)

    def test_foreign_session_rejected(self):
        self.offer()
        data = self.observation()
        data["sessionID"] = "ses_foreign"
        self.assertEqual(self.host.call("/observe", data)["action"], "deny")
        self.assertIsNone(self.a.candidate)

    def test_native_input_hash_changed_after_promotion(self):
        self.offer()
        with closing(sqlite3.connect(self.f.db)) as db, db:
            db.execute("update session_message set data=? where id=?",
                       (json.dumps({"text": "wrong"}), self.a.native_id))
        self.assertEqual(self.host.call("/observe", self.observation())["action"], "deny")

    def test_stale_workspace_denies_authorization(self):
        future, identity = self.held()
        self.current = replace(self.current, execution_revision=1)
        self.assertFalse(self.a.authorize_receipt(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)

    def test_duplicate_authorization_invalidates_candidate(self):
        future, identity = self.held()
        self.assertTrue(self.a.authorize_receipt(identity))
        future.result(timeout=1)
        self.assertFalse(self.a.authorize_receipt(identity))
        self.assertEqual(self.seal(identity)["action"], "deny")
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)

    def test_terminal_body_mutation_denied_after_authorization(self):
        future, identity = self.held()
        self.assertTrue(self.a.authorize_receipt(identity))
        future.result(timeout=1)
        self.assertEqual(self.seal(identity, body_sha256="changed")["action"], "deny")
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)

    def test_abort_then_late_old_callback_and_authorization_denied(self):
        future, identity = self.held()
        self.a.abort_receipt()
        self.assertFalse(self.a.authorize_receipt(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")
        self.assertEqual(self.seal(identity)["action"], "deny")
        data = self.observation()
        data["id"] = "test-epoch:2"
        self.assertEqual(self.host.call("/observe", data)["action"], "deny")

    def test_retry_after_receipt_stops_and_cannot_reuse_old_attempt(self):
        future, identity = self.held()
        self.assertTrue(self.a.authorize_receipt(identity))
        future.result(timeout=1)
        self.assertEqual(self.seal(identity)["action"], "allow")
        self.host.call("/retry", {"sessionID": "ses_test"})
        self.assertFalse(self.a.candidate["valid"])
        self.assertEqual(self.a.core.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertFalse(self.a.authorize_receipt(identity))
        data = self.observation()
        data["id"] = "test-epoch:2"
        self.assertEqual(self.host.call("/observe", data)["action"], "deny")

    def test_unknown_later_plugin_and_owner_loss_deny(self):
        future, identity = self.held()
        self.foreign_graph = True
        self.assertFalse(self.a.authorize_receipt(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")

    def test_owner_loss_denies(self):
        future, identity = self.held()
        self.owned = False
        self.assertFalse(self.a.authorize_receipt(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")

    def test_expiry_denies_old_authorization(self):
        future, identity = self.held()
        self.a.deadline = time.monotonic() - 1
        self.assertFalse(self.a.authorize_receipt(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")

    def test_host_disposal_denies_held_callback(self):
        future, identity = self.held()
        self.host.close()
        self.assertFalse(self.a.authorize_receipt(identity))
        self.assertEqual(future.result(timeout=1)["action"], "deny")

    def test_stale_epoch_observation_denied(self):
        self.offer()
        data = self.observation()
        data["id"] = "old-epoch:1"
        self.assertEqual(self.host.call("/observe", data)["action"], "deny")

    def test_attempt_replacement_invalidates_old_observation(self):
        future, identity = self.held()
        data = self.observation()
        data["id"] = "test-epoch:2"
        self.assertEqual(self.host.call("/observe", data)["action"], "deny")
        self.assertEqual(future.result(timeout=1)["action"], "deny")
        self.assertFalse(self.a.authorize_receipt(identity))

    def test_duplicate_terminal_release_has_one_receipt_record(self):
        future, identity = self.held()
        self.assertTrue(self.a.authorize_receipt(identity))
        future.result(timeout=1)
        self.assertEqual(self.seal(identity)["action"], "allow")
        ref = self.a.core.snapshot.receipt_evidence
        self.assertEqual(self.seal(identity)["action"], "deny")
        self.assertEqual(self.a.core.snapshot.receipt_evidence, ref)

    def test_wrong_serialized_model_denied(self):
        self.offer()
        data = self.observation()
        raw = json.dumps({"model": "foreign", "messages": [
            {"role": "user", "content": self.a.payload}]}).encode()
        data.update(body_base64=base64.b64encode(raw).decode(), body_sha256=sha256(raw).hexdigest())
        self.assertEqual(self.host.call("/observe", data)["action"], "deny")


if __name__ == "__main__":
    unittest.main()
