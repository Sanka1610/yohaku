"""Single-writer Core. Methods decide; adapters perform and attest external I/O.

No Hook result establishes safety. No method sends an RPC, writes a checkpoint,
or reconstructs runtime identity. All calls must be serialized by the owner.
"""

from dataclasses import replace
from math import isfinite
from uuid import uuid4

from .codex import CodexCompletionPolicy
from .completion import CompletionPolicy
from .model import (
    BoundaryVerification, Checkpoint,
    ContinuationBinding, Handoff, Lease, Request, ResumeVerification, Snapshot,
    State, WorkspaceRevision,
)


class TransitionError(ValueError):
    pass


class Controller:
    def __init__(self, thread_id: str, *, id_factory=None,
                 completion_policy: CompletionPolicy | None = None):
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise ValueError("exclusive thread identity is required")
        self._snapshot = Snapshot(thread_id=thread_id)
        self._id = id_factory or (lambda: uuid4().hex)
        self._completion_policy = (CodexCompletionPolicy() if completion_policy is None
                                   else completion_policy)

    @property
    def snapshot(self) -> Snapshot:
        return self._snapshot

    def _change(self, **changes):
        revisions = changes.pop("revisions", self.snapshot.revisions)
        self._snapshot = replace(
            self.snapshot,
            revisions=replace(revisions, control_revision=revisions.control_revision + 1),
            **changes,
        )

    def _require(self, *states):
        if self.snapshot.state not in states:
            raise TransitionError(f"operation rejected in {self.snapshot.state}")

    def require_work(self):
        self._require(State.WORKING)

    def propose_boundary(self, boundary_id: str) -> str:
        s = self.snapshot
        if not isinstance(boundary_id, str) or not boundary_id.strip():
            raise TransitionError("boundary ID is required")
        if boundary_id == s.boundary_id:
            return s.transition_id
        self._require(State.WORKING)
        if not boundary_id or boundary_id in s.used_boundary_ids:
            raise TransitionError("boundary ID must be new")
        transition_id = self._id()
        self._change(
            state=State.CANDIDATE, boundary_id=boundary_id,
            transition_id=transition_id,
            used_boundary_ids=s.used_boundary_ids | {boundary_id},
            invalidated=False, snapshot_captured=False, verification=None,
            checkpoint=None, lease=None,
            request=None, request_accepted=False, binding=None, completions=(),
            continuation_request_id=None, handoff=None, injection_evidence=None,
            receipt_evidence=None, reason=None,
        )
        return transition_id

    def arm_barrier(self):
        self._require(State.CANDIDATE)
        self._change(state=State.BARRIER_ARMING, barrier_requested=True)

    def begin_quiescence_check(self):
        self._require(State.BARRIER_ARMING)
        self._change(state=State.QUIESCENCE_CHECK)

    def observe_quiescence(self, *, relevant_work_remaining: bool):
        self._require(State.QUIESCENCE_CHECK)
        if type(relevant_work_remaining) is not bool:
            raise TransitionError("quiescence must be observed, not unknown")
        if relevant_work_remaining:
            self._change(state=State.DEFERRED, barrier_requested=False,
                         reason="relevant work remains")
        else:
            self._change(state=State.WORKSPACE_SNAPSHOT)

    def capture_workspace(self, workspace: WorkspaceRevision):
        self._require(State.WORKSPACE_SNAPSHOT)
        if not isinstance(workspace, WorkspaceRevision):
            raise TransitionError("an observed workspace revision is required")
        old = self.snapshot.workspace
        if old and (workspace.mutation_epoch < old.mutation_epoch
                    or (workspace != old and workspace.mutation_epoch == old.mutation_epoch)):
            raise TransitionError("workspace epoch cannot go backwards")
        self._change(workspace=workspace, snapshot_captured=True)

    def verify_boundary(self, evidence: BoundaryVerification):
        self._require(State.WORKSPACE_SNAPSHOT)
        s = self.snapshot
        if (not s.snapshot_captured or not evidence.evidence_ref or evidence.workspace != s.workspace
                or evidence.intent_revision != s.revisions.intent_revision
                or evidence.execution_revision != s.revisions.execution_revision):
            raise TransitionError("boundary evidence is missing or stale")
        if evidence.profile == "verification_passed":
            if evidence.verification != "passed" or evidence.integrity_window_verified is not True:
                raise TransitionError("fresh successful verification is required")
        elif evidence.profile == "implementation_complete":
            if evidence.verification not in {"not_run", "passed", "failed", "stale", "unknown"}:
                raise TransitionError("unknown verification status")
        else:
            raise TransitionError("unsupported evidence profile")
        self._change(state=State.VERIFIED, verification=evidence)

    def prepare_checkpoint(self) -> Checkpoint:
        self._require(State.VERIFIED)
        s = self.snapshot
        checkpoint = Checkpoint(self._id(), s.transition_id, s.boundary_id,
                                s.revisions, s.workspace, s.verification)
        self._change(state=State.CHECKPOINT_PREPARING, checkpoint=checkpoint)
        return checkpoint

    def checkpoint_committed(self, checkpoint_id: str, *, commit_evidence: str):
        """Called only after the persistence adapter's durable commit point."""
        s = self.snapshot
        if not s.checkpoint or checkpoint_id != s.checkpoint.checkpoint_id or not commit_evidence:
            raise TransitionError("commit must identify this checkpoint and its durable evidence")
        if s.checkpoint.commit_evidence == commit_evidence:
            return False
        self._require(State.CHECKPOINT_PREPARING)
        checkpoint = replace(s.checkpoint, commit_evidence=commit_evidence)
        self._change(state=State.CHECKPOINT_COMMITTED, checkpoint=checkpoint,
                     recoverable_checkpoint=checkpoint)
        return True

    def authorize_rollover(self, *, now: float, ttl: float) -> Lease:
        self._require(State.CHECKPOINT_COMMITTED)
        if not isfinite(now) or not isfinite(ttl) or ttl <= 0 or not isfinite(now + ttl):
            raise ValueError("finite clock and positive lease lifetime required")
        s = self.snapshot
        generation = s.rollover_generation + 1
        lease = Lease(self._id(), s.transition_id, s.boundary_id,
                      s.checkpoint.checkpoint_id, s.revisions.intent_revision,
                      s.revisions.execution_revision, s.workspace, generation, now + ttl)
        self._change(state=State.ROLLOVER_AUTHORIZED, lease=lease,
                     rollover_generation=generation)
        return lease

    def update_revisions(self, *, intent_changed=False, execution_changed=False,
                         archive_changed=False, workspace: WorkspaceRevision | None = None):
        """Relevant changes revoke before publication; counters never roll back."""
        if any(type(flag) is not bool for flag in (intent_changed, execution_changed, archive_changed)):
            raise ValueError("revision changes must be boolean events")
        s = self.snapshot
        if workspace is not None and workspace != s.workspace:
            if s.workspace and workspace.mutation_epoch <= s.workspace.mutation_epoch:
                raise TransitionError("changed workspace needs a newer mutation epoch")
            execution_changed = True
        if not (intent_changed or execution_changed or archive_changed):
            return
        if intent_changed or execution_changed:
            self.invalidate("current intent or execution changed")
        r = self.snapshot.revisions
        self._change(revisions=replace(
            r, intent_revision=r.intent_revision + int(intent_changed),
            execution_revision=r.execution_revision + int(execution_changed),
            archive_revision=r.archive_revision + int(archive_changed)),
            workspace=workspace if workspace is not None else self.snapshot.workspace)

    def invalidate(self, reason: str):
        s = self.snapshot
        if s.state == State.WORKING:
            return
        if s.lease is not None:
            self._change(revoked_lease_id=s.lease.lease_id)
        if s.request is not None:
            target = State.RECOVERY_REQUIRED if self._completed() else State.AMBIGUOUS
            self._change(state=target, lease=None, invalidated=True, reason=reason)
        elif s.state == State.RECOVERY_REQUIRED:
            self._change(lease=None, invalidated=True, reason=reason)
        else:
            self._change(state=State.INVALIDATED, lease=None, invalidated=True,
                         barrier_requested=False, reason=reason)
            self.return_to_work()

    def expire_lease(self, *, now: float) -> bool:
        if not isfinite(now):
            raise ValueError("finite clock required")
        lease = self.snapshot.lease
        if lease is None or now < lease.expires_at:
            return False
        self.invalidate("lease expired")
        return True

    def request_rollover(self, lease: Lease, *, now: float,
                         intent_revision: int, execution_revision: int,
                         workspace: WorkspaceRevision) -> Request:
        """Consume authority BEFORE transport. Return one dispatch instruction.

        The adapter must journal it before sending. Transport uncertainty enters
        AMBIGUOUS; retrying this method never issues a second dispatch. The final
        read-to-RPC race cannot be eliminated by this local Core.
        """
        self._require(State.ROLLOVER_AUTHORIZED)
        s = self.snapshot
        if lease != s.lease:
            raise TransitionError("lease does not match current authority")
        if self.expire_lease(now=now):
            raise TransitionError("lease expired before request")
        if (intent_revision != lease.intent_revision
                or execution_revision != lease.execution_revision
                or workspace != lease.workspace):
            self.invalidate("final revision revalidation failed")
            refusal = TransitionError('final revision revalidation failed')
            refusal.add_note('Yohaku rejected the transition request. Re-check the current task and workspace before requesting new authority.')
            raise refusal
        request = Request(self._id(), s.thread_id, s.transition_id, s.boundary_id,
                          s.checkpoint.checkpoint_id, lease.lease_id, s.rollover_generation)
        self._change(state=State.ROLLOVER_REQUESTED, request=request)
        return request

    def accept_request(self, request: Request) -> bool:
        if self.snapshot.request is None or request != self.snapshot.request:
            raise TransitionError("acceptance does not match request")
        if self.snapshot.request_accepted:
            return False
        self._change(request_accepted=True)
        return True

    def observe_native_start(self):
        """Record an external rollover observation; never authorize/send compact.

        The existing checkpoint remains historical. Current revisions/workspace
        are not replaced by its older values. The adapter must journal this
        stopped state before returning from the correlated PreCompact Hook.
        """
        s = self.snapshot
        self._require(State.WORKING, State.CANDIDATE, State.BARRIER_ARMING,
                      State.QUIESCENCE_CHECK, State.WORKSPACE_SNAPSHOT, State.VERIFIED,
                      State.CHECKPOINT_COMMITTED, State.ROLLOVER_AUTHORIZED)
        cp = s.recoverable_checkpoint
        if s.request is not None or cp is None or not cp.commit_evidence:
            raise TransitionError("native recovery requires a durable historical checkpoint")
        generation, transition = s.rollover_generation + 1, self._id()
        request = Request(self._id(), s.thread_id, transition, cp.boundary_id,
                          cp.checkpoint_id, "", generation, "native_auto")
        self._change(state=State.AMBIGUOUS, request=request, checkpoint=cp,
                     transition_id=transition, boundary_id=cp.boundary_id,
                     rollover_generation=generation, barrier_requested=True,
                     lease=None, revoked_lease_id=s.lease.lease_id if s.lease else s.revoked_lease_id,
                     invalidated=True, verification=None, snapshot_captured=False,
                     request_accepted=False, binding=None, completions=(),
                     handoff=None, continuation_request_id=None,
                     injection_evidence=None, receipt_evidence=None)
        return request

    def completion_unknown(self, reason="completion timeout"):
        self._require(State.ROLLOVER_REQUESTED, State.AMBIGUOUS)
        self._change(state=State.AMBIGUOUS, lease=None, reason=reason)

    def bind_completion(self, binding):
        """Adapter supplies actual identity under this Controller's fixed policy."""
        s = self.snapshot
        if (not self._completion_policy.valid_binding(binding)
                or binding.request != s.request):
            raise TransitionError("invalid completion binding")
        if s.binding == binding:
            return False
        self._require(State.ROLLOVER_REQUESTED, State.AMBIGUOUS)
        if s.binding is not None:
            self.completion_unknown("conflicting runtime identity")
            raise TransitionError("existing binding cannot be replaced")
        self._change(binding=binding)
        return True

    def _completed(self):
        return self._completion_policy.completed(self.snapshot.request, self.snapshot.completions)

    def observe_completion(self, event) -> bool:
        """Accept normalized successful completion evidence, not RPC acceptance."""
        s = self.snapshot
        if (not self._completion_policy.valid_event(event) or not event.evidence_ref
                or s.binding is None or event.binding != s.binding):
            if s.state == State.ROLLOVER_REQUESTED:
                self.completion_unknown("uncorrelated completion")
            return False
        if any(e.kind == event.kind for e in s.completions):
            return False
        self._require(State.ROLLOVER_REQUESTED, State.AMBIGUOUS)
        self._change(completions=s.completions + (event,))
        if self._completed():
            self._change(state=State.ROLLOVER_OBSERVED, lease=None, reason=None)
        return True

    def confirm_not_executed(self, request: Request, *, evidence_ref: str):
        self._require(State.ROLLOVER_REQUESTED, State.AMBIGUOUS)
        if request != self.snapshot.request or not evidence_ref or self.snapshot.completions:
            raise TransitionError("requires conclusive non-execution evidence without completion")
        self._change(state=State.INVALIDATED, request=None, lease=None,
                     invalidated=True, barrier_requested=False,
                     reason=f"not executed: {evidence_ref}")
        self.return_to_work()

    def _check_continuation_snapshot(self, expected_snapshot: Snapshot | None):
        s = self.snapshot
        r, cp = s.request, s.checkpoint
        if (expected_snapshot != s or s.invalidated or r is None or cp is None
                or not cp.commit_evidence or s.workspace is None
                or r.thread_id != s.thread_id or r.transition_id != s.transition_id
                or r.boundary_id != s.boundary_id or r.checkpoint_id != cp.checkpoint_id
                or r.rollover_generation != s.rollover_generation
                or s.binding is None or s.binding.request != r
                or (s.handoff is not None and (s.handoff.request != r
                    or s.handoff.intent_revision != cp.revisions.intent_revision
                    or s.handoff.execution_revision != cp.revisions.execution_revision))):
            refusal = TransitionError('continuation requires the current snapshot, request and handoff')
            refusal.add_note('Yohaku rejected this claim or binding. Reconcile the current task, workspace and handoff; do not reuse stale evidence.')
            raise refusal

    def claim_continuation(self, *, expected_snapshot: Snapshot | None = None) -> str:
        """Consume the transition's one task continuation permit before I/O.

        Journal the returned request ID before I/O. Uncertain dispatch must be
        reconciled; neither restart nor another completion grants a new permit.
        For an unbound handoff, the adapter supplies its post-receipt snapshot
        after successful settlement, fresh task reassessment and final recheck.
        Core checks consistency; it cannot attest those external observations.
        """
        s = self.snapshot
        if s.handoff is not None:
            self._require(State.HANDOFF_RECEIVED)
            self._check_continuation_snapshot(expected_snapshot)
            if s.handoff.continuation_turn_id or not s.receipt_evidence or not s.injection_evidence:
                raise TransitionError("delayed continuation requires a received unbound handoff")
        else:
            self._require(State.ROLLOVER_OBSERVED, State.RECOVERY_REQUIRED)
            if expected_snapshot is not None:
                self._check_continuation_snapshot(expected_snapshot)
        if not self._completed() or s.continuation_request_id is not None:
            refusal = TransitionError('continuation requires completion and an unused dispatch permit')
            refusal.add_note('Yohaku did not grant another claim. Check completion evidence and the existing claim; a consumed permit is not restored for retry.')
            raise refusal
        request_id = self._id()
        self._change(continuation_request_id=request_id)
        return request_id

    def offer_handoff(self, binding: ContinuationBinding | None, *, recovered_context: str,
                      handoff_id: str | None = None,
                      expected_snapshot: Snapshot | None = None) -> Handoff:
        """Offer one handoff, early-bound by default.

        Explicit binding=None opts into delayed binding and requires the current
        snapshot and durable document ID. Receipt transport remains adapter-owned.
        """
        self._require(State.ROLLOVER_OBSERVED, State.RECOVERY_REQUIRED)
        s = self.snapshot
        if binding is None:
            self._require(State.ROLLOVER_OBSERVED)
            self._check_continuation_snapshot(expected_snapshot)
            if (not self._completed() or s.continuation_request_id is not None
                    or s.handoff is not None or not handoff_id):
                raise TransitionError("unbound offer requires completed rollover and an unused permit")
            turn_id = ""
        elif (not self._completed() or s.continuation_request_id is None
                or binding.request_id != s.continuation_request_id
                or binding.thread_id != s.thread_id
                or s.handoff is not None or not binding.turn_id
                or not self._completion_policy.permits_continuation(s.binding, binding)):
            raise TransitionError("handoff needs completed rollover and a new continuation turn")
        else:
            turn_id = binding.turn_id
        handoff = Handoff(handoff_id or self._id(), s.request, turn_id,
                          s.checkpoint.revisions.intent_revision,
                          s.checkpoint.revisions.execution_revision, recovered_context)
        self._change(state=State.HANDOFF_OFFERED, handoff=handoff)
        return handoff

    def receive_handoff(self, handoff: Handoff, *, injection_evidence: str,
                        receipt_evidence: str) -> bool:
        s = self.snapshot
        if s.handoff is None or handoff != s.handoff or not injection_evidence or not receipt_evidence:
            refusal = TransitionError('receipt needs offered identity and actual injection evidence')
            refusal.add_note('Yohaku did not accept this receipt. Check the original handoff and runtime delivery identity; receipt success alone does not verify resume.')
            raise refusal
        if s.receipt_evidence:
            return False
        if not handoff.continuation_turn_id:
            self._require(State.HANDOFF_OFFERED)
            self._check_continuation_snapshot(s)
            if s.continuation_request_id is not None:
                raise TransitionError("unbound receipt cannot consume continuation authority")
        else:
            self._require(State.HANDOFF_OFFERED, State.RECOVERY_REQUIRED)
        self._change(state=State.HANDOFF_RECEIVED,
                     injection_evidence=injection_evidence,
                     receipt_evidence=receipt_evidence)
        return True

    def bind_continuation(self, binding: ContinuationBinding, *,
                          expected_snapshot: Snapshot) -> Handoff:
        """Bind an observed native task identity once, after the delayed claim.

        Retain the snapshot immediately after claim for this check. The trusted
        adapter must attest actual native identity (never a reservation/guess),
        persist the resulting snapshot, and recheck its gate before task effects.
        Failed binding or uncertain I/O never restores the consumed permit.
        """
        self._require(State.HANDOFF_RECEIVED)
        self._check_continuation_snapshot(expected_snapshot)
        s = self.snapshot
        if (s.handoff is None or s.handoff.continuation_turn_id
                or not s.receipt_evidence or not s.injection_evidence
                or not self._completed() or s.continuation_request_id is None
                or binding.request_id != s.continuation_request_id
                or binding.thread_id != s.thread_id
                or not isinstance(binding.turn_id, str) or not binding.turn_id.strip()
                or not self._completion_policy.permits_continuation(s.binding, binding)):
            refusal = TransitionError('binding requires the active claim and an observed task identity')
            refusal.add_note('Yohaku did not bind this continuation or restore its consumed permit. Check the existing claim and actual native task identity before proceeding.')
            raise refusal
        handoff = replace(s.handoff, continuation_turn_id=binding.turn_id)
        self._change(handoff=handoff)
        return handoff

    def verify_resume(self, evidence: ResumeVerification):
        self._require(State.HANDOFF_RECEIVED, State.RECOVERY_REQUIRED)
        s = self.snapshot
        if (s.handoff is None or not s.receipt_evidence
                or s.continuation_request_id is None or not s.handoff.continuation_turn_id
                or evidence.handoff_id != s.handoff.handoff_id
                or evidence.continuation_turn_id != s.handoff.continuation_turn_id
                or evidence.intent_revision != s.revisions.intent_revision
                or evidence.execution_revision != s.revisions.execution_revision
                or evidence.workspace != s.workspace or not evidence.evidence_ref
                or not all(flag is True for flag in (evidence.current_intent_reconciled,
                            evidence.current_workspace_checked, evidence.unresolved_checked,
                            evidence.historical_next_action_reevaluated,
                            evidence.completed_work_not_repeated,
                            evidence.historical_instructions_not_reexecuted,
                            evidence.same_task_continued))):
            raise TransitionError("receipt alone is not current-state resume verification")
        self._change(state=State.RESUME_VERIFIED, barrier_requested=False)

    def reconcile_resume_context(self, *, intent_revision, execution_revision, workspace):
        """Publish trusted current observations after rollover, without old authority."""
        self._require(State.ROLLOVER_OBSERVED, State.HANDOFF_RECEIVED, State.RECOVERY_REQUIRED)
        s = self.snapshot
        if (type(intent_revision) is not int or type(execution_revision) is not int
                or intent_revision < s.revisions.intent_revision
                or execution_revision < s.revisions.execution_revision
                or workspace.mutation_epoch < s.workspace.mutation_epoch
                or (workspace != s.workspace and
                    (workspace.mutation_epoch <= s.workspace.mutation_epoch
                     or execution_revision <= s.revisions.execution_revision))):
            refusal = TransitionError('stale resume context')
            refusal.add_note('Yohaku rejected this observation. Read the current task and workspace again before reconciliation; do not reuse older evidence.')
            raise refusal
        self._change(revisions=replace(s.revisions, intent_revision=intent_revision,
                                      execution_revision=execution_revision), workspace=workspace)

    def recovery_required(self, reason: str):
        self._require(State.ROLLOVER_OBSERVED, State.HANDOFF_OFFERED,
                      State.HANDOFF_RECEIVED, State.RECOVERY_REQUIRED)
        self._change(state=State.RECOVERY_REQUIRED, lease=None, reason=reason)

    def fail(self, reason: str):
        if self.snapshot.state == State.RECOVERY_REQUIRED:
            self.recovery_required(reason)
        elif self.snapshot.request is not None and not self._completed():
            self.completion_unknown(reason)
        elif self.snapshot.request is not None:
            self.recovery_required(reason)
        else:
            self._change(state=State.FAILED, lease=None, barrier_requested=False, reason=reason)

    def return_to_work(self):
        self._require(State.DEFERRED, State.INVALIDATED, State.RESUME_VERIFIED)
        self._change(state=State.WORKING, barrier_requested=False, lease=None,
                     request=None, binding=None, completions=(), handoff=None,
                     continuation_request_id=None, injection_evidence=None,
                     receipt_evidence=None)

    @classmethod
    def restart(cls, saved: Snapshot, *, id_factory=None):
        """Restore trusted adapter data, never old authority or clock deadlines.

        A saved checkpoint is recoverable, not automatically current/authorized.
        Missing/corrupt journals must be rejected by the persistence adapter.
        """
        controller = cls(saved.thread_id, id_factory=id_factory)
        checkpoint = saved.recoverable_checkpoint
        if checkpoint and not checkpoint.commit_evidence:
            raise TransitionError("uncommitted checkpoint is not recoverable")
        if saved.request is not None:
            request = saved.request
            if (checkpoint is None or request.checkpoint_id != checkpoint.checkpoint_id
                    or request.transition_id != saved.transition_id
                    or request.boundary_id != saved.boundary_id
                    or request.thread_id != saved.thread_id
                    or request.rollover_generation != saved.rollover_generation
                    or (saved.binding and saved.binding.request != request)):
                raise TransitionError("inconsistent saved request journal")
        if saved.binding is not None and not controller._completion_policy.valid_binding(saved.binding):
            raise TransitionError("restart requires Codex version-1 completion binding")
        if saved.completions and (saved.binding is None or saved.request is None or any(
                e.binding != saved.binding or not e.evidence_ref
                or not controller._completion_policy.valid_event(e) for e in saved.completions)):
            raise TransitionError("inconsistent saved completion journal")
        controller._snapshot = saved
        if saved.request is not None:
            state = State.RECOVERY_REQUIRED if controller._completed() else State.AMBIGUOUS
        else:
            state = State.RECOVERY_REQUIRED
        controller._change(state=state, lease=None, barrier_requested=False,
                           revoked_lease_id=saved.lease.lease_id if saved.lease else saved.revoked_lease_id,
                           invalidated=True, checkpoint=checkpoint,
                           reason="restart requires reconciliation; authority discarded")
        return controller

    def reconcile_restart(self, *, current_workspace: WorkspaceRevision,
                          current_intent_revision: int, current_execution_revision: int,
                          evidence_ref: str):
        self._require(State.RECOVERY_REQUIRED)
        s = self.snapshot
        if (s.request is not None or not evidence_ref
                or current_intent_revision < s.revisions.intent_revision
                or current_execution_revision < s.revisions.execution_revision
                or (s.workspace and current_workspace.mutation_epoch < s.workspace.mutation_epoch)
                or (s.workspace and current_workspace != s.workspace
                    and (current_workspace.mutation_epoch <= s.workspace.mutation_epoch
                         or current_execution_revision <= s.revisions.execution_revision))):
            raise TransitionError("restart needs current state; pending requests must be reconciled")
        self._change(state=State.INVALIDATED, workspace=current_workspace,
                     revisions=replace(s.revisions, intent_revision=current_intent_revision,
                                       execution_revision=current_execution_revision))
        self.return_to_work()
