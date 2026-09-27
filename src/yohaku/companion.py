"""Production owner of Core, durable state, and manual compact dispatch."""

from dataclasses import dataclass, replace
from math import isfinite
from time import monotonic

from .controller import Controller, TransitionError
from .manual import ManualCompactBackend
from .model import Lease, State, WorkspaceRevision
from .persistence import PersistenceError, SessionStore


@dataclass(frozen=True)
class CurrentState:
    intent_revision: int
    execution_revision: int
    workspace: WorkspaceRevision
    lease_id: str
    rollover_generation: int
    checkpoint_id: str
    thread_idle: bool


class CompanionController:
    """Serialize calls on the owner event loop, including observations and timers.

    send must write synchronously once on an initialized exclusive connection;
    it and read_current must not reenter this owner. The owner routes notifications with the
    immutable Request captured at observation, and calls poll_timeout regularly.
    """

    _STEPS = frozenset({"propose_boundary", "arm_barrier", "begin_quiescence_check",
                        "observe_quiescence", "capture_workspace", "verify_boundary",
                        "update_revisions", "invalidate", "expire_lease",
                        "return_to_work", "reconcile_restart", "fail"})

    def __init__(self, thread_id, send, *, create=False, clock=monotonic):
        self._clock = clock
        self._deadline = None
        self._blocked = False
        self.store = SessionStore(thread_id, create=create)
        try:
            if create:
                self._core = Controller(thread_id)
                cursor = None
            else:
                snapshot, cursor = self.store.latest
                # Crash after durable checkpoint rename but before journal commit:
                # adopt only the exact prepared ID as historical recovery data.
                prepared = snapshot.checkpoint
                if snapshot.state == State.CHECKPOINT_PREPARING and prepared:
                    for candidate in self.store.recovery_candidates():
                        if candidate.checkpoint_id == prepared.checkpoint_id:
                            if replace(candidate, commit_evidence=None) != prepared:
                                raise PersistenceError("prepared checkpoint content mismatch")
                            snapshot = replace(snapshot, recoverable_checkpoint=candidate)
                self._core = Controller.restart(snapshot)
            self._backend = ManualCompactBackend(self._core, send, cursor=cursor)
            self._save("created" if create else "restart")
        except Exception:
            self.store.close()
            raise

    @property
    def snapshot(self):
        return self._core.snapshot

    def close(self):
        self._blocked = True
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _ready(self):
        if self._blocked:
            raise PersistenceError("Controller stopped after storage failure or close")

    def _save(self, event):
        try:
            if self.snapshot.request is None:
                self._backend.reset()
            self.store.append(self.snapshot, self._backend.cursor, event)
        except Exception:
            self._blocked = True
            raise

    def step(self, operation, *args, **kwargs):
        self._ready()
        if operation not in self._STEPS:
            raise TransitionError("operation not exposed by this Companion stage")
        before = self.snapshot
        try:
            return getattr(self._core, operation)(*args, **kwargs)
        finally:
            if before != self.snapshot:
                self._save(operation)

    def require_work(self):
        self._ready()
        self._core.require_work()

    def commit_checkpoint(self):
        self._ready()
        checkpoint = self._core.prepare_checkpoint()
        self._save("checkpoint_preparing")
        try:
            committed = self.store.commit_checkpoint(checkpoint)
        except Exception:
            self._blocked = True
            raise
        self._core.checkpoint_committed(committed.checkpoint_id, commit_evidence=committed.commit_evidence)
        self._save("checkpoint_committed")
        return committed

    def authorize_rollover(self, *, ttl: float) -> Lease:
        self._ready()
        lease = self._core.authorize_rollover(now=self._clock(), ttl=ttl)
        self._save("authorized")
        return lease

    def request_compact(self, lease: Lease, read_current, *, completion_timeout=30.0):
        self._ready()
        if not isfinite(completion_timeout) or completion_timeout <= 0:
            raise ValueError("positive finite completion timeout required")
        if self.snapshot.state != State.ROLLOVER_AUTHORIZED:
            raise TransitionError("compact requires current authorization")
        try:
            checkpoint = self.snapshot.checkpoint
            if self.store.read_checkpoint(checkpoint.checkpoint_id) != checkpoint:
                raise PersistenceError("checkpoint changed before dispatch")
            current = read_current()
            if not isinstance(current, CurrentState):
                raise TransitionError("current revision observation required")
        except Exception:
            self._core.invalidate("final observation unavailable")
            self._save("invalidated")
            raise
        s = self.snapshot
        if (current.thread_idle is not True or lease != s.lease
                or current.lease_id != lease.lease_id
                or current.rollover_generation != s.rollover_generation
                or current.checkpoint_id != checkpoint.checkpoint_id):
            self._core.invalidate("final authority mismatch")
            self._save("invalidated")
            raise TransitionError("final authority mismatch; compact not sent")
        try:
            request = self._core.request_rollover(
                lease, now=self._clock(), intent_revision=current.intent_revision,
                execution_revision=current.execution_revision, workspace=current.workspace)
        except TransitionError:
            self._save("invalidated")
            raise
        self._backend.prepare(request)
        self._save("rollover_requested")  # must reach fsync(parent) before any RPC byte
        # Journal sync can be slow. Re-read once at the actual dispatch boundary.
        # Since send has not been entered, failure here is conclusive non-execution.
        try:
            final = read_current()
            valid = final == current and self._clock() < lease.expires_at
        except Exception:
            valid = False
        if not valid:
            self._core.confirm_not_executed(request, evidence_ref="controller-no-dispatch")
            self._save("invalidated")
            raise TransitionError("final dispatch revalidation failed; compact not sent")
        self._ready()
        self._deadline = self._clock() + completion_timeout
        try:
            self._backend.request(request)
        except Exception:
            self._core.completion_unknown("transport outcome unknown")
            self._save("ambiguous")
            raise TransitionError("compact dispatch uncertain; reconcile, do not retry") from None
        return request

    def receive(self, message, *, request):
        self._ready()
        before = self.snapshot
        event = self._backend.receive(message, request=request)
        if event or before != self.snapshot:
            self._save(event or "ambiguous")
        if self.snapshot.state == State.ROLLOVER_OBSERVED:
            self._deadline = None
        return event is not None

    def poll_timeout(self):
        self._ready()
        if self.snapshot.state == State.ROLLOVER_REQUESTED and self._core.expire_lease(now=self._clock()):
            self._save("ambiguous")
            return True
        if (self._deadline is not None and self._clock() >= self._deadline
                and self.snapshot.state == State.ROLLOVER_REQUESTED):
            self._core.completion_unknown()
            self._save("ambiguous")
            return True
        return False
