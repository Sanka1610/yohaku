"""Bounded local DSH contract checks. Native acceptance is recorded separately."""

from copy import deepcopy
from dataclasses import replace
import os
import tempfile
import unittest
from unittest.mock import patch

from yohaku.controller import TransitionError
from yohaku.dsh_adapter import DSH_VERSION, DshAdapter
from yohaku.model import State, WorkspaceRevision
from yohaku.persistence import SessionStore
from yohaku.recovery import CurrentContext


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
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=tmp.name)
        env.start()
        self.addCleanup(env.stop)
        self.store = SessionStore('dsh-fixture', create=True)
        self.addCleanup(self.store.close)
        self.host = Host()
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


if __name__ == '__main__':
    unittest.main()
