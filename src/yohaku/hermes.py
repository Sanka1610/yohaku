"""H-CLI-01 completion predicate; no Hermes host, transport or storage adapter.

Only the pinned, exclusive fresh session and its first manual compression are
covered. Readback is supplied by trusted host instrumentation after native
manual compression updates host history and an independent SessionDB read agrees.
Engine return alone is insufficient. Fresh task reads and controller-driven
continuation follow separately; no receipt, barrier or restart is inferred.
"""

from dataclasses import dataclass
import re

from .model import Request


HERMES_VERSION = "0.21.0"
HERMES_SOURCE = "c5594ec4b34097cafbe24deb6dfd9ac4b21d411d"


@dataclass(frozen=True)
class HermesManualBinding:
    request: Request
    session_id: str
    request_seq: int
    version: str
    source_commit: str
    exclusive_fresh_session: bool


@dataclass(frozen=True)
class HermesManualCompletion:
    binding: HermesManualBinding
    evidence_ref: str
    request_id: str
    readback_seq: int
    session_before: str
    session_after: str
    compressor_count: int
    manual_requests: int
    readback_count: int
    host_changed: bool
    independent_db_read: bool
    db_payload_matches_host: bool
    host_history_hash: str
    db_history_hash: str
    host_history_count: int
    db_message_count: int
    archived_rows: int

    @property
    def kind(self):
        return "hermes/host-storage-readback"


class HermesManualCompletionPolicy:
    def valid_binding(self, binding):
        return (isinstance(binding, HermesManualBinding)
                and isinstance(binding.request, Request)
                and binding.request.origin == "controller"
                and type(binding.request.rollover_generation) is int
                and binding.request.rollover_generation == 1
                and isinstance(binding.session_id, str) and bool(binding.session_id)
                and binding.session_id == binding.request.thread_id
                and type(binding.request_seq) is int and binding.request_seq > 0
                and binding.version == HERMES_VERSION and binding.source_commit == HERMES_SOURCE
                and binding.exclusive_fresh_session is True)

    def valid_event(self, event):
        if not isinstance(event, HermesManualCompletion) or not self.valid_binding(event.binding):
            return False
        b = event.binding
        return (event.request_id == b.request.request_id
                and type(event.readback_seq) is int and event.readback_seq > b.request_seq
                and event.session_before == event.session_after == b.session_id
                and all(type(n) is int and n == 1 for n in (
                    event.compressor_count, event.manual_requests, event.readback_count))
                and all(flag is True for flag in (event.host_changed,
                    event.independent_db_read, event.db_payload_matches_host))
                and isinstance(event.host_history_hash, str)
                and re.fullmatch(r"[0-9a-f]{64}", event.host_history_hash) is not None
                and event.db_history_hash == event.host_history_hash
                and type(event.host_history_count) is int and event.host_history_count > 0
                and type(event.db_message_count) is int
                and event.db_message_count == event.host_history_count
                and type(event.archived_rows) is int and event.archived_rows > 0)

    def completed(self, request, events):
        return (len(events) == 1 and self.valid_event(events[0])
                and events[0].binding.request == request)

    def permits_continuation(self, binding, continuation):
        # In-place compression has no separate compact turn/item identity.
        return self.valid_binding(binding) and bool(continuation.turn_id)
