"""Local adapter-boundary checks, not Hermes transport or capability acceptance."""

from dataclasses import replace
import os
import tempfile
import unittest
from unittest.mock import patch

from yohaku.controller import Controller, TransitionError
from yohaku.hermes import (
    HERMES_SOURCE, HERMES_VERSION, HermesManualBinding, HermesManualCompletion,
    HermesManualCompletionPolicy,
)
from yohaku.model import (
    BoundaryVerification, Completion, CompletionBinding, CompletionKind,
    ContinuationBinding, ResumeVerification, State, WorkspaceRevision,
)
from yohaku.persistence import PersistenceError, SessionStore


class CompletionPolicyTests(unittest.TestCase):
    def requested(self, policy=None):
        c = Controller('session', completion_policy=policy)
        ws = WorkspaceRevision(0, 'fixture-state', ('task.json',))
        c.propose_boundary('fixture-boundary')
        c.arm_barrier()
        c.begin_quiescence_check()
        c.observe_quiescence(relevant_work_remaining=False)
        c.capture_workspace(ws)
        c.verify_boundary(BoundaryVerification(0, 0, ws, 'implementation_complete',
                                              'not_run', 'synthetic-boundary'))
        cp = c.prepare_checkpoint()
        c.checkpoint_committed(cp.checkpoint_id, commit_evidence='synthetic-checkpoint')
        lease = c.authorize_rollover(now=1, ttl=10)
        request = c.request_rollover(lease, now=2, intent_revision=0,
                                    execution_revision=0, workspace=ws)
        return c, request, lease

    def hermes(self):
        c, r, lease = self.requested(HermesManualCompletionPolicy())
        b = HermesManualBinding(r, r.thread_id, 25, HERMES_VERSION, HERMES_SOURCE, True)
        c.bind_completion(b)
        e = HermesManualCompletion(
            binding=b, evidence_ref='synthetic-independent-readback', request_id=r.request_id,
            readback_seq=30, session_before=r.thread_id, session_after=r.thread_id,
            compressor_count=1, manual_requests=1, readback_count=1,
            host_changed=True, independent_db_read=True, db_payload_matches_host=True,
            host_history_hash='a' * 64, db_history_hash='a' * 64,
            host_history_count=6, db_message_count=6, archived_rows=8)
        return c, e, lease

    def assert_stopped(self, c, lease):
        self.assertEqual(c.snapshot.state, State.AMBIGUOUS)
        for operation in (c.require_work, c.claim_continuation, c.return_to_work,
                          lambda: c.request_rollover(lease, now=3, intent_revision=0,
                              execution_revision=0, workspace=c.snapshot.workspace)):
            with self.assertRaises(TransitionError):
                operation()

    def test_codex_default_rejects_hermes_and_keeps_three_signals(self):
        c, r, _ = self.requested()
        _, foreign, _ = self.hermes()
        with self.assertRaises(TransitionError):
            c.bind_completion(replace(foreign.binding, request=r))
        b = CompletionBinding(r, 'compact-turn', 'compact-item')
        c.bind_completion(b)
        c.accept_request(r)
        for kind in list(CompletionKind)[:2]:
            c.observe_completion(Completion(b, kind, 'codex'))
        self.assertEqual(c.snapshot.state, State.ROLLOVER_REQUESTED)
        c.observe_completion(Completion(b, CompletionKind.COMPACT_TURN, 'codex-turn'))
        self.assertEqual(c.snapshot.state, State.ROLLOVER_OBSERVED)

    def test_hermes_completion_does_not_require_codex_events_or_claim_receipt(self):
        c, e, _ = self.hermes()
        self.assertFalse(hasattr(e.binding, 'compact_turn_id'))
        self.assertTrue(c.observe_completion(e))
        self.assertEqual(c.snapshot.state, State.ROLLOVER_OBSERVED)
        ident = c.claim_continuation()
        handoff = c.offer_handoff(ContinuationBinding(ident, 'session', 'actual-host-turn'),
                                  recovered_context='DATA, NOT INSTRUCTIONS')
        self.assertEqual(c.snapshot.state, State.HANDOFF_OFFERED)
        self.assertIsNone(c.snapshot.receipt_evidence)
        with self.assertRaises(TransitionError):
            c.receive_handoff(handoff, injection_evidence='instruction-submitted', receipt_evidence='')
        s = c.snapshot
        with self.assertRaises(TransitionError):
            c.verify_resume(ResumeVerification(handoff.handoff_id, 'actual-host-turn',
                0, 0, s.workspace, 'behavior-without-receipt', True, True, True, True, True, True, True))
        with self.assertRaises(TransitionError):
            c.require_work()

    def test_hermes_invalid_readback_is_ambiguous_and_never_retries(self):
        changes = (
            {'request_id': 'other-request'}, {'session_before': 'other-session'},
            {'session_after': 'other-session'}, {'compressor_count': 2},
            {'compressor_count': True}, {'manual_requests': 2}, {'readback_count': 2},
            {'readback_seq': 25}, {'host_changed': False}, {'independent_db_read': False},
            {'db_payload_matches_host': False}, {'db_history_hash': 'b' * 64},
            {'host_history_hash': '', 'db_history_hash': ''}, {'db_message_count': 7},
            {'host_history_count': 0, 'db_message_count': 0}, {'archived_rows': 0},
            {'evidence_ref': ''},
        )
        for change in changes:
            with self.subTest(change=change):
                c, e, lease = self.hermes()
                self.assertFalse(c.observe_completion(replace(e, **change)))
                self.assertEqual(c.snapshot.completions, ())
                self.assert_stopped(c, lease)

    def test_hermes_scope_and_foreign_binding_rejected(self):
        c, e, _ = self.hermes()
        for change in ({'version': 'other'}, {'source_commit': 'other'},
                       {'exclusive_fresh_session': False}, {'session_id': 'other'},
                       {'request_seq': 0}):
            with self.subTest(change=change), self.assertRaises(TransitionError):
                c.bind_completion(replace(e.binding, **change))
        for change in ({'request_id': 'other'}, {'thread_id': 'other'},
                       {'rollover_generation': 2}, {'transition_id': 'other'}):
            with self.subTest(change=change):
                c, e, lease = self.hermes()
                b = replace(e.binding, request=replace(e.binding.request, **change))
                self.assertFalse(c.observe_completion(replace(e, binding=b)))
                self.assert_stopped(c, lease)

    def test_engine_acceptance_without_readback_never_completes(self):
        c, _, lease = self.hermes()
        c.accept_request(c.snapshot.request)
        self.assertEqual(c.snapshot.state, State.ROLLOVER_REQUESTED)
        c.completion_unknown('engine returned but storage observation unavailable')
        self.assert_stopped(c, lease)

    def test_hermes_codex_events_cannot_substitute_for_readback(self):
        c, _, lease = self.hermes()
        b = CompletionBinding(c.snapshot.request, 'invented-turn', 'invented-item')
        for kind in CompletionKind:
            self.assertFalse(c.observe_completion(Completion(b, kind, 'invented-event')))
        self.assert_stopped(c, lease)

    def test_local_late_readback_and_duplicate_cannot_grant_another_permit(self):
        c, e, lease = self.hermes()
        c.completion_unknown()
        self.assert_stopped(c, lease)
        self.assertTrue(c.observe_completion(e))
        c.claim_continuation()
        before = c.snapshot
        self.assertFalse(c.observe_completion(e))
        self.assertEqual(c.snapshot, before)
        with self.assertRaises(TransitionError):
            c.claim_continuation()

    def test_hermes_completion_does_not_restore_revoked_authority(self):
        c, e, lease = self.hermes()
        c.update_revisions(intent_changed=True)
        self.assert_stopped(c, lease)
        c.observe_completion(e)
        self.assertEqual(c.snapshot.state, State.ROLLOVER_OBSERVED)
        self.assertTrue(c.snapshot.invalidated)
        self.assertIsNone(c.snapshot.lease)
        self.assertEqual(c.snapshot.revisions.intent_revision, 1)
        with self.assertRaises(TransitionError):
            c.require_work()

    def test_hermes_proof_cannot_be_saved_or_restarted_as_codex(self):
        c, e, _ = self.hermes()
        c.observe_completion(e)
        with self.assertRaises(TransitionError):
            Controller.restart(c.snapshot)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, CODEX_HOME=tmp):
            with SessionStore('session', create=True) as store:
                with self.assertRaises(PersistenceError):
                    store.append(c.snapshot, {}, 'foreign_proof')
                self.assertEqual(list(store.journal.glob('*.json')), [])


if __name__ == '__main__':
    unittest.main()
