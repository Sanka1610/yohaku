"""Codex completion rules, including the distinct native automatic path.

The version-1 model names and serialized values stay in model.py for storage
and import compatibility. Transport and lifecycle mapping remain in the existing
manual, native, recovery, work and runtime_archive modules.
"""

from .model import Completion, CompletionBinding, CompletionKind


class CodexCompletionPolicy:
    def valid_binding(self, binding):
        return (isinstance(binding, CompletionBinding)
                and bool(binding.compact_turn_id) and bool(binding.compact_item_id))

    def valid_event(self, event):
        return isinstance(event, Completion) and isinstance(event.kind, CompletionKind)

    def completed(self, request, events):
        required = set(CompletionKind)
        if request and request.origin == "native_auto":
            required.remove(CompletionKind.COMPACT_TURN)
        return {e.kind for e in events} == required

    def permits_continuation(self, binding, continuation):
        return (continuation.turn_id != binding.compact_turn_id
                or binding.request.origin == "native_auto")
