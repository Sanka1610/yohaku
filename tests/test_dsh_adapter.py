"""Bounded local DSH contract checks. Native acceptance is recorded separately."""

from copy import deepcopy
from dataclasses import asdict, replace
import os
import tempfile
import unittest
from unittest.mock import patch

from yohaku.codec import encode
from yohaku.controller import TransitionError
from yohaku.dsh_adapter import DSH_VERSION, DSH_RECEIPT_PROFILE, DshAdapter
from yohaku.model import ContinuationBinding, State, WorkspaceRevision
from yohaku.persistence import SessionStore
from yohaku.recovery import CurrentContext, HandoffDocument, RecoveredData


class Host:
    version = DSH_VERSION
    session_id = 'dsh-fixture'

    def __init__(self):
        self.seq = self.calls = 0
        self.mutate = lambda proof: proof

    def observe(self):
        return dict(sessionId=self.session_id, seq=self.seq, settled=True, status='idle',
                    nextTurn=[], nextStep=[], lastTurnEnd={} if self.seq == 0 else
                    {'turn': 1, 'reason': {'kind': 'completed'}})

    def work(self, prompt):
        self.seq = 11
        return self.observe()

    def compact(self, request_seq, pre_seq):
        self.calls += 1
        cid = 'native-operation'
        old = dict(type='user/message', seq=5, data={'id': 'old-message'})
        replacement = dict(role='user', id='replacement', content=[{'type': 'text', 'text': 'summary'}],
                           source={'kind': 'compact-checkpoint', 'compactionId': cid})
        events = [
            dict(type='compaction/start', seq=11, data={'compactionId': cid, 'turn': None}),
            dict(type='compaction/summary', seq=12, data={'compactionId': cid,
                 'shadowedRange': {'start': 5, 'end': 5}, 'shadowedSeqs': [5]}),
            dict(type='user/message', seq=13, data=replacement,
                 surfaceOp={'op': 'replace', 'startSeq': 5, 'endSeq': 5}),
            dict(type='compaction/end', seq=14, data={'compactionId': cid, 'turn': None}),
        ]
        self.seq = 15
        self.messages = [replacement]
        result = dict(compactionId=cid, startSeq=11, summarySeq=12, endSeq=14,
                      shadowedRange={'start': 5, 'end': 5}, shadowedSeqs=[5])
        return self.mutate(dict(requestSeq=request_seq, preSeq=pre_seq, result=result,
            events=[dict(sessionId=self.session_id, **deepcopy(e)) for e in events],
            flushed=True, readbackSessionId=self.session_id, readbackEvents=[old] + deepcopy(events)))

    def project(self):
        return dict(sessionId=self.session_id, seq=self.seq, messages=self.messages)


