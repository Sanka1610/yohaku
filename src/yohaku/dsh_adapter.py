"""DSH 0.2.0-rc.2 fresh headless owner: one foreground turn, one compact.

The trusted host mounts stock BasicCompaction (auto:false), with no tool,
background, subagent or alternate input surface. Native history remains DSH's.
Only checkpoint/decision records use SessionStore; binding/proof are in-memory.
Receipt is opt-in for the qualified Messages profile. Restart is unsupported.
All owner calls must be serialized.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256

from .codec import encode
from .controller import Controller, TransitionError
from .model import BoundaryVerification, ContinuationBinding, Request, State
from .recovery import CurrentContext, HandoffDocument
from .persistence import _sync_directory

DSH_VERSION = "0.2.0-rc.2"
DSH_RECEIPT_PROFILE = "messages-plain-text-owner-no-retry"


@dataclass(frozen=True)
class DshManualBinding:
    request: Request
    session_id: str
    compaction_id: str
    request_seq: int


@dataclass(frozen=True)
class DshNativeCompletion:
    binding: DshManualBinding
    evidence_ref: str
    pre_seq: int
    result: dict
    events: tuple[dict, ...]
    flushed: bool
    readback_session_id: str
    readback_events: tuple[dict, ...]

    @property
    def kind(self):
        return "dsh/native-compaction-readback"


def _replacement(event, compaction_id):
    return (event.get('type') == 'user/message'
            and event.get('data', {}).get('source') == {
                'kind': 'compact-checkpoint', 'compactionId': compaction_id}
            and isinstance(event.get('surfaceOp'), dict)
            and event['surfaceOp'].get('op') == 'replace')


class DshNativeCompletionPolicy:
    def valid_binding(self, binding):
        return (isinstance(binding, DshManualBinding)
                and isinstance(binding.request, Request)
                and binding.request.origin == 'controller'
                and type(binding.request.rollover_generation) is int
                and binding.request.rollover_generation == 1
                and binding.session_id == binding.request.thread_id
                and isinstance(binding.compaction_id, str) and bool(binding.compaction_id)
                and type(binding.request_seq) is int and binding.request_seq == 1)

    def valid_event(self, event):
        if not isinstance(event, DshNativeCompletion) or not self.valid_binding(event.binding):
            return False
        try:
            b, r = event.binding, event.result
            if (event.flushed is not True or event.readback_session_id != b.session_id
                    or r['compactionId'] != b.compaction_id or len(event.events) != 4
                    or type(event.pre_seq) is not int or event.pre_seq < 0):
                return False
            start, summary, replacement, end = event.events
            if (tuple(e['type'] for e in event.events) != (
                    'compaction/start', 'compaction/summary', 'user/message', 'compaction/end')
                    or any(e['sessionId'] != b.session_id for e in event.events)
                    or any(e['data']['compactionId'] != b.compaction_id
                           for e in (start, summary, end))
                    or start['data']['turn'] is not None or end['data']['turn'] is not None
                    or 'error' in end['data'] or not _replacement(replacement, b.compaction_id)):
                return False
            seqs = tuple(e['seq'] for e in event.events)
            if (any(type(seq) is not int for seq in seqs)
                    or not event.pre_seq <= seqs[0] < seqs[1] < seqs[2] < seqs[3]
                    or seqs[2] != seqs[1] + 1
                    or (r['startSeq'], r['summarySeq'], r['endSeq']) != (seqs[0], seqs[1], seqs[3])):
                return False
            span = summary['data']['shadowedRange']
            if (replacement['surfaceOp'] != {
                    'op': 'replace', 'startSeq': span['start'], 'endSeq': span['end']}
                    or r['shadowedRange'] != span
                    or not summary['data']['shadowedSeqs']
                    or r['shadowedSeqs'] != summary['data']['shadowedSeqs']):
                return False
            # Native read handle is opened independently for this Session after flush.
            for captured in event.events:
                native = {k: v for k, v in captured.items() if k != 'sessionId'}
                matches = [e for e in event.readback_events if e['seq'] == captured['seq']]
                if matches != [native]:
                    return False
            return True
        except (KeyError, TypeError, ValueError):
            return False

    def completed(self, request, events):
        return (len(events) == 1 and self.valid_event(events[0])
                and events[0].binding.request == request)

    def permits_continuation(self, binding, continuation):
        return False  # No qualified handoff receipt on this profile.


class DshReceiptCompletionPolicy(DshNativeCompletionPolicy):
    """The completion predicate is unchanged; only an owned receipt turn is allowed."""
    receipt_turn = None

    def permits_continuation(self, binding, continuation):
        return (self.valid_binding(binding) and self.receipt_turn == continuation
                and continuation.thread_id == binding.session_id)


class DshAdapter:
    def __init__(self, host, store):
        fresh = host.observe()
        if (host.version != DSH_VERSION or store.thread_id != host.session_id
                or store.latest is not None or tuple(store.checkpoints.iterdir())
                or tuple(store.journal.iterdir()) or fresh['seq'] != 0):
            raise TransitionError('DSH needs the pinned, fresh headless owner and store')
        store._ready()
        self.host, self.store = host, store
        policy = (DshReceiptCompletionPolicy() if getattr(host, 'receipt_profile', None)
                  == DSH_RECEIPT_PROFILE else DshNativeCompletionPolicy())
        self.core = Controller(host.session_id, completion_policy=policy)
        self.records = store.path / 'dsh-events'
        self.records.mkdir(mode=0o700, exist_ok=False)
        _sync_directory(store.path)
        self.sequence = self.work_count = self.request_count = 0
        self.stopped = False
        self._idle(fresh)
        self._record('attached', version=host.version, session_id=host.session_id)

    def _record(self, kind, **data):
        self.sequence += 1
        path = self.records / f'{self.sequence:06d}.json'
        try:
            self.store._write(path, dict(kind=kind, **data))
        except BaseException:
            self.stopped = True
            self.core.fail('DSH decision write uncertain')
            raise
        return str(path)

    def _idle(self, native=None):
        self.store._ready()
        if self.stopped:
            raise TransitionError('DSH owner stopped; no retry or restart')
        native = self.host.observe() if native is None else native
        if (native['sessionId'] != self.core.snapshot.thread_id
                or native['settled'] is not True or native['status'] != 'idle'
                or native['nextTurn'] or native['nextStep']):
            raise TransitionError('owned foreground driver or inbox has not settled')
        return native

    def work(self, prompt):
        self._idle()
        self.core.require_work()
        if self.work_count:
            raise TransitionError('DSH profile permits one bounded foreground work item')
        self.work_count = 1
        try:
            self._record('work_requested')
            native = self.host.work(prompt)
            self._idle(native)
            if native['lastTurnEnd'].get('reason', {}).get('kind') != 'completed':
                raise TransitionError('bounded foreground turn lacks native successful end')
            self._record('work_completed', observation=native)
        except BaseException:
            self.stopped = True
            self.core.fail('DSH foreground outcome uncertain')
            raise
        return native

    def checkpoint(self, *, boundary_id, observe, evidence_ref):
        native = self._idle()
        current = observe()
        if (self.work_count != 1 or not isinstance(current, CurrentContext) or not evidence_ref
                or native['lastTurnEnd'].get('reason', {}).get('kind') != 'completed'):
            raise TransitionError('trusted bounded work and current task observation required')
        self.core.update_revisions(workspace=current.workspace)
        r = self.core.snapshot.revisions
        if (current.intent_revision, current.execution_revision) != (r.intent_revision, r.execution_revision):
            raise TransitionError('task and Core revisions disagree')
        try:
            self.core.propose_boundary(boundary_id)
            self.core.arm_barrier()  # Owner sequencing; no Runtime-wide freeze.
            self.core.begin_quiescence_check()
            self.core.observe_quiescence(relevant_work_remaining=False)
            self.core.capture_workspace(current.workspace)
            self.core.verify_boundary(BoundaryVerification(r.intent_revision, r.execution_revision,
                current.workspace, 'implementation_complete', 'passed', evidence_ref))
            cp = self.store.commit_checkpoint(self.core.prepare_checkpoint())
            if (observe() != current or self._idle() != native
                    or self.store.read_checkpoint(cp.checkpoint_id) != cp):
                raise TransitionError('checkpoint boundary changed')
            self.core.checkpoint_committed(cp.checkpoint_id, commit_evidence=cp.commit_evidence)
            self.current, self.boundary_native = current, native
            self._record('checkpoint_committed', checkpoint_id=cp.checkpoint_id)
        except BaseException:
            self.stopped = True
            self.core.fail('DSH checkpoint could not be verified')
            raise
        return cp

    def compact(self, *, observe, now, ttl=30):
        native = self._idle()
        if self.request_count:
            raise TransitionError('DSH permits one native transition; no retry')
        if self.core.snapshot.state != State.CHECKPOINT_COMMITTED:
            raise TransitionError('verified durable checkpoint required before authority')
        if native != self.boundary_native:
            self.core.invalidate('native Session changed after checkpoint')
            raise TransitionError('native Session changed after checkpoint')
        cp = self.core.snapshot.checkpoint
        if self.store.read_checkpoint(cp.checkpoint_id) != cp:
            self.stopped = True
            self.core.fail('checkpoint readback mismatch')
            raise TransitionError('checkpoint readback mismatch')
        lease = self.core.authorize_rollover(now=now(), ttl=ttl)
        current = observe()
        if current.logical_task_id != self.current.logical_task_id:
            self.core.invalidate('task identity changed')
            raise TransitionError('task identity changed')
        request = self.core.request_rollover(lease, now=now(),
            intent_revision=current.intent_revision, execution_revision=current.execution_revision,
            workspace=current.workspace)
        self.request_count = 1  # Consume BEFORE any native dispatch.
        try:
            self._record('compact_requested', request=asdict(request), request_seq=self.request_count)
            proof = self.host.compact(self.request_count, native['seq'])
            if proof['requestSeq'] != self.request_count or proof['preSeq'] != native['seq']:
                raise TransitionError('DSH host request correlation mismatch')
            binding = DshManualBinding(request, self.host.session_id,
                                       proof['result']['compactionId'], self.request_count)
            self.core.bind_completion(binding)
            ref = self._record('native_completion', proof=proof)
            event = DshNativeCompletion(binding, ref, native['seq'], proof['result'],
                tuple(proof['events']), proof['flushed'], proof['readbackSessionId'],
                tuple(proof['readbackEvents']))
            if not self.core.observe_completion(event):
                raise TransitionError('DSH native completion proof rejected')
            self.completion = event
        except BaseException:
            self.stopped = True
            self.core.fail('DSH dispatch or completion uncertain; no blind retry')
            raise
        try:
            # A new deriveMessages call AFTER completion/readback, never cached pre-state.
            post = self.host.project()
            replacement = event.events[2]['data']
            messages = post['messages']
            shadowed_ids = {e['data']['id'] for e in event.readback_events
                            if e['seq'] in event.result['shadowedSeqs'] and 'id' in e['data']}
            matches = [m for m in messages if m['id'] == replacement['id']]
            if (post['sessionId'] != binding.session_id
                    or post['seq'] <= event.result['endSeq'] or post['seq'] <= event.pre_seq
                    or len(matches) != 1 or matches[0] != replacement
                    or shadowed_ids.intersection(m['id'] for m in messages)
                    or observe() != current):
                raise TransitionError('DSH fresh post-state verification failed')
            self.post_state = post
            self._record('post_state_verified', session_id=post['sessionId'], seq=post['seq'],
                         replacement_id=replacement['id'], core_state=self.core.snapshot.state)
        except BaseException:
            self.stopped = True
            self.core.fail('DSH completion known; post-state needs review')
            raise
        return self.core.snapshot


    def offer_handoff(self, document, *, observe):
        """Persist one existing HandoffDocument, then inject without waking the Agent."""
        self._idle()
        s = self.core.snapshot
        if (not isinstance(self.core._completion_policy, DshReceiptCompletionPolicy)
                or s.state != State.ROLLOVER_OBSERVED or not hasattr(self, 'post_state')
                or not isinstance(document, HandoffDocument) or document.request != s.request
                or document.revisions != s.checkpoint.revisions
                or document.workspace != self.current.workspace
                or document.recovered.logical_task_id != self.current.logical_task_id
                or observe() != self.current):
            raise TransitionError('qualified receipt profile and current durable handoff required')
        try:
            target = self.host.reserve_receipt()
            if target['sessionId'] != s.thread_id or not target['turnId']:
                raise TransitionError('receipt target Session mismatch')
            permit = self.core.claim_continuation()
            binding = ContinuationBinding(permit, s.thread_id, target['turnId'])
            self.core._completion_policy.receipt_turn = binding
            self._record('receipt_turn_reserved', binding=asdict(binding), target=target)
            self.store.commit_handoff(document)
            if self.store.read_handoff(document.handoff_id) != document:
                raise TransitionError('durable handoff readback mismatch')
            handoff = self.core.offer_handoff(binding, handoff_id=document.handoff_id,
                recovered_context=f'handoff:{document.handoff_id}')
            text = document.render()
            delivery = self.host.deliver_handoff(handoff.handoff_id, binding.turn_id, text)
            expected_hash = sha256(text.encode()).hexdigest()
            if (delivery['sessionId'] != s.thread_id or not delivery['messageId']
                    or delivery['handoffId'] != handoff.handoff_id
                    or delivery['turnId'] != binding.turn_id
                    or delivery['handoffHash'] != expected_hash
                    or delivery['nonWaking'] is not True or delivery['durable'] is not True):
                raise TransitionError('non-waking delivery proof mismatch')
            self.delivery = delivery
            self.injection_ref = self._record('handoff_delivered', delivery=delivery)
            return handoff
        except BaseException:
            self._stop_receipt('DSH handoff delivery uncertain')
            raise

    def _stop_receipt(self, reason):
        self.stopped = True
        self.core.fail(reason)
        self.host.invalidate_receipt(reason)

    def receive_handoff(self, *, observe):
        """One explicit receipt request; no task continuation or resume verification."""
        if self.core.snapshot.receipt_evidence:
            return False
        if self.stopped or self.core.snapshot.state != State.HANDOFF_OFFERED:
            raise TransitionError('one offered handoff required')
        try:
            candidate = self.host.start_receipt_request()
            d, h = self.delivery, self.core.snapshot.handoff
            if (candidate['handoffId'] != h.handoff_id
                    or candidate['sessionId'] != h.request.thread_id
                    or candidate['messageId'] != d['messageId']
                    or candidate['turnId'] != h.continuation_turn_id
                    or candidate['handoffHash'] != d['handoffHash']
                    or candidate['profile'] != DSH_RECEIPT_PROFILE):
                raise TransitionError('receipt candidate identity mismatch')
            fresh = self.host.fresh_receipt()
            current = observe()
            if (current != self.current or fresh['current'] != encode(current)
                    or fresh['sessionId'] != h.request.thread_id
                    or fresh['status'] != 'running' or fresh['settled'] is not False
                    or fresh['seq'] < candidate['nativeSeq']):
                raise TransitionError('receipt fresh task or Session state is stale')
            self._record('receipt_candidate', candidate=candidate, fresh=fresh)
            evidence = self.host.authorize_receipt(candidate, fresh)
            if (evidence['binding'] != candidate or evidence['freshRevision'] != fresh['revision']
                    or evidence['authorization'] != 'one-shot'
                    or evidence['result'] != 'http-accepted'
                    or evidence['profile'] != DSH_RECEIPT_PROFILE):
                raise TransitionError('qualified current-attempt receipt proof mismatch')
            ref = self._record('receipt_received', evidence=evidence)
            return self.core.receive_handoff(h, injection_evidence=self.injection_ref,
                                             receipt_evidence=ref)
        except BaseException:
            self._stop_receipt('DSH receipt uncertain; no retry or continuation')
            raise
