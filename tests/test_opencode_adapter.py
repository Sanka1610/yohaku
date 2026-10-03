"""Bounded adapter negatives with native-shaped fixtures and real SQLite/store.

These are local synthetic checks, separate from live OpenCode acceptance.
"""

from copy import deepcopy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from yohaku.controller import TransitionError
from yohaku.model import BoundaryVerification, State, WorkspaceRevision
from yohaku.opencode import OpenCodeNativeCompletionPolicy
from yohaku.opencode_adapter import OpenCodeAdapter
from yohaku.persistence import SessionStore, _read
from yohaku.supervisor import YohakuSupervisor


class OpenCodeAdapterTests(unittest.TestCase):
    def test_supervisor_routes_standalone_to_existing_compact(self):
        supervisor = YohakuSupervisor()
        registration = supervisor.register_builtin('opencode', self.a)
        self.checkpoint()
        supervisor.request_transition(registration.session, requester='opencode',
                                      observe_workspace=lambda: self.workspace)
        self.assertEqual(self.a.core.snapshot.state, State.ROLLOVER_OBSERVED)
        self.assertEqual(self.compacts, 1)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, CODEX_HOME=self.tmp.name)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = SessionStore("ses_test", create=True)
        self.addCleanup(self.store.close)
        self.db = Path(self.tmp.name) / "native.db"
        self.workspace = WorkspaceRevision(0, "fixture", ("task",))
        self.message = dict(id="msg_compact", type="compaction", status="completed",
                            reason="manual", summary="retained", recent="", time={"created": 20},
                            model={"id": "local", "providerID": "local"}, cost=0, tokens={})
        self.start = dict(id="evt_start", type="session.compaction.started", created=20,
            location={"directory": self.tmp.name}, durable={"aggregateID": "ses_test", "seq": 5, "version": 1},
            data={"sessionID": "ses_test", "inputID": "msg_compact", "reason": "manual", "recent": ""})
        self.end = dict(id="evt_end", type="session.compaction.ended", created=30,
            location={"directory": self.tmp.name}, durable={"aggregateID": "ses_test", "seq": 6, "version": 1},
            data={"sessionID": "ses_test", "reason": "manual", "text": "retained",
                  "recent": "", "model": self.message["model"], "cost": 0, "tokens": {}})
        with sqlite3.connect(self.db) as db:
            db.execute("create table session_message(id text, session_id text, type text, "
                       "seq integer, time_updated integer, data text)")
            db.execute("insert into session_message values (?, ?, ?, ?, ?, ?)",
                ("msg_compact", "ses_test", "compaction", 5, 30,
                 json.dumps({k: v for k, v in self.message.items() if k not in ("id", "type")})))
        db.close()
        self.prompts = self.compacts = 0
        self.events = [self.start, self.end]
        self.lose_stream = False
        owner = self

        def api(adapter, method, path, body=None):
            if path == "/api/info":
                return {"version": "2.0.21", "pid": 1}
            if path.endswith("/prompt"):
                owner.prompts += 1
                return {"data": {"id": "msg_work" if owner.prompts == 1 else "msg_next"}}
            if path.endswith("/compact"):
                owner.compacts += 1
                # Core authority must already be consumed and journaled at I/O.
                owner.assertEqual(adapter.core.snapshot.state, State.ROLLOVER_REQUESTED)
                owner.assertEqual(_read(sorted(owner.store.journal.iterdir())[-1])["payload"]["event"],
                                  "opencode_compact_requested")
                owner.assertEqual(adapter.core.snapshot.completions, ())
                with owner.assertRaises(TransitionError):
                    adapter.core.request_rollover(adapter.core.snapshot.lease, now=0,
                        intent_revision=0, execution_revision=0, workspace=owner.workspace)
                for event in owner.events:
                    adapter._events.put(deepcopy(event))
                if owner.lose_stream:
                    adapter._lost.set()
                return {"data": {"id": "msg_compact", "sessionID": "ses_test", "type": "compaction"}}
            if path.endswith("/wait"):
                return None
            if path == "/api/session/active":
                return {"data": {}}
            if path.endswith("/inbox"):
                return {"data": []}
            if path.endswith("/context"):
                return {"data": owner.context()}
            return {"data": {"id": "ses_test", "location": {"directory": owner.tmp.name},
                             "outcome": "succeeded"}}

        def reader(adapter):
            adapter._connected.set()

        with patch.object(OpenCodeAdapter, "_api", api), patch.object(OpenCodeAdapter, "_read_events", reader):
            self.a = OpenCodeAdapter(self.store, server_url="http://127.0.0.1:1", session_id="ses_test",
                db_path=self.db, exclusive_fresh_session=True, timeout=0.03)
        self.addCleanup(self.a.close)
        self.api_patch = patch.object(OpenCodeAdapter, "_api", api)
        self.api_patch.start()
        self.addCleanup(self.api_patch.stop)

    def context(self):
        idle = dict(id="msg_idle", type="idle", outcome="succeeded")
        if self.compacts:
            messages = [deepcopy(self.message), idle]
            if self.prompts == 2:
                messages += [dict(id="msg_next", type="user", text="next"),
                             dict(id="msg_answer2", type="assistant", finish="stop", content=[]),
                             dict(id="msg_idle2", type="idle", outcome="succeeded")]
            return messages
        if self.prompts:
            return [dict(id="msg_work", type="user", text="work"),
                    dict(id="msg_answer", type="assistant", finish="stop", content=[]), idle]
        return []

    def checkpoint(self):
        self.a.work("work")
        verification = BoundaryVerification(0, 0, self.workspace, "verification_passed",
                                            "passed", "fixture:boundary", True)
        self.a.checkpoint(boundary_id="boundary", verification=verification,
                          observe_workspace=lambda: self.workspace)

    def compact(self):
        return self.a.compact(observe_workspace=lambda: self.workspace)

    def test_complete_then_duplicate_has_no_second_effect(self):
        self.checkpoint()
        proof = self.compact()
        self.assertEqual(self.a.core.snapshot.state, State.ROLLOVER_OBSERVED)
        before = self.a.core.snapshot
        self.assertFalse(self.a.core.observe_completion(proof))
        self.assertEqual(before, self.a.core.snapshot)
        self.assertEqual(len(before.completions), 1)
        self.a.continue_task("next")
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)
        self.assertEqual(self.a.core.snapshot.state, State.ROLLOVER_OBSERVED)
        with self.assertRaises(TransitionError):
            self.a.continue_task("next again")
        self.assertEqual(self.prompts, 2)

    def test_wrong_native_id_never_completes(self):
        self.checkpoint()
        self.events[0]["data"]["inputID"] = "msg_wrong"
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.a.core.snapshot.state, State.AMBIGUOUS)
        self.assertFalse(self.a.core.snapshot.completions)

    def test_incomplete_lifecycle_never_completes(self):
        self.checkpoint()
        self.events = [self.start]
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.a.core.snapshot.state, State.AMBIGUOUS)
        self.assertFalse(self.a.core.snapshot.completions)

    def test_ended_alone_never_completes(self):
        self.checkpoint()
        self.events = [self.end]
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.a.core.snapshot.state, State.AMBIGUOUS)

    def test_second_compact_and_consumed_lease_cannot_dispatch(self):
        self.checkpoint()
        proof = self.compact()
        with self.assertRaises(TransitionError):
            self.compact()
        s = self.a.core.snapshot
        with self.assertRaises(TransitionError):
            self.a.core.request_rollover(s.lease, now=1, intent_revision=0,
                                        execution_revision=0, workspace=self.workspace)
        self.assertEqual(self.compacts, 1)
        self.assertEqual(s.request, proof.binding.request)

    def test_sse_loss_cannot_be_inferred_from_completed_db(self):
        self.checkpoint()
        self.lose_stream = True
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.a.core.snapshot.state, State.AMBIGUOUS)
        self.assertFalse(self.a.core.snapshot.completions)
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.compacts, 1)

    def test_policy_rejects_wrong_projections_and_lifecycle(self):
        self.checkpoint()
        proof = self.compact()
        policy = OpenCodeNativeCompletionPolicy()
        for changes in (dict(started={}), dict(ended={}), dict(sqlite_message={}),
                        dict(session_after="ses_wrong"), dict(observation_intact=False),
                        dict(before_ids=proof.current_ids), dict(sqlite_updated=0),
                        dict(context_message={**proof.context_message, "id": "msg_wrong"})):
            with self.subTest(changes=changes):
                self.assertFalse(policy.valid_event(replace(proof, **changes)))

    def test_sse_reader_parses_order_and_marks_eof_as_loss(self):
        hello = {"type": "server.connected", "data": {}}
        wire = "".join("data: " + json.dumps(e) + "\n\n" for e in (hello, self.start, self.end))
        with patch("yohaku.opencode_adapter.urllib.request.urlopen", return_value=io.BytesIO(wire.encode())):
            self.a._read_events()
        self.assertTrue(self.a._lost.is_set())
        self.assertEqual([self.a._events.get_nowait() for _ in range(3)], [hello, self.start, self.end])

    def test_native_proof_is_not_a_schema_one_restart_snapshot(self):
        from yohaku.persistence import PersistenceError
        self.checkpoint()
        self.compact()
        with self.assertRaises(PersistenceError):
            self.store.append(self.a.core.snapshot, {}, "unsupported_restart")

    def test_changed_workspace_revokes_before_native_dispatch(self):
        self.checkpoint()
        with self.assertRaises(TransitionError):
            self.a.compact(observe_workspace=lambda: WorkspaceRevision(1, "changed", ("task",)))
        self.assertEqual(self.compacts, 0)


if __name__ == "__main__":
    unittest.main()
