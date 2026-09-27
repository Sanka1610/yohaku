# Architecture

Yohaku currently implements a Codex reference integration as a Python library.
The architecture is Plugin + Companion Controller in design; the repository
contains the Controller, Companion, Hook bridge and runtime integration code, but
does not yet ship an installable Plugin/Skill bundle or general-purpose launcher.

## Implemented responsibilities

| Component | Responsibility | Code |
|---|---|---|
| Controller and domain model | Serialized transition decisions, revision checks, lease invalidation, completion and resume gates | [controller.py](../src/yohaku/controller.py), [model.py](../src/yohaku/model.py) |
| Companion and persistence | Durable checkpoints, journal, handoffs, local writer lock, orchestration | [companion.py](../src/yohaku/companion.py), [persistence.py](../src/yohaku/persistence.py), [codec.py](../src/yohaku/codec.py) |
| Runtime host and Hook bridge | Owner-loop event handling, local Hook delivery, transport dispatch | [runtime.py](../src/yohaku/runtime.py), [hook.py](../src/yohaku/hook.py) |
| Manual / native lifecycle | Codex request/event correlation and the separate native recovery path | [manual.py](../src/yohaku/manual.py), [native.py](../src/yohaku/native.py) |
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

## Planned Core / Adapter boundary

The planned common Core covers boundary policy, revisions and freshness,
checkpoints, leases, archive integrity, ambiguity handling, handoff semantics,
resume verification, and evidence scope. Runtime adapters will own lifecycle
events, tool taxonomy and work observation, triggers, completion proof, runtime
identity, injection, continuation, and visible-turn extraction.

This separation is a design direction. The current Core still contains Codex
completion predicates; the Companion constructs `ManualCompactBackend`, and the
store uses a Codex namespace. Target-runtime probes must establish the smallest
necessary interface before extraction. Other runtimes must retain their actual
signals and must not synthesize Codex events to satisfy the existing predicate.

Transition Strategy is the design term for a runtime/surface/backend contract,
not an implemented public interface or a promise of multi-runtime support.

## Verification boundary

[Unit tests](../tests/) exercise local and synthetic contracts. The
[Probe scripts](../scripts/probe/) are developer tools, separate from the installed
package. Neither their presence nor a successful metadata collection proves live
runtime capability. See [Runtime support and evidence scope](runtime-support.md)
and the [support policy](../SUPPORT_POLICY.md) for the historical acceptance limits.
