"""Bounded automatic-compaction observation, using existing storage and recovery."""

from dataclasses import replace
import time

from .codec import encode
from .controller import TransitionError
from .model import Completion, CompletionBinding, CompletionKind, State
from .persistence import _mkdir
from .recovery import EmergencyDelta, RecoveredData


class NativeCompact:
    """One native rollover per attachment, same-turn continuation, no RPC dispatch.

    capture(checkpoint_id, pending_keys) supplies selected, unverified progress.
    settle(delta) independently incorporates terminal pre-compact work using the
    existing work ledger and returns updated RecoveredData. observe/recovered
    retain the RecoveryLifecycle contract.
    A missing Hook, stream gap, second compact or conflicting manual request stops
    this attachment. Runtime Hook failure may still fail open.
    """

    def __init__(self, host, *, capture, settle, observe, recovered, timeout=60.0):
        import math
        if host.work is None or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("native recovery needs a work ledger and positive timeout")
        if host.companion.snapshot.request is not None:
            raise TransitionError("native attachment cannot reconstruct an inflight rollover")
        self.host, self.owner = host, host.companion
        self.capture, self.settle, self.observe, self.recovered = capture, settle, observe, recovered
        self.timeout, self.deadline = timeout, None
        self.turn = self.pre_hook = self.post_hook = None
        self.pre_completed = False
        self.manual_pre = False
        self.delta = None
        self.stopped = False

    def stop(self):
        self.stopped = True
        self.owner.step("fail", "native compact evidence incomplete")

    def poll(self):
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.deadline = None
            if self.owner.snapshot.state not in (State.HANDOFF_OFFERED, State.HANDOFF_RECEIVED, State.RESUME_VERIFIED):
                self.stop()

    def deliver(self, payload):
        if payload.get("hook_event_name") != "PreCompact":
            return None
        if payload.get("trigger") == "manual":
            s = self.owner.snapshot
            self.manual_pre = bool(s.request and s.request.origin == "controller"
                and self.pre_hook and payload.get("session_id") == s.thread_id
                and payload.get("turn_id") == self.turn and payload.get("cwd") == self.host.work.cwd)
            return {} if self.manual_pre else {"continue": False}
        if payload.get("trigger") != "auto":
            return {"continue": False}
        if payload.get("session_id") != self.owner.snapshot.thread_id:
            return {"continue": False}
        try:
            if (self.stopped or self.delta is not None or not self.pre_hook
                    or payload.get("cwd") != self.host.work.cwd
                    or not self.turn or payload.get("turn_id") != self.turn
                    or self.owner.snapshot.request is not None or self.host.work.active
                    or self.host.work.observation_uncertain):
                raise TransitionError("uncorrelated native precompact")
            checkpoint = self.owner.snapshot.recoverable_checkpoint
            if checkpoint is None:
                raise TransitionError("historical checkpoint required")
            delta = self.capture(checkpoint.checkpoint_id, self.host.work.pending_results)
            if (not isinstance(delta, EmergencyDelta) or delta.checkpoint_id != checkpoint.checkpoint_id
                    or delta.logical_task_id != self.recovered.logical_task_id
                    or delta.intent_revision < self.owner.snapshot.revisions.intent_revision
                    or delta.execution_revision < self.owner.snapshot.revisions.execution_revision
                    or delta.workspace.mutation_epoch < self.owner.snapshot.workspace.mutation_epoch
                    or (delta.workspace != self.owner.snapshot.workspace and
                        delta.workspace.mutation_epoch <= self.owner.snapshot.workspace.mutation_epoch)
                    or set(delta.pending_tool_ids) != {k.tool_use_id for k in self.host.work.pending_results}):
                raise TransitionError("invalid emergency observation")
            directory = self.owner.store.path / "emergency"
            _mkdir(directory)
            self.owner.store._write(directory / (delta.snapshot_id + ".json"), {
                "thread_id": self.owner.snapshot.thread_id, "turn_id": self.turn,
                "precompact_hook_id": self.pre_hook, "delta": encode(delta)})
            self.delta = delta
            request = self.owner._core.observe_native_start()
            self.owner._backend.cursor = {"request_id": request.request_id,
                "generation": request.rollover_generation, "turn_id": self.turn}
            self.owner._save("native_observed")
            self.deadline = time.monotonic() + self.timeout
            return {}
        except Exception:
            self.stop()
            return {"continue": False}

    def receive(self, message):
        if message is None:
            if self.delta is not None and self.owner.snapshot.state != State.RESUME_VERIFIED:
                self.stop()
            return
        p, method = message.get("params", {}), message.get("method")
        if p.get("threadId") != self.owner.snapshot.thread_id:
            return
        s = self.owner.snapshot
        turn = (p.get("turn") or {}).get("id") or p.get("turnId")
        run, item = p.get("run") or {}, p.get("item") or {}
        if s.request and s.request.origin == "controller":
            if method == "hook/started" and run.get("eventName") == "preCompact":
                self.turn, self.pre_hook, self.manual_pre = turn, run.get("id"), False
            elif (method == "item/started" and item.get("type") == "contextCompaction"
                  and not self.manual_pre):
                self.stop()  # Missing Hook cannot classify this as the manual request.
            return
        if method == "turn/started" and self.delta is None:
            self.turn = turn
        if self.stopped:
            return
        if turn != self.turn:
            if self.delta and item.get("type") == "contextCompaction":
                self.stop()
            return
        if method == "hook/started" and run.get("eventName") == "preCompact":
            if self.delta is not None:
                self.stop()
            else:
                self.pre_hook = run.get("id")
        elif method == "hook/completed" and run.get("eventName") == "preCompact":
            if self.delta and run.get("id") == self.pre_hook and run.get("status") == "completed":
                self.pre_completed = True
            elif self.delta:
                self.stop()
        elif method in ("item/started", "item/completed") and item.get("type") == "contextCompaction":
            if not self.delta or not self.pre_completed or not item.get("id"):
                self.stop()
                return
            binding = CompletionBinding(s.request, self.turn, item["id"])
            if method == "item/started":
                self.owner._core.bind_completion(binding)
                self.owner._save("native_item_bound")
            elif s.binding == binding:
                self.owner._core.observe_completion(Completion(binding, CompletionKind.COMPACTION_ITEM,
                    "native-item:" + item["id"]))
                self.owner._save("native_item_completed")
            else:
                self.stop()
        elif self.delta and method == "hook/started" and run.get("eventName") == "postCompact":
            if not s.binding or not any(e.kind == CompletionKind.COMPACTION_ITEM for e in s.completions):
                self.stop()
            else:
                self.post_hook = run.get("id")
        elif self.delta and method == "hook/completed" and run.get("eventName") == "postCompact":
            if not self.post_hook or run.get("id") != self.post_hook or run.get("status") != "completed":
                self.stop()
            else:
                self.owner._core.observe_completion(Completion(s.binding, CompletionKind.POST_COMPACT,
                    "native-postcompact:" + self.post_hook))
                self.owner._save("native_completed")
        elif self.delta and method == "hook/started" and run.get("eventName") == "sessionStart":
            if s.state != State.ROLLOVER_OBSERVED or not run.get("id"):
                self.stop()
                return
            try:
                recovered = self.settle(self.delta)
                self.host.work.require_quiescent()
                if (not isinstance(recovered, RecoveredData)
                        or recovered.logical_task_id != self.recovered.logical_task_id):
                    raise TransitionError("settlement must preserve the logical task")
                self.owner.recovery.start(replace(recovered, emergency=self.delta),
                    cwd=self.host.work.cwd, observe=self.observe, native_turn_id=self.turn)
                self.host.deadline = time.monotonic() + self.timeout
                self.deadline = None
            except Exception:
                self.stop()
