"""Serialized trusted-host fixtures; live acceptance is separate."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from yohaku import doctor
from yohaku.cli import _failure_guidance
from yohaku.controller import TransitionError
from yohaku.model import BoundaryVerification, State, WorkspaceRevision
from yohaku.orca_adapter import OrcaAdapter, OrcaLocalHost, ORCA_VERSION, CODEX_VERSION
from yohaku.persistence import SessionStore
from yohaku.recovery import CurrentContext
from yohaku.supervisor import YohakuSupervisor, SupervisorError


def row(kind, event=None, **payload):
    return dict(type=kind, digest=str((kind, event, payload)),
                payload=dict(payload, **({'type': event} if event else {})), item={})


class Host:
    session_id = 'orca-session'
    def __init__(self):
        self.calls = 0
        self.mutate = lambda d, r: None
        self.data = dict(orcaVersion=ORCA_VERSION, codexVersion=CODEX_VERSION, platform='win32',
            structured=True, runtime=dict(runtimeId='runtime', pid=10, startedAt=1),
            processes=[dict(pid=10, parentPid=1, startedAtMs=1, executable='C:\\Orca.exe'),
                       dict(pid=20, parentPid=10, startedAtMs=2, executable='C:\\codex.exe')],
            worktree=dict(id='wt2:local:fixture', path='C:\\workspace', workspaceId='workspace',
                          executionHostId='local', wslDistro=None),
            record=dict(sessionId=self.session_id, provider='codex',
                location=dict(workspaceId='workspace', executionHostId='local', wslDistro=None),
                providerHandleChain=[dict(linkId='link', handle=dict(provider='codex', threadId='thread'))],
                lease=dict(sessionId=self.session_id, runtimeKind='native', runtimeFence=1,
                    claimStatus='live', unreconciled=False, deathEvidence=None, provenHandleLinkId='link',
                    ownerProcess=dict(hostId='local', pid=20, processStartTimeMs=2),
                    handoffStage=None, handoffOperationId=None)),
            history=dict(ok=True, _meta=dict(runtimeId='runtime'), result=dict(ok=True,
                providerSession=dict(id='thread'), page=dict(fence=1, hasOlder=False, hasNewer=False,
                    liveCursor=dict(epoch='epoch', sequence=5), backgroundTasks=None,
                    items=[dict(body=dict(kind='turn', turnId='pre', state='completed', outcome='success'))],
                    submissions=[dict(dispatchState='accepted')]))),
            native=[row('session_meta', id='thread', cli_version=CODEX_VERSION),
                    row('event_msg', 'task_started', turn_id='pre'),
                    row('event_msg', 'task_complete', turn_id='pre')])

    def observe(self):
        return deepcopy(self.data)

    def rpc(self, method, params):
        assert method == 'agentSession.conversationCommand' and params['command'] == 'compact'
        self.calls += 1
        e = params['envelope']
        assert e['sessionId'] == self.session_id and e['expectedRuntimeFence'] == 1
        from hashlib import sha256
        canonical = json.dumps(dict(method=method, sessionId=self.session_id, fields={'command': 'compact'}),
                               sort_keys=True, separators=(',', ':'))
        assert e['payloadFingerprint'] == sha256(canonical.encode()).hexdigest()
        command = dict(command='compact', runtimeFence=1, operationId=e['clientOperationId'],
                       phase='committed', state='completed')
        self.data['record']['conversationCommand'] = command
        response = dict(ok=True, _meta=dict(runtimeId='runtime'),
                        result=dict(ok=True, replayed=False, fence=1, value=deepcopy(command)))
        delta = [row('event_msg', 'task_started', turn_id='compact'), row('compacted'),
                 row('event_msg', 'item_completed', thread_id='thread', turn_id='compact'),
                 row('event_msg', 'task_complete', turn_id='compact')]
        delta[2]['item'] = dict(type='ContextCompaction', id='item')
        self.data['native'] += delta
        page = self.data['history']['result']['page']
        page['liveCursor']['sequence'] = 10
        page['items'].append(dict(body=dict(kind='turn', turnId='compact', state='completed', outcome='success')))
        self.mutate(self.data, response)
        return response


class OrcaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=self.tmp.name)
        env.start()
        self.addCleanup(env.stop)
        self.store = SessionStore('thread', create=True)
        self.addCleanup(self.store.close)
        self.host = Host()
        self.adapter = OrcaAdapter(self.host, self.store)
        self.current = CurrentContext('task', 0, 1, WorkspaceRevision(1, 'done', ('task',)))
        self.evidence = BoundaryVerification(0, 1, self.current.workspace,
                                              'verification_passed', 'passed', 'fixture', True)
        self.cp = self.adapter.checkpoint(boundary_id='boundary', observe=lambda: self.current, evidence=self.evidence)
        self.supervisor = YohakuSupervisor()
        self.session = self.adapter.register(self.supervisor)

    def compact(self):
        return self.supervisor.request_transition(self.session, requester='orca',
            observe=lambda: self.current, now=lambda: 1)

    def test_transition_routes_one_orca_request_with_codex_observer(self):
        self.assertEqual(self.supervisor.resolve(self.session).name, 'orca')
        observers = self.supervisor.observers(self.session)
        self.assertEqual([o.name for o in observers], ['codex', 'orca'])
        self.assertIsNone(observers[0].transition)
        with self.assertRaisesRegex(SupervisorError, 'SUPERVISOR_ORCA_DIRECT_TRIGGER'):
            self.supervisor.request_transition(self.session, requester='codex')
        self.assertEqual(self.host.calls, 0)
        self.assertEqual(self.compact().state, State.ROLLOVER_OBSERVED)
        self.assertEqual(self.host.calls, 1)
        with self.assertRaisesRegex(SupervisorError, 'SUPERVISOR_DUPLICATE_REQUEST'):
            self.compact()
        with self.assertRaises(TransitionError):
            self.adapter.compact(observe=lambda: self.current, now=lambda: 1)
        self.assertEqual(self.host.calls, 1)
        self.assertEqual(self.store.read_checkpoint(self.cp.checkpoint_id), self.cp)
        s = self.adapter.core.snapshot
        with self.assertRaisesRegex(TransitionError, 'ORCA_RECOVERY_UNQUALIFIED'):
            self.adapter.offer_handoff(object())
        self.assertEqual(self.adapter.core.snapshot, s)
        self.assertIsNone(s.handoff)
        self.assertIsNone(s.receipt_evidence)
        self.assertIsNone(s.continuation_request_id)

    def test_identity_drift_rejected_before_dispatch(self):
        paths = [('record', 'sessionId'), ('record', 'providerHandleChain', 0, 'handle', 'threadId'),
                 ('runtime', 'runtimeId'), ('runtime', 'pid'), ('record', 'lease', 'runtimeFence'),
                 ('record', 'lease', 'ownerProcess', 'processStartTimeMs'),
                 ('history', 'result', 'page', 'liveCursor', 'epoch'),
                 ('history', 'result', 'page', 'liveCursor', 'sequence'),
                 ('processes', 1, 'parentPid'), ('worktree', 'id'), ('worktree', 'path'),
                 ('record', 'location', 'wslDistro'), ('orcaVersion',), ('codexVersion',)]
        original = self.host.observe()
        for path in paths:
            with self.subTest(path=path):
                self.host.data = deepcopy(original)
                target = self.host.data
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = -1 if isinstance(target[path[-1]], int) else 'foreign'
                with self.assertRaises(SupervisorError):
                    self.compact()
                self.assertEqual(self.host.calls, 0)
        self.host.data = original
        with self.assertRaises(SupervisorError):
            self.supervisor.request_transition(replace(self.session, ownership_source=None), requester='orca')

    def test_unsafe_boundary_never_dispatches(self):
        original = self.host.observe()
        def tool(d):
            d['history']['result']['page']['items'].append(dict(body=dict(kind='tool-call', state='running')))
        def approval(d):
            d['history']['result']['page']['items'].append(dict(body=dict(kind='approval', resolution={'state': 'pending'})))
        mutations = [tool, approval,
            lambda d: d['history']['result']['page'].update(backgroundTasks={'active': 1}),
            lambda d: d['history']['result']['page']['submissions'].append(dict(dispatchState='pending')),
            lambda d: d['history']['result']['page'].update(hasOlder=True),
            lambda d: d['history']['result']['page']['items'][0]['body'].update(state='running'),
            lambda d: d['native'].pop()]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.host.data = deepcopy(original)
                mutation(self.host.data)
                with self.assertRaises(TransitionError):
                    self.adapter.compact(observe=lambda: self.current, now=lambda: 1)
                self.assertEqual(self.host.calls, 0)

    def test_core_semantic_boundary_evidence_is_required(self):
        with self.assertRaises(TransitionError):
            self.adapter.checkpoint(boundary_id='other', observe=lambda: self.current,
                                    evidence=replace(self.evidence, integrity_window_verified=False))
        self.assertEqual(self.host.calls, 0)

    def test_admission_native_failure_or_ambiguity_remains_unconfirmed(self):
        mutations = [
            lambda d, r: d['native'].pop(),
            lambda d, r: d['native'].pop(-2),
            lambda d, r: d['native'].pop(-3),
            lambda d, r: d['native'].append(row('compacted')),
            lambda d, r: d['native'][-2]['payload'].update(thread_id='foreign'),
            lambda d, r: d['native'][-1]['payload'].update(turn_id='foreign'),
            lambda d, r: d['record']['conversationCommand'].update(failure={'kind': 'compactionUnconfirmed'}),
            lambda d, r: r['result'].update(replayed=True),
            lambda d, r: d['history']['result']['page']['items'][-1]['body'].update(outcome='failure'),
            lambda d, r: d['runtime'].update(runtimeId='new-runtime'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                # Each failure uses a fresh owner/store; no retries to manufacture success.
                with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, CODEX_HOME=tmp):
                    with SessionStore('thread', create=True) as store:
                        host = Host()
                        adapter = OrcaAdapter(host, store)
                        adapter.checkpoint(boundary_id='b', observe=lambda: self.current, evidence=self.evidence)
                        host.mutate = mutation
                        with self.assertRaises(TransitionError):
                            adapter.compact(observe=lambda: self.current, now=lambda: 1)
                        self.assertEqual(adapter.core.snapshot.state, State.AMBIGUOUS)
                        self.assertEqual(host.calls, 1)
                        with self.assertRaises(TransitionError):
                            adapter.compact(observe=lambda: self.current, now=lambda: 1)
                        self.assertEqual(host.calls, 1)

    def test_transport_uncertainty_never_retries(self):
        def fail(d, r):
            raise OSError('uncertain')
        self.host.mutate = fail
        with self.assertRaises(OSError):
            self.compact()
        self.assertEqual(self.adapter.core.snapshot.state, State.AMBIGUOUS)
        with self.assertRaises(SupervisorError):
            self.compact()
        self.assertEqual(self.host.calls, 1)

    def test_exact_profile_mismatch_has_specific_guidance(self):
        self.host.data['orcaVersion'] = '1.4.219'
        with self.assertRaisesRegex(TransitionError, 'ORCA_PROFILE_MISMATCH'):
            self.adapter._observe()
        self.assertEqual(self.host.calls, 0)

    def test_post_dispatch_unsafe_state_does_not_claim_no_compact(self):
        self.host.mutate = lambda d, r: d['history']['result']['page'].update(backgroundTasks={'active': 1})
        with self.assertRaisesRegex(TransitionError, 'ORCA_COMPLETION_AMBIGUOUS') as caught:
            self.compact()
        self.assertNotIn('No compact was sent', '\n'.join(caught.exception.__notes__))
        self.assertEqual(self.host.calls, 1)
        self.assertEqual(self.adapter.core.snapshot.state, State.AMBIGUOUS)

    def test_decision_write_failure_prevents_dispatch(self):
        with patch.object(self.store, '_write', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                self.compact()
        self.assertEqual(self.host.calls, 0)
        self.assertTrue(self.adapter.stopped)

    def test_doctor_active_owner_and_failure_ux(self):
        with patch('yohaku.doctor.shutil.which', return_value=None):
            out = doctor.render(supervisor=self.supervisor)
            static = doctor.render()
        self.assertIn('Ownership: Orca structured', out)
        self.assertIn('Provider authority: Codex', out)
        self.assertIn('Observers: codex, orca', out)
        self.assertIn('Profile: orca/structured/codex/local', out)
        self.assertIn('Recovery: unsupported on this profile', out)
        self.assertIn('Resume: unsupported on this profile', out)
        self.assertNotIn('Ownership: Orca structured', static)
        for code in ('ORCA_PROFILE_MISMATCH', 'ORCA_OWNERSHIP_MISMATCH', 'ORCA_FENCE_CHANGED',
                     'ORCA_BOUNDARY_UNSAFE', 'ORCA_COMPLETION_AMBIGUOUS', 'ORCA_RECOVERY_UNQUALIFIED',
                     'SUPERVISOR_ORCA_DIRECT_TRIGGER'):
            self.assertTrue(_failure_guidance(code))

    def test_local_host_reads_native_facts_without_prompt_contents(self):
        base = Path(self.tmp.name)
        runtime, records, native = (base / name for name in ('runtime.json', 'records.json', 'native.jsonl'))
        runtime.write_text(json.dumps(self.host.data['runtime']))
        records.write_text(json.dumps(dict(records={self.host.session_id: self.host.data['record']})))
        native.write_text(json.dumps(dict(type='session_meta', payload=dict(id='thread', cli_version=CODEX_VERSION,
                                                                           instructions='SECRET'))) + '\n')
        facts = {k: self.host.data[k] for k in ('orcaVersion', 'codexVersion', 'platform', 'structured', 'processes', 'worktree')}
        host = OrcaLocalHost(runtime_path=runtime, records_path=records, native_path=native,
            session_id=self.host.session_id, rpc=lambda m, p: self.host.data['history'], inspect=lambda m, r: facts)
        observed = host.observe()
        self.assertNotIn('SECRET', json.dumps(observed))
        self.assertEqual(observed['native'][0]['payload']['id'], 'thread')
