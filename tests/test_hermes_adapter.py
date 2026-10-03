"""Bounded local host/DB integration; not live Hermes acceptance."""

from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from yohaku.controller import TransitionError
from yohaku.hermes import HERMES_SOURCE, HERMES_VERSION
from yohaku.hermes_adapter import HermesCLIAdapter, digest
from yohaku.model import State, WorkspaceRevision
from yohaku.persistence import SessionStore
from yohaku.recovery import CurrentContext, RecoveredData, ResumeProof
from yohaku.supervisor import YohakuSupervisor


class HermesAdapterTests(unittest.TestCase):
    def test_supervisor_routes_standalone_to_existing_compress(self):
        supervisor = YohakuSupervisor()
        registration = supervisor.register_builtin('hermes', self.a)
        self.checkpoint()
        supervisor.request_transition(registration.session, requester='hermes',
                                      observe=self.observe, now=lambda: 1)
        self.assertEqual(self.a.core.snapshot.state, State.ROLLOVER_OBSERVED)
        self.assertEqual(self.a.manual_requests, 1)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, CODEX_HOME=self.tmp.name)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = SessionStore('session', create=True)
        self.addCleanup(self.store.close)
        self.db = Path(self.tmp.name) / 'state.db'
        with sqlite3.connect(self.db) as c:
            c.execute('create table messages(session_id text, active integer)')
            c.execute('insert into messages values (?, 0)', ('session',))
        c.close()
        self.host = SimpleNamespace(session_id='session', conversation_history=[],
            agent=SimpleNamespace(compression_enabled=False, _current_turn_id='turn',
                context_compressor=SimpleNamespace(compression_count=0)))
        self.a = HermesCLIAdapter(self.host, self.store, version=HERMES_VERSION,
            source_commit=HERMES_SOURCE, exclusive_fresh_session=True,
            tool_name='fixture', db_path=self.db)
        self.context = CurrentContext('task', 0, 1, WorkspaceRevision(1, 'before', ('state',)))
        self.reader = SimpleNamespace(get_messages_as_conversation=lambda sid: self.host.conversation_history,
                                      close=lambda: None)
        self.module = patch.dict('sys.modules', hermes_state=SimpleNamespace(SessionDB=lambda **kw: self.reader))
        self.module.start()
        self.addCleanup(self.module.stop)
        def compress(command):
            self.assertEqual(command, '/compress')
            self.host.conversation_history = [{'role': 'user', 'content': 'compressed'}]
            self.host.agent.context_compressor.compression_count = 1
        self.host._manual_compress = compress

    def observe(self):
        return self.context

    def checkpoint(self):
        self.a.checkpoint(boundary_id='boundary', observe=self.observe, evidence_ref='fixture')

    def completed(self):
        self.checkpoint()
        self.a.compress(observe=self.observe, now=lambda: 1)

    def tool(self, cid, handler, *, status='ok', incorporate=True):
        kw = dict(tool_name='fixture', tool_call_id=cid, turn_id=self.a.turn_id,
                  session_id='session', api_request_id='api-' + cid)
        self.a.pre_tool(**kw)
        result = json.dumps(handler())
        self.a.post_tool(**kw, status=status, result=result)
        self.assertEqual(len(self.a.pending), 1)
        if incorporate:
            self.a.observe_request({'input': [{'type': 'function_call_output', 'call_id': cid, 'output': result}]})

    def continued(self, *, receipt=True, fields=None, fresh=True, action=True):
        def chat(prompt):
            self.host.agent._current_turn_id = 'continue-turn'
            self.a.observe_request({'input': [{'role': 'user', 'content': prompt}]})
            if receipt:
                self.tool('ack', lambda: self.a.acknowledge(fields or self.a.receipt_fields()))
            if fresh:
                self.tool('read', lambda: (self.a.reconcile_fresh(self.observe), {'state': 'fresh'})[1])
            if action:
                def work():
                    self.a.require_action()
                    self.context = replace(self.context, execution_revision=2,
                        workspace=WorkspaceRevision(2, 'after', ('state',)))
                    return {'completed': ['A', 'B']}
                self.tool('action', work)
            self.a.observe_terminal(turn_id='continue-turn', session_id='session', failed=False, interrupted=False)
        self.host.chat = chat
        recovered = RecoveredData('task', ('A',), 'A then B', ('B',), 'read then B', ('state',))
        self.a.continue_task(recovered, cwd=self.tmp.name, instructions='bounded fixture')

    def proof(self, document, tools):
        return ResumeProof(self.context, 'fixture-assessment', ('read',), ('action',),
                           True, True, True, True, True)

    def test_complete_chain_keeps_existing_checkpoint_handoff_contract(self):
        self.completed()
        self.assertEqual(self.a.core.snapshot.state, State.ROLLOVER_OBSERVED)
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)
        cp = self.a.core.snapshot.checkpoint
        self.assertEqual(self.store.read_checkpoint(cp.checkpoint_id), cp)
        self.continued()
        self.assertEqual(self.a.core.snapshot.state, State.HANDOFF_RECEIVED)
        self.assertEqual(self.store.read_handoff(self.a.document.handoff_id), self.a.document)
        self.a.verify_resume(observe=self.observe, assess=self.proof)
        self.assertEqual(self.a.core.snapshot.state, State.RESUME_VERIFIED)
        self.assertEqual(list(self.store.journal.iterdir()), [])
        with self.assertRaises(TransitionError):
            self.a.compress(observe=self.observe, now=lambda: 1)

    def test_context_assist_failure_preserves_receipt_and_resume(self):
        self.completed()
        with patch('yohaku.context_assist.build_task_context', side_effect=RuntimeError('builder')) as build:
            self.continued()
        build.assert_called_once()
        self.assertEqual(self.a.handoff_text, self.a.document.render(context_assist=False))
        self.a.verify_resume(observe=self.observe, assess=self.proof)
        self.assertEqual(self.a.core.snapshot.state, State.RESUME_VERIFIED)

    def test_native_return_and_count_without_history_change_are_ambiguous(self):
        self.checkpoint()
        self.host._manual_compress = lambda cmd: setattr(self.host.agent.context_compressor, 'compression_count', 1)
        with self.assertRaises(TransitionError):
            self.a.compress(observe=self.observe, now=lambda: 1)
        self.assertEqual(self.a.core.snapshot.state, State.AMBIGUOUS)
        self.assertTrue(self.a.stopped)

    def test_db_mismatch_cannot_complete(self):
        self.checkpoint()
        self.reader.get_messages_as_conversation = lambda sid: []
        with self.assertRaises(TransitionError):
            self.a.compress(observe=self.observe, now=lambda: 1)
        self.assertEqual(self.a.core.snapshot.state, State.AMBIGUOUS)

    def test_behavior_without_receipt_stays_unverified(self):
        self.completed()
        self.continued(receipt=False, fresh=False, action=False)
        self.assertEqual(self.a.core.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)
        with self.assertRaises(TransitionError):
            self.a.verify_resume(observe=self.observe, assess=self.proof)

    def test_wrong_receipt_stops_before_read_or_action(self):
        self.completed()
        with self.assertRaises(TransitionError):
            self.continued(fields={'checkpoint_hash': 'wrong'})
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)
        self.assertNotIn('action', self.a.tools)

    def test_action_requires_incorporated_fresh_read(self):
        self.completed()
        with self.assertRaises(TransitionError):
            self.continued(fresh=False)
        self.assertNotEqual(self.a.core.snapshot.state, State.RESUME_VERIFIED)

    def test_false_assessment_cannot_verify_resume(self):
        self.completed()
        self.continued()
        with self.assertRaises(TransitionError):
            self.a.verify_resume(observe=self.observe, assess=lambda d, t:
                replace(self.proof(d, t), completed_work_not_repeated=False))
        self.assertEqual(self.a.core.snapshot.state, State.HANDOFF_RECEIVED)

    def test_pending_result_prevents_boundary_and_payload_mismatch_stops(self):
        self.a.foreground = True
        self.a.observe_request({'input': []})
        self.tool('a', lambda: {'result': 'one'}, incorporate=False)
        self.a.foreground = False
        with self.assertRaises(TransitionError):
            self.checkpoint()
        self.a.foreground = True
        with self.assertRaises(TransitionError):
            self.a.observe_request({'input': [{'type': 'function_call_output', 'call_id': 'a', 'output': 'wrong'}]})

    def test_receipt_cannot_be_accepted_without_tool_handler(self):
        self.completed()
        with self.assertRaises(TransitionError):
            self.a.acknowledge({})
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)

    def test_changed_final_state_prevents_compression_dispatch(self):
        self.checkpoint()
        self.context = replace(self.context, execution_revision=2,
                               workspace=WorkspaceRevision(2, 'changed', ('state',)))
        with self.assertRaises(TransitionError):
            self.a.compress(observe=self.observe, now=lambda: 1)
        self.assertEqual(self.a.manual_requests, 0)

    def test_handler_without_pre_tool_observation_stops(self):
        self.a.foreground = True
        with self.assertRaises(TransitionError):
            self.a.require_tool()
        self.assertTrue(self.a.stopped)

    def test_chat_return_without_native_terminal_is_not_idle_proof(self):
        self.host.chat = lambda prompt: None
        with self.assertRaises(TransitionError):
            self.a.chat('fixture')
        self.assertTrue(self.a.stopped)


if __name__ == '__main__':
    unittest.main()
