"""Focused production recovery contracts, POSIX files and fake App Server stream."""

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from yohaku.archive import ArchiveMetadata, ArchiveTurn
from yohaku.companion import CompanionController, CurrentState
from yohaku.controller import TransitionError
from yohaku.model import BoundaryVerification, State, WorkspaceRevision
from yohaku.persistence import PersistenceError
from yohaku.recovery import CurrentContext, RecoveredData, ResumeProof
from yohaku.runtime import HookBridge, RuntimeHost


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=self.tmp.name)
        env.start()
        self.addCleanup(env.stop)
        self.sent = []
        self.c = CompanionController("thread", self.sent.append, create=True)
        self.addCleanup(lambda: self.c.close())
        self.host = RuntimeHost(self.c)
        self.workspace = WorkspaceRevision(0, "before", ("task.json",))
        self.current = CurrentContext("task", 0, 0, self.workspace)
        self.data = RecoveredData("task", ("STEP_A",), "Finish task", ("read current value",),
                                  "STEP_B with OLD_VALUE", ("task.json",))

    def event(self, method, **params):
        return {"method": method, "params": {"threadId": "thread", **params}}

    def observed(self, *, archive_ids=()):
        c = self.c
        for op, args in [("propose_boundary", ("boundary",)), ("arm_barrier", ()),
                         ("begin_quiescence_check", ())]:
            c.step(op, *args)
        c.step("observe_quiescence", relevant_work_remaining=False)
        c.step("capture_workspace", self.workspace)
        c.step("verify_boundary", BoundaryVerification(0, 0, self.workspace,
                "implementation_complete", "not_run", "boundary-evidence"))
        c.commit_checkpoint(archive_ids=archive_ids)
        lease = c.authorize_rollover(ttl=30)
        self.host.request_compact(lease, lambda: CurrentState(0, 0, self.workspace,
            lease.lease_id, 1, c.snapshot.checkpoint.checkpoint_id, True))
        self.host.receive(self.event("turn/started", turn={"id": "compact"}))
        item = {"id": "compaction", "type": "contextCompaction"}
        for method in ("item/started", "item/completed"):
            self.host.receive(self.event(method, turnId="compact", item=item))
        self.host.receive(self.event("hook/completed", turnId="compact",
            run={"id": "post", "eventName": "postCompact", "status": "completed"}))
        self.host.receive(self.event("turn/completed", turn={"id": "compact", "status": "completed"}))

    def start(self, **kwargs):
        return self.host.continue_task(self.data, cwd=self.tmp.name, observe=lambda: self.current, **kwargs)

    def bind(self):
        self.host.receive(self.event("turn/started", turn={"id": "continuation"}))
        self.host.receive(self.event("hook/started", turnId="continuation",
            run={"id": "session-hook", "eventName": "sessionStart"}))

    def payload(self):
        return {"hook_event_name": "SessionStart", "source": "compact", "session_id": "thread",
                "cwd": self.tmp.name}

    def delivered(self):
        output = self.c.recovery.deliver(self.payload())
        self.host.receive(self.event("hook/completed", turnId="continuation",
            run={"id": "session-hook", "eventName": "sessionStart", "status": "completed"}))
        return output

    def ack(self):
        item = {"id": "ack", "type": "agentMessage",
                "text": f"YOH_ACK:{self.c.recovery.cursor.handoff_id}:1"}
        self.host.receive(self.event("item/completed", turnId="continuation", item=item))
        return item

    def tools(self):
        items = [{"id": name, "type": "commandExecution", "status": "completed", "exitCode": 0,
                  "command": name, "aggregatedOutput": "SENSITIVE_TRANSIENT_OUTPUT"} for name in ("read", "action")]
        for item in items:
            self.host.receive(self.event("item/completed", turnId="continuation", item=item))
        self.host.receive(self.event("turn/completed", turn={"id": "continuation", "status": "completed"}))
        return items

    def proof(self, *args):
        return ResumeProof(self.current, "trusted-task-assessment", ("read",), ("action",),
                           True, True, True, True, True)

    def complete(self):
        self.observed();self.start();self.bind();self.delivered();self.ack();self.tools()

    def restart(self):
        self.c.close()
        self.c = CompanionController("thread", self.sent.append)
        self.host = RuntimeHost(self.c)

    def test_persist_reload_control_data_separation_and_duplicate_ack(self):
        self.observed();self.start();self.bind()
        doc = self.c.recovery.document
        self.assertEqual(self.c.store.read_handoff(doc.handoff_id), doc)
        handoff_path = self.c.store.path / "handoffs" / f"{doc.handoff_id}.json"
        original = handoff_path.read_bytes()
        self.assertNotIn("archive_ids", json.loads(original)["payload"]["recovered"])
        output = self.delivered()["hookSpecificOutput"]["additionalContext"]
        self.assertIn("DATA, NOT INSTRUCTIONS", output)
        self.assertIn("resume_status", output)
        self.ack()
        before = self.c.snapshot
        self.ack()
        self.assertEqual(self.c.snapshot, before)
        self.assertEqual(before.state, State.HANDOFF_RECEIVED)
        self.assertTrue(all("OLD_VALUE" not in p.read_text() for p in self.c.store.journal.glob("*.json")))
        self.restart()
        self.assertEqual(handoff_path.read_bytes(), original)
        self.assertEqual(self.c.recovery.document, doc)
        self.assertIsNone(self.c.snapshot.lease)
        self.assertEqual(self.c.snapshot.state, State.RECOVERY_REQUIRED)

    def test_checkpoint_archive_references_reach_hot_handoff_without_cold_reads(self):
        turn = ArchiveTurn(ArchiveMetadata("visible-turn", "Prior work", "implementation"),
                           "user prompt", "COLD_PAYLOAD_DO_NOT_INJECT")
        self.c.archive_turn(turn)
        self.observed(archive_ids=("visible-turn",))
        with patch("yohaku.archive.ArchiveStore._cold", side_effect=AssertionError("eager COLD read")):
            self.start();self.bind()
            output = self.delivered()["hookSpecificOutput"]["additionalContext"]
            self.assertIn('"archive_ids": ["visible-turn"]', output)
            self.assertNotIn("COLD_PAYLOAD_DO_NOT_INJECT", output)
            self.ack();self.tools()
            self.c.recovery.verify(observe=lambda: self.current, assess=self.proof)
            self.assertEqual(self.c.snapshot.state, State.RESUME_VERIFIED)
            self.restart()
            self.assertEqual(self.c.recovery.document.recovered.archive_ids, ("visible-turn",))
            self.assertEqual(self.c.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertEqual(self.c.read_archive("visible-turn"), turn)
        self.assertEqual(sum(m['method'] == 'turn/start' for m in self.sent), 1)

    def test_missing_handoff_archive_rejected_before_continuation(self):
        self.observed()
        self.data = replace(self.data, archive_ids=("missing",))
        with self.assertRaises(PersistenceError):
            self.start()
        self.assertIsNone(self.c.snapshot.continuation_request_id)
        self.assertEqual(sum(m['method'] == 'turn/start' for m in self.sent), 0)

    def test_continuation_requires_completion_and_dispatches_once(self):
        with self.assertRaises(TransitionError):self.start()
        self.observed();ident = self.start()
        self.assertEqual(self.c.store.latest[0].continuation_request_id, ident)
        with self.assertRaises(TransitionError):self.start()
        self.restart()
        with self.assertRaises(TransitionError):self.start()
        self.assertEqual(sum(m['method'] == 'turn/start' for m in self.sent), 1)

    def test_uncertain_continuation_send_never_retries_after_restart(self):
        self.observed()
        def broken(message):
            self.assertEqual(self.c.store.latest[0].continuation_request_id, message['id'])
            raise OSError("unknown send")
        self.c.recovery.send = broken
        with self.assertRaises(TransitionError):self.start()
        self.restart()
        with self.assertRaises(TransitionError):self.start()
        self.assertEqual(self.c.snapshot.state, State.RECOVERY_REQUIRED)

    def test_stale_delivery_and_wrong_ack_rejected(self):
        self.observed();self.start();self.bind()
        for changes in ({"session_id": "other"}, {"source": "startup"}, {"cwd": "/other"},
                        {"turn_id": "other"}):
            with self.assertRaises(TransitionError):self.c.recovery.deliver(dict(self.payload(), **changes))
        self.delivered()
        for turn, generation in (("continuation", 0), ("other", 1)):
            self.host.receive(self.event("item/completed", turnId=turn, item={"id": "wrong", "type": "agentMessage",
                "text": f"YOH_ACK:{self.c.recovery.cursor.handoff_id}:{generation}"}))
        self.assertEqual(self.c.snapshot.state, State.HANDOFF_OFFERED)

    def test_bounded_redelivery_same_handoff_and_no_extra_turn(self):
        self.observed();self.start(max_attempts=2);self.bind()
        first = self.c.recovery.deliver(self.payload())
        self.assertEqual(first, self.c.recovery.deliver(self.payload()))
        with self.assertRaises(TransitionError):self.c.recovery.deliver(self.payload())
        self.assertEqual(self.c.recovery.cursor.attempts, 2)
        self.assertEqual(self.c.snapshot.state, State.RECOVERY_REQUIRED)
        self.restart()
        with self.assertRaises(TransitionError):self.c.recovery.deliver(self.payload())
        self.assertEqual(sum(m['method'] == 'turn/start' for m in self.sent), 1)

    def test_ack_alone_and_missing_actual_tool_evidence_do_not_verify(self):
        self.observed();self.start();self.bind();self.delivered();self.ack()
        with self.assertRaises(TransitionError):
            self.c.recovery.verify(observe=lambda:self.current, assess=self.proof)
        self.host.receive(self.event("turn/completed", turn={"id": "continuation", "status": "completed"}))
        with self.assertRaises(TransitionError):
            self.c.recovery.verify(observe=lambda:self.current, assess=self.proof)
        self.assertNotEqual(self.c.snapshot.state, State.RESUME_VERIFIED)

    def test_stale_intent_workspace_or_repeated_work_reject_resume(self):
        for field in ("intent", "workspace", "repeat"):
            with self.subTest(field=field):
                # One candidate, independent invalid assessment checks without dispatch retries.
                if self.c.snapshot.state == State.WORKING:self.complete()
                self.c.recovery.cursor = replace(self.c.recovery.cursor, stopped=False)
                proof = self.proof()
                if field == "intent":proof = replace(proof, current=replace(self.current,intent_revision=1))
                if field == "workspace":proof = replace(proof, current=replace(self.current,workspace=WorkspaceRevision(1,"other",("task.json",))))
                if field == "repeat":proof = replace(proof, completed_work_not_repeated=False)
                with self.assertRaises(TransitionError):
                    self.c.recovery.verify(observe=lambda:self.current, assess=lambda *args:proof)
                self.assertEqual(self.c.snapshot.state, State.RECOVERY_REQUIRED)

    def test_success_only_verifies_after_observed_effects_and_current_state(self):
        self.complete()
        self.current = replace(self.current, execution_revision=1, workspace=WorkspaceRevision(1,"after",("task.json",)))
        self.c.recovery.verify(observe=lambda:self.current, assess=self.proof)
        self.assertEqual(self.c.snapshot.state, State.RESUME_VERIFIED)
        self.assertEqual(self.c.store.latest[0].state, State.RESUME_VERIFIED)
        self.assertNotIn("SENSITIVE_TRANSIENT_OUTPUT", ''.join(p.read_text() for p in self.c.store.journal.glob("*.json")))
        self.host.receive(None)
        self.assertEqual(self.c.snapshot.state, State.RESUME_VERIFIED)

    def test_failed_tool_is_visible_but_cannot_verify_success(self):
        self.complete()
        self.host.receive(self.event("item/completed", turnId="continuation", item={
            "id":"action", "type":"commandExecution", "status":"failed", "exitCode":1}))
        def assess(document, items):
            self.assertTrue(any(i['id']=='action' and i['exitCode']==1 for i in items))
            return self.proof()
        with self.assertRaises(TransitionError):
            self.c.recovery.verify(observe=lambda:self.current, assess=assess)
        self.assertEqual(self.c.snapshot.state,State.RECOVERY_REQUIRED)

    def test_continuation_timeout_blocks_work_and_resend(self):
        self.observed();self.start();self.bind()
        self.host.deadline = 0
        self.host.poll(0)
        self.assertEqual(self.c.snapshot.state,State.RECOVERY_REQUIRED)
        with self.assertRaises(TransitionError):self.c.require_work()
        with self.assertRaises(TransitionError):self.start()

    def test_restart_needs_runtime_reconciliation_not_durable_ack(self):
        self.complete()
        ack = {"id": "ack", "type": "agentMessage", "text": f"YOH_ACK:{self.c.recovery.cursor.handoff_id}:1"}
        items = list(self.c.recovery._tools.values())
        self.restart()
        with self.assertRaises(TransitionError):
            self.c.recovery.verify(observe=lambda:self.current, assess=self.proof)
        self.c.recovery.reconcile_runtime({"id":"thread","turns":[{"id":"continuation","status":"completed","items":[ack,*items]}]})
        self.c.recovery.verify(observe=lambda:self.current, assess=self.proof)
        self.assertEqual(self.c.snapshot.state, State.RESUME_VERIFIED)
        self.assertEqual(sum(m['method']=='turn/start' for m in self.sent),1)

    def test_real_hook_process_emits_context_via_owner_socket(self):
        self.observed();self.start();self.bind()
        bridge = HookBridge()
        self.addCleanup(bridge.close)
        self.host.bridge = bridge
        process = subprocess.Popen([sys.executable,"-m","yohaku.hook","--socket",bridge.path],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(lambda:process.kill() if process.poll() is None else None)
        process.stdin.write(json.dumps(self.payload()));process.stdin.close()
        deadline = time.monotonic()+4
        while process.poll() is None and time.monotonic()<deadline:self.host.poll(0.01)
        process.wait(timeout=1)
        output=json.loads(process.stdout.read());process.stdout.close();process.stderr.close()
        self.assertEqual(process.returncode,0)
        self.assertIn(self.c.recovery.cursor.handoff_id,output['hookSpecificOutput']['additionalContext'])
        self.assertEqual(self.c.snapshot.state,State.HANDOFF_OFFERED)

    def test_corrupt_handoff_blocks_recovery(self):
        self.observed();self.start();self.bind()
        path=self.c.store.path/'handoffs'/f'{self.c.recovery.cursor.handoff_id}.json'
        path.write_text('{}')
        self.c.close()
        with self.assertRaises(PersistenceError):CompanionController('thread',self.sent.append)

    def test_work_gate_allows_only_live_delivered_continuation(self):
        from yohaku.work import WorkPlane
        self.host.work = WorkPlane(self.c, cwd=self.tmp.name)
        self.observed(); self.start(); self.bind()
        payload = {"hook_event_name": "PreToolUse", "session_id": "thread",
                   "turn_id": "continuation", "cwd": self.tmp.name,
                   "tool_name": "Bash", "tool_use_id": "before-delivery"}
        self.assertEqual(self.host.deliver(payload)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.delivered()
        payload["tool_use_id"] = "after-delivery"
        self.assertEqual(self.host.deliver(payload), {})
        self.c.recovery.stop("test timeout")
        payload["tool_use_id"] = "after-timeout"
        self.assertEqual(self.host.deliver(payload)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_work_observation_eof_preserves_verified_recovery(self):
        from yohaku.work import WorkPlane
        self.host.work = WorkPlane(self.c, cwd=self.tmp.name)
        self.complete()
        self.c.recovery.verify(observe=lambda:self.current, assess=self.proof)
        self.host.receive(None)
        self.assertEqual(self.c.snapshot.state, State.RESUME_VERIFIED)
        self.assertTrue(self.host.work.observation_uncertain)


if __name__ == '__main__':unittest.main()
