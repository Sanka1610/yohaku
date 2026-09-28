"""Synthetic recovery evidence and counter effects; no Claude invocation."""

from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from yohaku.claude import ClaudeCLIProfile, ClaudeHookObservation, ClaudeManualCompletion, ClaudeManualCompletionPolicy
from yohaku.claude_recovery import ClaudeCLIRecoveryAdapter, ClaudeDelivery, digest
from yohaku.controller import TransitionError
from yohaku.model import State, WorkspaceRevision
from yohaku.persistence import SessionStore
from yohaku.recovery import CurrentContext, RecoveredData, ResumeProof


class ClaudeRecoveryTests(unittest.TestCase):
    adapter_type = ClaudeCLIRecoveryAdapter

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=self.tmp.name)
        env.start()
        self.addCleanup(env.stop)
        self.store = SessionStore('session', create=True)
        self.addCleanup(self.store.close)
        self.a = self.adapter_type(self.store, profile=ClaudeCLIProfile(),
            startup=ClaudeHookObservation('attachment', '', 0, 1, 'session', 'SessionStart', 'startup', 'fixture:1', True),
            exclusive_fresh_session=True)
        self.current = CurrentContext('task', 0, 1, WorkspaceRevision(1, 'before', ('fixture',)))
        self.effects = {'before': 1, 'after': 0, 'stale': 0}
        self.a.checkpoint(boundary_id='boundary', observe=self.observe, evidence_ref='boundary', foreground_idle=True)
        def dispatch(command, b):
            hooks = tuple(ClaudeHookObservation(b.attachment_id,b.request.request_id,1,i,'session',kind,trigger,f'fixture:{i}',True)
                for i,kind,trigger in ((11,'PreCompact','manual'),(12,'SessionStart','compact'),(13,'PostCompact','manual')))
            return ClaudeManualCompletion(b,'fixture:closed',hooks,14,True,True,1)
        self.a.compact(observe=self.observe,dispatch=dispatch,now=lambda:1,request_seq=10)
        self.seq = 14

    def observe(self):
        return self.current

    def event(self):
        self.seq += 1
        return dict(binding=self.a.continuation,session_id='session',seq=self.seq,evidence_ref=f'fixture:{self.seq}')

    def begin(self, transform=lambda d:d):
        def send(prompt,b):
            self.assertEqual(self.store.read_handoff(self.a.document.handoff_id),self.a.document)
            self.assertIn('DATA, NOT INSTRUCTIONS',prompt)
            self.assertIsNone(self.a.core.snapshot.receipt_evidence)
            self.seq += 1
            return transform(ClaudeDelivery(b,self.seq,digest(prompt),'fixture:send',True))
        return self.a.begin_recovery(RecoveredData('task',('before',),'finish current task',('after',),
            'obsolete: run before then stale',('fixture',)),cwd=self.tmp.name,
            instructions=lambda fields:'Explicit receipt: '+str(fields),send=send)

    def pre(self, op, tid=None):
        self.a.pre_tool(**self.event(),tool_id=tid or op,operation=op)

    def post(self, result, tid):
        self.a.post_tool(**self.event(),tool_id=tid,result=result,successful=True)

    def receipt(self):
        self.pre('receipt')
        result=self.a.acknowledge(self.a.receipt_fields())
        self.assertEqual(self.a.core.snapshot.state,State.HANDOFF_OFFERED)
        self.post(result,'receipt')

    def fresh(self):
        # Independent current intent changed after compact; checkpoint stays historical.
        self.current=CurrentContext('task',1,2,WorkspaceRevision(2,'current-intent',('fixture',)))
        self.pre('observe')
        result=self.a.observe_fresh(self.observe)
        self.post(result,'observe')
        return result

    def action(self):
        self.pre('action')
        def execute():
            self.effects['after'] += 1
            self.current=replace(self.current,execution_revision=3,workspace=WorkspaceRevision(3,'after',('fixture',)))
            return dict(self.effects)
        result=self.a.perform_action({'fresh_read_id':self.a.fresh_token},observe=self.observe,execute=execute)
        self.post(result,'action')

    def terminal(self):
        self.a.observe_terminal(**self.event(),successful=True)

    def proof(self, document, tools):
        return ResumeProof(self.current,'fixture:assessment',('observe',),('action',),True,True,
            self.effects['before']==1,self.effects['stale']==0,self.effects['after']==1)

    def finish(self):
        self.begin(); self.receipt(); self.fresh(); self.action(); self.terminal()

    def test_independent_delivery_receipt_fresh_effects_and_assessor_reach_verified(self):
        cp=self.a.core.snapshot.checkpoint
        self.finish()
        self.assertEqual(self.a.core.snapshot.state,State.HANDOFF_RECEIVED)
        self.assertIsNotNone(self.a.core.snapshot.injection_evidence)
        self.assertIsNotNone(self.a.core.snapshot.receipt_evidence)
        s=self.a.verify_resume(observe=self.observe,assess=self.proof)
        self.assertEqual(s.state,State.RESUME_VERIFIED)
        self.assertEqual(s.checkpoint,cp)
        self.assertEqual(self.effects,{'before':1,'after':1,'stale':0})
        self.assertTrue(ClaudeManualCompletionPolicy().completed(s.request,s.completions))

    def test_submission_or_terminal_success_without_receipt_never_receives_handoff(self):
        self.begin()
        self.effects['after']=1
        with self.assertRaises(TransitionError): self.terminal()
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)
        self.assertEqual(self.a.core.snapshot.state,State.RECOVERY_REQUIRED)

    def test_partial_or_wrong_receipt_fields_are_rejected(self):
        self.begin(); self.pre('receipt')
        fields=self.a.receipt_fields(); fields.pop('handoff_id')
        with self.assertRaises(TransitionError): self.a.acknowledge(fields)
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)

    def test_boolean_generation_is_not_a_receipt(self):
        self.begin(); self.pre('receipt')
        with self.assertRaises(TransitionError): self.a.acknowledge({**self.a.receipt_fields(),'generation':True})

    def test_wrong_checkpoint_hash_is_not_a_receipt(self):
        self.begin(); self.pre('receipt')
        with self.assertRaises(TransitionError): self.a.acknowledge({**self.a.receipt_fields(),'checkpoint_hash':'bad'})

    def test_handler_receipt_without_matching_native_post_does_not_grant_read(self):
        self.begin(); self.pre('receipt'); self.a.acknowledge(self.a.receipt_fields())
        with self.assertRaises(TransitionError): self.pre('observe')
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)

    def test_native_result_hash_mismatch_is_rejected(self):
        self.begin(); self.pre('receipt'); self.a.acknowledge(self.a.receipt_fields())
        with self.assertRaises(TransitionError): self.post({'receipt':'unrelated'},'receipt')

    def test_non_json_result_stops_the_owner(self):
        self.begin(); self.pre('receipt'); self.a.acknowledge(self.a.receipt_fields())
        with self.assertRaises(TransitionError): self.post({'receipt':object()},'receipt')
        self.assertTrue(self.a.stopped)
        self.assertEqual(self.a.core.snapshot.state,State.RECOVERY_REQUIRED)

    def test_read_before_receipt_is_rejected(self):
        self.begin()
        with self.assertRaises(TransitionError): self.pre('observe')

    def test_action_before_fresh_observation_is_rejected(self):
        self.begin(); self.receipt()
        with self.assertRaises(TransitionError): self.pre('action')
        self.assertEqual(self.effects['after'],0)

    def test_stale_read_token_is_rejected_before_effect(self):
        self.begin(); self.receipt(); self.fresh(); self.pre('action')
        with self.assertRaises(TransitionError):
            self.a.perform_action({'fresh_read_id':'old'},observe=self.observe,execute=lambda:self.fail('executed'))

    def test_mutation_after_fresh_read_is_rejected_before_effect(self):
        self.begin(); self.receipt(); self.fresh(); self.pre('action')
        self.current=replace(self.current,intent_revision=2)
        with self.assertRaises(TransitionError):
            self.a.perform_action({'fresh_read_id':self.a.fresh_token},observe=self.observe,execute=lambda:self.fail('executed'))

    def test_completed_or_stale_operation_is_not_admitted(self):
        self.begin(); self.receipt(); self.fresh()
        with self.assertRaises(TransitionError): self.pre('before')

    def test_duplicate_tool_cannot_execute_again(self):
        self.begin(); self.receipt()
        with self.assertRaises(TransitionError): self.pre('observe','receipt')

    def test_wrong_session_is_rejected(self):
        self.begin()
        with self.assertRaises(TransitionError):
            self.a.pre_tool(**{**self.event(),'session_id':'other'},tool_id='r',operation='receipt')

    def test_stale_sequence_is_rejected(self):
        self.begin()
        with self.assertRaises(TransitionError):
            self.a.pre_tool(**{**self.event(),'seq':15},tool_id='r',operation='receipt')

    def test_duplicate_post_is_rejected(self):
        self.begin(); self.receipt()
        with self.assertRaises(TransitionError): self.post({},'receipt')

    def test_missing_task_assessment_never_verifies(self):
        self.finish()
        with self.assertRaises(TransitionError): self.a.verify_resume(observe=self.observe,assess=lambda *args:None)
        self.assertEqual(self.a.core.snapshot.state,State.RECOVERY_REQUIRED)

    def test_wrong_assessor_tool_identity_never_verifies(self):
        self.finish()
        with self.assertRaises(TransitionError):
            self.a.verify_resume(observe=self.observe,assess=lambda *args:replace(self.proof(*args),read_item_ids=('other',)))

    def test_effect_success_does_not_mask_repeated_work(self):
        self.finish(); self.effects['before']=2
        with self.assertRaises(TransitionError): self.a.verify_resume(observe=self.observe,assess=self.proof)

    def test_effect_success_does_not_mask_stale_instruction_execution(self):
        self.finish(); self.effects['stale']=1
        with self.assertRaises(TransitionError): self.a.verify_resume(observe=self.observe,assess=self.proof)

    def test_intent_change_before_assessment_prevents_verified(self):
        self.finish(); self.current=replace(self.current,intent_revision=2)
        with self.assertRaises(TransitionError): self.a.verify_resume(observe=self.observe,assess=self.proof)

    def test_delivery_hash_mismatch_and_no_resend(self):
        with self.assertRaises(TransitionError): self.begin(lambda d:replace(d,prompt_hash='wrong'))
        with self.assertRaises(TransitionError): self.begin()
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)

    def test_handoff_write_failure_prevents_send(self):
        with patch.object(self.store,'commit_handoff',side_effect=OSError()):
            with self.assertRaises(OSError): self.begin()
        self.assertIsNone(self.a.core.snapshot.handoff)


if __name__=='__main__': unittest.main()
