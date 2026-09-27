"""Local native rollover contracts; live auto-compaction is separate evidence."""
from dataclasses import replace
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from yohaku.codec import decode, encode
from yohaku.companion import CompanionController
from yohaku.controller import TransitionError
from yohaku.model import BoundaryVerification, Request, State, WorkspaceRevision
from yohaku.recovery import CurrentContext, EmergencyDelta, RecoveredData, ResumeProof
from yohaku.runtime import RuntimeHost


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=self.tmp.name);env.start();self.addCleanup(env.stop)
        self.sent = []
        self.c = CompanionController('thread', self.sent.append, create=True)
        self.addCleanup(lambda: self.c.close())
        self.ws = WorkspaceRevision(0, 'old', ('task.json',))
        for op,args in [('propose_boundary', ('old-boundary',)), ('arm_barrier', ()), ('begin_quiescence_check', ())]:
            self.c.step(op,*args)
        self.c.step('observe_quiescence', relevant_work_remaining=False)
        self.c.step('capture_workspace', self.ws)
        self.c.step('verify_boundary', BoundaryVerification(0,0,self.ws,'verification_passed','passed','old-test',True))
        self.cp = self.c.commit_checkpoint()
        self.lease = self.c.authorize_rollover(ttl=60)
        self.c.step('invalidate', 'work advances')
        self.current = CurrentContext('task',1,1,WorkspaceRevision(1,'new',('task.json',)))
        self.recovered = RecoveredData('task',('STEP_A',),'Finish task',('recheck current',),'STEP_B OLD',('task.json',))
        self.host = RuntimeHost(self.c, work_cwd=self.tmp.name)
        self.native = self.host.enable_native_recovery(capture=self.capture, settle=self.settle,
            observe=lambda:self.current, recovered=self.recovered)
        self.event('turn/started', turn={'id':'turn'})

    def capture(self, checkpoint_id, pending):
        return EmergencyDelta('delta',checkpoint_id,'task',1,1,self.current.workspace,
            ('STEP_B completed after checkpoint; STEP_C remains',),tuple(k.tool_use_id for k in pending),'fixture-state')

    def settle(self, delta):
        for k in self.host.work.pending_results:
            self.host.work.incorporate(k,execution_complete=True,evidence_ref='terminal-fixture')
        return replace(self.recovered, completed_work=('STEP_A','STEP_B'))

    def event(self, method, **p):
        p.setdefault('threadId','thread');p.setdefault('turnId','turn')
        self.host.receive({'method':method,'params':p})

    def hook(self,name,**p):
        return self.host.deliver({'hook_event_name':name,'session_id':'thread',
            'turn_id':'turn','cwd':self.tmp.name,**p})

    def precompact(self):
        self.event('hook/started', run={'id':'pre','eventName':'preCompact'})
        out=self.hook('PreCompact',trigger='auto')
        self.event('hook/completed',run={'id':'pre','eventName':'preCompact','status':'completed'})
        return out

    def completed(self):
        self.event('item/started',item={'id':'compact','type':'contextCompaction'})
        self.event('item/completed',item={'id':'compact','type':'contextCompaction'})
        self.event('hook/started',run={'id':'post','eventName':'postCompact'})
        self.event('hook/completed',run={'id':'post','eventName':'postCompact','status':'completed'})

    def test_stale_checkpoint_unverified_delta_same_turn_resume(self):
        self.hook('PreToolUse',tool_use_id='old-tool',tool_name='Bash')
        self.hook('PostToolUse',tool_use_id='old-tool',tool_name='Bash')
        self.assertEqual(self.precompact(),{})
        self.assertEqual(self.c.snapshot.state,State.AMBIGUOUS)
        self.assertIsNone(self.c.snapshot.lease)
        self.assertEqual(self.c.snapshot.checkpoint,self.cp)
        self.assertIsNone(self.c.snapshot.verification)
        delta=json.loads((self.c.store.path/'emergency/delta.json').read_text())['payload']['delta']
        self.assertEqual(delta['delta_status'],'unverified')
        self.assertEqual(delta['pending_tool_ids'],['old-tool'])
        self.assertEqual(self.hook('PreToolUse',tool_use_id='blocked',tool_name='Bash')['hookSpecificOutput']['permissionDecision'],'deny')
        self.completed()
        self.assertEqual(self.c.snapshot.state,State.ROLLOVER_OBSERVED)
        self.event('hook/started',run={'id':'session','eventName':'sessionStart'})
        self.assertEqual(self.c.snapshot.state,State.HANDOFF_OFFERED)
        self.assertEqual(self.c.snapshot.handoff.continuation_turn_id,'turn')
        self.assertEqual(self.sent,[])
        doc=self.c.recovery.document
        text=self.hook('SessionStart',source='compact')['hookSpecificOutput']['additionalContext']
        self.assertIn('"checkpoint_current": false',text)
        self.assertIn('"checkpoint_freshness": "stale"',text)
        self.assertIn('"delta_status": "unverified"',text)
        self.assertIn('DATA, NOT INSTRUCTIONS',text)
        self.event('hook/completed',run={'id':'session','eventName':'sessionStart','status':'completed'})
        self.event('item/completed',item={'id':'ack','type':'agentMessage','text':f'YOH_ACK:{doc.handoff_id}:{self.c.snapshot.rollover_generation}'})
        for ident in ('read','act'):
            self.event('item/completed',item={'id':ident,'type':'commandExecution','status':'completed','exitCode':0})
        self.event('turn/completed',turn={'id':'turn','status':'completed','error':None})
        self.c.recovery.verify(observe=lambda:self.current,assess=lambda d,i:ResumeProof(
            self.current,'fixture-current-effects',('read',),('act',),True,True,True,True,True))
        self.assertEqual(self.c.snapshot.state,State.RESUME_VERIFIED)
        self.assertEqual(self.c.store.read_checkpoint(self.cp.checkpoint_id),self.cp)
        self.assertEqual(self.c.recovery.document.recovered.emergency.delta_status,'unverified')
        self.host.receive(None)
        self.assertEqual(self.c.snapshot.state,State.RESUME_VERIFIED)

    def test_missing_precompact_stops_and_denies_work(self):
        self.event('item/started',item={'id':'compact','type':'contextCompaction'})
        self.assertEqual(self.c.snapshot.state,State.FAILED)
        self.assertEqual(self.hook('SessionStart',source='compact'),{'continue':False})
        with self.assertRaises(TransitionError):self.c.require_work()
        self.assertEqual(self.sent,[])

    def test_missing_or_failed_completion_cannot_offer_handoff(self):
        self.precompact()
        self.event('item/started',item={'id':'compact','type':'contextCompaction'})
        self.event('hook/completed',run={'id':'post','eventName':'postCompact','status':'failed'})
        self.event('hook/started',run={'id':'session','eventName':'sessionStart'})
        self.assertEqual(self.c.snapshot.state,State.AMBIGUOUS)
        self.assertIsNone(self.c.snapshot.handoff)
        self.assertEqual(self.hook('SessionStart',source='compact'),{'continue':False})

    def test_active_or_unincorporated_work_cannot_resume(self):
        self.hook('PreToolUse',tool_use_id='active',tool_name='Bash')
        self.assertEqual(self.precompact(),{'continue':False})
        self.assertIsNone(self.native.delta)
        self.assertEqual(self.c.snapshot.state,State.FAILED)

    def test_stale_current_observation_rejected_after_native_complete(self):
        self.precompact();self.completed()
        self.current=CurrentContext('task',0,0,self.ws)
        self.event('hook/started',run={'id':'session','eventName':'sessionStart'})
        self.assertEqual(self.c.snapshot.state,State.RECOVERY_REQUIRED)
        self.assertIsNone(self.c.snapshot.handoff)
        self.assertEqual(self.sent,[])

    def test_restart_preserves_origin_but_never_infers_native_provenance(self):
        self.precompact();self.completed()
        self.event('hook/started',run={'id':'session','eventName':'sessionStart'})
        self.c.close();self.c=CompanionController('thread',self.sent.append)
        self.assertEqual(self.c.snapshot.request.origin,'native_auto')
        self.assertEqual(self.c.snapshot.state,State.RECOVERY_REQUIRED)
        self.assertIsNone(self.c.snapshot.lease)
        with self.assertRaises(TransitionError):self.c.recovery.reconcile_runtime({'id':'thread','turns':[]})
        self.assertEqual(self.sent,[])

    def test_native_cannot_complete_pending_manual_request(self):
        from yohaku.companion import CurrentState
        self.assertEqual(self.host.work.quiesce('manual-boundary'),State.WORKSPACE_SNAPSHOT)
        self.c.step('capture_workspace',self.ws)
        self.c.step('verify_boundary',BoundaryVerification(0,0,self.ws,'verification_passed','passed','test',True))
        cp=self.c.commit_checkpoint();lease=self.c.authorize_rollover(ttl=60)
        self.host.request_compact(lease,lambda:CurrentState(0,0,self.ws,lease.lease_id,
            self.c.snapshot.rollover_generation,cp.checkpoint_id,True))
        request=self.c.snapshot.request
        self.assertEqual(self.precompact(),{'continue':False})
        self.completed()
        self.assertEqual(self.c.snapshot.request,request)
        self.assertEqual(self.c.snapshot.state,State.AMBIGUOUS)
        self.assertIsNone(self.c.snapshot.binding)
        self.assertEqual(self.c.snapshot.completions,())
        self.assertEqual(len(self.sent),1)

    def test_timeout_never_grants_native_continuation(self):
        self.precompact()
        self.native.deadline=0
        self.native.poll()
        self.completed()
        self.assertTrue(self.native.stopped)
        self.assertEqual(self.c.snapshot.state,State.AMBIGUOUS)
        self.assertIsNone(self.c.snapshot.handoff)
        self.assertEqual(self.sent,[])

    def test_capture_failure_and_pending_results_block_recovery(self):
        self.native.capture=lambda cp,keys: (_ for _ in ()).throw(RuntimeError('unavailable'))
        self.assertEqual(self.precompact(),{'continue':False})
        self.assertEqual(self.c.snapshot.state,State.FAILED)
        self.assertIsNone(self.native.delta)

    def test_unincorporated_result_blocks_handoff(self):
        self.hook('PreToolUse',tool_use_id='prior',tool_name='Bash')
        self.hook('PostToolUse',tool_use_id='prior',tool_name='Bash')
        self.precompact();self.completed()
        self.native.settle=lambda delta:None
        self.event('hook/started',run={'id':'session','eventName':'sessionStart'})
        self.assertTrue(self.native.stopped)
        self.assertIsNone(self.c.snapshot.handoff)
        self.assertEqual(self.c.snapshot.state,State.RECOVERY_REQUIRED)

    def test_controller_request_format_is_unchanged(self):
        old={'request_id':'r','thread_id':'t','transition_id':'x','boundary_id':'b',
             'checkpoint_id':'c','lease_id':'l','rollover_generation':1}
        self.assertEqual(encode(decode(Request,old)),old)
        with self.assertRaises(ValueError):decode(Request,dict(old,origin='native_auto'))

    def test_conflicting_item_and_second_compact_stop(self):
        self.precompact()
        self.event('item/started',item={'id':'compact','type':'contextCompaction'})
        self.event('item/completed',item={'id':'different','type':'contextCompaction'})
        self.assertTrue(self.native.stopped)
        self.assertEqual(self.c.snapshot.state,State.AMBIGUOUS)


if __name__=='__main__':unittest.main()
