"""Best-effort admission for the measured Bash/apply_patch Hook paths.

Attach before the first work turn on an exclusively owned, observed-idle thread.
All methods run on the RuntimeHost owner loop. This in-memory ledger is not a
process detector or restart reconstruction; missing observations stop quiescence.
"""

from dataclasses import dataclass
from pathlib import Path

from .controller import TransitionError
from .model import State


@dataclass(frozen=True)
class WorkKey:
    turn_id: str
    tool_use_id: str
    tool_name: str


def _deny():
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Yohaku work admission unavailable"}}


class WorkPlane:
    TOOLS = frozenset({"Bash", "apply_patch"})

    def __init__(self, companion, *, cwd):
        self.owner = companion
        path = Path(cwd)
        if not path.is_absolute():
            raise ValueError("absolute work workspace required")
        self.cwd = str(path.resolve())
        self._turn = None
        self._closed_turns = set()
        self._entries = {}
        self._uncertain = False

    @property
    def active(self):
        return tuple(k for k, phase in self._entries.items() if phase == "admitted")

    @property
    def pending_results(self):
        return tuple(k for k, phase in self._entries.items() if phase == "pending")

    @property
    def observation_uncertain(self):
        return self._uncertain

    def observation_lost(self):
        self._uncertain = True
        if self.owner.snapshot.state not in (State.WORKING, State.RESUME_VERIFIED):
            self.owner.step("invalidate", "work observation incomplete")

    def receive(self, message):
        if message is None:
            self.observation_lost()
            return
        p = message.get("params", {})
        if p.get("threadId") != self.owner.snapshot.thread_id:
            return
        method, turn = message.get("method"), p.get("turn", {})
        ident = turn.get("id")
        if method == "turn/started" and isinstance(ident, str) and ident:
            if ident in self._closed_turns:
                return
            if self._turn not in (None, ident):
                self.observation_lost()
            self._turn = ident
        elif method == "turn/completed" and isinstance(ident, str) and ident:
            self._closed_turns.add(ident)
            if ident == self._turn:
                self._turn = None
            # Keep unincorporated work across turn completion; discard only tombstones.
            self._entries = {k: v for k, v in self._entries.items()
                             if k.turn_id != ident or v in ("admitted", "pending")}
        elif method == "hook/completed":
            run = p.get("run", {})
            if (p.get("turnId") == self._turn
                    and run.get("eventName") in ("preToolUse", "postToolUse")
                    and run.get("status") != "completed"
                    and not (run.get("eventName") == "preToolUse"
                             and run.get("status") == "blocked")):
                self.observation_lost()

    def _continuation_work(self, turn_id):
        s, cursor = self.owner.snapshot, self.owner.recovery.cursor
        return (s.state in (State.HANDOFF_OFFERED, State.HANDOFF_RECEIVED)
                and s.handoff is not None and s.handoff.continuation_turn_id == turn_id
                and cursor is not None and cursor.injection_confirmed
                and not cursor.stopped and not cursor.terminal)

    def deliver(self, payload):
        self.owner._ready()
        event = payload.get("hook_event_name")
        pre = event == "PreToolUse"
        if event not in ("PreToolUse", "PostToolUse"):
            raise TransitionError("not a work Hook")
        turn, tool, name = (payload.get(k) for k in ("turn_id", "tool_use_id", "tool_name"))
        if (payload.get("session_id") != self.owner.snapshot.thread_id
                or payload.get("cwd") != self.cwd or not isinstance(name, str)
                or name not in self.TOOLS
                or not all(isinstance(v, str) and 0 < len(v) <= 160 for v in (turn, tool))):
            return _deny() if pre else {}
        key = WorkKey(turn, tool, name)
        phase = self._entries.get(key)
        if not pre:
            if phase == "admitted":
                self._entries[key] = "pending"
            elif phase not in ("pending", "incorporated"):
                # A Post without admission may be a fail-open execution.
                self.observation_lost()
            return {}
        if turn != self._turn or phase is not None:
            return _deny()  # No replay can grant another execution permit.
        s = self.owner.snapshot
        ordinary = s.state == State.WORKING and not s.barrier_requested
        if self._uncertain or not (ordinary or self._continuation_work(turn)):
            self._entries[key] = "denied"
            return _deny()
        # Registration precedes Hook response; arm/check uses this same owner loop.
        self._entries[key] = "admitted"
        return {}

    def incorporate(self, key, *, execution_complete, evidence_ref):
        """Trusted host attests terminal execution AND effects reflected in current state.

        PostToolUse can describe a yielded shell session. It is never enough on
        its own. The host updates its revision/workspace observer before this call;
        failed tools also require incorporation of their possible partial effects.
        """
        self.owner._ready()
        if (execution_complete is not True or not isinstance(evidence_ref, str)
                or not evidence_ref.strip() or len(evidence_ref) > 160):
            raise TransitionError("terminal execution and incorporated-result evidence required")
        phase = self._entries.get(key)
        if phase == "incorporated":
            return False
        if phase != "pending":
            raise TransitionError("matching PostToolUse observation required")
        self._entries[key] = "incorporated"
        return True

    def quiesce(self, boundary_id):
        """Arm and inspect once; DEFER releases immediately without awaiting work."""
        self.owner.step("propose_boundary", boundary_id)
        if self.owner.snapshot.state != State.CANDIDATE:
            return self.owner.snapshot.state
        self.owner.step("arm_barrier")
        self.owner.step("begin_quiescence_check")
        self.owner.step("observe_quiescence", relevant_work_remaining=bool(
            self.active or self.pending_results or self._uncertain))
        result = self.owner.snapshot.state
        if result == State.DEFERRED:
            self.owner.step("return_to_work")
        return result

    def cancel(self):
        if self.owner.snapshot.request is not None:
            raise TransitionError("dispatched rollover requires reconciliation, not cancel")
        self.owner.step("invalidate", "boundary cancelled")

    def require_quiescent(self):
        if self.active or self.pending_results or self._uncertain:
            self.owner.step("invalidate", "work remains or observation incomplete")
            raise TransitionError("work ledger does not permit compact")
