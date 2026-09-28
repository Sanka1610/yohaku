"""Local synthetic C-CLI boundary checks. No Claude process or provider calls."""

from dataclasses import replace
import os
import tempfile
import unittest
from unittest.mock import patch

from yohaku.claude import (ClaudeCLIProfile, ClaudeHookObservation, ClaudeManualCompletion,
                           ClaudeManualCompletionPolicy, classify_hook_result)
from yohaku.claude_adapter import ClaudeCLIAdapter
from yohaku.controller import Controller, TransitionError
from yohaku.model import ContinuationBinding, State, WorkspaceRevision
from yohaku.persistence import PersistenceError, SessionStore
from yohaku.recovery import CurrentContext


class ClaudeAdapterTests(unittest.TestCase):
    def adapter(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=tmp.name)
        env.start()
        self.addCleanup(env.stop)
        store = SessionStore("session", create=True)
        self.addCleanup(store.close)
        startup = ClaudeHookObservation("attachment", "", 0, 1, "session",
            "SessionStart", "startup", "local-fixture/startup", True)
        a = ClaudeCLIAdapter(store, profile=ClaudeCLIProfile(), startup=startup,
                             exclusive_fresh_session=True)
        current = CurrentContext("task", 0, 1, WorkspaceRevision(1, "before", ("fixture.json",)))
        a.checkpoint(boundary_id="boundary", observe=lambda: current,
                     evidence_ref="local-fixture/boundary", foreground_idle=True)
        return a, current

    def proof(self, binding, reverse=False):
        kinds = [("PreCompact", "manual"), ("PostCompact", "manual"), ("SessionStart", "compact")]
        if reverse:
            kinds[1:] = reversed(kinds[1:])
        hooks = tuple(ClaudeHookObservation(binding.attachment_id, binding.request.request_id,
            1, binding.request_seq + i, binding.session_id, event, trigger,
            f"local-fixture/hook-{i}", True) for i, (event, trigger) in enumerate(kinds, 1))
        return ClaudeManualCompletion(binding, "local-fixture/window", hooks,
                                      binding.request_seq + 4, True, True, 1)

    def run_compact(self, a, current, transform=lambda p: p):
        def dispatch(command, binding):
            self.assertEqual(command, "/compact")
            self.assertTrue(any('compact_requested' in p.read_text()
                                for p in a.records.glob("*.json")))
            self.assertEqual(a.core.snapshot.state, State.ROLLOVER_REQUESTED)
            return transform(self.proof(binding))
        return a.compact(observe=lambda: current, dispatch=dispatch, now=lambda: 1, request_seq=10)

    def test_closed_manual_proof_completes_both_post_orders_without_resume(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                a, current = self.adapter()
                s = self.run_compact(a, current, lambda p: self.proof(p.binding, reverse))
                self.assertEqual(s.state, State.ROLLOVER_OBSERVED)
                self.assertIsNone(s.receipt_evidence)
                self.assertIsNone(s.handoff)
                with self.assertRaises(TransitionError):
                    a.require_work()
                permit = a.core.claim_continuation()
                with self.assertRaises(TransitionError):
                    a.core.offer_handoff(ContinuationBinding(permit, "session", "turn"),
                                         recovered_context="fixture")
                with self.assertRaises(TransitionError):
                    self.run_compact(a, current)

    def test_missing_stale_duplicate_and_faulted_evidence_stops_without_retry(self):
        transforms = [
            lambda p: None,
            lambda p: replace(p, hooks=()),
            lambda p: replace(p, hooks=p.hooks[:-1]),
            lambda p: replace(p, hooks=p.hooks + (p.hooks[-1],)),
            lambda p: replace(p, hooks=(p.hooks[0], p.hooks[1], p.hooks[1])),
            lambda p: replace(p, hooks=tuple(reversed(p.hooks))),
            lambda p: replace(p, collection_closed=False),
            lambda p: replace(p, transport_ok=False),
            lambda p: replace(p, closed_seq=p.hooks[-1].seq),
            lambda p: replace(p, manual_requests=2),
            lambda p: replace(p, manual_requests=True),
            lambda p: replace(p, evidence_ref=""),
            lambda p: replace(p, binding=replace(p.binding, attachment_id="old")),
        ]
        for field, value in (("attachment_id", "old"), ("request_id", "old"),
                             ("generation", 0), ("generation", True), ("seq", 10),
                             ("seq", True), ("session_id", "other"), ("trigger", "auto"),
                             ("evidence_ref", ""), ("hook_ok", False)):
            transforms.append(lambda p, k=field, v=value:
                replace(p, hooks=(replace(p.hooks[0], **{k: v}),) + p.hooks[1:]))
        for index, transform in enumerate(transforms):
            with self.subTest(index=index):
                a, current = self.adapter()
                with self.assertRaises(TransitionError):
                    self.run_compact(a, current, transform)
                self.assertEqual(a.core.snapshot.state, State.AMBIGUOUS)
                self.assertIsNone(a.core.snapshot.lease)
                for op in (a.require_work, a.core.claim_continuation,
                           lambda: self.run_compact(a, current)):
                    with self.assertRaises(TransitionError):
                        op()

    def test_transport_timeout_and_request_write_failure_do_not_retry(self):
        for error in (TimeoutError, OSError):
            a, current = self.adapter()
            calls = []
            def dispatch(*args):
                calls.append(args)
                raise TimeoutError()
            with patch.object(a, "_record", side_effect=OSError()) if error is OSError else patch.object(a, "attempted", False):
                with self.assertRaises(error):
                    a.compact(observe=lambda: current, dispatch=dispatch, now=lambda: 1, request_seq=10)
            self.assertEqual(len(calls), int(error is TimeoutError))
            self.assertEqual(a.core.snapshot.state, State.AMBIGUOUS)
            with self.assertRaises(TransitionError):
                self.run_compact(a, current)

    def test_current_workspace_change_prevents_dispatch(self):
        a, current = self.adapter()
        changed = replace(current, workspace=WorkspaceRevision(2, "changed", ("fixture.json",)))
        calls = []
        with self.assertRaises(TransitionError):
            a.compact(observe=lambda: changed, dispatch=lambda *args: calls.append(args),
                      now=lambda: 1, request_seq=10)
        self.assertEqual(calls, [])

    def test_policy_rejects_other_profile_and_missing_identity(self):
        a, current = self.adapter()
        self.run_compact(a, current)
        b = a.core.snapshot.binding
        policy = ClaudeManualCompletionPolicy()
        for profile in (replace(b.profile, version="2.1.283"), replace(b.profile, os="Windows"),
                        replace(b.profile, surface="Agent SDK"), replace(b.profile, hooks="HTTP"),
                        replace(b.profile, output_format="json")):
            self.assertFalse(policy.valid_binding(replace(b, profile=profile)))
        for change in ({"exclusive_fresh_session": False}, {"startup_seq": 10},
                       {"request_seq": True}, {"session_id": "UNKNOWN"},
                       {"request": replace(b.request, rollover_generation=2)}):
            self.assertFalse(policy.valid_binding(replace(b, **change)))

    def test_claude_proof_cannot_restart_or_serialize_as_codex(self):
        a, current = self.adapter()
        self.run_compact(a, current)
        with self.assertRaises(TransitionError):
            Controller.restart(a.core.snapshot)
        with self.assertRaises(PersistenceError):
            a.store.append(a.core.snapshot, {}, "foreign_proof")
        self.assertEqual(list(a.store.journal.glob("*.json")), [])

    def test_deny_classification_requires_owned_response_not_cli_display(self):
        deny = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"}}
        base = dict(event="PreToolUse", intentional_deny=True, exit_code=0, output=deny)
        self.assertEqual(classify_hook_result(**base), "NORMAL_DENY")
        self.assertEqual(classify_hook_result(**{**base, "exit_code": 2, "output": None}), "NORMAL_DENY")
        self.assertEqual(classify_hook_result(**{**base, "exit_code": None}), "UNKNOWN")
        self.assertEqual(classify_hook_result(**{**base, "intentional_deny": None}), "UNKNOWN")
        for change in ({"timed_out": True}, {"process_failed": True}, {"exit_code": 1},
                       {"output": "hook error"}, {"output": {}}, {"output": None}):
            self.assertEqual(classify_hook_result(**{**base, **change}), "HOOK_FAILURE")


if __name__ == "__main__":
    unittest.main()
