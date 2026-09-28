# Claude Code C-CLI adapter

`ClaudeCLIAdapter` is an experimental completion adapter for **Claude Code
2.1.280 on Linux, `claude -p`, stream-json and synchronous command Hooks**.
It covers one fresh exclusive session and one manual `/compact` request.
Its endpoint is `ROLLOVER_OBSERVED`. The separate opt-in
`ClaudeCLIRecoveryAdapter` adds one bounded post-compact recovery path on the same
process, with acceptance scoped separately by backend and receipt protocol.
Agent SDK/API is a separate, unimplemented profile.

## Evidence scope

An external live-runtime synthetic Probe reported startup, paired foreground
tool Hooks, intentional denial, manual compaction, externally prompted
continuation and nonduplication of completed fixture work. The retained source
is the external tester's inspection report. The original event JSON and native
stream were not available for independent replay. Final Probe observations and
overall verdict remain **PARTIAL**, including a `TIME_LIMIT` issue attributed by
the tester to delayed session shutdown.

A later returned Yohaku-mediated bounded acceptance includes sanitized event JSON
and a tester report. Its bundle source hashes match; replay of the unchanged manual
completion predicate passes. Record **ManualRequest → ROLLOVER_OBSERVED: live PASS**,
**overall PARTIAL**, **issues []**, with external/live-runtime/synthetic provenance.
It observed PreCompact, SessionStart(compact), then PostCompact. Anonymized identity
consistency can be checked; private checkpoint/lease fields were not exported and
are not independently read back. This later result does not overwrite the older Probe.

The opt-in recovery implementation has local synthetic tests, including a fake CLI
that runs actual local Hook and fixture subprocesses. Its external subscription
recovery live acceptance is **NOT_RUN**. Separately recorded maintainer local-backend
runs do not establish subscription recovery or Claude-wide support.

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
   observations within its window and seals/drains that collection before returning
   a `ClaudeManualCompletion`. A successful CLI result/ACK alone is insufficient.
   Hook/transport failures, malformed input and unexpected work must not be
   silently filtered into a successful proof. The accepted completion-only host closes
   stdin after the compact result and waits for clean process termination. The new
   opt-in recovery host instead seals a logical collection window at a successful
   terminal result, retains the same process, and rejects unexpected late compact
   observations. That process-lifetime change requires the new live acceptance.

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

The proof is submitted once after collection closes. The default adapter exposes no
post-completion dispatch route. Timeout closes the owner
permanently; late evidence cannot reopen it. A second call to `compact` is rejected.
The Core's generic continuation permit is not a Claude transport implementation:
this policy's `permits_continuation` always returns false, so it cannot offer a
Claude handoff or reach `RESUME_VERIFIED` through this adapter.

## Opt-in post-compact recovery

Construct `ClaudeCLIRecoveryAdapter` from `yohaku.claude_recovery` with the same
profile/startup/store inputs. `ClaudeRecoveryCompletionPolicy` inherits the
unchanged manual-completion validation and both permitted post-event orders; only
`permits_continuation` is specialized. No Hermes storage proof or Codex event set
is added. The trusted host must exclusively own and serialize one live print
process, one compact window and one following recovery input.

1. After ROLLOVER_OBSERVED, call `begin_recovery(recovered, cwd=...,
   instructions=..., send=...)`. The adapter commits and reads back the existing
   `HandoffDocument`, binds its checkpoint hash, claims one Core continuation
   permit, and records the offer before sending. Historical content remains DATA,
   NOT INSTRUCTIONS. `send` must only submit/flush that exact input and return a
   matching `ClaudeDelivery`; it must not pump callbacks before returning.
   Submission proves delivery to the owned transport, not receipt by the model.
2. The native foreground receipt call must explicitly carry handoff ID, checkpoint
   ID/hash, handoff hash, compact request, session, attachment, generation, local
   continuation request/turn IDs and logical task ID. `pre_tool`, `acknowledge`
   and a matching successful `post_tool` with the actual handler JSON result are
   all required. An automatic helper that reads hidden IDs from storage is not a
   receipt. A printed ACK or a successful later action is also insufficient.
3. Only then may the native observation call invoke `observe_fresh`. Its trusted
   observer reads current task/revision/workspace state twice around any optional
   task description. Reconciliation uses this fresh state, not the checkpoint.
   A new read token is returned and the native result must match the handler result.
