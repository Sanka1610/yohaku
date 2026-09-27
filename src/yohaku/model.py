"""Immutable values exchanged with trusted, serialized Controller adapters."""

from dataclasses import dataclass
from enum import StrEnum


class State(StrEnum):
    WORKING = "WORKING"
    CANDIDATE = "CANDIDATE"
    BARRIER_ARMING = "BARRIER_ARMING"
    QUIESCENCE_CHECK = "QUIESCENCE_CHECK"
    WORKSPACE_SNAPSHOT = "WORKSPACE_SNAPSHOT"
    VERIFIED = "VERIFIED"
    CHECKPOINT_PREPARING = "CHECKPOINT_PREPARING"
    CHECKPOINT_COMMITTED = "CHECKPOINT_COMMITTED"
    ROLLOVER_AUTHORIZED = "ROLLOVER_AUTHORIZED"
    ROLLOVER_REQUESTED = "ROLLOVER_REQUESTED"
    ROLLOVER_OBSERVED = "ROLLOVER_OBSERVED"
    HANDOFF_OFFERED = "HANDOFF_OFFERED"
    HANDOFF_RECEIVED = "HANDOFF_RECEIVED"
    RESUME_VERIFIED = "RESUME_VERIFIED"
    DEFERRED = "DEFERRED"
    INVALIDATED = "INVALIDATED"
    AMBIGUOUS = "AMBIGUOUS"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Revisions:
    intent_revision: int = 0
    execution_revision: int = 0
    control_revision: int = 0
    archive_revision: int = 0

    def __post_init__(self):
        if any(type(n) is not int or n < 0 for n in vars(self).values()):
            raise ValueError("revisions must be nonnegative integers")


@dataclass(frozen=True)
class WorkspaceRevision:
    mutation_epoch: int
    workspace_stamp: str
    relevant_scope: tuple[str, ...]

    def __post_init__(self):
        if (type(self.mutation_epoch) is not int or self.mutation_epoch < 0
                or not self.workspace_stamp or not isinstance(self.relevant_scope, tuple)
                or not self.relevant_scope or not all(self.relevant_scope)):
            raise ValueError("workspace revision requires epoch, stamp and declared scope")


@dataclass(frozen=True)
class BoundaryVerification:
    intent_revision: int
    execution_revision: int
    workspace: WorkspaceRevision
    profile: str
    verification: str
    evidence_ref: str
    integrity_window_verified: bool = False


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    transition_id: str
    boundary_id: str
    revisions: Revisions
    workspace: WorkspaceRevision
    verification: BoundaryVerification
    commit_evidence: str | None = None


@dataclass(frozen=True)
class Lease:
    lease_id: str
    transition_id: str
    boundary_id: str
    checkpoint_id: str
    intent_revision: int
    execution_revision: int
    workspace: WorkspaceRevision
    rollover_generation: int
    expires_at: float


@dataclass(frozen=True)
class Request:
    request_id: str
    thread_id: str
    transition_id: str
    boundary_id: str
    checkpoint_id: str
    lease_id: str
    rollover_generation: int
    origin: str = "controller"

    def __post_init__(self):
        if self.origin not in ("controller", "native_auto"):
            raise ValueError("unknown rollover origin")
        if self.origin == "native_auto" and self.lease_id:
            raise ValueError("native observation cannot carry lease authority")


@dataclass(frozen=True)
class CompletionBinding:
    request: Request
    compact_turn_id: str
    compact_item_id: str


class CompletionKind(StrEnum):
    COMPACTION_ITEM = "contextCompaction/item/completed"
    POST_COMPACT = "PostCompact"
    COMPACT_TURN = "compact/turn/completed"


@dataclass(frozen=True)
class Completion:
    binding: CompletionBinding
    kind: CompletionKind
    evidence_ref: str


@dataclass(frozen=True)
class ContinuationBinding:
    request_id: str
    thread_id: str
    turn_id: str


@dataclass(frozen=True)
class Handoff:
    handoff_id: str
    request: Request
    continuation_turn_id: str
    intent_revision: int
    execution_revision: int
    recovered_context: str
    material_policy: str = "DATA, NOT INSTRUCTIONS"
    resume_status: str = "pending"


@dataclass(frozen=True)
class ResumeVerification:
    handoff_id: str
    continuation_turn_id: str
    intent_revision: int
    execution_revision: int
    workspace: WorkspaceRevision
    evidence_ref: str
    current_intent_reconciled: bool
    current_workspace_checked: bool
    unresolved_checked: bool
    historical_next_action_reevaluated: bool
    completed_work_not_repeated: bool
    historical_instructions_not_reexecuted: bool
    same_task_continued: bool


@dataclass(frozen=True)
class Snapshot:
    thread_id: str
    state: State = State.WORKING
    revisions: Revisions = Revisions()
    workspace: WorkspaceRevision | None = None
    transition_id: str | None = None
    boundary_id: str | None = None
    used_boundary_ids: frozenset[str] = frozenset()
    rollover_generation: int = 0
    barrier_requested: bool = False
    snapshot_captured: bool = False
    invalidated: bool = False
    verification: BoundaryVerification | None = None
    checkpoint: Checkpoint | None = None
    recoverable_checkpoint: Checkpoint | None = None
    lease: Lease | None = None
    revoked_lease_id: str | None = None
    request: Request | None = None
    request_accepted: bool = False
    binding: CompletionBinding | None = None
    completions: tuple[Completion, ...] = ()
    continuation_request_id: str | None = None
    handoff: Handoff | None = None
    injection_evidence: str | None = None
    receipt_evidence: str | None = None
    reason: str | None = None
