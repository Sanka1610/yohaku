"""OpenCode V2 2.0.21 native proof for one fresh, owned session.

Admission is not completion. The trusted adapter supplies ordered native events,
an independent SQLite projection and a newly fetched active context. This policy
does no I/O. Proofs are in-memory only; schema-1 restart is unsupported.
"""

from dataclasses import dataclass

from .model import Request


OPENCODE_VERSION = "2.0.21"


@dataclass(frozen=True)
class OpenCodeCompactBinding:
    request: Request
    session_id: str
    server_url: str
    directory: str
    native_id: str
    version: str = OPENCODE_VERSION


@dataclass(frozen=True)
class OpenCodeNativeCompletion:
    binding: OpenCodeCompactBinding
    evidence_ref: str
    started: dict
    ended: dict
    context_message: dict
    sqlite_message: dict
    sqlite_seq: int
    sqlite_updated: int
    before_ids: tuple[str, ...]
    current_ids: tuple[str, ...]
    session_after: str
    settled: bool
    observation_intact: bool

    @property
    def kind(self):
        return "opencode/native-completion-readback"


class OpenCodeNativeCompletionPolicy:
    def valid_binding(self, binding):
        return (isinstance(binding, OpenCodeCompactBinding)
                and isinstance(binding.request, Request)
                and binding.request.origin == "controller"
                and binding.request.rollover_generation == 1
                and binding.session_id == binding.request.thread_id
                and bool(binding.server_url) and bool(binding.directory)
                and isinstance(binding.native_id, str) and binding.native_id.startswith("msg_")
                and binding.version == OPENCODE_VERSION)

    def valid_event(self, event):
        if not isinstance(event, OpenCodeNativeCompletion) or not self.valid_binding(event.binding):
            return False
        b = event.binding
        start, end, message = event.started, event.ended, event.context_message
        try:
            return (bool(event.evidence_ref)
                    and start["type"] == "session.compaction.started"
                    and end["type"] == "session.compaction.ended"
                    and bool(start["id"]) and bool(end["id"]) and start["id"] != end["id"]
                    and start["data"]["inputID"] == b.native_id
                    and all(e["data"]["sessionID"] == b.session_id
                            and e["data"]["reason"] == "manual"
                            and e["location"]["directory"] == b.directory
                            and e["durable"]["aggregateID"] == b.session_id
                            and e["durable"]["version"] == 1 for e in (start, end))
                    and type(start["durable"]["seq"]) is int
                    and type(end["durable"]["seq"]) is int
                    and 0 <= start["durable"]["seq"] < end["durable"]["seq"]
                    and start["created"] <= end["created"]
                    and message["id"] == b.native_id and message["type"] == "compaction"
                    and message["status"] == "completed" and message["reason"] == "manual"
                    and message["time"]["created"] == start["created"]
                    and bool(message["summary"]) and message["summary"] == end["data"]["text"]
                    and all(message.get(k) == end["data"].get(k) for k in
                            ("recent", "model", "providerState", "providerContext", "tokens", "cost"))
                    and event.sqlite_message == message
                    and event.sqlite_seq == start["durable"]["seq"]
                    and event.sqlite_updated >= end["created"]
                    and b.native_id not in event.before_ids
                    and event.current_ids.count(b.native_id) == 1
                    and event.current_ids != event.before_ids
                    and event.session_after == b.session_id
                    and event.settled is True and event.observation_intact is True)
        except (KeyError, TypeError, AttributeError):
            return False

    def completed(self, request, events):
        return (len(events) == 1 and self.valid_event(events[0])
                and events[0].binding.request == request)

    def permits_continuation(self, binding, continuation):
        # A native next prompt is available; qualified Yohaku handoff is not.
        return False
