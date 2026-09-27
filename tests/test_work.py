"""Measured work admission through real owner/Hook, with synthetic Runtime events."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from yohaku.companion import CompanionController
from yohaku.controller import TransitionError
from yohaku.model import State
from yohaku.runtime import HookBridge, RuntimeHost
from yohaku.work import WorkKey


class WorkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=self.tmp.name)
        env.start(); self.addCleanup(env.stop)
        self.sent = []
        self.c = CompanionController("thread", self.sent.append, create=True)
        self.addCleanup(self.c.close)
        self.host = RuntimeHost(self.c, work_cwd=self.tmp.name)
        self.work = self.host.work
        self.host.receive(self.event("turn/started", turn={"id": "turn"}))

    def event(self, method, **params):
        return {"method": method, "params": {"threadId": "thread", **params}}

    def payload(self, event="PreToolUse", ident="tool", name="Bash", **changes):
        return {"hook_event_name": event, "session_id": "thread", "turn_id": "turn",
                "tool_use_id": ident, "tool_name": name, "cwd": self.tmp.name,
                "tool_input": {"command": "PRIVATE_COMMAND"}, **changes}

    def deny(self, value):
        self.assertEqual(value["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_arm_first_denies_both_measured_tools(self):
        self.assertEqual(self.work.quiesce("boundary"), State.WORKSPACE_SNAPSHOT)
        for tool in ("Bash", "apply_patch"):
            self.deny(self.host.deliver(self.payload(ident=tool, name=tool)))
        self.assertEqual(self.work.active, ())
        self.assertTrue(self.c.snapshot.barrier_requested)

    def test_registered_work_defers_releases_and_preserves_active(self):
        self.assertEqual(self.host.deliver(self.payload()), {})
        self.assertEqual(self.work.quiesce("boundary"), State.DEFERRED)
        self.assertEqual(self.c.snapshot.state, State.WORKING)
        self.assertFalse(self.c.snapshot.barrier_requested)
        self.assertEqual(len(self.work.active), 1)
        states = [json.loads(p.read_text())["payload"]["snapshot"]["state"]
                  for p in sorted(self.c.store.journal.glob("*.json"))]
        self.assertEqual(states[-4:], ["BARRIER_ARMING", "QUIESCENCE_CHECK", "DEFERRED", "WORKING"])
        self.assertEqual(self.sent, [])

    def test_host_compact_guard_cannot_bypass_unincorporated_work(self):
        self.host.deliver(self.payload())
        self.host.deliver(self.payload("PostToolUse"))
        with self.assertRaises(TransitionError):
            self.host.request_compact(None, lambda: self.fail("must not observe or send"))
        self.assertEqual(self.sent, [])

    def test_post_and_turn_completion_do_not_incorporate_results(self):
        self.host.deliver(self.payload())
        self.host.deliver(self.payload("PostToolUse"))
        self.host.receive(self.event("turn/completed", turn={"id": "turn", "status": "completed"}))
        self.assertEqual(self.work.active, ())
        self.assertEqual(self.work.quiesce("pending"), State.DEFERRED)
        key = self.work.pending_results[0]
        with self.assertRaises(TransitionError):
            self.work.incorporate(key, execution_complete=False, evidence_ref="yielded-session")
        self.c.step("update_revisions", execution_changed=True)
        self.assertTrue(self.work.incorporate(key, execution_complete=True, evidence_ref="terminal-and-applied"))
        self.assertFalse(self.work.incorporate(key, execution_complete=True, evidence_ref="duplicate"))
        self.assertEqual(self.work.quiesce("new-boundary"), State.WORKSPACE_SNAPSHOT)

    def test_missing_post_cannot_be_cleared_by_turn_or_ack(self):
        self.host.deliver(self.payload())
        self.host.receive(self.event("turn/completed", turn={"id": "turn", "status": "completed"}))
        with self.assertRaises(TransitionError):
            self.work.incorporate(self.work.active[0], execution_complete=True, evidence_ref="turn-only")
        self.assertEqual(self.work.quiesce("boundary"), State.DEFERRED)

    def test_cancel_and_revision_invalidation_release_live_gate(self):
        self.work.quiesce("cancel")
        self.work.cancel()
        self.assertFalse(self.c.snapshot.barrier_requested)
        self.work.quiesce("revision")
        self.c.step("update_revisions", intent_changed=True)
        self.assertFalse(self.c.snapshot.barrier_requested)
        self.assertEqual(self.host.deliver(self.payload()), {})
        self.assertEqual(len(self.work.active), 1)

    def test_duplicate_boundary_never_rearms_consumed_transition(self):
        self.work.quiesce("boundary")
        first = self.c.snapshot.transition_id
        self.work.quiesce("boundary")
        self.assertEqual(self.c.snapshot.transition_id, first)
        self.work.cancel()
        self.assertEqual(self.work.quiesce("boundary"), State.WORKING)
        self.assertFalse(self.c.snapshot.barrier_requested)

    def test_identity_and_unmeasured_tools_cannot_grant_admission(self):
        for change in ({"session_id": "other"}, {"turn_id": "other"}, {"cwd": "/elsewhere"},
                       {"tool_name": "mcp"}, {"tool_use_id": None}, {"tool_name": []}):
            self.deny(self.host.deliver(self.payload(**change)))
        self.assertFalse(self.work.active)
        self.assertEqual(self.host.deliver(self.payload()), {})
        self.host.deliver(self.payload("PostToolUse", session_id="other"))
        self.assertEqual(len(self.work.active), 1)
        with self.assertRaises(TransitionError):
            self.work.incorporate(WorkKey("other", "tool", "Bash"),
                                  execution_complete=True, evidence_ref="wrong")

    def test_replayed_pre_never_grants_another_permit(self):
        self.host.deliver(self.payload())
        self.deny(self.host.deliver(self.payload()))
        self.host.deliver(self.payload("PostToolUse"))
        self.host.deliver(self.payload("PostToolUse"))
        self.work.incorporate(self.work.pending_results[0], execution_complete=True, evidence_ref="applied")
        self.host.deliver(self.payload("PostToolUse"))
        self.assertFalse(self.work.pending_results)
        self.host.receive(self.event("turn/completed", turn={"id": "turn"}))
        self.host.receive(self.event("turn/started", turn={"id": "turn"}))
        self.deny(self.host.deliver(self.payload()))

    def test_unknown_post_and_observed_hook_failure_prevent_quiescence(self):
        self.host.deliver(self.payload("PostToolUse"))
        self.assertTrue(self.work.observation_uncertain)
        self.assertEqual(self.work.quiesce("unknown-post"), State.DEFERRED)
        self.deny(self.host.deliver(self.payload()))

    def test_hook_failure_and_eof_invalidate_without_claiming_protection(self):
        self.work.quiesce("boundary")
        self.host.receive(self.event("hook/completed", turnId="turn",
            run={"eventName": "preToolUse", "status": "failed"}))
        self.assertTrue(self.work.observation_uncertain)
        self.assertFalse(self.c.snapshot.barrier_requested)
        self.host.receive(None)
        self.assertEqual(self.work.quiesce("after-eof"), State.DEFERRED)

    def test_expired_hook_payload_never_registers_or_establishes_quiescence(self):
        bridge = HookBridge(); self.addCleanup(bridge.close)
        import threading
        response, ready = {}, threading.Event()
        bridge.pending.put((self.payload(), response, ready, 0))
        bridge.poll(self.host)
        self.assertTrue(ready.is_set())
        self.assertTrue(self.work.observation_uncertain)
        self.assertFalse(self.work.active)

    def test_real_work_hook_process_uses_owner_barrier(self):
        bridge = HookBridge(); self.addCleanup(bridge.close)
        self.host.bridge = bridge
        self.work.quiesce("boundary")
        process = subprocess.Popen([sys.executable, "-m", "yohaku.hook", "--socket", bridge.path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        process.stdin.write(json.dumps(self.payload())); process.stdin.close()
        deadline = time.monotonic() + 4
        while process.poll() is None and time.monotonic() < deadline:
            self.host.poll(.01)
        process.wait(timeout=1)
        output = json.loads(process.stdout.read()); process.stdout.close(); process.stderr.close()
        self.assertEqual(process.returncode, 0)
        self.deny(output)
        self.assertNotIn("PRIVATE_COMMAND", ''.join(p.read_text() for p in self.c.store.journal.glob("*.json")))


if __name__ == "__main__":
    unittest.main()
