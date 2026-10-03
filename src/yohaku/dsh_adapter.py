"""DSH 0.2.0-rc.2 fresh headless owner: one foreground turn, one compact.

The trusted host mounts stock BasicCompaction (auto:false), with no tool,
background, subagent or alternate input surface. Native history remains DSH's.
Only checkpoint/decision records use SessionStore; binding/proof are in-memory.
Receipt is opt-in for the qualified Messages profile. Restart is unsupported.
All owner calls must be serialized.
"""

from dataclasses import asdict, dataclass
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from .codec import encode
from .controller import Controller, TransitionError
from .model import BoundaryVerification, ContinuationBinding, Request, ResumeVerification, State
from .recovery import CurrentContext, HandoffDocument
from .persistence import _read, _sync_directory

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
    """Completion is unchanged; task binding requires an observed owned turn."""
    task_turn = None

    def permits_continuation(self, binding, continuation):
        return (self.valid_binding(binding) and self.task_turn == continuation
                and continuation.thread_id == binding.session_id)


class DshAdapter:
    def __init__(self, host, store):
        fresh = host.observe()
        if (host.version != DSH_VERSION or store.thread_id != host.session_id
                or store.latest is not None or tuple(store.checkpoints.iterdir())
                or tuple(store.journal.iterdir()) or fresh['seq'] != 0):
            refusal = TransitionError('DSH needs the pinned, fresh headless owner and store')
            refusal.add_note('This configuration is outside the Beta-qualified profile. No transition was started. Check the version, fresh Session/store and exclusive headless owner; yohaku doctor checks local version information only.')
            raise refusal
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
        except BaseException as exc:
            self.stopped = True
            self.core.fail('DSH dispatch or completion uncertain; no blind retry')
            exc.add_note('The native transition may have executed; completion is uncertain. Yohaku stopped without retrying. Preserve state and reconcile the native Session and compaction evidence before proceeding.')
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
            self._record('receipt_turn_reserved', target=target)
            self.store.commit_handoff(document)
            if self.store.read_handoff(document.handoff_id) != document:
                raise TransitionError('durable handoff readback mismatch')
            handoff = self.core.offer_handoff(None, handoff_id=document.handoff_id,
                recovered_context=f'handoff:{document.handoff_id}', expected_snapshot=s)
            self._record('handoff_offered', handoff=asdict(handoff))
            self.document = document
            text = self.handoff_text = document.render(checkpoint=s.checkpoint)
            delivery = self.host.deliver_handoff(handoff.handoff_id, target['turnId'], text)
            expected_hash = sha256(text.encode()).hexdigest()
            if (delivery['sessionId'] != s.thread_id or not delivery['messageId']
                    or delivery['handoffId'] != handoff.handoff_id
                    or delivery['turnId'] != target['turnId']
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
                    or candidate['turnId'] != d['turnId']
                    or h.continuation_turn_id or self.core.snapshot.continuation_request_id is not None
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
            received = self.core.receive_handoff(h, injection_evidence=self.injection_ref,
                                                 receipt_evidence=ref)
            self.receipt = evidence
            return received
        except BaseException as exc:
            self._stop_receipt('DSH receipt uncertain; no retry or continuation')
            exc.add_note('Handoff receipt could not be verified. Yohaku stopped without retrying or starting the task continuation. Check the offered handoff, actual attempt identity and fresh task/Session state.')
            raise

    def qualify_resume(self, *, observe, reassess):
        """Re-read settled state and reassess historical work; grants no dispatch.

        reassess(document, current) returns the still-unresolved historical next
        action, or None when that work is already complete, from trusted reads.
        """
        s = self.core.snapshot
        if (self.stopped or s.state != State.HANDOFF_RECEIVED or not s.receipt_evidence
                or s.handoff.continuation_turn_id or s.continuation_request_id is not None
                or not hasattr(self, 'receipt') or hasattr(self, 'resume_qualification')):
            raise TransitionError('one received handoff required for resume qualification')
        try:
            document = self.store.read_handoff(s.handoff.handoff_id)
            if (document.request != s.request or document.workspace != self.current.workspace
                    or document.revisions != s.checkpoint.revisions
                    or document.recovered.logical_task_id != self.current.logical_task_id
                    or document != self.document
                    or sha256(self.handoff_text.encode()).hexdigest() != self.delivery['handoffHash']):
                raise TransitionError('old or changed handoff')
            native = self.host.post_receipt()
            self._idle(native)
            current = observe()
            binding = self.receipt['binding']
            messages = [m for m in native['messages'] if m['id'] == self.delivery['messageId']]
            if (native['phase'] != 'post-receipt-idle' or current != self.current
                    or native['current'] != encode(current)
                    or native['handoffId'] != s.handoff.handoff_id
                    or native['messageId'] != self.delivery['messageId']
                    or native['receiptBinding'] != binding
                    or native['receiptFreshRevision'] != self.receipt['freshRevision']
                    or native['revision'] == native['receiptFreshRevision']
                    or native['seq'] <= native['terminalSeq']
                    or native['terminalSeq'] < binding['nativeSeq']
                    or f"{native['sessionId']}:{native['lastTurnEnd']['turn']}" != self.delivery['turnId']
                    or native['lastTurnEnd']['reason'].get('kind') != 'completed'
                    or len(messages) != 1
                    or messages[0]['content'] != [{'type': 'text', 'text': self.handoff_text}]):
                raise TransitionError('stale post-receipt task, revision or Session')
            ref = self._record('post_receipt_observed', observation=native)
            next_action = reassess(document, current)
            if (next_action is not None and (not isinstance(next_action, str) or not next_action
                    or not document.recovered.unresolved
                    or next_action != document.recovered.next_action_candidate)):
                raise TransitionError('historical next action changed or unresolved work unknown')
            after = self.host.post_receipt()
            comparable = {k: v for k, v in after.items() if k != 'revision'}
            if (observe() != current or comparable != {k: v for k, v in native.items() if k != 'revision'}
                    or after['revision'] == native['revision']):
                raise TransitionError('post-receipt state changed during reassessment')
            self.core.reconcile_resume_context(intent_revision=current.intent_revision,
                execution_revision=current.execution_revision, workspace=current.workspace)
            self._qualified = (current, next_action, after, self.core.snapshot)
            result = dict(fresh_state='PASS', unresolved_work=next_action is not None,
                historical_next_action_reevaluated=True, current=encode(current),
                observation_ref=ref, continuation_authorized=False,
                stop_reason=('awaiting explicit continuation' if next_action is not None
                             else 'no unresolved work'))
            self._record('resume_qualified', **result)
            self.resume_qualification = result
            return result
        except BaseException:
            self._stop_receipt('DSH post-receipt reconciliation failed; no continuation')
            raise

    def continue_task(self, *, observe):
        """One reassessed text interaction; bind its observed turn before release.

        Host reads are not tool observations. This no-tool profile stops after
        completion without constructing ResumeProof or clearing the Core barrier.
        """
        if (self.stopped or not hasattr(self, '_qualified')
                or self.core.snapshot.continuation_request_id is not None):
            raise TransitionError('fresh qualification and an unused task claim required')
        current, action, post, qualified = self._qualified
        if action is None:
            raise TransitionError('no unresolved work')
        try:
            fresh_post = self.host.post_receipt()
            if (self.core.snapshot != qualified or observe() != current
                    or fresh_post['revision'] == post['revision']
                    or {k: v for k, v in fresh_post.items() if k != 'revision'} !=
                       {k: v for k, v in post.items() if k != 'revision'}):
                raise TransitionError('qualification changed before task claim')
            document = self.store.read_handoff(qualified.handoff.handoff_id)
            if (document.request != qualified.request
                    or document != self.document
                    or sha256(self.handoff_text.encode()).hexdigest() != self.delivery['handoffHash']):
                raise TransitionError('task handoff changed')
            claim = self.core.claim_continuation(expected_snapshot=qualified)
            claimed = self.core.snapshot
            claim_ref = self._record('task_claimed', claim_id=claim, handoff=asdict(claimed.handoff),
                         current=encode(current), revisions=asdict(claimed.revisions),
                         next_action=action, observation=fresh_post)
            if observe() != current or self.core.snapshot != claimed:
                raise TransitionError('current state changed after task claim')
            candidate = self.host.start_task_interaction(claim, claimed.handoff.handoff_id,
                                                         action, fresh_post)
            if (candidate['sessionId'] != claimed.thread_id
                    or candidate['handoffId'] != claimed.handoff.handoff_id
                    or candidate['claimId'] != claim
                    or type(candidate['turn']) is not int
                    or candidate['turn'] <= self.receipt['binding']['turn']
                    or candidate['turnId'] != f"{claimed.thread_id}:{candidate['turn']}"
                    or candidate['step'] != 1 or candidate['nativeSeq'] <= fresh_post['seq']
                    or not candidate['taskMessageId']
                    or candidate['taskHash'] != sha256(action.encode()).hexdigest()):
                raise TransitionError('foreign or unobserved task identity')
            fresh = self.host.fresh_task()
            if (observe() != current or fresh['current'] != encode(current)
                    or fresh['sessionId'] != claimed.thread_id or fresh['status'] != 'running'
                    or fresh['seq'] < candidate['nativeSeq']):
                raise TransitionError('task gate state changed before binding')
            binding = ContinuationBinding(claim, claimed.thread_id, candidate['turnId'])
            self.core._completion_policy.task_turn = binding
            handoff = self.core.bind_continuation(binding, expected_snapshot=claimed)
            bound = self.core.snapshot
            ref = self._record('task_bound', binding=asdict(binding), handoff=asdict(handoff),
                               revisions=asdict(bound.revisions), candidate=candidate, fresh=fresh)
            final = self.host.fresh_task()
            if (self.core.snapshot != bound or observe() != current
                    or final['revision'] == fresh['revision']
                    or {k: v for k, v in final.items() if k != 'revision'} !=
                       {k: v for k, v in fresh.items() if k != 'revision'}):
                raise TransitionError('current state changed after task binding')
            authorization = dict(claimId=claim, handoffId=handoff.handoff_id,
                turnId=binding.turn_id, bindingRecord=ref, controlRevision=bound.revisions.control_revision)
            release_ref = self._record('task_release_authorized', authorization=authorization, fresh=final)
            if self.core.snapshot != bound or observe() != current:
                raise TransitionError('task release state changed')
            accepted = self.host.authorize_task(candidate, final, authorization)
            if (accepted['binding'] != candidate or accepted['freshRevision'] != final['revision']
                    or accepted['result'] != 'http-accepted'):
                refusal = TransitionError('task dispatch outcome uncertain')
                refusal.add_note('The continuation may have been sent. Yohaku stops without restoring the claim or retrying. Preserve state and reconcile the native task and provider acceptance before proceeding.')
                raise refusal
            dispatch_ref = self._record('task_http_accepted', evidence=accepted)
            native = self.host.post_task()
            self._idle(native)
            end = native['lastTurnEnd']
            if (self.core.snapshot != bound or native['taskBinding'] != candidate
                    or native['handoffId'] != handoff.handoff_id or native['claimId'] != claim
                    or end['turn'] != candidate['turn'] or end['reason'].get('kind') != 'completed'
                    or native['terminalSeq'] < candidate['nativeSeq']
                    or native['seq'] <= native['terminalSeq']
                    or native['current'] != encode(observe())
                    or native['current'] != encode(current)):
                raise TransitionError('task terminal or final current state mismatch')
            result = dict(continuation_completed='PASS', native=native,
                          resume_proof='BLOCKED_BY_EXISTING_CONTRACT', resume_verified='NOT_REACHED')
            completion_ref = self._record('task_completed', **result)
            self._completed_task = (bound, deepcopy(native), dict(claim=claim_ref,
                binding=ref, release=release_ref, dispatch=dispatch_ref, completion=completion_ref))
            self.task_result = result
            return result
        except BaseException as exc:
            self._stop_receipt('DSH task dispatch/binding/completion uncertain; no retry')
            exc.add_note('The continuation may have been sent or completed. Yohaku stopped without restoring the claim/binding or retrying. Preserve state and reconcile the actual native task and provider acceptance before proceeding.')
            raise

    def verify_finalized(self, *, observe):
        """Verify only the bounded FINALIZED-once text task under the owned profile.

        Native terminal/readback and dispatch provenance authorize assessment;
        model text alone never authorizes Core verification. Calls are serialized.
        """
        s = self.core.snapshot
        if (self.stopped or s.state != State.HANDOFF_RECEIVED
                or not hasattr(self, '_completed_task') or hasattr(self, 'resume_verification')):
            raise TransitionError('one completed bound continuation required')
        try:
            bound, completed, refs = self._completed_task
            current, action, _, _ = self._qualified
            document = self.store.read_handoff(s.handoff.handoff_id)
            if (s != bound or not s.receipt_evidence or not s.continuation_request_id
                    or not s.handoff.continuation_turn_id
                    or document.request != s.request or document.workspace != current.workspace
                    or document.revisions != s.checkpoint.revisions
                    or document.recovered.logical_task_id != current.logical_task_id
                    or document.recovered.unresolved != ('FINALIZE',)
                    or action != 'Produce FINALIZED exactly once after current task reconciliation.'
                    or document.recovered.next_action_candidate != action
                    or document != self.document
                    or sha256(self.handoff_text.encode()).hexdigest() != self.delivery['handoffHash']
                    or observe() != current
                    or (s.revisions.intent_revision, s.revisions.execution_revision, s.workspace) !=
                       (current.intent_revision, current.execution_revision, current.workspace)):
                raise TransitionError('final task, handoff or Core revision mismatch')
            records = {key: _read(Path(ref))['payload'] for key, ref in refs.items()}
            candidate = records['binding']['candidate']
            binding = records['binding']['binding']
            authorization = records['release']['authorization']
            if (tuple(records[k]['kind'] for k in refs) != ('task_claimed', 'task_bound',
                    'task_release_authorized', 'task_http_accepted', 'task_completed')
                    or list(refs.values()) != sorted(set(refs.values()))
                    or records['claim']['claim_id'] != s.continuation_request_id
                    or binding != asdict(ContinuationBinding(s.continuation_request_id,
                        s.thread_id, s.handoff.continuation_turn_id))
                    or records['binding']['handoff'] != asdict(s.handoff)
                    or authorization != dict(claimId=s.continuation_request_id,
                        handoffId=s.handoff.handoff_id, turnId=s.handoff.continuation_turn_id,
                        bindingRecord=refs['binding'], controlRevision=s.revisions.control_revision)
                    or records['dispatch']['evidence']['binding'] != candidate
                    or records['dispatch']['evidence']['result'] != 'http-accepted'
                    or records['dispatch']['evidence']['freshRevision'] !=
                       records['release']['fresh']['revision']
                    or records['completion']['native'] != completed
                    or candidate['sessionId'] != s.thread_id
                    or candidate['handoffId'] != s.handoff.handoff_id
                    or candidate['claimId'] != s.continuation_request_id
                    or candidate['turnId'] != s.handoff.continuation_turn_id
                    or candidate['turnId'] == self.delivery['turnId']):
                raise TransitionError('missing or foreign completion provenance')
            final = self.host.final_task()
            self._idle(final)
            c = final['completion']
            if ({k: v for k, v in final.items() if k not in ('revision', 'completion')} !=
                    {k: v for k, v in completed.items() if k != 'revision'}
                    or final['revision'] == completed['revision']
                    or final['phase'] != 'post-task-idle' or final['taskBinding'] != candidate
                    or final['lastTurnEnd'] != {'turn': candidate['turn'], 'reason': {'kind': 'completed'}}
                    or c['readbackSessionId'] != s.thread_id or c['readbackSeq'] != final['seq']
                    or c['terminalSeq'] != final['terminalSeq']
                    or not c['turnStartSeq'] <= candidate['nativeSeq'] <= c['outputSeq'] < c['terminalSeq'] < final['seq']
                    or any(c[key] != 1 for key in ('taskInputs', 'taskTurns', 'taskRequests', 'nativeCalls'))
                    or observe() != current or self.core.snapshot != s):
                raise TransitionError('stale or incomplete final native observation')
            observation_ref = self._record('final_task_observed', observation=final)
            outputs = [m for m in final['messages'] if m['id'] == c['outputMessageId']]
            if (len(outputs) != 1 or outputs[0]['role'] != 'assistant'
                    or outputs[0]['content'] != c['outputContent']
                    or c['outputContent'] != [{'type': 'text', 'text': 'FINALIZED'}]
                    or c['finalizedCount'] != 1):
                raise TransitionError('bounded FINALIZED-once assessment failed')
            assessment = dict(task='FINALIZED exactly once', result='PASS', nonduplication='PASS',
                              observation_ref=observation_ref)
            assessment_ref = self._record('bounded_task_assessed', **assessment)
            record = dict(session_id=s.thread_id, handoff_id=s.handoff.handoff_id,
                claim_id=s.continuation_request_id, continuation_turn_id=s.handoff.continuation_turn_id,
                records=refs, terminal=final['lastTurnEnd'], terminal_seq=final['terminalSeq'],
                observation_ref=observation_ref, observation_revision=final['revision'],
                current=encode(current), revisions=asdict(s.revisions), assessment_ref=assessment_ref,
                assessment=assessment)
            proof_ref = self._record('resume_verified_evidence', **record)
            # Persistence/assessment can take time. Reuse the same host predicate
            # once more, then compare everything except its read revision.
            reread = self.host.final_task()
            if (reread['revision'] == final['revision']
                    or {k: v for k, v in reread.items() if k != 'revision'} !=
                       {k: v for k, v in final.items() if k != 'revision'}
                    or self.core.snapshot != s or observe() != current
                    or self.store.read_handoff(s.handoff.handoff_id) != document
                    or _read(Path(proof_ref))['payload'] != dict(kind='resume_verified_evidence', **record)):
                raise TransitionError('final consistency check failed')
            self.store._ready()
            evidence = ResumeVerification(s.handoff.handoff_id, s.handoff.continuation_turn_id,
                current.intent_revision, current.execution_revision, current.workspace, proof_ref,
                current_intent_reconciled=True, current_workspace_checked=True, unresolved_checked=True,
                historical_next_action_reevaluated=True, completed_work_not_repeated=True,
                historical_instructions_not_reexecuted=True, same_task_continued=True)
            self.core.verify_resume(evidence)
            self.resume_verification = evidence
            return evidence
        except BaseException:
            self._stop_receipt('DSH final resume verification failed; no retry')
            raise
