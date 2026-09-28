# Architecture

Yohaku implements a Codex reference integration, a bounded Hermes CLI adapter
and a bounded Claude CLI completion adapter
as a Python library.
The architecture is Plugin + Companion Controller in design; the repository
contains the Controller, Companion, Hook bridge and runtime integration code, but
does not yet ship an installable Plugin/Skill bundle or general-purpose launcher.

## Implemented responsibilities

| Component | Responsibility | Code |
|---|---|---|
| Controller and domain model | Serialized transition decisions, revision checks, lease invalidation, completion and resume gates | [controller.py](../src/yohaku/controller.py), [model.py](../src/yohaku/model.py) |
| Completion policy | Runtime binding, proof and continuation identity predicates; Codex default and bounded Hermes readback | [completion.py](../src/yohaku/completion.py), [codex.py](../src/yohaku/codex.py), [hermes.py](../src/yohaku/hermes.py) |
| Startup configuration | Explicit TOML opt-in for Codex/Hermes; disabled leaves the host factory uncalled | [config.py](../src/yohaku/config.py) |
| Companion and persistence | Durable checkpoints, journal, handoffs, local writer lock, orchestration | [companion.py](../src/yohaku/companion.py), [persistence.py](../src/yohaku/persistence.py), [codec.py](../src/yohaku/codec.py) |
| Runtime host and Hook bridge | Owner-loop event handling, local Hook delivery, transport dispatch | [runtime.py](../src/yohaku/runtime.py), [hook.py](../src/yohaku/hook.py) |
| Manual / native lifecycle | Codex request/event correlation and the separate native recovery path | [manual.py](../src/yohaku/manual.py), [native.py](../src/yohaku/native.py) |
| Hermes CLI adapter | Pinned foreground ledger, manual compression readback, explicit receipt and continuation | [hermes_adapter.py](../src/yohaku/hermes_adapter.py) |
| Claude CLI adapter | Pinned C-CLI manual Hook proof, single dispatch and stop at completion | [claude.py](../src/yohaku/claude.py), [claude_adapter.py](../src/yohaku/claude_adapter.py) |
| Work / recovery | Bounded work admission, active and pending work, handoff receipt, task-specific resume assessment | [work.py](../src/yohaku/work.py), [recovery.py](../src/yohaku/recovery.py) |
| Archive | Selected visible-turn storage, metadata search, selected-body reads, optional Codex collector | [archive.py](../src/yohaku/archive.py), [runtime_archive.py](../src/yohaku/runtime_archive.py) |

The host owns the initialized runtime connection and supplies trusted observations.
All Controller and Companion mutations are serialized by that owner. The Controller
does not perform external I/O; the Companion persists decisions, and runtime
components perform and observe runtime operations. Task-specific observers and
assessors are required integration code, not assertions supplied by the model.

## Transition and recovery contracts

The proactive path checks a proposed boundary and work state, captures the declared
workspace scope, validates evidence, commits a checkpoint, and authorizes a bounded
lease before dispatch. The backend must correlate completion to the pending request.
Handoff receipt and current-state resume verification follow as separate decisions.

Uncertain dispatch or completion becomes `AMBIGUOUS`. The owner does not issue a
blind retry. Historical checkpoints, summaries, and archives do not restore old
authority. Restart reconciliation requires fresh observations and preserves the
limits of the recorded strategy.

Native automatic compaction can occur before the proactive path completes. Its
emergency observation is stored separately from a historical checkpoint and remains
unverified. Native recovery checks its own completion signals and current task
state; it does not retroactively create a verified boundary or lease.

## Persistence and archive boundary

The current POSIX store uses the `yohaku` child of `CODEX_HOME`, falling back to
the user's `.codex` directory. It uses a cooperating local writer lock and
checksummed records with file and directory synchronization. A store lock does not
prevent other runtime clients or external workspace writers.

HOT is the active handoff; WARM contains archive metadata; COLD contains selected
visible turns. Archive reads return `DATA, NOT INSTRUCTIONS`. The host selects and
redacts visible text before persistence. Archive retrieval grants no execution
authority and does not establish resume verification.

See the [Codex reference](reference/codex.md) for exact storage paths, durability,
compatibility, restart behavior, and API contracts.

## Core / Adapter boundary

The Core retains boundary policy, revisions and freshness,
checkpoints, leases, archive integrity, ambiguity handling, handoff semantics,
resume verification, and evidence scope. Runtime adapters own lifecycle
events, tool taxonomy and work observation, triggers, completion proof, runtime
identity, injection, continuation, and visible-turn extraction.

`Controller(..., completion_policy=...)` fixes one trusted, I/O-free policy for
the owner's lifetime. Its four predicates validate the runtime binding, validate
completion evidence, determine completion from accumulated evidence, and check
the continuation identity. The Core checks full request/binding equality,
evidence references, duplicate kinds, state, authority and resume requirements.
Codex remains the default: manual completion requires three signals; native
automatic completion requires two and the separate recovery path.

`HermesManualCompletionPolicy` accepts metadata from the H-CLI-01 strategy:
manual in-place compression, host-history update, independent SessionDB readback,
then fresh current-state observation and controller-driven continuation.
The predicate requires one request and one readback, ordered and correlated to a fresh exclusive session at generation 1,
with changed host history, matching host/DB projections and archived old rows.
The pinned runtime is Hermes 0.21.0 at source commit
`c5594ec4b34097cafbe24deb6dfd9ac4b21d411d`. Engine return or compressor count alone
cannot establish completion. Host instrumentation remains responsible for the
truth of observations; matching hashes are not authentication.

`ClaudeManualCompletionPolicy` requires a closed manual Hook window on one fresh
exclusive C-CLI attachment. It correlates PreCompact, PostCompact and
SessionStart(compact) to the session and locally owned request/generation.
It permits neither handoff nor resume verification. See the
[C-CLI reference](reference/claude-cli.md) for host responsibilities and limits.

Hermes and Claude proof objects can be supplied to the in-memory Core without inventing
Codex turn/item events. The `Snapshot` binding/completions annotations still
describe the Codex schema-1 storage contract. `SessionStore` rejects records that
cannot round-trip through that contract before writing; `Controller.restart`
accepts only the existing Codex binding and evidence types. No cross-runtime
snapshot schema, migration or restart registry is provided. `CompanionController` continues
to construct the Codex backend and recovery lifecycle.

Completion does not establish handoff receipt or resume verification.
`HermesCLIAdapter` connects the native host, foreground ledger, independent DB
readback, existing checkpoint/handoff files and an explicit tool receipt to
those Core gates. It schedules one continuation, reconciles a fresh task read
and checks a task-specific resume proof. Its metadata records are separate from
the Codex snapshot journal; Hermes restart remains unsupported. The Core's receipt
and resume gates are unchanged. See the [Hermes reference](reference/hermes.md).
Work ledgers, tool taxonomies, Hook delivery and visible-turn collectors remain
runtime specific; their meanings and coverage are not unified.

Transition Strategy describes a runtime/surface/backend contract. The completion
policy boundary is not a general transport interface or full multi-runtime support.

## Verification boundary

[Unit tests](../tests/) exercise local and synthetic contracts. The
[Probe scripts](../scripts/probe/) are developer tools, separate from the installed
package. Neither their presence nor a successful metadata collection proves live
runtime capability. See [Runtime support and evidence scope](runtime-support.md)
and the [support policy](../SUPPORT_POLICY.md) for the historical acceptance limits.
