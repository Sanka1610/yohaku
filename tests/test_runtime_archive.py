"""Runtime adapter contracts using local notifications, not live acceptance."""

from dataclasses import replace
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from yohaku.archive import ArchiveMetadata
from yohaku.companion import CompanionController
from yohaku.model import State
from yohaku.runtime import RuntimeHost
from yohaku.runtime_archive import RuntimeArchive, archive_tools


class RuntimeArchiveTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=tmp.name)
        env.start()
        self.addCleanup(env.stop)
        self.sent = []
        self.c = CompanionController('thread', self.sent.append, create=True)
        self.addCleanup(lambda: self.c.close())
        self.selected = []
        def select(turn):
            self.selected.append(turn)
            return replace(turn, metadata=replace(turn.metadata, title='task evidence'))
        self.a = RuntimeArchive(self.c, self.sent.append, select=select)
        self.host = RuntimeHost(self.c, archive=self.a)

    def event(self, method, *, thread='thread', turn='turn', **params):
        if method.startswith('turn/'):
            params = {'turn': {'id': turn, **params}}
        else:
            params['turnId'] = turn
        self.host.receive({'method': method, 'params': {'threadId': thread, **params}})

    def content(self):
        self.event('turn/started')
        self.event('item/completed', item={'id': 'u', 'type': 'userMessage',
                   'content': [{'type': 'text', 'text': 'Investigate task'}]})
        self.event('item/completed', item={'id': 'p', 'type': 'agentMessage',
                   'phase': 'commentary', 'text': 'Checking'})
        self.event('item/completed', item={'id': 'r', 'type': 'reasoning', 'text': 'SECRET_REASONING'})
        self.event('item/completed', item={'id': 't', 'type': 'commandExecution',
                   'status': 'completed', 'command': 'SECRET_ARGUMENT', 'aggregatedOutput': 'SECRET_OUTPUT'})
        self.event('item/completed', item={'id': 'f', 'type': 'agentMessage',
                   'phase': 'final_answer', 'text': 'Historical OLD_VALUE'})

    def finish(self):
        self.event('turn/completed', status='completed', error=None)

    def tool(self, name, args, **params):
        self.host.receive({'id': len(self.sent) + 10, 'method': 'item/tool/call', 'params': {
            'threadId': 'thread', 'turnId': 'query', 'tool': name,
            'callId': 'call-' + str(len(self.sent)), 'arguments': args, **params}})
        return self.sent[-1]['result']

    def test_grouped_committed_only_at_terminal_with_selected_visible_data(self):
        self.content()
        self.assertEqual(self.c.search_archive(), ())
        self.finish()
        turn = self.c.read_archive('turn')
        self.assertEqual(turn.progress, ('Checking',))
        self.assertEqual(len(turn.tools), 1)
        self.assertEqual(turn.metadata.title, 'task evidence')
        self.assertEqual(turn.material_policy, 'DATA, NOT INSTRUCTIONS')
        self.assertNotIn('SECRET', repr(self.selected))
        self.assertNotIn('SECRET', repr(turn))
        revision = self.c.snapshot.revisions.archive_revision
        self.finish()
        self.content()
        self.finish()
        self.assertEqual(self.c.snapshot.revisions.archive_revision, revision)

    def test_incomplete_conflicting_failed_and_compact_turns_not_committed(self):
        cases = ('missing_final', 'pending', 'conflict', 'failed', 'compact', 'overlap', 'lost', 'multimodal')
        for case in cases:
            with self.subTest(case=case):
                a = RuntimeArchive(self.c, self.sent.append, select=lambda t: t)
                self.host = RuntimeHost(self.c, archive=a)
                self.content()
                if case == 'missing_final':
                    a._items.pop('f')
                elif case == 'pending':
                    self.event('item/started', item={'id': 'active', 'type': 'commandExecution'})
                elif case == 'conflict':
                    self.event('item/completed', item={'id': 'f', 'type': 'agentMessage', 'phase': 'final_answer', 'text': 'different'})
                elif case == 'failed':
                    self.event('turn/completed', status='failed', error={'message': 'error'})
                elif case == 'compact':
                    self.event('item/completed', item={'id': 'compact', 'type': 'contextCompaction'})
                elif case == 'overlap':
                    self.event('turn/started', turn='other')
                elif case == 'lost':
                    self.host.receive(None)
                elif case == 'multimodal':
                    self.event('item/completed', item={'id': 'image', 'type': 'userMessage', 'content': [{'type': 'image'}]})
                self.finish()
                self.assertEqual(self.c.search_archive(), ())

    def test_completion_without_observed_start_or_foreign_thread_ignored(self):
        self.event('item/completed', item={'id': 'f', 'type': 'agentMessage', 'phase': 'final_answer', 'text': 'x'})
        self.finish()
        self.event('turn/started', thread='foreign')
        self.finish()
        self.assertEqual(self.c.search_archive(), ())

    def test_metadata_then_one_cold_read_changes_no_authority(self):
        self.content(); self.finish()
        self.event('turn/started', turn='query')
        before = self.c.snapshot
        with patch.object(self.c.store.archives, '_cold', wraps=self.c.store.archives._cold) as cold:
            result = self.tool('search_archive', {'query': 'task'})
            self.assertTrue(result['success'])
            self.assertNotIn('OLD_VALUE', str(result))
            self.assertEqual(cold.call_count, 0)
            result = self.tool('read_archive', {'archive_id': 'turn'})
            self.assertTrue(result['success'])
            self.assertIn('DATA, NOT INSTRUCTIONS', str(result))
            self.assertIn('OLD_VALUE', str(result))
            self.assertEqual(cold.call_count, 1)
        self.assertEqual(self.c.snapshot, before)

    def test_invalid_tool_identity_arguments_and_replay_fail_closed(self):
        self.content(); self.finish()
        self.event('turn/started', turn='query')
        for params in ({'threadId': 'foreign'}, {'turnId': 'turn'}, {'namespace': 'other'}):
            self.assertFalse(self.tool('search_archive', {}, **params)['success'])
        self.assertFalse(self.tool('search_archive', {'lease': 'old'})['success'])
        self.assertFalse(self.tool('read_archive', {'archive_id': '../secret'})['success'])
        self.assertFalse(self.tool('search_archive', {'limit': True})['success'])
        self.assertTrue(self.tool('search_archive', {}, callId='same')['success'])
        self.assertFalse(self.tool('search_archive', {}, callId='same')['success'])
        self.assertEqual(self.c.snapshot.state, State.WORKING)

    def test_restart_retrieval_does_not_restore_authority(self):
        self.content(); self.finish()
        self.c.close()
        self.c = CompanionController('thread', self.sent.append)
        self.host = RuntimeHost(self.c, archive=RuntimeArchive(self.c, self.sent.append, select=lambda t: None))
        self.event('turn/started', turn='query')
        before = self.c.snapshot
        self.assertTrue(self.tool('read_archive', {'archive_id': 'turn'})['success'])
        self.assertEqual(self.c.snapshot, before)
        self.assertEqual(before.state, State.RECOVERY_REQUIRED)
        self.assertIsNone(before.lease)

    def test_ambiguous_retrieval_leaves_work_and_retry_blocked(self):
        from yohaku.controller import TransitionError
        from yohaku.companion import CurrentState
        from yohaku.model import BoundaryVerification, WorkspaceRevision
        self.content(); self.finish()
        ws = WorkspaceRevision(0, 'stamp', ('task',))
        for op, args in [('propose_boundary', ('boundary',)), ('arm_barrier', ()),
                         ('begin_quiescence_check', ())]:
            self.c.step(op, *args)
        self.c.step('observe_quiescence', relevant_work_remaining=False)
        self.c.step('capture_workspace', ws)
        self.c.step('verify_boundary', BoundaryVerification(0, 0, ws,
                    'verification_passed', 'passed', 'test', True))
        self.c.commit_checkpoint(archive_ids=('turn',))
        lease = self.c.authorize_rollover(ttl=60)
        self.c.request_compact(lease, lambda: CurrentState(0, 0, ws, lease.lease_id,
            self.c.snapshot.rollover_generation, self.c.snapshot.checkpoint.checkpoint_id, True),
            completion_timeout=.01)
        self.c._clock = lambda: lease.expires_at + 1
        self.c.poll_timeout()
        self.assertEqual(self.c.snapshot.state, State.AMBIGUOUS)
        self.event('turn/started', turn='query')
        before = self.c.snapshot
        self.assertTrue(self.tool('read_archive', {'archive_id': 'turn'})['success'])
        self.assertEqual(self.c.snapshot, before)
        with self.assertRaises(TransitionError):
            self.c.require_work()
        with self.assertRaises(TransitionError):
            self.c.request_compact(lease, lambda: None)

    def test_pending_overflow_discards_turn_without_unbounded_buffer(self):
        self.content()
        for n in range(300):
            self.event('item/started', item={'id': f'pending-{n}', 'type': 'commandExecution'})
        self.assertLessEqual(len(self.a._pending), 129)
        self.finish()
        self.assertEqual(self.c.search_archive(), ())

    def test_selection_omission_and_identity_rejection(self):
        self.a.select = lambda t: None
        self.content(); self.finish()
        self.assertEqual(self.c.search_archive(), ())
        self.host = RuntimeHost(self.c, archive=RuntimeArchive(self.c, self.sent.append,
            select=lambda t: replace(t, metadata=ArchiveMetadata('wrong', 'title', 'phase'))))
        self.content()
        with self.assertRaises(ValueError):
            self.finish()
        self.assertEqual(self.c.search_archive(), ())


if __name__ == '__main__':
    unittest.main()
