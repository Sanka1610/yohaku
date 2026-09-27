"""Measured Codex manual-compaction protocol, behind an initialized transport."""

import json

from .controller import TransitionError
from .model import Completion, CompletionBinding, CompletionKind, State


class JsonLineSender:
    """Write to an already initialized App Server connection; owns no process/auth."""

    def __init__(self, stream):
        self.stream = stream

    def __call__(self, message):
        data = json.dumps(message, separators=(",", ":")) + "\n"
        if self.stream.write(data) != len(data):
            raise OSError("incomplete RPC write")
        self.stream.flush()


class ManualCompactBackend:
    def __init__(self, core, send, *, cursor=None):
        self.core = core
        self._send = send
        self._pending_send = False
        self._allow_binding = False
        self.cursor = cursor if cursor is not None else {"request_id": None, "generation": 0, "turn_id": None}
        self._validate_cursor()

    def _validate_cursor(self):
        c, r = self.cursor, self.core.snapshot.request
        if (type(c) is not dict or set(c) != {"request_id", "generation", "turn_id"}
                or type(c["generation"]) is not int or c["generation"] < 0
                or (c["turn_id"] is not None and (not isinstance(c["turn_id"], str) or not c["turn_id"]))):
            raise TransitionError("invalid runtime correlation journal")
        if r is None:
            if c != {"request_id": None, "generation": 0, "turn_id": None}:
                raise TransitionError("orphan runtime correlation")
        elif c["request_id"] != r.request_id or c["generation"] != r.rollover_generation:
            raise TransitionError("runtime correlation/request mismatch")
        if self.core.snapshot.binding and c["turn_id"] != self.core.snapshot.binding.compact_turn_id:
            raise TransitionError("runtime correlation/turn mismatch")

    def prepare(self, request):
        self.cursor = {"request_id": request.request_id,
                       "generation": request.rollover_generation, "turn_id": None}
        self._pending_send = True
        self._allow_binding = True

    def reset(self):
        self.cursor = {"request_id": None, "generation": 0, "turn_id": None}
        self._pending_send = False
        self._allow_binding = False

    def request(self, request):
        if (not self._pending_send or self.core.snapshot.state != State.ROLLOVER_REQUESTED
                or self.core.snapshot.request != request):
            raise TransitionError("only the Controller's new durable request may dispatch")
        self._pending_send = False
        self._send({"id": request.request_id, "method": "thread/compact/start",
                    "params": {"threadId": request.thread_id}})

    def _unknown(self, reason):
        if self.core.snapshot.state in (State.ROLLOVER_REQUESTED, State.AMBIGUOUS):
            self.core.completion_unknown(reason)
            return "ambiguous"
        return None

    def receive(self, message: dict, *, request):
        """The owner captures Request with the event, never stamps replay with latest.

        Native notifications have no Controller generation. Mapping starts only
        in this live dispatch's ordered stream, under exclusive-thread ownership.
        After restart, only the already persisted full binding can be consumed.
        """
        s = self.core.snapshot
        if request is None or request != s.request or not isinstance(message, dict):
            return None
        if "id" in message:
            if message["id"] != request.request_id:
                return None
            if "error" in message or message.get("result") != {}:
                return self._unknown("compact RPC outcome unknown")
            return "accepted" if self.core.accept_request(request) else None
        method, params = message.get("method"), message.get("params")
        if method not in {"turn/started", "item/started", "item/completed", "hook/completed", "turn/completed"}:
            return None
        if not isinstance(params, dict) or params.get("threadId") != request.thread_id:
            return None
        turn = params.get("turn")
        turn_id = turn.get("id") if isinstance(turn, dict) else params.get("turnId")
        if not isinstance(turn_id, str) or not turn_id:
            return self._unknown("missing event turn identity")
        if method == "turn/started":
            if self.cursor["turn_id"] == turn_id:
                return None
            if not self._allow_binding or self.cursor["turn_id"] is not None:
                return self._unknown("unmapped or conflicting turn")
            self.cursor = dict(self.cursor, turn_id=turn_id)
            return "turn_bound"
        if turn_id != self.cursor["turn_id"]:
            return self._unknown("event turn mismatch")
        item = params.get("item")
        if method in ("item/started", "item/completed"):
            if not isinstance(item, dict) or item.get("type") != "contextCompaction":
                return None
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id:
                return self._unknown("missing compaction item identity")
            binding = CompletionBinding(request, turn_id, item_id)
            if method == "item/started":
                if s.binding == binding:
                    return None
                if not self._allow_binding or s.binding is not None:
                    return self._unknown("unmapped or conflicting item")
                self.core.bind_completion(binding)
                return "item_bound"
            kind = CompletionKind.COMPACTION_ITEM
        elif method == "hook/completed":
            run = params.get("run")
            if not isinstance(run, dict) or run.get("eventName") != "postCompact":
                return None
            if run.get("status") != "completed":
                return self._unknown("PostCompact not successfully observed")
            binding, kind = s.binding, CompletionKind.POST_COMPACT
        elif method == "turn/completed":
            if not isinstance(turn, dict) or turn.get("status") != "completed" or turn.get("error") is not None:
                return self._unknown("compact turn not successfully completed")
            binding, kind = s.binding, CompletionKind.COMPACT_TURN
        else:
            return None
        if binding is None:
            return self._unknown("completion without durable identity mapping")
        # Only normalized identity and kind survive into the journal, never run.entries or turn.items.
        evidence = Completion(binding, kind, f"manual:{request.request_id}:{kind.name}")
        return "completion" if self.core.observe_completion(evidence) else None