4. Admit one task-specific action only after that completed read. The action must
   explicitly echo the fresh token. `perform_action` rechecks current state before
   executing the trusted host callback. The host chooses/adjudicates the actual
   operation against current task intent and separately rejects stale or completed
   work. The generic adapter is not an arbitrary-command safety oracle.
5. Record the matching successful recovery terminal. Close/drain the bounded
   process and reject late evidence before `verify_resume`. The independent
   assessor must read back the actual task effects, identify the exact read/action
   tool IDs, and verify unresolved work, re-evaluated next action, nonduplication,
   no historical-instruction execution and same-task continuation. Current state
   must remain stable around assessment and intent must still match the fresh read.
   Only this complete chain can reach RESUME_VERIFIED.

`ClaudeContinuationBinding.turn_id` is a locally generated dispatch identity for
one serialized recovery input; it is **not** a native CLI turn identifier. Native
session and tool IDs are correlated with this local binding by the exclusive host.
This contract does not infer semantic understanding or general result incorporation.
Missing, stale, duplicate, foreign or mismatched recovery evidence stops the owner
in RECOVERY_REQUIRED. Uncertain submission is never blindly retried.

The bounded fixture changes current intent after compaction. Its historical next
action says to repeat completed work and run a stale operation; the new observation
selects the sole remaining action. Acceptance independently requires counters
`before=1`, `after=1`, `stale=0`, explicit receipt, current-state hashes/revisions,
a matching read-token echo, and the task assessor. Local negative tests also check
that successful effects cannot conceal missing receipt or a failed assessment.

The new command-Hook harness requires Bash `tool_response.stdout` to contain the
exact fixture JSON. This tool-specific shape is a strict candidate contract for
the pinned runtime; live acceptance is limited to separately recorded maintainer
profiles. Absence or mismatch stops the run.
Metadata validation verifies schema and correlation, not runtime authenticity.

## Opt-in host-bound nonce receipt

`ClaudeCLINonceRecoveryAdapter` keeps the recovery gates above and changes only
receipt argument transport. It is restricted to the same fresh, exclusively owned
process, one pending handoff, one recovery input and generation 1. The original
`ClaudeCLIRecoveryAdapter` retains its full-identity echo contract.

The nonce adapter snapshots the complete receipt identity and continuation binding
on the trusted host. The `instructions` callback receives only `{"nonce": value}`,
where `value` is a fresh 128-bit, 22-character challenge. Include that exact value
in the model-visible receipt command. The native call must pass this dictionary to
`acknowledge`; a no-argument ACK or a helper loading the nonce from storage is not
accepted. Do not expose an automatic ACK endpoint.

The adapter checks the captured native session/tool event binding, complete host
identity and exact one-time nonce. It consumes the nonce once and records its hash
separately from the host-owned identity. Receipt still requires the matching
successful PostToolUse with the actual handler result. Wrong identity, owner,
nonce, generation, stale sequence, duplicate or missing evidence stops recovery.
The embedding host must stop the owner at its deadline; there is no automatic
reissue, correction or retry. A submitted handoff or successful later action cannot
stand in for this evidence.

The nonce response demonstrates an explicit acknowledgment correlated to this
handoff. Tool success does not establish semantic incorporation of its result.
The separate fresh-read token echo demonstrates use of that specific observation;
current-state checks and independent task assessment still determine resume.
Neither receipt mode claims general semantic understanding.

This mode does not generalize to parallel owners or multiple pending handoffs.
Local generation and dispatch identity still depend on the trusted serialized
collector; they are not native CLI turn/generation IDs. The nonce is not an
identity-authentication boundary against a malicious host or forged same-session
Hook traffic. Prior full-identity Evidence and verdicts are not reinterpreted.
See [runtime support](../runtime-support.md) for the separately measured profile.

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

The adapters reuse committed checkpoint files and write checksummed metadata
under a fresh store's `claude-cli-events` directory. It does not serialize the
Claude proof as a Codex snapshot or change the existing codec/schema. Core restart
rejects Claude bindings, and `SessionStore.append` rejects such snapshots.
The opt-in path also uses existing handoff files. Neither metadata records nor
historical checkpoints grant restart authority.

External subscription live evidence currently stops at manual completion. The
maintainer local-backend recovery results, including controller-driven continuation
and RESUME_VERIFIED, do not establish that separate external acceptance. Hook-fault
fail-closed, background/subagent coverage, repeated or automatic compaction, restart
and SDK/API are outside this adapter's accepted coverage.
