"""Contract-focused local Core checks; no runtime or durable filesystem claims."""

import unittest
from dataclasses import replace
from itertools import count

from yohaku.controller import Controller, TransitionError
from yohaku.model import (
    BoundaryVerification, Completion, CompletionBinding, CompletionKind, ContinuationBinding,
    ResumeVerification, State, WorkspaceRevision,
)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        ids = count()
        self.controller = Controller("thread-1", id_factory=lambda: f"id-{next(ids)}")
        self.workspace = WorkspaceRevision(0, "stamp-0", ("src/", "tests/"))

    def to_snapshot(self, boundary="boundary-1"):
        c = self.controller
        c.propose_boundary(boundary)
        c.arm_barrier()
        c.begin_quiescence_check()
        c.observe_quiescence(relevant_work_remaining=False)
        c.capture_workspace(self.workspace)

    def evidence(self, **changes):
        r = self.controller.snapshot.revisions
        return replace(BoundaryVerification(
            r.intent_revision, r.execution_revision, self.workspace,
            "verification_passed", "passed", "test-result", True), **changes)

    def to_authorized(self, boundary="boundary-1"):
        c = self.controller
        self.to_snapshot(boundary)
        c.verify_boundary(self.evidence())
        checkpoint = c.prepare_checkpoint()
        c.checkpoint_committed(checkpoint.checkpoint_id, commit_evidence="durable-commit")
        return c.authorize_rollover(now=10, ttl=5)

    def request(self, lease):
        c = self.controller
        return c.request_rollover(
            lease, now=11, intent_revision=c.snapshot.revisions.intent_revision,
            execution_revision=c.snapshot.revisions.execution_revision,
            workspace=self.workspace)

    def to_requested(self):
        lease = self.to_authorized()
        request = self.request(lease)
        binding = CompletionBinding(request, "compact-turn", "compact-item")
        self.controller.bind_completion(binding)
        return lease, request, binding

    def complete(self, binding):
        c = self.controller
        for kind in CompletionKind:
            c.observe_completion(Completion(binding, kind, f"observed:{kind}"))

    def resume_evidence(self, handoff):
        s = self.controller.snapshot
        return ResumeVerification(
            handoff.handoff_id, handoff.continuation_turn_id,
            s.revisions.intent_revision, s.revisions.execution_revision,
            s.workspace, "observed-current-state-and-next-work",
            True, True, True, True, True, True, True)

    def continuation_binding(self, turn="next-turn"):
        s = self.controller.snapshot
        return ContinuationBinding(s.continuation_request_id, s.thread_id, turn)

    def test_normal_transition_requires_completion_receipt_and_actual_resume(self):
        c = self.controller
        lease, request, binding = self.to_requested()
        c.accept_request(request)
        self.assertEqual(c.snapshot.state, State.ROLLOVER_REQUESTED)
        self.assertEqual(len({request.transition_id, request.boundary_id,
                              request.checkpoint_id, request.lease_id, request.request_id}), 5)
        for kind in list(CompletionKind)[:2]:
            c.observe_completion(Completion(binding, kind, f"observed:{kind}"))
        self.assertEqual(c.snapshot.state, State.ROLLOVER_REQUESTED)
        with self.assertRaises(TransitionError):
            c.claim_continuation()
        c.observe_completion(Completion(binding, CompletionKind.COMPACT_TURN, "turn-complete"))
        self.assertEqual(c.snapshot.state, State.ROLLOVER_OBSERVED)
        c.claim_continuation()
        with self.assertRaises(TransitionError):
            c.offer_handoff(replace(self.continuation_binding(), thread_id="wrong-thread"),
                            recovered_context="data")
        handoff = c.offer_handoff(self.continuation_binding(), recovered_context="Old next action")
        self.assertEqual(handoff.material_policy, "DATA, NOT INSTRUCTIONS")
        self.assertEqual(handoff.resume_status, "pending")
        c.receive_handoff(handoff, injection_evidence="SessionStart(compact)", receipt_evidence="ack")
        self.assertEqual(c.snapshot.state, State.HANDOFF_RECEIVED)
        with self.assertRaises(TransitionError):
            c.require_work()
        with self.assertRaises(TransitionError):
            c.verify_resume(replace(self.resume_evidence(handoff), same_task_continued=False))
        c.verify_resume(self.resume_evidence(handoff))
        self.assertEqual(c.snapshot.state, State.RESUME_VERIFIED)
        c.return_to_work()
        c.require_work()
        self.assertFalse(c.snapshot.barrier_requested)

    def test_lease_expiry_before_request_releases_barrier_and_revokes_forever(self):
        c = self.controller
        lease = self.to_authorized()
        self.assertTrue(c.expire_lease(now=15))
        self.assertEqual(c.snapshot.state, State.WORKING)
        self.assertTrue(c.snapshot.invalidated)
        self.assertIsNone(c.snapshot.lease)
        self.assertEqual(c.snapshot.revoked_lease_id, lease.lease_id)
        self.assertFalse(c.snapshot.barrier_requested)
        with self.assertRaises(TransitionError):
            self.request(lease)
        new_lease = self.to_authorized("boundary-2")
        self.assertGreater(new_lease.rollover_generation, lease.rollover_generation)
        with self.assertRaises(TransitionError):
            self.request(lease)

    def test_expiry_is_checked_at_dispatch(self):
        lease = self.to_authorized()
        with self.assertRaises(TransitionError):
            self.controller.request_rollover(lease, now=15, intent_revision=0,
                                              execution_revision=0, workspace=self.workspace)
        self.assertEqual(self.controller.snapshot.state, State.WORKING)

    def test_timeout_and_post_request_expiry_block_work_and_retry(self):
        for cause in ("timeout", "expiry", "transport-error", "intent-change"):
            with self.subTest(cause=cause):
                self.setUp()
                c = self.controller
                lease, _, binding = self.to_requested()
                if cause == "expiry":
                    c.expire_lease(now=15)
                elif cause == "transport-error":
                    c.fail("transport disconnected")
                elif cause == "intent-change":
                    c.update_revisions(intent_changed=True)
                else:
                    c.completion_unknown()
                self.assertEqual(c.snapshot.state, State.AMBIGUOUS)
                for action in (c.require_work, c.return_to_work, c.claim_continuation,
                               lambda: self.request(lease),
                               lambda: c.propose_boundary("another-boundary"),
                               lambda: c.authorize_rollover(now=20, ttl=5)):
                    with self.assertRaises(TransitionError):
                        action()
                self.complete(binding)
                self.assertEqual(c.snapshot.state, State.ROLLOVER_OBSERVED)

    def test_duplicates_do_not_start_second_continuation_or_change_revision(self):
        c = self.controller
        _, request, binding = self.to_requested()
        self.complete(binding)
        c.claim_continuation()
        handoff = c.offer_handoff(self.continuation_binding(), recovered_context="data")
        c.receive_handoff(handoff, injection_evidence="injection", receipt_evidence="ack")
        self.assertTrue(c.accept_request(request))
        before = c.snapshot
        self.assertFalse(c.accept_request(request))
        self.complete(binding)
        self.assertFalse(c.receive_handoff(handoff, injection_evidence="injection", receipt_evidence="ack"))
        self.assertEqual(before, c.snapshot)
        for action in (c.claim_continuation,
                       lambda: c.offer_handoff(self.continuation_binding("another-turn"), recovered_context="data")):
            with self.assertRaises(TransitionError):
                action()

    def test_unmatched_late_events_never_rebind_to_current_generation(self):
        c = self.controller
        _, request, binding = self.to_requested()
        c.completion_unknown()
        for wrong_request in (replace(request, rollover_generation=0),
                              replace(request, request_id="other-request"),
                              replace(request, thread_id="other-thread"),
                              replace(request, boundary_id="other-boundary")):
            wrong = replace(binding, request=wrong_request)
            self.assertFalse(c.observe_completion(Completion(wrong, CompletionKind.COMPACT_TURN, "event")))
        for wrong in (replace(binding, compact_turn_id="other-turn"),
                      replace(binding, compact_item_id="other-item")):
            self.assertFalse(c.observe_completion(Completion(wrong, CompletionKind.COMPACT_TURN, "event")))
        self.assertEqual(c.snapshot.completions, ())
        self.assertEqual(c.snapshot.state, State.AMBIGUOUS)
        self.complete(binding)
        self.assertEqual(c.snapshot.state, State.ROLLOVER_OBSERVED)

    def test_missing_mapping_does_not_infer_identity_from_completion(self):
        c = self.controller
        request = self.request(self.to_authorized())
        binding = CompletionBinding(request, "turn", "item")
        self.assertFalse(c.observe_completion(Completion(binding, CompletionKind.POST_COMPACT, "event")))
        self.assertEqual(c.snapshot.state, State.AMBIGUOUS)
        self.assertIsNone(c.snapshot.binding)

    def test_restart_keeps_checkpoint_and_generation_but_not_lease(self):
        lease = self.to_authorized()
        saved = self.controller.snapshot
        c = Controller.restart(saved)
        self.controller = c
        self.assertEqual(c.snapshot.checkpoint, saved.recoverable_checkpoint)
        self.assertEqual(c.snapshot.rollover_generation, lease.rollover_generation)
        self.assertIsNone(c.snapshot.lease)
        self.assertEqual(c.snapshot.state, State.RECOVERY_REQUIRED)
        with self.assertRaises(TransitionError):
            self.request(lease)
        c.update_revisions(intent_changed=True)
        self.assertEqual(c.snapshot.state, State.RECOVERY_REQUIRED)
        c.reconcile_restart(current_workspace=self.workspace, current_intent_revision=1,
                            current_execution_revision=0, evidence_ref="current-observation")
        new_lease = self.to_authorized("boundary-2")
        self.assertGreater(new_lease.rollover_generation, lease.rollover_generation)
        self.assertNotEqual(new_lease.lease_id, lease.lease_id)

    def test_restart_inflight_preserves_partial_completion_and_blocks_retry(self):
        c = self.controller
        _, _, binding = self.to_requested()
        c.observe_completion(Completion(binding, CompletionKind.POST_COMPACT, "post-compact"))
        self.controller = c = Controller.restart(c.snapshot)
        self.assertEqual(c.snapshot.state, State.AMBIGUOUS)
        self.assertIsNone(c.snapshot.lease)
        with self.assertRaises(TransitionError):
            c.reconcile_restart(current_workspace=self.workspace, current_intent_revision=0,
                                current_execution_revision=0, evidence_ref="current-state")
        self.complete(binding)
        c.claim_continuation()
        c = Controller.restart(c.snapshot)
        with self.assertRaises(TransitionError):
            c.claim_continuation()

    def test_revisions_are_separate_and_reverting_bytes_does_not_restore_authority(self):
        for domain in ("intent_changed", "execution_changed"):
            with self.subTest(domain=domain):
                self.setUp()
                c = self.controller
                lease = self.to_authorized()
                c.update_revisions(archive_changed=True)
                self.assertEqual(c.snapshot.lease, lease)
                self.assertEqual(c.snapshot.revisions.execution_revision, 0)
                c.update_revisions(**{domain: True})
                self.assertEqual(c.snapshot.state, State.WORKING)
                c.update_revisions(**{domain: True})
                with self.assertRaises(TransitionError):
                    self.request(lease)
        self.setUp()
        c = self.controller
        lease = self.to_authorized()
        c.update_revisions(workspace=WorkspaceRevision(1, "different", self.workspace.relevant_scope))
        c.update_revisions(workspace=replace(self.workspace, mutation_epoch=2))
        self.assertEqual(c.snapshot.revisions.execution_revision, 2)
        self.assertIsNone(c.snapshot.lease)
        with self.assertRaises(TransitionError):
            c.update_revisions(workspace=self.workspace)

    def test_final_revision_mismatch_invalidates_authority(self):
        for changes in ({"intent_revision": 1}, {"execution_revision": 1},
                        {"workspace": WorkspaceRevision(1, "new", ("src/",))}):
            with self.subTest(changes=changes):
                self.setUp()
                lease = self.to_authorized()
                arguments = dict(now=11, intent_revision=0, execution_revision=0, workspace=self.workspace)
                arguments.update(changes)
                with self.assertRaises(TransitionError):
                    self.controller.request_rollover(lease, **arguments)
                self.assertEqual(self.controller.snapshot.state, State.WORKING)
                self.assertIsNone(self.controller.snapshot.request)

    def test_quiescence_defer_and_illegal_state_transition(self):
        c = self.controller
        with self.assertRaises(TransitionError):
            c.propose_boundary(None)
        with self.assertRaises(TransitionError):
            c.prepare_checkpoint()
        transition = c.propose_boundary("boundary-1")
        self.assertEqual(c.propose_boundary("boundary-1"), transition)
        with self.assertRaises(TransitionError):
            c.propose_boundary("boundary-2")
        c.arm_barrier()
        c.begin_quiescence_check()
        with self.assertRaises(TransitionError):
            c.observe_quiescence(relevant_work_remaining=None)
        c.observe_quiescence(relevant_work_remaining=True)
        self.assertEqual(c.snapshot.state, State.DEFERRED)
        self.assertFalse(c.snapshot.barrier_requested)
        c.return_to_work()
        c.require_work()

    def test_stale_pass_rejected_but_failed_implementation_checkpointable(self):
        self.to_snapshot()
        c = self.controller
        for evidence in (self.evidence(execution_revision=1),
                         self.evidence(workspace=replace(self.workspace, mutation_epoch=1)),
                         self.evidence(integrity_window_verified=False),
                         self.evidence(verification="unknown")):
            with self.assertRaises(TransitionError):
                c.verify_boundary(evidence)
        c.verify_boundary(self.evidence(profile="implementation_complete", verification="failed",
                                        integrity_window_verified=False))
        checkpoint = c.prepare_checkpoint()
        with self.assertRaises(TransitionError):
            c.authorize_rollover(now=10, ttl=5)
        self.assertIsNone(checkpoint.commit_evidence)
        c.checkpoint_committed(checkpoint.checkpoint_id, commit_evidence="fsync-complete")
        before = c.snapshot
        self.assertFalse(c.checkpoint_committed(checkpoint.checkpoint_id, commit_evidence="fsync-complete"))
        self.assertEqual(before, c.snapshot)
        self.assertEqual(c.snapshot.revisions.execution_revision, 0)

    def test_new_boundary_requires_new_snapshot_even_if_workspace_unchanged(self):
        lease = self.to_authorized()
        c = self.controller
        c.expire_lease(now=lease.expires_at)
        c.propose_boundary("boundary-2")
        c.arm_barrier()
        c.begin_quiescence_check()
        c.observe_quiescence(relevant_work_remaining=False)
        with self.assertRaises(TransitionError):
            c.capture_workspace(None)
        with self.assertRaises(TransitionError):
            c.verify_boundary(self.evidence())

    def test_restart_rejects_inconsistent_journal(self):
        c = self.controller
        _, _, binding = self.to_requested()
        self.complete(binding)
        with self.assertRaises(TransitionError):
            Controller.restart(replace(c.snapshot, binding=None))
        with self.assertRaises(TransitionError):
            Controller.restart(replace(c.snapshot, recoverable_checkpoint=None))
        c = Controller.restart(Controller("new-thread").snapshot)
        with self.assertRaises(TransitionError):
            c.receive_handoff(None, injection_evidence="injection", receipt_evidence="ack")

    def test_conclusive_non_execution_requires_new_boundary_and_lease(self):
        c = self.controller
        lease, request, _ = self.to_requested()
        c.completion_unknown()
        c.confirm_not_executed(request, evidence_ref="adapter-proven-no-dispatch")
        c.require_work()
        with self.assertRaises(TransitionError):
            self.request(lease)
        new_lease = self.to_authorized("boundary-2")
        self.assertGreater(new_lease.rollover_generation, lease.rollover_generation)

    def test_failed_pre_request_does_not_automatically_resume_work(self):
        self.to_snapshot()
        c = self.controller
        c.fail("snapshot failed")
        self.assertEqual(c.snapshot.state, State.FAILED)
        with self.assertRaises(TransitionError):
            c.require_work()
        c.invalidate("cancel failed transition")
        c.require_work()


if __name__ == "__main__":
    unittest.main()
