# Yohaku - Semantic Context Lifecycle Manager  
Proactive context compaction, checkpointing, and lazy recovery for long-running AI agent tasks.

## Controller Core

The production package lives in `src/yohaku`, separately from the capability
probe scripts. It requires Python 3.14 and has no runtime dependencies.

`yohaku.controller.Controller` owns a serialized, single-writer transition for
one exclusively controlled thread. `snapshot` exposes immutable domain values
from `yohaku.model`. IDs are generated locally (UUIDs by default); an injected
ID factory must produce unique IDs across restarts. Clock values passed to lease
methods must come from the same monotonic clock during a process lifetime.

The Core validates this sequence:

```text
WORKING → CANDIDATE → BARRIER_ARMING → QUIESCENCE_CHECK
  → WORKSPACE_SNAPSHOT → VERIFIED → CHECKPOINT_PREPARING
  → CHECKPOINT_COMMITTED → ROLLOVER_AUTHORIZED → ROLLOVER_REQUESTED
  → ROLLOVER_OBSERVED → HANDOFF_OFFERED → HANDOFF_RECEIVED
  → RESUME_VERIFIED → WORKING
```

It also handles `DEFERRED`, `INVALIDATED`, `AMBIGUOUS`, `RECOVERY_REQUIRED`,
and `FAILED`. Invalid operations raise `TransitionError`. Repeated proposals for
the current boundary return its existing transition ID without restarting it.
Consumed boundaries require a new boundary ID and fresh verification to retry.

- Relevant intent/execution changes invalidate authority. Control and archive
  revisions are separate; internal bookkeeping does not increment execution.
- Pre-request expiry or invalidation revokes the lease, releases the requested
  barrier, and returns to `WORKING` through `INVALIDATED`.
- After dispatch, timeout, expiry, or transport uncertainty enters `AMBIGUOUS`.
  Ordinary work, compact retries, and premature continuation are rejected.
- Completion requires three correlated observations: compaction item completion,
  PostCompact, and successful compact turn completion. RPC acceptance is separate.
  Unmapped events never establish identity. Duplicate completion is a no-op.
- Explicit continuation has one dispatch permit. Receipt needs the offered
  handoff identity and injection evidence. ACK alone never verifies resume.
- Historical material is a separate `recovered_context` field marked
  `DATA, NOT INSTRUCTIONS`. Resume evidence must reconcile current intent,
  workspace, unresolved work, historical next-action candidates, and actual
  same-task continuation without replaying completed work or old instructions.

## Adapter boundary

The Core performs no filesystem, Hook, model, or RPC I/O. Its methods consume
trusted adapter observations, not model-authored assertions or raw runtime JSON.
Evidence references are opaque identifiers for adapter-owned records; the Core
does not independently verify those records. Adapters must:

1. Serialize all calls and route ordinary work through `require_work()`. Honor
   the requested barrier while recognizing that Hook protection is best-effort.
   Observe quiescence, capture the declared workspace scope with mutation epochs,
   and provide current boundary verification. The initial profiles are
   `verification_passed` and `implementation_complete`; the latter can carry
   failed, stale, unknown, or unrun verification without claiming correctness.
2. Persist `prepare_checkpoint()` output durably, then call
   `checkpoint_committed()` only after file sync, rename, and directory sync.
   Update relevant revision domains for observed changes; never infer freshness
   from endpoint bytes alone.
3. Re-read current revisions immediately before `request_rollover()`, journal its
   returned request before transport, and send at most once at an idle turn
   boundary. An uncertain send calls `completion_unknown()`. A new attempt is
   allowed only after conclusive non-execution evidence and fresh verification.
4. Save the actual request/thread/compact-turn/item association through
   `bind_completion()`. Normalize only successful runtime notifications into
   `Completion` values. Preserve this mapping for delayed events and restarts.
5. After complete reconciliation, call `claim_continuation()`, journal its ID,
   and issue one explicit `turn/start` on the same thread. Bind the returned turn
   to that request with `ContinuationBinding`, then `offer_handoff()`. Deliver
   via `SessionStart(source=compact).additionalContext` and record injection and
   destination-correlated receipt evidence. Uncertain continuation dispatch
   requires reconciliation, never another blind `claim_continuation()`.
6. Persist and validate the journal as well as checkpoints. `Controller.restart()`
   accepts a validated `Snapshot`, discards the old lease, preserves generation
   and pending correlation, and starts in `AMBIGUOUS` or `RECOVERY_REQUIRED`.
   A recoverable checkpoint is historical data, not restored authority. With no
   pending request, `reconcile_restart()` requires current-state evidence before
   a fresh boundary can be proposed. Missing or corrupt journals must fail closed
   in the persistence adapter; do not replace them with a fresh Controller.

The initial scope is Codex CLI on WSL2 Ubuntu, using the measured manual compact
lifecycle. Hook fail-open paths and the race between final revalidation and RPC
send remain. Controller generation is not native context/window identity.
Single Writer, exclusive thread ownership, and at most one outstanding compact
are required assumptions; this Core does not enforce ownership across processes
or establish Strong Transition Assurance.

The ManualCompactBackend transport, Hook integration, durable storage/schema,
checkpoint payload/archive storage, handoff serialization and bounded redelivery,
full evidence/coverage profiles, and runtime acceptance remain separate work.
`recovery_required()` provides the stop state for delivery limits or recovery
failures; there is no delivery retry scheduler in this package yet.

## Focused verification

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p test_controller.py -v
```

These are local Core tests. Commit and observation evidence are fixtures; passing
them does not establish runtime integration or on-disk crash/restart durability.