class DshAdapterTests(unittest.TestCase):
    host_type = Host
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=tmp.name)
        env.start()
        self.addCleanup(env.stop)
        self.store = SessionStore('dsh-fixture', create=True)
        self.addCleanup(self.store.close)
        self.host = self.host_type()
        self.adapter = DshAdapter(self.host, self.store)
        self.current = CurrentContext('bounded-task', 0, 1,
            WorkspaceRevision(1, 'fixture-done', ('task.json',)))
        self.adapter.work('one bounded turn')
        self.cp = self.adapter.checkpoint(boundary_id='bounded', observe=lambda: self.current,
                                         evidence_ref='local-fixture')

    def compact(self):
        return self.adapter.compact(observe=lambda: self.current, now=lambda: 1)

    def test_native_completion_and_fresh_post_state_keep_endpoint(self):
        self.assertEqual(self.compact().state, State.ROLLOVER_OBSERVED)
        self.assertEqual(self.store.read_checkpoint(self.cp.checkpoint_id), self.cp)
        self.assertIsNone(self.adapter.core.snapshot.receipt_evidence)
        self.assertIsNone(self.adapter.core.snapshot.handoff)
        self.assertIsNone(self.adapter.core.snapshot.continuation_request_id)
        self.assertEqual(list(self.store.journal.iterdir()), [])

    def test_stock_profile_cannot_offer_receipt_handoff(self):
        self.compact()
        s = self.adapter.core.snapshot
        document = HandoffDocument('stock-handoff', s.request, self.cp.revisions,
            self.cp.workspace, '/bounded-workspace', RecoveredData('bounded-task',
                ('work completed',), 'bounded task', ('remaining bounded work',), 'bounded next action', ('task.json',)))
        with self.assertRaises(TransitionError):
            self.adapter.offer_handoff(document, observe=lambda: self.current)
        self.assertEqual(self.adapter.core.snapshot.state, State.ROLLOVER_OBSERVED)
        self.assertIsNone(self.adapter.core.snapshot.continuation_request_id)

    def test_wrong_compaction_id_and_incomplete_sets_are_ambiguous(self):
        def wrong(p):
            p['events'][3]['data']['compactionId'] = 'other-operation'
            return p
        self.host.mutate = wrong
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.adapter.core.snapshot.state, State.AMBIGUOUS)
        self.assertEqual(self.adapter.core.snapshot.completions, ())
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.host.calls, 1)

    def test_each_missing_native_signal_is_not_completion(self):
        self.compact()
        event = self.adapter.completion
        policy = self.adapter.core._completion_policy
        for index in range(4):
            with self.subTest(index=index):
                self.assertFalse(policy.valid_event(replace(event,
                    events=event.events[:index] + event.events[index + 1:])))
        self.assertFalse(policy.valid_event(replace(event, flushed=False)))
        self.assertFalse(policy.valid_event(replace(event, readback_events=())))

    def test_duplicate_completion_is_noop_and_request_cannot_dispatch_twice(self):
        self.compact()
        core = self.adapter.core
        before = core.snapshot
        self.assertFalse(core.observe_completion(self.adapter.completion))
        self.assertEqual(core.snapshot, before)
        with self.assertRaises(TransitionError):
            self.compact()
        request = core.snapshot.request
        with self.assertRaises(TransitionError):
            core.request_rollover(before.lease, now=2, intent_revision=0,
                execution_revision=1, workspace=self.current.workspace)
        self.assertEqual(core.snapshot.request, request)
        self.assertEqual(self.host.calls, 1)

    def test_consumed_lease_cannot_issue_second_request_while_native_is_pending(self):
        native_compact = self.host.compact
        def compact_once(request_seq, pre_seq):
            core = self.adapter.core
            before = core.snapshot
            self.assertEqual(before.state, State.ROLLOVER_REQUESTED)
            with self.assertRaises(TransitionError):
                core.request_rollover(before.lease, now=1, intent_revision=0,
                    execution_revision=1, workspace=self.current.workspace)
            self.assertEqual(core.snapshot, before)
            return native_compact(request_seq, pre_seq)
        self.host.compact = compact_once
        self.compact()
        self.assertEqual(self.host.calls, 1)

    def test_incomplete_lifecycle_stops_core_before_post_state(self):
        def missing_end(proof):
            proof['events'].pop()
            return proof
        self.host.mutate = missing_end
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.adapter.core.snapshot.state, State.AMBIGUOUS)
        self.assertEqual(self.adapter.core.snapshot.completions, ())
        self.assertFalse(hasattr(self.adapter, 'post_state'))
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.host.calls, 1)

    def test_stale_projection_requires_recovery_after_known_completion(self):
        self.host.project = lambda: dict(sessionId=self.host.session_id, seq=11, messages=[])
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertEqual(self.adapter.core.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertEqual(self.host.calls, 1)

    def test_changed_workspace_revokes_lease_without_native_dispatch(self):
        self.current = replace(self.current, execution_revision=2,
            workspace=WorkspaceRevision(2, 'changed', ('task.json',)))
        with self.assertRaises(TransitionError):
            self.compact()
        self.assertIsNone(self.adapter.core.snapshot.lease)
        self.assertEqual(self.host.calls, 0)



class ReceiptHost(Host):
    receipt_profile = DSH_RECEIPT_PROFILE

    def reserve_receipt(self):
        return dict(sessionId=self.session_id, turnId=f'{self.session_id}:2')

    def deliver_handoff(self, handoff_id, turn_id, text):
        from hashlib import sha256
        self.handoff_text = text
        self.delivery = dict(sessionId=self.session_id, handoffId=handoff_id,
            messageId='native-handoff', turnId=turn_id, handoffHash=sha256(text.encode()).hexdigest(),
            durable=True, nonWaking=True)
        return self.delivery

    def start_receipt_request(self):
        self.starts = getattr(self, 'starts', 0) + 1
        candidate = dict(self.delivery, profile=DSH_RECEIPT_PROFILE, nativeSeq=16,
            nativeCall=3, turn=2, step=1, nativeAttemptId='dsh-fixture:2',
            hostEpoch='local-owner', hostAttempt=1, bodyHash='serialized-fixture')
        return self.mutate_candidate(candidate)

    mutate_candidate = staticmethod(lambda candidate: candidate)

    def fresh_receipt(self):
        return dict(current=encode(self.current), sessionId=self.session_id,
                    seq=16, status='running', settled=False, revision='local-owner:1')

    def authorize_receipt(self, candidate, fresh):
        self.authorizations = getattr(self, 'authorizations', 0) + 1
        self.receipt = self.mutate_receipt(dict(binding=candidate, freshRevision=fresh['revision'],
            authorization='one-shot', result='http-accepted', profile=DSH_RECEIPT_PROFILE))
        return self.receipt

    def post_receipt(self):
        self.post_reads = getattr(self, 'post_reads', 0) + 1
        return self.mutate_post(dict(sessionId=self.session_id, seq=20, terminalSeq=19,
            status='idle', settled=True, nextTurn=[], nextStep=[],
            lastTurnEnd={'turn': 2, 'reason': {'kind': 'completed'}},
            current=encode(self.current), messages=[{'id': self.delivery['messageId'],
                'content': [{'type': 'text', 'text': self.handoff_text}]}],
            handoffId=self.delivery['handoffId'], messageId=self.delivery['messageId'],
            receiptBinding=self.receipt['binding'], receiptFreshRevision=self.receipt['freshRevision'],
            revision=f'local-owner:{self.post_reads + 1}', phase='post-receipt-idle'))

    mutate_post = staticmethod(lambda observation: observation)

    mutate_receipt = staticmethod(lambda proof: proof)

    def invalidate_receipt(self, reason):
        self.invalidated = True

    def start_task_interaction(self, claim, handoff, action, post):
        from hashlib import sha256
        self.task_starts = getattr(self, 'task_starts', 0) + 1
        self.task_candidate = dict(self.receipt['binding'], claimId=claim, handoffId=handoff,
            turn=3, turnId=f'{self.session_id}:3', nativeSeq=23, nativeAttemptId=f'{self.session_id}:3',
            nativeCall=2, hostAttempt=2, taskMessageId='actual-task',
            taskHash=sha256(action.encode()).hexdigest())
        return self.task_candidate

    def fresh_task(self):
        self.task_reads = getattr(self, 'task_reads', 0) + 1
        return dict(current=encode(self.current), sessionId=self.session_id,
                    status='running', settled=False, seq=23, revision=f'task:{self.task_reads}')

    def authorize_task(self, candidate, fresh, bound):
        self.task_sends = getattr(self, 'task_sends', 0) + 1
        return dict(binding=candidate, freshRevision=fresh['revision'], result='http-accepted')

    def post_task(self):
        self.final_reads = getattr(self, 'final_reads', 0) + 1
        return dict(sessionId=self.session_id, seq=30, terminalSeq=29, status='idle', settled=True,
            nextTurn=[], nextStep=[], lastTurnEnd={'turn': 3, 'reason': {'kind': 'completed'}},
            current=encode(self.current), taskBinding=self.task_candidate,
            revision=f'final:{self.final_reads}', phase='post-task-idle',
            messages=[dict(id='output', role='assistant', content=[{'type': 'text', 'text': 'FINALIZED'}])],
            handoffId=self.delivery['handoffId'], claimId=self.task_candidate['claimId'])


    def final_task(self):
        return dict(self.post_task(), completion=dict(readbackSessionId=self.session_id,
            readbackSeq=30, turnStartSeq=21, terminalSeq=29, outputSeq=25,
            outputMessageId='output', outputContent=[{'type': 'text', 'text': 'FINALIZED'}],
            finalizedCount=1, taskInputs=1, taskTurns=1, taskRequests=1, nativeCalls=1))


class DshReceiptAdapterTests(unittest.TestCase):
    host_type = ReceiptHost
    setUp = DshAdapterTests.setUp
    compact = DshAdapterTests.compact

    def offer(self):
        self.compact()
        self.host.current = self.current
        s = self.adapter.core.snapshot
        document = HandoffDocument('handoff-fixture', s.request, self.cp.revisions,
            self.cp.workspace, '/bounded-workspace', RecoveredData('bounded-task',
                ('work completed',), 'bounded task', getattr(self, 'unresolved', ('remaining bounded work',)),
                getattr(self, 'action', 'bounded next action'), ('task.json',)))
        self.host.document = document
        return self.adapter.offer_handoff(document, observe=lambda: self.current)

    def test_delivery_remains_offered_and_receipt_is_one_shot(self):
        handoff = self.offer()
        self.assertEqual(self.adapter.core.snapshot.state, State.HANDOFF_OFFERED)
        self.assertIsNone(self.adapter.core.snapshot.receipt_evidence)
        self.assertIsNone(self.adapter.core.snapshot.continuation_request_id)
        self.assertEqual(handoff.continuation_turn_id, '')
        self.assertEqual(self.store.read_handoff(handoff.handoff_id).request, handoff.request)
        self.assertTrue(self.adapter.receive_handoff(observe=lambda: self.current))
        self.assertEqual(self.adapter.core.snapshot.state, State.HANDOFF_RECEIVED)
        before = self.adapter.core.snapshot
        self.assertFalse(self.adapter.receive_handoff(observe=lambda: self.current))
        self.assertEqual(self.adapter.core.snapshot, before)
        self.assertEqual(self.host.starts, 1)
        self.assertEqual(self.host.authorizations, 1)
        self.assertTrue(before.barrier_requested)

    def test_foreign_candidate_stops_before_authorization(self):
        self.offer()
        self.host.mutate_candidate = lambda candidate: dict(candidate, messageId='foreign')
        with self.assertRaises(TransitionError):
            self.adapter.receive_handoff(observe=lambda: self.current)
        self.assertFalse(hasattr(self.host, 'authorizations'))
        self.assertTrue(self.host.invalidated)
        self.assertEqual(self.adapter.core.snapshot.state, State.RECOVERY_REQUIRED)

    def test_stale_direct_state_stops_before_authorization(self):
        self.offer()
        self.current = replace(self.current, execution_revision=2)
        with self.assertRaises(TransitionError):
            self.adapter.receive_handoff(observe=lambda: self.current)
        self.assertFalse(hasattr(self.host, 'authorizations'))
        self.assertTrue(self.host.invalidated)

    def test_mismatched_receipt_does_not_reach_received(self):
        self.offer()
        self.host.mutate_receipt = lambda proof: dict(proof, freshRevision='old')
        with self.assertRaises(TransitionError):
            self.adapter.receive_handoff(observe=lambda: self.current)
        self.assertEqual(self.adapter.core.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertIsNone(self.adapter.core.snapshot.receipt_evidence)

    def received(self):
        self.offer()
        self.adapter.receive_handoff(observe=lambda: self.current)

    def qualify(self, reassess=None):
        return self.adapter.qualify_resume(observe=lambda: self.current,
            reassess=reassess or (lambda document, current: document.recovered.next_action_candidate))

    def test_fresh_unresolved_work_qualifies_without_consuming_core_authority(self):
        self.received()
        before = self.adapter.core.snapshot
        result = self.qualify()
        self.assertTrue(result['unresolved_work'])
        self.assertFalse(result['continuation_authorized'])
        self.assertEqual(self.adapter.core.snapshot.state, before.state)
        self.assertIsNone(self.adapter.core.snapshot.continuation_request_id)
        self.assertEqual(self.adapter.core.snapshot.handoff.continuation_turn_id, '')
        before = self.adapter.core.snapshot
        self.assertEqual(self.host.post_reads, 2)
        self.assertTrue(before.barrier_requested)
        with self.assertRaises(TransitionError):
            self.adapter.core.claim_continuation()
        with self.assertRaises(TransitionError):
            self.qualify()
        self.assertFalse(self.adapter.receive_handoff(observe=lambda: self.current))
        self.assertEqual(self.host.starts, 1)
        self.assertEqual(self.adapter.core.snapshot, before)

    def test_already_completed_work_never_authorizes_continuation(self):
        self.received()
        result = self.qualify(lambda document, current: None)
        self.assertFalse(result['unresolved_work'])
        self.assertEqual(result['stop_reason'], 'no unresolved work')
        self.assertEqual(self.adapter.core.snapshot.state, State.HANDOFF_RECEIVED)

    def test_changed_task_and_workspace_revision_fail_closed(self):
        self.received()
        self.current = replace(self.current, execution_revision=2,
            workspace=WorkspaceRevision(2, 'changed', ('task.json',)))
        with self.assertRaises(TransitionError):
            self.qualify()
        self.assertTrue(self.host.invalidated)
        self.assertEqual(self.adapter.core.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertEqual(self.host.starts, 1)

    def reject_post(self, change):
        self.received()
        self.host.mutate_post = lambda observation: dict(observation, **change)
        with self.assertRaises(TransitionError):
            self.qualify()
        self.assertEqual(self.host.starts, 1)
        self.assertEqual(self.adapter.core.snapshot.state, State.RECOVERY_REQUIRED)

    def test_changed_historical_action_does_not_dispatch(self):
        self.received()
        with self.assertRaises(TransitionError):
            self.qualify(lambda document, current: 'a different historical action')
        self.assertEqual(self.host.starts, 1)

    def test_uncertain_post_receipt_read_stops_without_retry(self):
        self.received()
        calls = []
        def unavailable():
            calls.append(True)
            raise OSError('independent read unavailable')
        self.host.post_receipt = unavailable
        with self.assertRaises(OSError):
            self.qualify()
        with self.assertRaises(TransitionError):
            self.qualify()
        self.assertEqual(calls, [True])
        self.assertEqual(self.host.starts, 1)
        self.assertEqual(self.adapter.core.snapshot.state, State.RECOVERY_REQUIRED)

    def test_state_change_during_reassessment_stops(self):
        self.received()
        def reassess(document, current):
            self.host.current = replace(current, execution_revision=2)
            return document.recovered.next_action_candidate
        with self.assertRaises(TransitionError):
            self.qualify(reassess)
        self.assertEqual(self.adapter.core.snapshot.state, State.RECOVERY_REQUIRED)

    def test_old_durable_handoff_is_not_reused(self):
        self.received()
        with patch.object(self.store, 'read_handoff', return_value=replace(self.host.document,
                recovered=replace(self.host.document.recovered, next_action_candidate='old action'))):
            with self.assertRaises(TransitionError):
                self.qualify()
        self.assertFalse(hasattr(self.host, 'post_reads'))

    def test_task_binds_actual_identity_and_persists_before_effect(self):
        import json
        from pathlib import Path
        self.received()
        self.qualify()
        original = self.host.authorize_task
        def send(candidate, fresh, bound):
            snapshot = self.adapter.core.snapshot
            self.assertEqual(snapshot.handoff.continuation_turn_id, 'dsh-fixture:3')
            record = json.loads(Path(bound['bindingRecord']).read_text())['payload']
            self.assertEqual(record['binding']['turn_id'], candidate['turnId'])
            self.assertEqual(record['binding']['request_id'], snapshot.continuation_request_id)
            with self.assertRaises(TransitionError):
                self.adapter.core.claim_continuation(expected_snapshot=snapshot)
            with self.assertRaises(TransitionError):
                self.adapter.core.bind_continuation(ContinuationBinding(snapshot.continuation_request_id,
                    snapshot.thread_id, candidate['turnId']), expected_snapshot=snapshot)
            return original(candidate, fresh, bound)
        self.host.authorize_task = send
        result = self.adapter.continue_task(observe=lambda: self.current)
        self.assertEqual(result['continuation_completed'], 'PASS')
        self.assertEqual(result['resume_proof'], 'BLOCKED_BY_EXISTING_CONTRACT')
        self.assertEqual(self.adapter.core.snapshot.state, State.HANDOFF_RECEIVED)
        self.assertTrue(self.adapter.core.snapshot.barrier_requested)
        with self.assertRaises(TransitionError):
            self.adapter.continue_task(observe=lambda: self.current)
        self.assertFalse(self.adapter.receive_handoff(observe=lambda: self.current))
        self.assertEqual((self.host.task_starts, self.host.task_sends, self.host.starts), (1, 1, 1))

    def test_task_without_unresolved_work_never_claims(self):
        self.received()
        self.qualify(lambda d, c: None)
        with self.assertRaises(TransitionError):
            self.adapter.continue_task(observe=lambda: self.current)
        self.assertIsNone(self.adapter.core.snapshot.continuation_request_id)

    def test_qualification_cannot_survive_a_later_task_change(self):
        self.received()
        self.qualify()
        self.current = replace(self.current, execution_revision=2)
        with self.assertRaises(TransitionError):
            self.adapter.continue_task(observe=lambda: self.current)
        self.assertIsNone(self.adapter.core.snapshot.continuation_request_id)

    def task_failure(self, method, replacement, *, bound=False, sent=0):
        self.received()
        self.qualify()
        original = getattr(self.host, method)
        setattr(self.host, method, lambda *args: replacement(original, *args))
        with self.assertRaises((TransitionError, OSError)) as stopped:
            self.adapter.continue_task(observe=lambda: self.current)
        self.assertIn('may have been sent or completed', ' '.join(stopped.exception.__notes__))
        self.assertIn('without restoring the claim/binding or retrying', ' '.join(stopped.exception.__notes__))
        snapshot = self.adapter.core.snapshot
        self.assertIsNotNone(snapshot.continuation_request_id)
        self.assertEqual(bool(snapshot.handoff.continuation_turn_id), bound)
        self.assertEqual(snapshot.state, State.RECOVERY_REQUIRED)
        self.assertTrue(self.host.invalidated)
        with self.assertRaises(TransitionError):
            self.adapter.continue_task(observe=lambda: self.current)
        self.assertEqual(getattr(self.host, 'task_sends', 0), sent)

    def test_stale_core_revision_after_claim_blocks_binding(self):
        def change(original, *args):
            result = original(*args)
            self.adapter.core.update_revisions(archive_changed=True)
            return result
        self.task_failure('start_task_interaction', change)

    def test_foreign_actual_task_identity_never_binds(self):
        self.task_failure('start_task_interaction',
            lambda original, *a: dict(original(*a), turnId='foreign:3'))

    def test_stale_core_revision_after_binding_blocks_release(self):
        def change(original):
            result = original()
            if self.host.task_reads == 2:
                self.adapter.core.update_revisions(archive_changed=True)
            return result
        self.task_failure('fresh_task', change, bound=True)

    def test_stale_task_state_after_binding_blocks_release(self):
        def change(original):
            result = original()
            if self.host.task_reads == 2:
                self.current = replace(self.current, execution_revision=2)
            return result
        self.task_failure('fresh_task', change, bound=True)

    def test_uncertain_task_admission_keeps_claim_consumed(self):
        def uncertain(original, *args):
            original(*args)
            raise OSError('native admission outcome unknown')
        self.task_failure('start_task_interaction', uncertain)

    def test_uncertain_send_keeps_binding_and_never_resends(self):
        def uncertain(original, *args):
            original(*args)
            raise OSError('task HTTP outcome unknown')
        self.task_failure('authorize_task', uncertain, bound=True, sent=1)

    def test_binding_record_failure_never_releases_task(self):
        self.received()
        self.qualify()
        original = self.adapter._record
        def fail(kind, **data):
            if kind == 'task_bound':
                raise OSError('durable binding write uncertain')
            return original(kind, **data)
        with patch.object(self.adapter, '_record', side_effect=fail):
            with self.assertRaises(OSError):
                self.adapter.continue_task(observe=lambda: self.current)
        self.assertEqual(self.adapter.core.snapshot.handoff.continuation_turn_id, 'dsh-fixture:3')
        self.assertFalse(hasattr(self.host, 'task_sends'))
        self.assertTrue(self.host.invalidated)


# Each negative gets its own fresh owner/store; no restart or restored authority.
for _name, _change in {
        'wrong_session': dict(sessionId='foreign'),
        'old_handoff': dict(handoffId='old'),
        'old_message': dict(messageId='old-message'),
        'gate_revision': dict(revision='local-owner:1'),
        'pre_receipt_seq': dict(seq=16, terminalSeq=15),
        'gate_phase': dict(phase='receipt-gate'),
        'running_agent': dict(status='running', settled=False),
        'pending_turn': dict(nextTurn=['pending']),
        'pending_step': dict(nextStep=['pending']),
        'missing_projection': dict(messages=[]),
        'foreign_receipt': dict(receiptBinding={}),
        'wrong_terminal': dict(lastTurnEnd={'turn': 3, 'reason': {'kind': 'completed'}}),
        'wrong_task': dict(current={'logical_task_id': 'foreign'}),
    }.items():
    def _test(self, change=_change):
        self.reject_post(change)
    setattr(DshReceiptAdapterTests, 'test_post_receipt_rejects_' + _name, _test)


if __name__ == '__main__':
    unittest.main()


class DshFinalVerificationTests(unittest.TestCase):
    host_type = ReceiptHost
    setUp = DshAdapterTests.setUp
    compact = DshAdapterTests.compact
    offer = DshReceiptAdapterTests.offer
    received = DshReceiptAdapterTests.received
    qualify = DshReceiptAdapterTests.qualify
    unresolved = ('FINALIZE',)
    action = 'Produce FINALIZED exactly once after current task reconciliation.'

    def completed(self):
        self.received()
        self.qualify()
        self.adapter.continue_task(observe=lambda: self.current)

    def verify(self):
        return self.adapter.verify_finalized(observe=lambda: self.current)

    def test_context_assist_failure_at_delivery_keeps_exact_fallback_through_resume(self):
        with patch('yohaku.context_assist.build_task_context', side_effect=RuntimeError('builder')):
            self.received()
        self.assertEqual(self.adapter.handoff_text, self.host.document.render(context_assist=False))
        self.qualify()
        self.adapter.continue_task(observe=lambda: self.current)
        self.verify()
        self.assertEqual(self.adapter.core.snapshot.state, State.RESUME_VERIFIED)

    def test_later_builder_failure_cannot_change_delivered_context(self):
        self.received()
        self.assertIn('Historical task context', self.adapter.handoff_text)
        with patch('yohaku.context_assist.build_task_context', side_effect=RuntimeError('builder')) as build:
            self.qualify()
            self.adapter.continue_task(observe=lambda: self.current)
            self.verify()
        build.assert_not_called()
        self.assertEqual(self.adapter.core.snapshot.state, State.RESUME_VERIFIED)

    def rejected(self):
        with patch.object(self.adapter.core, 'verify_resume') as verify:
            with self.assertRaises((TransitionError, OSError)):
                self.verify()
            verify.assert_not_called()
        self.assertFalse(hasattr(self.adapter, 'resume_verification'))
        self.assertNotEqual(self.adapter.core.snapshot.state, State.RESUME_VERIFIED)

    def test_complete_chain_record_order_and_second_verify(self):
        import json
        from pathlib import Path
        self.completed()
        verify = self.adapter.core.verify_resume
        def checked(evidence):
            record = json.loads(Path(evidence.evidence_ref).read_text())['payload']
            self.assertEqual(record['claim_id'], self.adapter.core.snapshot.continuation_request_id)
            self.assertEqual(record['continuation_turn_id'], 'dsh-fixture:3')
            self.assertEqual(record['assessment']['nonduplication'], 'PASS')
            kinds = [json.loads(p.read_text())['payload']['kind'] for p in sorted(self.adapter.records.iterdir())]
            self.assertEqual(kinds[-4:], ['task_completed', 'final_task_observed',
                'bounded_task_assessed', 'resume_verified_evidence'])
            verify(evidence)
        with patch.object(self.adapter.core, 'verify_resume', side_effect=checked) as call:
            evidence = self.verify()
            call.assert_called_once()
        self.assertEqual(self.adapter.core.snapshot.state, State.RESUME_VERIFIED)
        self.assertFalse(self.adapter.core.snapshot.barrier_requested)
        self.assertEqual(self.host.final_reads, 3)
        with self.assertRaises(TransitionError):
            self.verify()
        with self.assertRaises(TransitionError):
            self.adapter.core.verify_resume(evidence)
        self.assertEqual(self.host.task_sends, 1)

    def test_receipt_evidence_cannot_verify_resume(self):
        self.received()
        self.rejected()

    def test_receipt_record_cannot_replace_completion_record(self):
        self.completed()
        self.adapter._completed_task[2]['completion'] = self.adapter.core.snapshot.receipt_evidence
        self.rejected()

    def test_foreign_handoff_and_claim_in_final_observation(self):
        self.completed()
        original = self.host.final_task
        with patch.object(self.host, 'final_task', side_effect=lambda: dict(original(),
                handoffId='foreign', claimId='foreign')):
            self.rejected()

    def test_model_self_report_without_native_completion_cannot_verify(self):
        self.received()
        self.adapter.task_result = dict(continuation_completed='PASS', text='FINALIZED')
        self.rejected()

    def test_send_uncertainty_never_creates_or_calls_verification(self):
        self.received()
        self.qualify()
        with patch.object(self.host, 'authorize_task', side_effect=OSError('send uncertain')):
            with self.assertRaises(OSError):
                self.adapter.continue_task(observe=lambda: self.current)
        self.rejected()

    def test_changed_workspace_before_verification(self):
        self.completed()
        self.current = replace(self.current, workspace=WorkspaceRevision(2, 'changed', ('task.json',)))
        self.rejected()

    def test_verification_record_save_failure(self):
        self.completed()
        write = self.store._write
        def fail(path, payload):
            if payload['kind'] == 'resume_verified_evidence':
                raise OSError('record save failure')
            return write(path, payload)
        with patch.object(self.store, '_write', side_effect=fail):
            self.rejected()
        self.assertTrue(self.adapter.stopped)

    def test_core_verify_failure_safely_stops(self):
        self.completed()
        with patch.object(self.adapter.core, 'verify_resume', side_effect=TransitionError('Core rejects')) as call:
            with self.assertRaises(TransitionError):
                self.verify()
            call.assert_called_once()
        self.assertEqual(self.adapter.core.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertTrue(self.adapter.stopped)

    def test_core_revision_changes_during_record_write(self):
        self.completed()
        write = self.adapter._record
        def change(kind, **payload):
            ref = write(kind, **payload)
            if kind == 'resume_verified_evidence':
                self.adapter.core.update_revisions(archive_changed=True)
            return ref
        with patch.object(self.adapter, '_record', side_effect=change):
            self.rejected()


def _final_negative(name, mutate, *, reread=False):
    def test(self):
        self.completed()
        original = self.host.final_task
        calls = 0
        def changed():
            nonlocal calls
            calls += 1
            final = original()
            if not reread or calls == 2:
                mutate(final, self)
            return final
        with patch.object(self.host, 'final_task', side_effect=changed):
            self.rejected()
    setattr(DshFinalVerificationTests, 'test_final_' + name, test)


for _name, _mutate in {
    'wrong_bound_turn': lambda f, t: f['taskBinding'].update(turnId='foreign:3'),
    'foreign_session': lambda f, t: f.update(sessionId='foreign'),
    'stale_observation': lambda f, t: f.update(revision=t.adapter._completed_task[1]['revision']),
    'failed_terminal': lambda f, t: f['lastTurnEnd'].update(reason={'kind': 'error'}),
    'incomplete_terminal': lambda f, t: f.update(lastTurnEnd={}),
    'duplicate_continuation': lambda f, t: f['completion'].update(taskRequests=2),
    'duplicate_output': lambda f, t: f['completion'].update(finalizedCount=2),
    'task_mismatch': lambda f, t: f['current'].update(logical_task_id='foreign'),
    'readback_mismatch': lambda f, t: f['completion'].update(readbackSessionId='foreign'),
    'missing_assessment': lambda f, t: f['completion'].update(outputContent=[{'type': 'text', 'text': 'done'}]),
    'pending_inbox': lambda f, t: f.update(nextTurn=['pending']),
    'active_task': lambda f, t: f.update(status='running'),
}.items():
    _final_negative(_name, _mutate)
_final_negative('stale_reread', lambda f, t: f.update(revision=f"final:{t.host.final_reads - 1}"), reread=True)
_final_negative('changed_after_record', lambda f, t: f.update(seq=f['seq'] + 1), reread=True)
