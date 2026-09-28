# Claude Code C-CLI adapter

`ClaudeCLIAdapter` is an experimental completion adapter for **Claude Code
2.1.280 on Linux, `claude -p`, stream-json and synchronous command Hooks**.
It covers one fresh exclusive session and one manual `/compact` request.
Its endpoint is `ROLLOVER_OBSERVED`; it provides no handoff, task continuation,
resume verification or restart implementation. Agent SDK/API is a separate,
unimplemented profile.

## Evidence scope

An external live-runtime synthetic Probe reported startup, paired foreground
tool Hooks, intentional denial, manual compaction, externally prompted
continuation and nonduplication of completed fixture work. The retained source
is the external tester's inspection report. The original event JSON and native
stream were not available for independent replay. Final Probe observations and
overall verdict remain **PARTIAL**, including a `TIME_LIMIT` issue attributed by
the tester to delayed session shutdown.

The adapter has local synthetic tests, including a subprocess transport rehearsal.
These establish local behavior only. Yohaku-mediated live acceptance remains
`NOT_RUN`. No Claude-wide support or PASS follows from either evidence set.

## Host integration

The embedding host must own a fresh dedicated session and serialize observations
and dispatch. Pin `ClaudeCLIProfile()` exactly; a different version, OS, surface,
output format or Hook type needs a separate profile review.

1. Observe `SessionStart(source="startup")` as collector sequence 1. Preserve
   the actual native `session_id`. Create a run-specific attachment ID and a
   `ClaudeHookObservation` with empty request ID and generation 0. Use a trusted
   synchronous collector; background Hooks are outside this contract.
2. Set a dedicated absolute `CODEX_HOME` in the host process and create a fresh
   `SessionStore(session_id, create=True)`. Never point it at a regular Codex or
   Hermes store. Construct `ClaudeCLIAdapter(store, profile=ClaudeCLIProfile(),
   startup=startup, exclusive_fresh_session=True)`. Exclusivity is a host
   attestation, not something the boolean discovers or enforces.
3. The host observes foreground Pre/PostToolUse pairs, actual fixture effects,
   and a successful terminal result. Call `checkpoint(boundary_id=...,
   observe=..., evidence_ref=..., foreground_idle=True)` at that idle boundary.
   `observe()` returns a trusted `CurrentContext`; after the first workspace
   publication its execution revision is 1 and intent revision is 0. This
   attests the selected task boundary, not a global barrier or semantic result
   incorporation. Boundary verification remains `not_run`.
4. Call `compact(observe=..., dispatch=..., now=time.monotonic,
   request_seq=...)`. Reserve the next sequence in the same serialized collector.
   The adapter commits the checkpoint, consumes a revision-bound Core lease and
   writes the full request/binding before calling `dispatch("/compact", binding)`
   once. The final task read must still match the checkpoint. No retry is issued
   after uncertain dispatch or evidence failure.
5. The callback submits that exact manual command, collects **all** Hook
   observations within its window and closes/drains the transport before returning
   a `ClaudeManualCompletion`. A successful CLI result/ACK alone is insufficient.
   Hook/transport failures, malformed input and unexpected work must not be
   silently filtered into a successful proof. The bounded acceptance host closes
   stdin after the compact result and waits for clean process termination.

The library does not launch Claude, install Hooks, configure authentication or
verify payment settings. The existing TOML startup helper continues to support
Codex/Hermes only; it does not activate this adapter. C-CLI construction must be
explicit in its embedding host. Installation uses the shared Python >=3.11 wheel.

## Completion proof

`ClaudeManualCompletionPolicy` implements the Stage 3 `CompletionPolicy` boundary.
It requires one closed, successful collection with exactly these three observations:

| Observation | Required relationship |
|---|---|
| `PreCompact`, `trigger=manual` | After the recorded manual request |
| `PostCompact`, `trigger=manual` | After that PreCompact |
| `SessionStart`, `source=compact` | After that PreCompact |

PostCompact and SessionStart(compact) may arrive in either order. Every observation
must match the session, attachment, request ID and generation, have a unique
positive collector sequence and evidence reference, and precede collection close.
The profile permits generation 1 only. Missing, stale, duplicate, failed,
foreign-session, automatic or extra observations reject the proof as `AMBIGUOUS`.
The host must include events rather than collapsing duplicates into a set.

Session identity and lifecycle fields originate in native Hook payloads.
Attachment ID, Yohaku request ID, generation and collection sequences originate
in the host. They must be attached **at capture time**, never retroactively
stamped onto old events. CLI Hook payloads do not provide an atomic native
Yohaku request/generation identity. Correlation therefore depends on the fresh
exclusive attachment, one request and the trusted ordered collector. It is not
protection against a malicious collector, another client or undetectable replay
of raw same-session payloads. No Hermes host/DB proof or Codex event set is used.

The proof is submitted once after collection closes. The adapter exposes no
late-event callback or post-completion dispatch route. Timeout closes the owner
permanently; late evidence cannot reopen it. A second call to `compact` is rejected.
The Core's generic continuation permit is not a Claude transport implementation:
this policy's `permits_continuation` always returns false, so it cannot offer a
Claude handoff or reach `RESUME_VERIFIED` through this adapter.

## Normal denial and Hook faults

`classify_hook_result` classifies the collector's own response/exit observation.
An intentional PreToolUse deny with its exact structured JSON and exit 0, or an
intentional exit-2 denial without JSON, is `NORMAL_DENY`. Timeout, process failure,
malformed/missing deny output or inconsistent exit information is `HOOK_FAILURE`.
Missing intent or exit information is `UNKNOWN`. A generic parsed object is not
treated as schema-valid success.

These labels describe the Hook outcome, not enforcement. Confirm enforcement
separately using the matching tool ID, absence of successful PostToolUse and an
independent fixture counter. The external report's `hook error` display is
consistent with its recorded denial, but its exact version-specific UI semantics
and Hook process outcome have not been independently verified. The display alone
cannot distinguish denial from a broken Hook. Hook-fault fail-closed remains
unproven, even if the Yohaku owner stops.

The [official Hook reference](https://code.claude.com/docs/en/hooks) defines the
lifecycle fields and denial format; the [CLI reference](https://code.claude.com/docs/en/cli-reference)
documents print-mode stream transport. These are design inputs, not acceptance
evidence for the pinned runtime.

## Storage and unsupported paths

The adapter reuses committed checkpoint files and writes checksummed metadata
under a fresh store's `claude-cli-events` directory. It does not serialize the
Claude proof as a Codex snapshot or change the existing codec/schema. Core restart
rejects Claude bindings, and `SessionStore.append` rejects such snapshots.
Neither the metadata records nor historical checkpoints grant restart authority.

Autonomous continuation, Yohaku handoff receipt, current-state reconciliation,
`RESUME_VERIFIED`, Hook-fault fail-closed, background/subagent coverage, repeated
compaction, auto-compaction, crash recovery and power-loss acceptance remain
outside this implementation's evidence scope. The host's pre-dispatch workspace
check does not establish post-compact current-state reconciliation.
