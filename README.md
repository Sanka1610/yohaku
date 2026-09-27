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

## Production architecture and persistence

Yohaku uses a Plugin + Companion Controller architecture. The production
Companion now connects the Core to POSIX persistence and ManualCompactBackend.
The Companion also owns same-thread continuation, durable handoff delivery through
a synchronous SessionStart Hook, correlated receipt, and task-specific resume
verification. The host supplies an initialized Runtime connection and trusted
current-state/task observers; there is no general-purpose task success oracle.

Persistence resolves `CODEX_HOME` first and stores data below its `yohaku` child.
When unset or empty, the resolver uses the platform user's home plus `.codex`:
Linux/WSL `~/.codex/yohaku/`, Windows path resolution equivalent to
`%USERPROFILE%\.codex\yohaku\`. The storage implementation itself is POSIX only.
Relative `CODEX_HOME` values are rejected to avoid cwd-dependent state. No
additional home variable is introduced, and isolated `CODEX_HOME` values isolate
Yohaku automatically. Existing storage is not migrated implicitly.

```text
$CODEX_HOME/yohaku/sessions/<thread-id>/
├─ writer.lock
├─ checkpoints/<checkpoint-id>.json
├─ handoffs/<handoff-id>.json
└─ journal/000000000001.json, 000000000002.json, ...
```

`SessionStore` writes schema-versioned, SHA-256 checked records using temporary
write → flush → fsync(file) → atomic rename → fsync(parent directory). Only after
this returns does the Companion report `CHECKPOINT_COMMITTED`. Temporary files
are ignored during recovery. Checkpoints contain the current Core checkpoint
metadata. Handoff documents store explicitly supplied historical task summaries
separately from control metadata. Archive storage is not implemented.

The journal is an append-only sequence of immutable JSON records with sequence
and predecessor hashes. Each record contains Core state/transition metadata and
the compact request/turn cursor and optional recovery cursor. It records request intent before any transport
byte, acceptance separately, correlation, completion, ambiguity, restart, continuation
intent, HANDOFF_OFFERED, delivery attempts, HANDOFF_RECEIVED and RESUME_VERIFIED.
The optional recovery field is an additive read extension: old journals remain
readable without rewriting them. Older package versions reject new records; do
not downgrade a session with recovery records.
It does not store raw notifications, provider bodies, Hook output, or transport
error text. Adapter-supplied evidence references must be non-secret record IDs.
Active leases and clock deadlines are omitted entirely. Files are created with
mode 0600 and directories with 0700. A session-lifetime POSIX lock excludes a
second cooperating local writer; it does not lock the runtime thread globally.

Any durable write failure stops the open Companion. Missing/corrupt journals or
checkpoint mismatches reject recovery instead of selecting an older state.
On reopen, committed checkpoints are historical recovery candidates and pending
requests become `AMBIGUOUS`; old authority is never restored. A checkpoint found
after rename but before its journal commit can be recovered only against the
exact prepared checkpoint ID/content. This is not proof that the interrupted
process reached its commit point. No automatic resend occurs.

## ManualCompactBackend and owner API

The Core remains independent of App Server and storage. Use
`CompanionController(thread_id, send, create=True)` for a new session; omit
`create=True` to reopen an existing session. Existing sessions cannot be silently
overwritten. The `send` callable synchronously writes one request on an already initialized,
exclusively owned App Server connection. `JsonLineSender(text_stream)` is provided
for JSONL streams. Connection launch, initialization, authentication, subscription,
and event-loop scheduling belong to the host; the adapter opens no connection
and changes no authentication or Hook configuration.
Neither `send` nor `read_current` may reenter the owner. The host must expose the
measured PostCompact notification; its absence keeps completion unconfirmed.

The owner must serialize these operations on one event loop:

1. Route ordinary work through `require_work()` and Core preparation/revision
   operations through `step(operation, ...)`, which journals state changes. Honor
   the requested barrier while recognizing that Hook protection is best-effort.
   Observe quiescence, capture the declared workspace scope with mutation epochs,
   and provide current boundary verification. The initial profiles are
   `verification_passed` and `implementation_complete`; the latter can carry
   failed, stale, unknown, or unrun verification without claiming correctness.
2. Call `commit_checkpoint()` for the durable checkpoint operation, then
   `authorize_rollover(ttl=...)` to obtain a current in-process lease.
   Update relevant revision domains for observed changes; never infer freshness
   from endpoint bytes alone.
3. Call `request_compact(lease, read_current, completion_timeout=...)`.
   `read_current()` must return a fresh `CurrentState` observation of intent,
   execution, workspace, lease ID, generation, checkpoint ID, and idle status.
   The Companion validates the checkpoint file and authority, persists the
   request, re-reads current state after journal sync, then sends exactly one
   `thread/compact/start`. A mismatch before send revokes authority and sends
   nothing. Transport uncertainty is durably `AMBIGUOUS`.
4. Route RPC responses and notifications to `receive(message, request=...)` with
   the immutable Request captured for that observation stream. Never attach the
   latest generation to replayed events. On this exclusively owned idle thread,
   the backend journals `turn/started`, then the matching contextCompaction
   `item/started` before consuming completion. The native protocol does not carry
   Yohaku request/generation on notifications; this association relies on the
   single-outstanding-request and ordered-stream assumptions. After restart,
   missing turn/item mapping cannot be reconstructed by guessing from new events.
5. Acceptance `{}` only records acceptance. Successful contextCompaction
   `item/completed`, `hook/completed` with `run.eventName=postCompact` and
   `run.status=completed`, and matching `turn/completed` with completed status
   and no error are all required. Duplicates do not append another completion or
   cause another dispatch. Call `poll_timeout()` regularly; timeout or lease expiry
   makes a pending request `AMBIGUOUS`. Late matching evidence can still reach
   `ROLLOVER_OBSERVED`, including after a store close/reopen with intact mapping.
6. Do not dispatch work or compact while `AMBIGUOUS`. After restart with no
   pending request, `step("reconcile_restart", ...)` requires current-state
   evidence before a new verified boundary. After observed rollover, use the
   production recovery path below; restart never grants another continuation permit.

The basic RPC format is also documented in the official
[App Server reference](https://learn.chatgpt.com/docs/app-server). The stricter
three-part completion predicate and failure limits follow Yohaku's measured
Reference Runtime, Codex CLI `0.155.0-alpha.16.4` on WSL2 Ubuntu.

The initial scope is Codex CLI on WSL2 Ubuntu, using the measured manual compact
lifecycle. PreToolUse and PreCompact have measured `FAIL_OPEN` paths for timeout,
nonzero exit, malformed output, and missing output. Hook Barrier remains
best-effort. The race between final revalidation and RPC
send remains. Controller generation is not native context/window identity.
Single Writer, exclusive thread ownership, and at most one outstanding compact
are required assumptions. The local store lock does not prevent another client
from operating the thread or an unobserved external writer from changing files.
Operational Continuity was demonstrated within the Probe's measured scope;
these local adapter tests do not establish production runtime acceptance.
Strong Transition Assurance remains unestablished.

## Production recovery and continuation

`RuntimeHost(companion, initialized_stdout, bridge=HookBridge())` reads the JSONL
stream on a reader thread. Its `poll()` processes events, Hook requests and timers
on the single owner thread. Use `host.request_compact(...)` to capture the immutable
request for that stream. The host must close the Runtime process/stream on shutdown
and close both the Companion and HookBridge. Do not use a second reader on stdout.

After `ROLLOVER_OBSERVED`, call:

```python
host.continue_task(recovered_data, cwd=workspace, observe=read_current_context,
                   timeout=60, max_attempts=2)
