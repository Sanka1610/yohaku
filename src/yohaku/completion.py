"""Runtime-owned completion predicates for the serialized, in-memory Core.

Bindings expose request; evidence exposes binding, kind and evidence_ref. Kind
is a runtime-local deduplication key, not a shared event taxonomy. The policy is
trusted integration code fixed when the Controller is constructed. It performs
no I/O and must return booleans without mutating the Core.
"""

from typing import Protocol


class CompletionPolicy(Protocol):
    def valid_binding(self, binding) -> bool: ...

    def valid_event(self, event) -> bool: ...

    def completed(self, request, events) -> bool: ...

    def permits_continuation(self, binding, continuation) -> bool: ...
