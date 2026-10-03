"""Local POSIX persistence and fake-transport adapter contract checks."""

import io
import json
import os
import stat
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from yohaku.companion import CompanionController, CurrentState
from yohaku.codec import decode, encode
from yohaku.controller import TransitionError
from yohaku.manual import JsonLineSender
from yohaku.model import BoundaryVerification, ContinuationBinding, Handoff, Snapshot, State, WorkspaceRevision
from yohaku.persistence import PersistenceError, SessionStore, resolve_yohaku_home
from yohaku.recovery import HandoffDocument, RecoveredData
from yohaku import persistence
from yohaku.supervisor import (AdapterRegistration, OBSERVER, TRIGGER, SessionProfile,
                               SupervisorError, YohakuSupervisor)


class CompanionTests(unittest.TestCase):
    def test_supervisor_meta_owner_keeps_codex_observer_only(self):
        supervisor = YohakuSupervisor()
        session = SessionProfile('codex', 'thread-1', 'meta', 'fixture: explicit meta owner')
        supervisor.register_session(session)
        observer = supervisor.register_builtin('codex', self.c, session=session, roles=(OBSERVER,))
        self.assertIsNone(observer.transition)
        meta = Mock(return_value='meta request')
        supervisor.register_adapter(AdapterRegistration('meta', session,
            frozenset({TRIGGER, OBSERVER}), lambda: ('thread-1',), lambda: self.c.snapshot, meta))
        before = self.c.snapshot
        with self.assertRaises(SupervisorError) as caught:
            supervisor.request_transition(session, requester='codex')
        self.assertEqual(str(caught.exception), 'SUPERVISOR_NOT_TRIGGER')
        self.assertEqual(supervisor.request_transition(session, requester='meta'), 'meta request')
        meta.assert_called_once()
        self.assertEqual(self.c.snapshot, before)
        self.assertEqual(self.sent, [])
        self.assertEqual([r.name for r in supervisor.observers(session)], ['codex', 'meta'])

    def test_supervisor_routes_standalone_native_thread_to_existing_compact(self):
        supervisor = YohakuSupervisor()
        registration = supervisor.register_builtin('codex', self.c)
        lease = self.authorized()
        request = supervisor.request_transition(registration.session, lease, self.current,
            requester='codex', completion_timeout=2)
        self.assertEqual(self.sent, [{"id": request.request_id, "method": "thread/compact/start",
                                    "params": {"threadId": "thread-1"}}])
        self.assertEqual(self.c.snapshot.state, State.ROLLOVER_REQUESTED)
        before = self.c.snapshot
        with self.assertRaises(SupervisorError):
            supervisor.request_transition(registration.session, lease, self.current, requester='codex')
        self.assertEqual(self.c.snapshot, before)
        self.assertEqual(len(self.sent), 1)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"CODEX_HOME": self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.now = 10.0
        self.sent = []
        self.c = CompanionController("thread-1", self.send, create=True, clock=lambda: self.now)
        self.addCleanup(lambda: self.c.close())
        self.workspace = WorkspaceRevision(0, "stamp", ("src/",))

    def send(self, message):
        # The durable dispatch record must exist before the first transport byte.
        self.assertEqual(self.c.store.latest[0].state, State.ROLLOVER_REQUESTED)
        self.assertEqual(self.c.store.latest[0].request.request_id, message["id"])
        self.sent.append(message)

    def verified(self):
        c = self.c
        c.step("propose_boundary", "boundary-1")
        c.step("arm_barrier")
        c.step("begin_quiescence_check")
        c.step("observe_quiescence", relevant_work_remaining=False)
        c.step("capture_workspace", self.workspace)
        c.step("verify_boundary", BoundaryVerification(
            0, 0, self.workspace, "verification_passed", "passed", "test-record", True))

    def authorized(self):
        self.verified()
        self.c.commit_checkpoint()
        return self.c.authorize_rollover(ttl=10)

    def current(self):
        s = self.c.snapshot
        return CurrentState(s.revisions.intent_revision, s.revisions.execution_revision,
                            s.workspace, s.lease.lease_id, s.rollover_generation,
                            s.checkpoint.checkpoint_id, True)

    def requested(self):
        lease = self.authorized()
        return self.c.request_compact(lease, self.current, completion_timeout=2)

    def event(self, method, **params):
        return {"method": method, "params": {"threadId": "thread-1", **params}}

    def bind(self, request):
        self.c.receive(self.event("turn/started", turn={"id": "compact-turn", "status": "inProgress"}), request=request)
        self.c.receive(self.event("item/started", turnId="compact-turn",
                                 item={"id": "compact-item", "type": "contextCompaction"}), request=request)

    def completions(self):
        return [
            self.event("item/completed", turnId="compact-turn",
                       item={"id": "compact-item", "type": "contextCompaction"}),
            self.event("hook/completed", turnId="compact-turn",
                       run={"eventName": "postCompact", "status": "completed",
                            "entries": [{"text": "SECRET_BODY_MUST_NOT_BE_STORED"}]}),
            self.event("turn/completed", turn={"id": "compact-turn", "status": "completed",
                                               "error": None, "items": ["SECRET_BODY_MUST_NOT_BE_STORED"]}),
        ]

    def restart(self):
        self.c.close()
        self.c = CompanionController("thread-1", self.send, clock=lambda: self.now)

    def test_home_resolution_is_independent_of_cwd(self):
        self.assertEqual(resolve_yohaku_home(), Path(self.tmp.name) / "yohaku")
        with patch.dict(os.environ, {"CODEX_HOME": ""}), patch("pathlib.Path.home", return_value=Path(self.tmp.name)):
            self.assertEqual(resolve_yohaku_home(), Path(self.tmp.name) / ".codex" / "yohaku")
        with patch.dict(os.environ, {"CODEX_HOME": "relative"}):
            with self.assertRaises(PersistenceError):
                resolve_yohaku_home()

    def test_handoff_binding_uses_existing_append_only_format_and_reader(self):
        request = self.requested()
        self.bind(request)
        for event in self.completions():
            self.c.receive(event, request=request)
        core = self.c._core
        s = core.snapshot
        document = HandoffDocument("delayed", s.request, s.checkpoint.revisions,
            s.checkpoint.workspace, self.tmp.name,
            RecoveredData("task", (), "Finish task", ("remaining work",), "read task", ("task.json",)))
        self.c.store.commit_handoff(document)
        document_path = self.c.store.path / "handoffs" / "delayed.json"
        original_document = document_path.read_bytes()
        handoff = core.offer_handoff(None, handoff_id=document.handoff_id,
            recovered_context="handoff:delayed", expected_snapshot=s)
        snapshots = [("handoff_offered", core.snapshot)]
        core.receive_handoff(handoff, injection_evidence="inspection", receipt_evidence="receipt")
        snapshots.append(("handoff_received", core.snapshot))
        core.claim_continuation(expected_snapshot=core.snapshot)
        snapshots.append(("continuation_requested", core.snapshot))
        claimed = core.snapshot
        core.bind_continuation(ContinuationBinding(claimed.continuation_request_id,
            claimed.thread_id, "actual-task"), expected_snapshot=claimed)
        snapshots.append(("continuation_bound", core.snapshot))
        original_records = {p: p.read_bytes() for p in self.c.store.journal.glob("*.json")}
        for event, snapshot in snapshots:
            with self.subTest(event=event):
                self.assertEqual(decode(Handoff, encode(snapshot.handoff)), snapshot.handoff)
                self.assertEqual(decode(Snapshot, encode(snapshot)), snapshot)
                self.c.store.append(snapshot, {}, event)
                # Reopen only the existing journal reader, without rebuilding a Runtime owner.
                self.c.store.close()
                self.c.store = SessionStore("thread-1")
                self.assertEqual(self.c.store.latest, (snapshot, {}))
                for path, content in original_records.items():
                    self.assertEqual(path.read_bytes(), content)
                newest = sorted(self.c.store.journal.glob("*.json"))[-1]
                record = json.loads(newest.read_bytes())
                self.assertEqual(set(record), {"schema", "sha256", "payload"})
                self.assertEqual(record["schema"], 1)
                self.assertEqual(set(record["payload"]),
                                 {"sequence", "previous", "event", "snapshot", "cursor"})
                self.assertEqual(set(record["payload"]["snapshot"]["handoff"]), {
                    "handoff_id", "request", "continuation_turn_id", "intent_revision",
                    "execution_revision", "recovered_context", "material_policy", "resume_status"})
                original_records[newest] = newest.read_bytes()
        self.assertEqual(document_path.read_bytes(), original_document)
        self.assertEqual(self.c.store.read_handoff("delayed"), document)

    def test_checkpoint_roundtrip_temp_ignored_restart_revokes_lease(self):
        lease = self.authorized()
        checkpoint = self.c.snapshot.checkpoint
        self.assertEqual(self.c.store.read_checkpoint(checkpoint.checkpoint_id), checkpoint)
        (self.c.store.checkpoints / ".tmp-incomplete").write_text('{"checkpoint":')
        (self.c.store.journal / ".tmp-incomplete").write_text('{')
        self.assertEqual(self.c.store.recovery_candidates(), (checkpoint,))
        self.restart()
        self.assertEqual(self.c.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertEqual(self.c.snapshot.recoverable_checkpoint, checkpoint)
        self.assertIsNone(self.c.snapshot.lease)
        self.assertEqual(self.c.snapshot.revoked_lease_id, lease.lease_id)
        with self.assertRaises(TransitionError):
            self.c.request_compact(lease, self.current)
        self.assertEqual(self.sent, [])

    def test_checkpoint_commit_fsync_order(self):
        self.verified()
        operations = []
        real_fsync, real_replace = os.fsync, os.replace

        def fsync(fd):
            operations.append("directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
            return real_fsync(fd)

        def rename(source, target):
            operations.append("rename")
            return real_replace(source, target)

        with patch("yohaku.persistence.os.fsync", side_effect=fsync), patch("yohaku.persistence.os.replace", side_effect=rename):
            self.c.commit_checkpoint()
        self.assertEqual(operations, ["file", "rename", "directory"] * 3)
        self.assertEqual(self.c.snapshot.state, State.CHECKPOINT_COMMITTED)

    def test_checkpoint_directory_sync_failure_and_crash_gap_recovery(self):
        self.verified()
        sync = persistence._sync_directory

        def fail_checkpoint_sync(path):
            if path == self.c.store.checkpoints:
                raise OSError("injected directory fsync failure")
            return sync(path)

        with patch("yohaku.persistence._sync_directory", side_effect=fail_checkpoint_sync):
            with self.assertRaises(PersistenceError):
                self.c.commit_checkpoint()
        self.assertEqual(self.c.snapshot.state, State.CHECKPOINT_PREPARING)
        with self.assertRaises(PersistenceError):
            self.c.authorize_rollover(ttl=10)
        self.restart()
        self.assertIsNotNone(self.c.snapshot.recoverable_checkpoint)
        self.assertEqual(self.c.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertIsNone(self.c.snapshot.lease)

    def test_acceptance_not_completion_and_duplicate_suppression(self):
        request = self.requested()
        self.assertFalse(self.c.receive(self.event("thread/status/changed", status={"type": "active"}), request=request))
        self.assertEqual(self.c.snapshot.state, State.ROLLOVER_REQUESTED)
        self.assertEqual(self.sent, [{"id": request.request_id, "method": "thread/compact/start",
                                      "params": {"threadId": "thread-1"}}])
        self.c.receive({"id": request.request_id, "result": {}}, request=request)
        self.assertTrue(self.c.snapshot.request_accepted)
        self.assertEqual(self.c.snapshot.state, State.ROLLOVER_REQUESTED)
        self.bind(request)
        for event in self.completions()[:2]:
            self.c.receive(event, request=request)
        self.assertEqual(self.c.snapshot.state, State.ROLLOVER_REQUESTED)
        self.c.receive(self.completions()[2], request=request)
        self.assertEqual(self.c.snapshot.state, State.ROLLOVER_OBSERVED)
        before = self.c.snapshot
        count = len(list(self.c.store.journal.glob("*.json")))
        for event in self.completions():
            self.assertFalse(self.c.receive(event, request=request))
        self.assertEqual(self.c.snapshot, before)
        self.assertEqual(len(list(self.c.store.journal.glob("*.json"))), count)
        self.assertEqual(len(self.sent), 1)
        disk = b"".join(p.read_bytes() for p in self.c.store.journal.glob("*.json"))
        self.assertNotIn(b"SECRET_BODY_MUST_NOT_BE_STORED", disk)

    def test_timeout_restart_late_completion_reconciles_without_retry(self):
        request = self.requested()
        self.bind(request)
        self.c.receive(self.completions()[0], request=request)
        self.now = 13
        self.assertTrue(self.c.poll_timeout())
        self.assertEqual(self.c.snapshot.state, State.AMBIGUOUS)
        self.restart()
        self.assertEqual(self.c.snapshot.state, State.AMBIGUOUS)
        with self.assertRaises(TransitionError):
            self.c.require_work()
        with self.assertRaises(TransitionError):
            self.c.request_compact(None, self.current)
        with self.assertRaises(TransitionError):
            self.c.step("claim_continuation")
        for event in self.completions():
            self.c.receive(event, request=request)
        self.assertEqual(self.c.snapshot.state, State.ROLLOVER_OBSERVED)
        self.assertEqual(len(self.sent), 1)

    def test_wrong_generation_identity_and_failed_events_cannot_complete(self):
        request = self.requested()
        self.bind(request)
        for wrong in (replace(request, rollover_generation=0), replace(request, request_id="wrong")):
            for event in self.completions():
                self.assertFalse(self.c.receive(event, request=wrong))
        bad = self.event("item/completed", turnId="compact-turn", item={"id": "wrong", "type": "contextCompaction"})
        self.c.receive(bad, request=request)
        self.c.receive(self.event("hook/completed", turnId="compact-turn", run={"eventName": "postCompact", "status": "failed"}), request=request)
        self.c.receive(self.event("turn/completed", turn={"id": "compact-turn", "status": "failed"}), request=request)
        self.assertEqual(self.c.snapshot.state, State.AMBIGUOUS)
        self.assertEqual(self.c.snapshot.completions, ())
        for event in self.completions():
            self.c.receive(event, request=request)
        self.assertEqual(self.c.snapshot.state, State.ROLLOVER_OBSERVED)

    def test_restart_without_mapping_does_not_infer_from_new_events(self):
        request = self.requested()
        self.restart()
        self.bind(request)
        for event in self.completions():
            self.c.receive(event, request=request)
        self.assertEqual(self.c.snapshot.state, State.AMBIGUOUS)
        self.assertIsNone(self.c.snapshot.binding)

    def test_revision_and_authority_mismatch_prevent_dispatch(self):
        lease = self.authorized()
        original = self.current()
        # First validation succeeds; known intent mutation during journal commit is caught.
        reads = iter((original, replace(original, intent_revision=1)))
        with self.assertRaises(TransitionError):
            self.c.request_compact(lease, lambda: next(reads))
        self.assertEqual(self.c.snapshot.state, State.WORKING)
        self.assertTrue(self.c.snapshot.invalidated)
        self.assertIsNone(self.c.snapshot.lease)
        self.assertEqual(self.sent, [])
        self.restart()
        self.assertIsNone(self.c.snapshot.request)

    def test_initial_execution_mismatch_prevents_dispatch(self):
        lease = self.authorized()
        current = replace(self.current(), execution_revision=1,
                          workspace=replace(self.workspace, mutation_epoch=1, workspace_stamp="changed"))
        with self.assertRaises(TransitionError):
            self.c.request_compact(lease, lambda: current)
        self.assertEqual(self.sent, [])
        self.assertIsNone(self.c.snapshot.lease)

    def test_authority_mismatch_prevents_dispatch(self):
        for changes in ({"lease_id": "wrong"}, {"rollover_generation": 99},
                        {"checkpoint_id": "wrong"}, {"thread_idle": False}):
            # Each invalidation consumes authority; use a distinct isolated thread.
            self.c.close()
            thread_id = "thread-" + str(len(list((Path(self.tmp.name) / "yohaku/sessions").iterdir()))) + "-case"
            self.c = CompanionController(thread_id, self.send, create=True, clock=lambda: self.now)
            lease = self.authorized()
            current = replace(self.current(), **changes)
            with self.assertRaises(TransitionError):
                self.c.request_compact(lease, lambda: current)
            self.assertIsNone(self.c.snapshot.lease)
        self.assertEqual(self.sent, [])

    def test_post_request_lease_expiry_is_ambiguous_even_before_timeout(self):
        lease = self.authorized()
        self.c.request_compact(lease, self.current, completion_timeout=100)
        self.now = 21
        self.assertTrue(self.c.poll_timeout())
        self.assertEqual(self.c.snapshot.state, State.AMBIGUOUS)

    def test_journal_failure_blocks_dispatch_and_corruption_blocks_restart(self):
        lease = self.authorized()
        with patch.object(self.c.store, "append", side_effect=PersistenceError("disk failure")):
            with self.assertRaises(PersistenceError):
                self.c.request_compact(lease, self.current)
        self.assertEqual(self.sent, [])
        with self.assertRaises(PersistenceError):
            self.c.require_work()
        latest = sorted(self.c.store.journal.glob("*.json"))[-1]
        latest.write_text('{}')
        self.c.close()
        with self.assertRaises(PersistenceError):
            CompanionController("thread-1", self.sent.append)

    def test_transport_error_is_durably_ambiguous(self):
        lease = self.authorized()
        self.c._backend._send = lambda message: (_ for _ in ()).throw(OSError("secret transport body"))
        with self.assertRaises(TransitionError):
            self.c.request_compact(lease, self.current)
        self.restart()
        self.assertEqual(self.c.snapshot.state, State.AMBIGUOUS)
        disk = b"".join(p.read_bytes() for p in self.c.store.journal.glob("*.json"))
        self.assertNotIn(b"secret transport body", disk)

    def test_local_writer_lock_and_path_validation(self):
        with self.assertRaises(BlockingIOError):
            SessionStore("thread-1")
        with self.assertRaises(PersistenceError):
            SessionStore("../escape", create=True)
        self.assertEqual(stat.S_IMODE(self.c.store.path.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(next(self.c.store.journal.glob("*.json")).stat().st_mode), 0o600)

    def test_json_line_sender_writes_documented_rpc(self):
        stream = io.StringIO()
        JsonLineSender(stream)({"id": "request", "method": "thread/compact/start", "params": {"threadId": "thread-1"}})
        self.assertEqual(json.loads(stream.getvalue())["method"], "thread/compact/start")
        self.assertTrue(stream.getvalue().endswith("\n"))


if __name__ == "__main__":
    unittest.main()
