"""C-CLI/2.1.280 completion proof; identities outside Hook payloads are local.

One fresh exclusive CLI session, one manual request, synchronous command Hooks.
The host closes and drains the bounded collection before submitting one proof.
Neither a CLI result nor a Hook alone establishes completion or handoff receipt.
"""

from dataclasses import dataclass

from .model import Request


CLAUDE_CLI_VERSION = "2.1.280"


def _identity(value):
    return isinstance(value, str) and bool(value.strip()) and value != "UNKNOWN"


def _sequence(value):
    return type(value) is int and value > 0


@dataclass(frozen=True)
class ClaudeCLIProfile:
    version: str = CLAUDE_CLI_VERSION
    os: str = "Linux"
    surface: str = "claude -p"
    output_format: str = "stream-json"
    hooks: str = "command"


@dataclass(frozen=True)
class ClaudeManualBinding:
    request: Request
    attachment_id: str
    session_id: str
    startup_seq: int
    request_seq: int
    profile: ClaudeCLIProfile
    exclusive_fresh_session: bool


@dataclass(frozen=True)
class ClaudeHookObservation:
    """Allowlisted metadata; seq/request/generation belong to the collector.

    Preserve native session_id and event/trigger (SessionStart uses source).
    Do not substitute a local ID for a missing native session identity.
    """

    attachment_id: str
    request_id: str
    generation: int
    seq: int
    session_id: str
    event: str
    trigger: str
    evidence_ref: str
    hook_ok: bool


@dataclass(frozen=True)
class ClaudeManualCompletion:
    binding: ClaudeManualBinding
    evidence_ref: str
    hooks: tuple[ClaudeHookObservation, ...]
    closed_seq: int
    collection_closed: bool
    transport_ok: bool
    manual_requests: int

    @property
    def kind(self):
        return "claude-cli/manual-hook-window"


class ClaudeManualCompletionPolicy:
    def valid_binding(self, binding):
        if not isinstance(binding, ClaudeManualBinding) or not isinstance(binding.request, Request):
            return False
        r = binding.request
        return (binding.profile == ClaudeCLIProfile()
                and binding.exclusive_fresh_session is True
                and all(_identity(v) for v in (binding.attachment_id, binding.session_id,
                    r.request_id, r.thread_id, r.transition_id, r.boundary_id,
                    r.checkpoint_id, r.lease_id))
                and r.origin == "controller" and r.thread_id == binding.session_id
                and type(r.rollover_generation) is int and r.rollover_generation == 1
                and _sequence(binding.startup_seq) and _sequence(binding.request_seq)
                and binding.startup_seq < binding.request_seq)

    def valid_event(self, event):
        if (not isinstance(event, ClaudeManualCompletion)
                or not self.valid_binding(event.binding)
                or not _identity(event.evidence_ref)
                or event.collection_closed is not True or event.transport_ok is not True
                or type(event.manual_requests) is not int or event.manual_requests != 1
                or not _sequence(event.closed_seq)
                or not isinstance(event.hooks, tuple) or len(event.hooks) != 3):
            return False
        b = event.binding
        previous = b.request_seq
        found = {}
        refs = set()
        for h in event.hooks:
            if (not isinstance(h, ClaudeHookObservation)
                    or h.attachment_id != b.attachment_id
                    or h.request_id != b.request.request_id
                    or type(h.generation) is not int or h.generation != 1
                    or h.session_id != b.session_id or h.hook_ok is not True
                    or not isinstance(h.event, str) or not isinstance(h.trigger, str)
                    or not _sequence(h.seq) or not previous < h.seq < event.closed_seq
                    or not _identity(h.evidence_ref) or h.evidence_ref in refs):
                return False
            key = (h.event, h.trigger)
            if key not in (("PreCompact", "manual"), ("PostCompact", "manual"),
                           ("SessionStart", "compact")) or key in found:
                return False
            found[key] = h.seq
            refs.add(h.evidence_ref)
            previous = h.seq
        return (found[("PreCompact", "manual")] < found[("PostCompact", "manual")]
                and found[("PreCompact", "manual")] < found[("SessionStart", "compact")])

    def completed(self, request, events):
        return (len(events) == 1 and self.valid_event(events[0])
                and events[0].binding.request == request)

    def permits_continuation(self, binding, continuation):
        # This adapter deliberately stops at completion: no evidenced receipt path.
        return False


def classify_hook_result(*, event, intentional_deny, exit_code, output,
                         timed_out=False, process_failed=False):
    """Classify collector-owned outcomes, never a UI 'hook error' string.

    NORMAL_DENY describes the Hook's response, not Runtime enforcement.
    Missing outcome/intent is UNKNOWN even when the CLI prints 'hook error'.
    """
    if timed_out is True or process_failed is True:
        return "HOOK_FAILURE"
    if type(exit_code) is not int or type(intentional_deny) is not bool:
        return "UNKNOWN"
    if event == "PreToolUse" and intentional_deny:
        if exit_code == 2 and output is None:
            return "NORMAL_DENY"
        if exit_code == 0 and isinstance(output, dict):
            decision = output.get("hookSpecificOutput")
            if (set(output) == {"hookSpecificOutput"} and isinstance(decision, dict)
                    and set(decision) <= {"hookEventName", "permissionDecision", "permissionDecisionReason"}
                    and isinstance(decision.get("permissionDecisionReason", ""), str)
                    and decision.get("hookEventName") == event
                    and decision.get("permissionDecision") == "deny"):
                return "NORMAL_DENY"
        return "HOOK_FAILURE"
    if exit_code != 0 or not isinstance(output, dict):
        return "HOOK_FAILURE"
    return "UNKNOWN"  # A parsed object alone does not prove schema-valid success.
