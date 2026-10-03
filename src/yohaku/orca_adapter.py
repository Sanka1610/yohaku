"""Pinned Orca-owned structured Codex transition; recovery is unqualified.

The embedding host serializes all calls and supplies local Windows RPC/process
readers. One Core/store, one request, no direct Codex transport, no restart.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import time
from uuid import uuid4

from .controller import Controller, TransitionError
from .model import BoundaryVerification, Request, State
from .recovery import CurrentContext
from .supervisor import AdapterRegistration, OBSERVER, TRIGGER, SessionProfile

ORCA_VERSION = '1.4.218'
CODEX_VERSION = '0.159.0-alpha.12.1'
ORCA_PROFILE = 'orca/structured/codex/local'


def failure_guidance(code):
    return {
        'ORCA_PROFILE_MISMATCH': 'Outside the exact qualified Orca structured Codex local profile. No transition was started.',
        'ORCA_OWNERSHIP_MISMATCH': 'The Orca session no longer matches the provider-native Codex thread. Yohaku stopped before transition.',
        'ORCA_FENCE_CHANGED': 'The Orca runtime/session fence changed during transition qualification. Yohaku stopped. No retry was attempted.',
        'ORCA_BOUNDARY_UNSAFE': 'Fresh structured and native state did not establish an idle boundary. No compact was sent.',
        'ORCA_COMPLETION_AMBIGUOUS': 'Yohaku could not correlate a unique provider-native completion with Orca completion and fresh state. The transition remains unconfirmed. No second compact was sent.',
        'ORCA_RECOVERY_UNQUALIFIED': 'Orca handoff receipt and gated task continuation are not qualified. Yohaku stopped before sending recovery input. Preserve the checkpoint and transition evidence.',
    }.get(code)


def _reject(code):
    error = TransitionError(code)
    error.add_note(failure_guidance(code))
    raise error


class OrcaLocalHost:
    """Explicit paths and trusted Windows readers; no discovery or config writes.

    rpc(method, params) returns the full Orca RPC response and checks its request
    identity. inspect(runtime, record) freshly reads Windows process identities,
    executable versions and the selected worktree, returning those raw facts.
    Neither reader may attach a second Codex connection or retry mutations.
    """
    def __init__(self, *, runtime_path, records_path, native_path, session_id, rpc, inspect):
        self.runtime_path = Path(runtime_path)
        self.records_path = Path(records_path)
        self.native_path = Path(native_path)
        self.session_id = session_id
        self.rpc, self.inspect = rpc, inspect

    def observe(self):
        runtime = json.loads(self.runtime_path.read_text())
        record = json.loads(self.records_path.read_text())['records'][self.session_id]
        if record['lease']['claimStatus'] != 'live':
            _reject('ORCA_OWNERSHIP_MISMATCH')  # Do not restore a dormant session.
        history = self.rpc('agentSession.history',
            dict(sessionId=self.session_id, direction='tail', limit=100))
        identity = self.inspect(runtime, record)
        rows = []
        for line in self.native_path.read_bytes().splitlines():
            row = json.loads(line)
            p = row.get('payload', {})
            # Keep only identity/lifecycle facts and hashes; never archive prompts.
            item = p.get('item', {})
            rows.append(dict(type=row['type'], digest=sha256(line).hexdigest(),
                payload={k: p[k] for k in ('id', 'cli_version', 'turn_id', 'thread_id', 'type') if k in p},
                item={k: item[k] for k in ('type', 'id') if k in item}))
        # Detect a runtime/lease change during the multi-surface read itself.
        latest = json.loads(self.runtime_path.read_text())
        rerecord = json.loads(self.records_path.read_text())['records'][self.session_id]
        keys = ('sessionId', 'location', 'provider', 'providerHandleChain')
        leasekeys = ('runtimeFence', 'ownerProcess', 'claimStatus', 'provenHandleLinkId')
        if (any(latest[k] != runtime[k] for k in ('runtimeId', 'pid', 'startedAt'))
                or any(rerecord[k] != record[k] for k in keys)
                or any(rerecord['lease'][k] != record['lease'][k] for k in leasekeys)):
            _reject('ORCA_FENCE_CHANGED')
        return dict(runtime={k: runtime[k] for k in ('runtimeId', 'pid', 'startedAt')},
                    record=rerecord, history=history, native=rows, **identity)


@dataclass(frozen=True)
class OrcaBinding:
    runtime: tuple
    processes: tuple
    worktree: tuple
    session_id: str
    provider_thread: str
    handle_link: str
    fence: int
    epoch: str


@dataclass(frozen=True)
class OrcaCompletionBinding:
    request: Request
    owner: OrcaBinding
    operation_id: str


@dataclass(frozen=True)
class OrcaCompletion:
    binding: OrcaCompletionBinding
    evidence_ref: str
    turn_id: str
    item_id: str
    native_digests: tuple[str, ...]
    kind: str = 'orca/structured-codex-completion'


class OrcaCompletionPolicy:
    def valid_binding(self, binding):
        return (isinstance(binding, OrcaCompletionBinding)
                and binding.request.origin == 'controller'
                and binding.request.rollover_generation == 1
                and binding.request.thread_id == binding.owner.provider_thread
                and bool(binding.operation_id))

    def valid_event(self, event):
        return (isinstance(event, OrcaCompletion) and self.valid_binding(event.binding)
                and bool(event.turn_id) and bool(event.item_id) and bool(event.native_digests))

    def completed(self, request, events):
        return len(events) == 1 and self.valid_event(events[0]) and events[0].binding.request == request

    def permits_continuation(self, binding, continuation):
        return False


class OrcaAdapter:
    def __init__(self, host, store):
        self.host, self.store = host, store
        self.stopped = False
        self.request_count = self.sequence = 0
        first = self._read()
        self.binding = self._identity(first)
        if (store.thread_id != self.binding.provider_thread or store.latest is not None
                or tuple(store.checkpoints.iterdir()) or tuple(store.journal.iterdir())):
            _reject('ORCA_OWNERSHIP_MISMATCH')
        store._ready()
        self.core = Controller(store.thread_id, completion_policy=OrcaCompletionPolicy())
        self.records = store.path / 'orca-events'
        self.records.mkdir(mode=0o700, exist_ok=False)
        from .persistence import _sync_directory
        _sync_directory(store.path)
        self.cursor = first['history']['result']['page']['liveCursor']['sequence']
        self._record('attached', binding=asdict(self.binding), profile=ORCA_PROFILE)

    def _record(self, kind, **facts):
        self.sequence += 1
        path = self.records / f'{self.sequence:06d}.json'
        try:
            self.store._write(path, dict(kind=kind, **facts))
        except BaseException:
            self.stopped = True
            self.core.fail('Orca durable decision write uncertain; no retry')
            raise
        return str(path)

    def _read(self):
        try:
            return deepcopy(self.host.observe())
        except TransitionError:
            raise
        except Exception:
            _reject('ORCA_OWNERSHIP_MISMATCH')

    def _identity(self, data):
        try:
            if (data['orcaVersion'] != ORCA_VERSION or data['codexVersion'] != CODEX_VERSION
                    or data['platform'] != 'win32' or data['structured'] is not True):
                _reject('ORCA_PROFILE_MISMATCH')
            r, h, runtime = data['record'], data['history'], data['runtime']
            location, lease = r['location'], r['lease']
            processes, worktree = data['processes'], data['worktree']
            owner = next(p for p in processes if p['pid'] == lease['ownerProcess']['pid'])
            parent = next(p for p in processes if p['pid'] == runtime['pid'])
            handle, = r['providerHandleChain']
            thread = handle['handle']['threadId']
            meta, = [row for row in data['native'] if row['type'] == 'session_meta']
            if (location['executionHostId'] != 'local' or location['wslDistro'] is not None
                    or worktree['executionHostId'] != 'local' or worktree['wslDistro'] is not None
                    or worktree['workspaceId'] != location['workspaceId']
                    or not worktree['id'] or not worktree['path']
                    or r['sessionId'] != self.host.session_id or lease['sessionId'] != r['sessionId']
                    or r['provider'] != 'codex' or handle['handle']['provider'] != 'codex'
                    or lease['provenHandleLinkId'] != handle['linkId']
                    or lease['claimStatus'] != 'live' or lease['runtimeKind'] != 'native'
                    or lease['unreconciled'] is not False or lease['deathEvidence'] is not None
                    or lease['ownerProcess']['hostId'] != 'local'
                    or owner['parentPid'] != parent['pid']
                    or owner['startedAtMs'] != lease['ownerProcess']['processStartTimeMs']
                    or not owner['executable'].lower().endswith('\\codex.exe')
                    or not parent['executable'].lower().endswith('\\orca.exe')
                    or h['_meta']['runtimeId'] != runtime['runtimeId']
                    or h['ok'] is not True or h['result']['ok'] is not True
                    or h['result']['providerSession']['id'] != thread
                    or meta['payload']['id'] != thread or meta['payload']['cli_version'] != CODEX_VERSION
                    or h['result']['page']['fence'] != lease['runtimeFence']
                    or type(lease['runtimeFence']) is not int or lease['runtimeFence'] < 1):
                _reject('ORCA_OWNERSHIP_MISMATCH')
            return OrcaBinding(tuple(runtime[k] for k in ('runtimeId', 'pid', 'startedAt')),
                tuple((p['pid'], p['parentPid'], p['startedAtMs'], p['executable']) for p in (parent, owner)),
                tuple(worktree[k] for k in ('id', 'path', 'workspaceId')), r['sessionId'], thread,
                handle['linkId'], lease['runtimeFence'], h['result']['page']['liveCursor']['epoch'])
        except TransitionError:
            raise
        except (KeyError, TypeError, ValueError, StopIteration):
            _reject('ORCA_OWNERSHIP_MISMATCH')

    def _observe(self, *, idle=False):
        self.store._ready()
        if self.stopped:
            raise TransitionError('Orca owner stopped; no retry or restart')
        data = self._read()
        binding = self._identity(data)
        if binding != self.binding:
            _reject('ORCA_FENCE_CHANGED')
        page = data['history']['result']['page']
        if page['liveCursor']['sequence'] < self.cursor:
            _reject('ORCA_FENCE_CHANGED')
        self.cursor = page['liveCursor']['sequence']
        if idle:
            self._idle(data)
        return data

    @staticmethod
    def _idle(data):
        try:
            page, r = data['history']['result']['page'], data['record']
            bodies = [item['body'] for item in page['items']]
            turns = [b for b in bodies if b['kind'] == 'turn']
            native = data['native']
            starts = [r['payload']['turn_id'] for r in native if r['payload'].get('type') == 'task_started']
            ends = [r['payload']['turn_id'] for r in native if r['payload'].get('type') == 'task_complete']
            if (page['hasOlder'] is not False or page['hasNewer'] is not False
                    or page['backgroundTasks'] is not None or not starts or starts != ends
                    or not turns or any(t['state'] != 'completed' or t['outcome'] != 'success' for t in turns)
                    or starts != [t['turnId'] for t in turns]
                    or any(b['kind'] == 'tool-call' and b['state'] not in ('completed', 'failed', 'cancelled') for b in bodies)
                    or any(b['kind'] in ('approval', 'question') and b['resolution']['state'] == 'pending' for b in bodies)
                    or any(s['dispatchState'] != 'accepted' for s in page['submissions'])
                    or r.get('rewind') is not None
                    or r['lease']['handoffStage'] is not None or r['lease']['handoffOperationId'] is not None
                    or (r.get('conversationCommand') is not None and
                        (r['conversationCommand']['phase'] != 'committed' or r['conversationCommand']['state'] != 'completed'))):
                _reject('ORCA_BOUNDARY_UNSAFE')
        except (KeyError, TypeError):
            _reject('ORCA_BOUNDARY_UNSAFE')

    def register(self, supervisor):
        self._observe()
        session = SessionProfile('codex', self.store.thread_id, 'orca', 'orca-structured-session')
        supervisor.register_session(session)
        def ids():
            self._observe()
            return (self.binding.provider_thread,)
        supervisor.register_adapter(AdapterRegistration('orca', session, frozenset({TRIGGER, OBSERVER}),
            ids, lambda: self.core.snapshot, self.compact))
        # Provider-native observer shares this Core; never instantiate another owner/controller.
        supervisor.register_adapter(AdapterRegistration('codex', session, frozenset({OBSERVER}),
            ids, lambda: self.core.snapshot))
        return session

    def checkpoint(self, *, boundary_id, observe, evidence):
        native = self._observe(idle=True)
        if (native['record'].get('conversationCommand') is not None
                or any(row['type'] == 'compacted' for row in native['native'])
                or len(native['history']['result']['page']['submissions']) != 1):
            _reject('ORCA_BOUNDARY_UNSAFE')
        current = observe()
        if (not isinstance(current, CurrentContext) or not isinstance(evidence, BoundaryVerification)
                or evidence.workspace != current.workspace
                or (evidence.intent_revision, evidence.execution_revision) !=
                   (current.intent_revision, current.execution_revision)):
            _reject('ORCA_BOUNDARY_UNSAFE')
        self.core.update_revisions(workspace=current.workspace)
        r = self.core.snapshot.revisions
        if (r.intent_revision, r.execution_revision) != (current.intent_revision, current.execution_revision):
            _reject('ORCA_BOUNDARY_UNSAFE')
        try:
            self.core.propose_boundary(boundary_id)
            self.core.arm_barrier()
            self.core.begin_quiescence_check()
            self.core.observe_quiescence(relevant_work_remaining=False)
            self.core.capture_workspace(current.workspace)
            self.core.verify_boundary(evidence)
            cp = self.store.commit_checkpoint(self.core.prepare_checkpoint())
            self.boundary = self._observe(idle=True)
            if (self._signature(native) != self._signature(self.boundary) or observe() != current
                    or self.store.read_checkpoint(cp.checkpoint_id) != cp):
                _reject('ORCA_BOUNDARY_UNSAFE')
            self.core.checkpoint_committed(cp.checkpoint_id, commit_evidence=cp.commit_evidence)
            self.current = current
            self._record('checkpoint_committed', checkpoint_id=cp.checkpoint_id)
            return cp
        except BaseException:
            self.stopped = True
            self.core.fail('Orca checkpoint qualification failed')
            raise

    @staticmethod
    def _signature(data):
        page = data['history']['result']['page']
        return (page['liveCursor'], page['items'], page['submissions'], data['native'])

    def compact(self, *, observe, now, ttl=30):
        if self.request_count or self.core.snapshot.state != State.CHECKPOINT_COMMITTED:
            raise TransitionError('Orca needs an unused durable checkpoint; no retry')
        pre = self._observe(idle=True)
        cp = self.core.snapshot.checkpoint
        if (self._signature(pre) != self._signature(self.boundary) or observe() != self.current
                or self.store.read_checkpoint(cp.checkpoint_id) != cp):
            _reject('ORCA_BOUNDARY_UNSAFE')
        lease = self.core.authorize_rollover(now=now(), ttl=ttl)
        request = self.core.request_rollover(lease, now=now(), intent_revision=self.current.intent_revision,
            execution_revision=self.current.execution_revision, workspace=self.current.workspace)
        operation = f'{int(time.time() * 1000)}-{uuid4().hex}'
        binding = OrcaCompletionBinding(request, self.binding, operation)
        self.core.bind_completion(binding)
        self.request_count = 1  # Consume before persistence or transport can fail.
        method, fields = 'agentSession.conversationCommand', {'command': 'compact'}
        canonical = json.dumps(dict(method=method, sessionId=self.binding.session_id, fields=fields),
                               sort_keys=True, separators=(',', ':'))
        envelope = dict(sessionId=self.binding.session_id, clientOperationId=operation,
            expectedRuntimeFence=self.binding.fence, payloadFingerprint=sha256(canonical.encode()).hexdigest())
        dispatched = False
        try:
            self._record('compact_requested', request=asdict(request), envelope=envelope)
            fresh = self._observe(idle=True)  # Admission does not enforce expectedRuntimeFence.
            if self._signature(fresh) != self._signature(pre) or observe() != self.current:
                _reject('ORCA_BOUNDARY_UNSAFE')
            dispatched = True
            response = self.host.rpc(method, dict(envelope=envelope, **fields))
            post = self._observe(idle=True)
            event = self._completion(binding, pre, post, response)
            if observe() != self.current:
                _reject('ORCA_COMPLETION_AMBIGUOUS')
            ref = self._record('completion_verified', operation_id=operation,
                turn_id=event.turn_id, item_id=event.item_id, native_digests=event.native_digests,
                cursor=post['history']['result']['page']['liveCursor'])
            event = OrcaCompletion(binding, ref, event.turn_id, event.item_id, event.native_digests)
            if not self.core.observe_completion(event):
                _reject('ORCA_COMPLETION_AMBIGUOUS')
            self.post_state = post
            return self.core.snapshot
        except BaseException as exc:
            self.stopped = True
            if self.core.snapshot.state in (State.ROLLOVER_REQUESTED, State.AMBIGUOUS):
                self.core.completion_unknown('Orca dispatch/completion unconfirmed; no retry')
            if dispatched:
                if isinstance(exc, TransitionError) and str(exc) in (
                        'ORCA_OWNERSHIP_MISMATCH', 'ORCA_PROFILE_MISMATCH', 'ORCA_BOUNDARY_UNSAFE'):
                    _reject('ORCA_COMPLETION_AMBIGUOUS')
                exc.add_note(failure_guidance('ORCA_COMPLETION_AMBIGUOUS'))
            raise

    def _completion(self, binding, pre, post, response):
        try:
            result = response['result']
            command = post['record']['conversationCommand']
            expected = dict(command='compact', runtimeFence=self.binding.fence,
                operationId=binding.operation_id, phase='committed', state='completed')
            if (response['ok'] is not True or result['ok'] is not True or result['replayed'] is not False
                    or response['_meta']['runtimeId'] != self.binding.runtime[0]
                    or result['fence'] != self.binding.fence
                    or any(command.get(k) != v or result['value'].get(k) != v for k, v in expected.items())
                    or any(key in obj for obj in (command, result['value']) for key in ('failure', 'error'))
                    or post['native'][:len(pre['native'])] != pre['native']
                    or post['history']['result']['page']['liveCursor']['sequence'] <=
                       pre['history']['result']['page']['liveCursor']['sequence']):
                _reject('ORCA_COMPLETION_AMBIGUOUS')
            delta = post['native'][len(pre['native']):]
            start, = [r for r in delta if r['payload'].get('type') == 'task_started']
            compacted, = [r for r in delta if r['type'] == 'compacted']
            item, = [r for r in delta if r['payload'].get('type') == 'item_completed'
                     and r['item'].get('type') == 'ContextCompaction']
            end, = [r for r in delta if r['payload'].get('type') == 'task_complete']
            turn = start['payload']['turn_id']
            if (item['payload']['thread_id'] != binding.request.thread_id
                    or item['payload']['turn_id'] != turn or end['payload']['turn_id'] != turn
                    or not delta.index(start) < delta.index(compacted) < delta.index(item) < delta.index(end)):
                _reject('ORCA_COMPLETION_AMBIGUOUS')
            turns = [r['body'] for r in post['history']['result']['page']['items']
                     if r['body']['kind'] == 'turn' and r['body']['turnId'] == turn]
            if len(turns) != 1 or turns[0]['state'] != 'completed' or turns[0]['outcome'] != 'success':
                _reject('ORCA_COMPLETION_AMBIGUOUS')
            return OrcaCompletion(binding, 'pending', turn, item['item']['id'], tuple(r['digest'] for r in delta))
        except (KeyError, TypeError, ValueError):
            _reject('ORCA_COMPLETION_AMBIGUOUS')

    def offer_handoff(self, *args, **kwargs):
        _reject('ORCA_RECOVERY_UNQUALIFIED')