```

`RecoveredData` contains logical task identity, completed work, historical goal,
unresolved items, next-action candidate and workspace pointers. The handoff file
binds it to the checkpoint, boundary, compact request, generation and revisions.
It is durable before the continuation permit is journaled, and that permit is
durable before `turn/start` is sent. The fixed continuation prompt contains no
historical command or task-specific action. Transport uncertainty consumes the
permit; no restart or duplicate completion can send another continuation turn.
The final observation-to-dispatch race still exists.

Register the following command in the run's trusted project Hook configuration,
using the installed Python/package location and `bridge.path`:

```text
python3 -m yohaku.hook --socket <bridge.path>
```

Use `SessionStart` with matcher `startup|resume|clear|compact` and a synchronous
command timeout exceeding the bridge's five-second timeout (for example eight
seconds). Also register this command as `PostCompact` with matcher `manual|auto`
so the required completion notification is observable. Review/trust the exact
Hook command using the measured Runtime's trust mechanism; the package does not
modify normal config or bypass trust. `PostCompact` returns `{}`; only
`SessionStart(source=compact)` requests delivery from the live owner.

The Hook's private Unix socket is temporary, local to the owner process, and
exposes no network listener. If the Runtime is separately sandboxed, the host
must make this socket accessible to its Hook process. The background bridge
thread never changes Core or storage. The owner matches the Runtime
`turn/started` and `hook/started` envelopes with the Hook's session/source/cwd
before returning `hookSpecificOutput.additionalContext`. Hook payloads lack a
native turn ID in this Reference Runtime; this association requires the exclusive
thread and ordered-stream assumptions. A missing owner or failed Hook never
counts as receipt, even though the Runtime may fail open.

Delivery attempts use the same handoff ID and have a persisted limit. Repeated
matching Hook requests can redeliver within that limit; the Controller does not
create extra continuation turns to force another SessionStart. Exhaustion,
completion without ACK, or continuation timeout stops in `RECOVERY_REQUIRED`.
A live Runtime may still be sampling after a Controller timeout: this is a local
work/dispatch gate, not proof of Runtime cancellation. Exactly-once delivery is
not promised.

A completed SessionStart output plus an exact `YOH_ACK:<handoff-id>:<generation>`
marker on a completed assistant item of the bound continuation turn establishes
`HANDOFF_RECEIVED`. The generation comes from the saved Controller binding, not
a native context-generation identifier. Duplicate ACKs are no-ops. Successful
Hook output alone is not proof that a model acted on it; provider-request delivery
is independently checked in acceptance, and production receipt additionally
requires the correlated ACK.

After a successful continuation turn, call:

```python
companion.recovery.verify(observe=read_current_context, assess=assess_task_progress)
```

The current-state observer returns `CurrentContext`. The task assessor receives
the immutable handoff and transient actual tool items, including failed commands
that might have partial effects. It must return `ResumeProof` based on current
intent, tool reads/outputs and resulting workspace state. Read/action item IDs
must identify successful tools in the bound turn. The Controller re-observes
current revisions/workspace around assessment, requires the same logical task,
checks all continuity criteria, then calls the Core's resume verifier. An ACK,
an assistant's success statement, unknown assessment, stale state or repeated
completed work cannot establish `RESUME_VERIFIED`. Tool/provider bodies are never
journaled. Task observers are trusted adapters, not model-supplied assertions;
applications must supply an assessor for their task and declared workspace scope.

After restart the durable handoff and ACK are recovery candidates. The state is
`RECOVERY_REQUIRED`, with no lease or continuation dispatch authority. Obtain a
fresh trusted Runtime thread observation and pass its normalized thread object
to `companion.recovery.reconcile_runtime(thread)`. It requires the exact saved
continuation turn, successful terminal status, current item replay including ACK,
and fresh task assessment before verification. Missing identity cannot be guessed
from newer events. An in-progress/unknown continuation stays stopped; reconcile
again once its terminal state is observable. No automatic resend occurs.

Archive/Lazy Rehydration and broad work-tool barrier integration remain separate.
The contract/profile distinguishes default and experimental `new_context`, both
UNSUPPORTED in measured configurations; neither is selected by this package.

## Focused verification

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p test_controller.py -v
PYTHONPATH=src python3 -m unittest discover -s tests -p test_companion.py -v
PYTHONPATH=src python3 -m unittest discover -s tests -p test_recovery.py -v
```

The first command checks Core contracts. The second uses real local POSIX files,
close/reopen recovery, injected write failures, and fake runtime notifications.
The third checks durable handoff, bounded redelivery, restart reconciliation,
continuation suppression, actual Hook subprocess output and task verification.
These commands do not contact a provider or establish power-loss durability.
A separate 2026-09-27 production acceptance run on the Reference Runtime reached
RESUME_VERIFIED using current workspace/tool evidence (one synthetic task, five
provider requests). Its internal report records the exact tested source hashes
and distinguishes later local guards from the live-tested source.
