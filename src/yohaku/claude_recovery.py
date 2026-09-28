"""Opt-in C-CLI recovery on the same live, exclusively owned print process.

One controller-submitted recovery input; native foreground tool IDs are correlated
with its locally owned dispatch ID. Receipt, fresh read, action and task assessment
are separate evidence. The host serializes callbacks and seals the compact window
before beginning recovery. No native turn ID or semantic understanding is inferred.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from .claude import ClaudeManualCompletionPolicy, _identity, _sequence
from .claude_adapter import ClaudeCLIAdapter
from .controller import TransitionError
from .model import ContinuationBinding, ResumeVerification, State
from .persistence import _read
from .recovery import CurrentContext, HandoffDocument, RecoveredData, ResumeProof


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class ClaudeContinuationBinding(ContinuationBinding):
    # turn_id is the owner's one recovery-input ID, not a claimed native turn ID.
    attachment_id: str
    compact_request_id: str
    generation: int


@dataclass(frozen=True)
class ClaudeDelivery:
    binding: ClaudeContinuationBinding
    seq: int
    prompt_hash: str
    evidence_ref: str
    submitted: bool


class ClaudeRecoveryCompletionPolicy(ClaudeManualCompletionPolicy):
    """Reuse the exact manual predicate; opt in only to a bound recovery input."""

    def permits_continuation(self, binding, continuation):
        return (self.valid_binding(binding) and isinstance(continuation, ClaudeContinuationBinding)
                and continuation.attachment_id == binding.attachment_id
                and continuation.thread_id == binding.session_id
                and continuation.compact_request_id == binding.request.request_id
                and type(continuation.generation) is int and continuation.generation == 1
                and _identity(continuation.request_id) and _identity(continuation.turn_id)
                and continuation.request_id != binding.request.request_id)


class ClaudeCLIRecoveryAdapter(ClaudeCLIAdapter):
    _policy_type = ClaudeRecoveryCompletionPolicy

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.document = None
        self.continuation = None
        self.delivery = None
        self.active = None
        self.tools = {}
        self.receipt_tool = None
        self.read_tool = None
        self.action_tool = None
        self.fresh = None
        self.fresh_token = None
        self.terminal = None
        self.last_seq = 0

    def _record(self, kind, **data):
        try:
            return super()._record(kind, **data)
        except BaseException:
            self.stopped = True
            self.core.fail("C-CLI recovery persistence uncertain")
            raise

    def _stop(self, reason):
        self.stopped = True
        self.core.fail(reason)
        raise TransitionError(reason)

    def _event(self, binding, session_id, seq, evidence_ref):
        self._ready()
        if (self.continuation is None or binding != self.continuation
                or session_id != self.store.thread_id or not _sequence(seq)
                or seq <= self.last_seq or not _identity(evidence_ref)):
            self._stop("uncorrelated or stale recovery event")
        self.last_seq = seq

    def receipt_fields(self):
        d, b = self.document, self.continuation
        return dict(handoff_id=d.handoff_id, checkpoint_id=d.request.checkpoint_id,
            checkpoint_hash=self.checkpoint_hash, handoff_hash=digest(d.storage_payload()),
            request_id=d.request.request_id, session_id=b.thread_id, attachment_id=b.attachment_id,
            generation=b.generation, continuation_request_id=b.request_id,
            continuation_turn_id=b.turn_id, logical_task_id=d.recovered.logical_task_id)

    def begin_recovery(self, recovered, *, cwd, instructions, send):
        """Persist and submit one handoff. send only flushes input; it must not pump callbacks.

        instructions is trusted host code: callable(receipt_fields) -> current
        control instructions. Receipt fields must be supplied explicitly by the
        native tool call, not read from a hidden file by an automatic ACK helper.
        send(prompt, binding) returns ClaudeDelivery after submitting exact bytes.
        Transport submission is only delivery evidence; receipt is still absent.
        """
        self._ready()
        if self.document is not None or self.core.snapshot.state != State.ROLLOVER_OBSERVED:
            raise TransitionError("one recovery input after observed compaction required")
        try:
            s = self.core.snapshot
            if (not isinstance(recovered, RecoveredData)
                    or recovered.logical_task_id != self.current.logical_task_id
                    or recovered.archive_ids != self.store.checkpoint_archive_ids(s.checkpoint.checkpoint_id)
                    or self.store.read_checkpoint(s.checkpoint.checkpoint_id) != s.checkpoint):
                self._stop("handoff does not match committed task/checkpoint")
            self.checkpoint_hash = _read(self.store.checkpoints / f"{s.checkpoint.checkpoint_id}.json")["sha256"]
            self.document = HandoffDocument(uuid4().hex, s.request, s.checkpoint.revisions,
                s.checkpoint.workspace, str(Path(cwd).resolve()), recovered)
            self.store.commit_handoff(self.document)
            if self.store.read_handoff(self.document.handoff_id) != self.document:
                self._stop("handoff readback mismatch")
            permit = self.core.claim_continuation()
            self.continuation = ClaudeContinuationBinding(permit, s.thread_id, uuid4().hex,
                s.binding.attachment_id, s.request.request_id, s.request.rollover_generation)
            self.last_seq = s.completions[0].closed_seq
            self.prompt = self.document.render() + "\n[Current Yohaku recovery instructions]\n" + instructions(self.receipt_fields())
            if len(self.prompt.encode()) > 100000:
                self._stop("oversized recovery input")
            self.core.offer_handoff(self.continuation, recovered_context=self.document.render(),
                                   handoff_id=self.document.handoff_id)
            self._record("handoff_offered", binding=asdict(self.continuation),
                         receipt=self.receipt_fields(), prompt_hash=digest(self.prompt))
            sent = send(self.prompt, self.continuation)
            if (not isinstance(sent, ClaudeDelivery) or sent.binding != self.continuation
                    or sent.prompt_hash != digest(self.prompt) or sent.submitted is not True):
                self._stop("handoff submission uncertain")
            self._event(sent.binding, sent.binding.thread_id, sent.seq, sent.evidence_ref)
            self.delivery = self._record("handoff_submitted", delivery=asdict(sent))
            return self.continuation
        except BaseException:
            self.stopped = True
            self.core.fail("C-CLI handoff submission uncertain")
            raise

    def pre_tool(self, *, binding, session_id, seq, tool_id, operation, evidence_ref):
        self._event(binding, session_id, seq, evidence_ref)
        if (not self.delivery or self.terminal or self.active is not None
                or not _identity(tool_id) or tool_id in self.tools):
            self._stop("recovery tool lacks unique foreground admission")
        expected = "receipt" if self.receipt_tool is None else "observe" if self.read_tool is None else "action"
        if operation != expected or self.action_tool is not None:
            self._stop("receipt, fresh observation and one action must occur in order")
        self.active = dict(tool_id=tool_id, operation=operation, pre_seq=seq,
                           status="active", handled=False)
        self.tools[tool_id] = self.active
        self._record("recovery_tool_start", binding=asdict(binding), **self.active)

    def _handler(self, operation):
        self._ready()
        if self.active is None or self.active["operation"] != operation or self.active["handled"]:
            self._stop("missing or repeated native recovery tool handler")

    def _result(self, payload):
        self.active.update(handled=True, result_hash=digest(payload))
        return payload

    def acknowledge(self, fields):
        self._handler("receipt")
        if (self.core.snapshot.state != State.HANDOFF_OFFERED or not isinstance(fields, dict)
                or fields != self.receipt_fields() or type(fields.get("generation")) is not int):
            self._stop("explicit handoff receipt identity mismatch")
        self._record("receipt_handler", tool_id=self.active["tool_id"], receipt=fields)
        return self._result({"receipt": "accepted", "handoff_id": self.document.handoff_id})

    def observe_fresh(self, observe, *, describe=None):
        self._handler("observe")
        if self.core.snapshot.state != State.HANDOFF_RECEIVED:
            self._stop("fresh read requires a completed explicit receipt")
        try:
            current = observe()
            if not isinstance(current, CurrentContext) or current.logical_task_id != self.current.logical_task_id:
                self._stop("fresh task identity mismatch")
            details = describe() if describe is not None else {}
            if observe() != current:
                self._stop("task changed during fresh observation")
            self.core.reconcile_resume_context(intent_revision=current.intent_revision,
                execution_revision=current.execution_revision, workspace=current.workspace)
            self.fresh, self.fresh_token = current, uuid4().hex
            self._record("fresh_observation", tool_id=self.active["tool_id"], current=asdict(current),
                         fresh_read_id=self.fresh_token)
            return self._result(dict(fresh_read_id=self.fresh_token, current=asdict(current), task=details))
        except BaseException:
            self.stopped = True
            self.core.fail("fresh observation uncertain")
            raise

    def perform_action(self, fields, *, observe, execute):
        self._handler("action")
        if (self.read_tool is None or fields != {"fresh_read_id": self.fresh_token}
                or self.core.snapshot.state != State.HANDOFF_RECEIVED):
            self._stop("action lacks receipt and completed fresh read")
        try:
            if observe() != self.fresh:
                self._stop("current state changed after fresh read")
            value = execute()
            self._record("recovery_action_handler", tool_id=self.active["tool_id"])
            return self._result(value)
        except BaseException:
            self.stopped = True
            self.core.fail("recovery action uncertain")
            raise

    def post_tool(self, *, binding, session_id, seq, tool_id, result, successful, evidence_ref):
        self._event(binding, session_id, seq, evidence_ref)
        try:
            result_hash = digest(result)
        except (TypeError, ValueError):
            self._stop("native tool result is not canonical JSON")
        if (self.active is None or self.active["tool_id"] != tool_id
                or not self.active["handled"] or successful is not True
                or result_hash != self.active["result_hash"]):
            self._stop("native tool result does not match the executed recovery handler")
        r = self.active
        ref = self._record("recovery_tool_completed", tool_id=tool_id, post_seq=seq,
                           result_hash=r["result_hash"], evidence_ref=evidence_ref)
        r.update(status="ok", post_seq=seq, evidence_ref=ref)
        if r["operation"] == "receipt":
            self.core.receive_handoff(self.core.snapshot.handoff, injection_evidence=self.delivery,
                                      receipt_evidence=ref)
            self.receipt_tool = tool_id
        elif r["operation"] == "observe":
            self.read_tool = tool_id
        else:
            self.action_tool = tool_id
        self.active = None

    def observe_terminal(self, *, binding, session_id, seq, successful, evidence_ref):
        self._event(binding, session_id, seq, evidence_ref)
        if (self.terminal or successful is not True or self.active is not None
                or not all((self.receipt_tool, self.read_tool, self.action_tool))):
            self._stop("terminal success lacks independent recovery evidence")
        self.terminal = self._record("recovery_terminal", binding=asdict(binding),
                                     seq=seq, evidence_ref=evidence_ref)

    def verify_resume(self, *, observe, assess):
        self._ready()
        if not self.terminal or self.active is not None or self.core.snapshot.state != State.HANDOFF_RECEIVED:
            self._stop("resume requires completed receipt/read/action and terminal evidence")
        try:
            before = observe()
            proof = assess(self.document, tuple(dict(r) for r in self.tools.values()))
            current = observe()
            if (not isinstance(proof, ResumeProof) or before != current or proof.current != current
                    or current.logical_task_id != self.current.logical_task_id
                    or current.intent_revision != self.fresh.intent_revision
                    or proof.read_item_ids != (self.read_tool,)
                    or proof.action_item_ids != (self.action_tool,)
                    or not _identity(proof.evidence_ref)):
                self._stop("task-specific resume assessment is absent, stale or uncorrelated")
            self.core.reconcile_resume_context(intent_revision=current.intent_revision,
                execution_revision=current.execution_revision, workspace=current.workspace)
            self._record("resume_assessment", proof=asdict(proof))
            self.core.verify_resume(ResumeVerification(self.document.handoff_id, self.continuation.turn_id,
                current.intent_revision, current.execution_revision, current.workspace, proof.evidence_ref,
                True, True, proof.unresolved_checked, proof.next_action_reevaluated,
                proof.completed_work_not_repeated, proof.historical_instructions_not_reexecuted,
                proof.same_task_continued))
            self._record("resume_verified", handoff_id=self.document.handoff_id, current=asdict(current))
            return self.core.snapshot
        except BaseException:
            self.stopped = True
            self.core.fail("C-CLI resume assessment failed")
            raise
