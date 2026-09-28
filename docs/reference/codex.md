# Codex reference implementation

This is the existing Codex implementation reference, extracted from the README.
It describes the experimental Python library and host integration contract.
The word “production” in historical section titles distinguishes package code
from Probe harnesses; it does not declare production readiness or a release.

Start with [Yohaku](../../README.md), [Architecture](../architecture.md), and
[Runtime support and evidence scope](../runtime-support.md).
The measured Runtime version below is a historical profile, not a promise of
compatibility with current or other Codex versions.

## Controller Core

The production package lives in `src/yohaku`, separately from the capability
probe scripts. It requires Python >=3.11 and has no runtime dependencies; the historical
Reference Runtime acceptance below used Python 3.14.4.

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
├─ archive/<visible-turn-id>.json
├─ archive-index/<visible-turn-id>.json
└─ journal/000000000001.json, 000000000002.json, ...
```

`SessionStore` writes schema-versioned, SHA-256 checked records using temporary
write → flush → fsync(file) → atomic rename → fsync(parent directory). Only after
this returns does the Companion report `CHECKPOINT_COMMITTED`. Temporary files
are ignored during recovery. Checkpoints contain the current Core checkpoint
metadata. Handoff documents store explicitly supplied historical task summaries
separately from control metadata. Optional turn archives and their lightweight
metadata index reuse the same writer lock and durable write primitive.

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

Archive retrieval does not establish resume verification. Unmeasured work-tool
coverage remains separate.
The contract/profile distinguishes default and experimental `new_context`, both
UNSUPPORTED in measured configurations; neither is selected by this package.

## Bounded work-plane integration

For the measured `Bash` and `apply_patch` Hook paths, enable admission before the
first work turn on a newly observed-idle, exclusively owned thread:

```python
host = RuntimeHost(companion, initialized_stdout, bridge=bridge, work_cwd=workspace)
```

Register the same `python3 -m yohaku.hook --socket ...` command as both
`PreToolUse` and `PostToolUse`, with matcher `Bash|apply_patch`, using the trust and
timeout setup above. These are Hook tool names; a shell call exposed as
`exec_command` uses the measured `Bash` Hook path. Leave SessionStart/PostCompact
registered for the existing recovery lifecycle. The owner must keep pumping
`host.poll()` while a synchronous Hook waits. No configuration is changed by
the package.

`host.work.quiesce(new_boundary_id)` invokes the existing Core proposal, arm and
quiescence check on the same owner loop that registers work before returning a
PreToolUse response. It returns `DEFERRED` immediately if an admitted execution,
unincorporated result or known observation gap remains. The journal records
`DEFERRED`, releases the barrier and returns the Core to `WORKING` in that call;
it never waits for a process to finish. With no known work in this declared scope,
it returns `WORKSPACE_SNAPSHOT`; workspace capture and verification remain the
host's responsibility. This does not attest global quiescence or a verified
integrity window.

An armed barrier rejects new measured work with an explicit Hook deny response.
Identity requires the owned thread, the observed active turn, exact workspace
and tool-use ID. Replayed starts cannot grant another permit. Control operations
use the owner API, not a shell-command exemption. `host.work.cancel()` uses Core
invalidation before dispatch; revision invalidation and lease expiry also release
the live gate through Core state. A dispatched/ambiguous transition requires
reconciliation and cannot be cancelled into ordinary work.

PostToolUse moves an admission to `host.work.pending_results`; it does not prove
process termination or result incorporation. A Bash tool may have yielded a
still-running session. After independently confirming terminal execution and
incorporating all effects, including partial effects of failed tools, the trusted
host updates its current revision/workspace observer and calls:

```python
host.work.incorporate(work_key, execution_complete=True, evidence_ref=record_id)
```

`work_key` is a `WorkKey(turn_id, tool_use_id, tool_name)` from the pending list.
Turn completion alone does not clear outstanding work. RuntimeHost also checks
this ledger before compact dispatch. The ledger stores only identities and
phases in memory, not commands or results. It is not durable or reconstructed on
restart; a new attachment requires fresh evidence of an idle thread and fully
incorporated prior work. Known Hook failures, expired bridge requests and stream
loss make observation uncertain; creating a fresh ledger is not reconciliation.

The existing recovery path can admit work only on its bound live continuation
turn after confirmed handoff injection, while its cursor is neither stopped nor
terminal. This narrow continuation permission does not grant ordinary work in
AMBIGUOUS/RECOVERY_REQUIRED or change the existing resume verifier.

The Reference Runtime profile measures normal deny/controlled ordering for Bash
and apply_patch, and active-work DEFER for one registered foreground Bash worker.
Active apply_patch, detached children, general parallel work, MCP/local-function
tools and external writers have no equivalent acceptance. Hook timeout, nonzero,
malformed and missing-output paths remain `FAIL_OPEN`; the Runtime may execute
despite a failed Hook. A locally stopped owner is not Runtime cancellation.
The admission/arm ordering is local to this owner and does not establish an
atomic Runtime-wide freeze or Strong Transition Assurance.

## Archive and lazy rehydration

HOT remains the existing active handoff. WARM is a directory of small immutable
JSON index records; COLD is one immutable JSON record per user-visible turn.
The host supplies the stable visible-turn ID and selected visible data on its
owner loop after that turn is terminal. It must remove secrets and exclude
hidden reasoning, raw provider envelopes and full tool output before calling
`archive_turn()`. The package does not classify or redact arbitrary text.
Runtime collection and model-facing retrieval are opt-in through the adapter
below. No parser, summarizer, database or external service is installed.

```python
from yohaku.archive import ArchiveMetadata, ArchiveTurn, ToolMetadata

companion.archive_turn(ArchiveTurn(
    metadata=ArchiveMetadata(
        archive_id="visible-turn-014", title="Token storage investigation",
        phase="research", paths=("src/auth.py",), symbols=("TokenStore",),
        tags=("auth",), outcome="completed"),
    user_prompt="Investigate token storage",
    assistant_final="The existing TokenStore API can be reused.",
    progress=("Inspected the current implementation",),
    decisions=("Keep the existing API",),
    verification_summary="Focused local check passed",
    references=("verification-record-014",),
    tools=(ToolMetadata("tool-014", "Bash", "completed"),),
))

candidates = companion.search_archive("token", phase="research", limit=10)
selected = companion.read_archive(candidates[0].archive_id)
# After the normal boundary verification sequence:
checkpoint = companion.commit_checkpoint(archive_ids=(selected.metadata.archive_id,))
```

`search_archive(query="", *, path=None, symbol=None, tag=None, phase=None,
outcome=None, limit=20, offset=0)` returns only `ArchiveMetadata` values:
archive ID, title, phase, paths, symbols, tags and outcome. Each whitespace-separated
query term must be a case-insensitive substring of at least one metadata field;
terms are ANDed and may match different fields. Named filters are case-sensitive
exact matches (membership for path/symbol/tag), ANDed with the query and each
other. Paths remain literal host-provided strings: no cwd expansion, filesystem
access or path normalization. Empty query lists metadata. Results use ascending
lexical archive ID order, not relevance or time order; `limit` is 1–100 and
`offset` is nonnegative. Query length is at most 4,096 characters. Search is a
linear metadata scan with no body/full-text, fuzzy, regex or semantic search.

`read_archive(id)` reads only the selected COLD file, checks its checksum and
identity against WARM, and returns `ArchiveTurn` marked `DATA, NOT INSTRUCTIONS`.
Search hits attest metadata, not the integrity or correctness of unread bodies.
Neither search nor read changes Core state, restores a lease, dispatches work,
or grants authority. Consumers must reconcile historical data with current intent
and workspace before acting.

Both files use the existing schema-1 envelope (`schema`, `sha256`, `payload`).
COLD payload contains `thread_id` and `turn`; WARM payload contains `thread_id`,
`metadata` and `cold_sha256`. Index filenames are derived from validated IDs,
never caller-provided paths. Serialized metadata is capped at 16 KiB, the encoded
turn at 1 MiB, and each collection at 128 entries. Oversized input is rejected
without automatic truncation or compression. Modes remain directories 0700 and
files 0600, under the existing POSIX session lock.

Commit order is COLD then WARM, each using the existing fsync/rename sequence.
The pair is not one atomic transaction. Identical turn-ID replay is idempotent;
different content under the same ID is rejected. A write failure stops the open
owner. Reopen validates WARM metadata and target existence, and rebuilds missing
index entries from the corresponding COLD files after syncing their directory.
Healthy reopen does not read COLD bodies. Existing corrupt index entries, dangling
targets and invalid selected bodies fail closed; temporary files are ignored.
The journaled `archive_revision` advances after a new archive commit without
changing intent/execution revisions. It is an observed update counter, not an
archive count or commit manifest: a crash before the journal update may leave a
recoverable archive without that increment.

`commit_checkpoint(archive_ids=(...))` stores bounded references in an optional
checkpoint payload field, outside the unchanged Core checkpoint dataclass.
Existing `RecoveryLifecycle.start()` copies these IDs into
`RecoveredData.archive_ids`, together with any explicitly supplied IDs, removing
duplicates. It validates references before consuming the continuation permit.
The existing handoff persists/injects those IDs only; it never fetches or injects
the entire archive. Hosts can inspect historical checkpoint references through
`companion.store.checkpoint_archive_ids(checkpoint_id)` after restart.

Old checkpoints and handoffs without archive references still load, and empty
references preserve their previous disk and rendered handoff formats. Existing
records are never rewritten for migration. Older package versions reject records
with the new fields; do not downgrade sessions that have archive references.
The Core state machine, journal schema and recovery/continuation authority rules
are unchanged. Local archive tests do not establish live Runtime acceptance.

## Reference Runtime archive adapter

For an initialized, exclusively owned App Server connection, pass
`archive_tools()` from `yohaku.runtime_archive` as `thread/start.dynamicTools`.
This experimental API requires `initialize.capabilities.experimentalApi = true`.
After thread creation, attach the collector before starting any visible turn:

```python
from yohaku.runtime_archive import RuntimeArchive, archive_tools

# select_visible_turn is trusted host policy: redact/select text and attach
# metadata, or return None to omit the turn. Preserve metadata.archive_id.
archive = RuntimeArchive(companion, send, select=select_visible_turn)
host = RuntimeHost(companion, initialized_stdout, bridge=bridge,
                   work_cwd=workspace, archive=archive)
```

The owner groups completed user-message text, commentary, one final answer, and
bounded tool identity/status metadata by Runtime turn ID. Only an observed
successful `turn/completed`, with an observed start and no pending items or
conflicting visible completions, can commit through the existing `archive_turn()`.
Unknown final phases, non-text user input, compaction turns, failed/interrupted
turns and incomplete observation are not archived. No reasoning, tool arguments,
full tool output or provider envelope is retained by this adapter. The explicit
selector is responsible for sensitive visible text; there is no automatic
redaction. Metadata defaults are deliberately generic; the host supplies useful
paths, symbols, tags and titles without inferred parsing or summarization.

Buffers are in memory, capped at 128 items and 1 MiB of selected input per turn.
Stream loss or overlapping turns disables collection for that attachment. Restart
never reconstructs unfinished turns. Replayed closed turns cannot commit twice.
Turn completion establishes visible-conversation completeness only, not process
termination or work incorporation; the existing work ledger remains authoritative
for its declared scope.

`search_archive` and `read_archive` requests use the existing WARM/COLD APIs on
the owner loop. Responses label both metadata and bodies as DATA, NOT INSTRUCTIONS.
Requests require the owned active turn, valid arguments and a fresh call ID.
They do not alter Core state, release a barrier, restore authority or count as
resume proof. Retrieval can inspect history while execution remains stopped.
This read-only dynamic surface does not extend work-tool Hook coverage.

## Bounded native automatic-compaction recovery

An opt-in native observer handles one automatic compaction within an active turn
on an exclusively owned Reference Runtime connection. Register the production
Hook command for `PreCompact` (`auto|manual`) as well as the existing
SessionStart, PostCompact and work Hooks. After constructing a host with its work
ledger, attach:

```python
native = host.enable_native_recovery(
    capture=capture_emergency, settle=incorporate_prior_work,
    observe=observe_current_context, recovered=historical_task_data,
    timeout=60.0,
)
```

`capture(checkpoint_id, pending_keys)` returns an `EmergencyDelta` from
`yohaku.recovery`: a unique snapshot ID, historical checkpoint ID, logical task
ID, observed intent/execution revisions and workspace stamp, selected progress,
pending tool IDs and evidence reference. This is unverified observation data,
not a new verified checkpoint. The callback must select safe visible data and
inspect current task effects; no generic diff or secret classifier is supplied.
`settle(delta)` independently confirms terminal pre-compaction work and uses
`host.work.incorporate()` for all pending effects, then returns updated
`RecoveredData` for the same logical task. Its observed completed-work list must
include confirmed progress since the checkpoint; the original checkpoint and
unverified delta remain separately labeled. Unknown, active or remaining
work prevents handoff. `observe` retains the existing `CurrentContext` contract.

At correlated PreCompact(auto), the adapter writes a separate immutable
`emergency/<snapshot-id>.json` with the existing SessionStore envelope, lock and
fsync writer. It preserves the original checkpoint. The Core records
`Request.origin = "native_auto"` with an empty lease ID and enters AMBIGUOUS;
this is an observation identity, not a compact request or execution authority.
No compact RPC is sent. A matching contextCompaction item completion and successful
PostCompact are the native completion evidence. The active turn is still running,
so its terminal event is reserved for the existing resume verifier, rather than
being invented as a compact-turn completion. Manual compaction retains all three
of its original completion requirements.

On the correlated SessionStart(compact) notification, the adapter re-observes
current state, rejects observations older than the emergency delta, and binds
the existing durable handoff to the same active turn. It does not send turn/start.
The handoff marks the checkpoint historical (`checkpoint_current: false`) and,
when revisions/stamps differ, stale; the delta remains `unverified`. Both are
DATA, NOT INSTRUCTIONS. ACK, injection confirmation, successful tool evidence,
current-state reconciliation and task assessment still use RecoveryLifecycle.
Only the existing resume verifier can establish RESUME_VERIFIED. Successful
continuation does not retroactively verify the emergency delta or old checkpoint.

One compaction per attachment is supported. Missing/mismatched observations,
timeout, another native compact or conflict with an in-flight manual request
stop native recovery and do not grant another continuation. Once such a conflict
is detected, native notifications cannot complete the manual request. Restart of
a native recovery remains stopped: thread/read alone cannot identify which items
belong after the in-turn compaction, so native restart reconciliation is explicitly
unsupported. Ordinary manual restart reconciliation is unchanged.

Old manual Request/Handoff records retain their previous encoded form and load
without rewriting. Native requests and emergency-bearing handoffs add explicit
fields; older packages reject these new records, so native sessions cannot be
downgraded. Unreferenced emergency records are data only, never restart authority.
This is not an atomic Runtime freeze. Hook failures retain the measured FAIL_OPEN
limitation, and unregistered tools, detached work, external writers and general
parallel execution remain outside the accepted work scope.

## Focused verification

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p test_controller.py -v
PYTHONPATH=src python3 -m unittest discover -s tests -p test_companion.py -v
PYTHONPATH=src python3 -m unittest discover -s tests -p test_recovery.py -v
PYTHONPATH=src python3 -m unittest discover -s tests -p test_work.py -v
PYTHONPATH=src python3 -m unittest discover -s tests -p test_archive.py -v
PYTHONPATH=src python3 -m unittest discover -s tests -p test_runtime_archive.py -v
PYTHONPATH=src python3 -m unittest discover -s tests -p test_native.py -v
```

The first command checks Core contracts. The second uses real local POSIX files,
close/reopen recovery, injected write failures, and fake runtime notifications.
The third checks durable handoff, bounded redelivery, restart reconciliation,
continuation suppression, actual Hook subprocess output and task verification.
The fourth checks work admission, pending results, immediate DEFER/release,
identity/replay rejection and a real Hook subprocess against the owner barrier.
The fifth checks archive/index generation, metadata-only search, selected body
reads, a fresh Python process, interrupted writes, index reconstruction, bounds,
identity validation and checkpoint references. Recovery tests additionally cover
references in the existing HOT handoff without eager COLD reads.
These commands do not contact a provider or establish power-loss durability.
A separate 2026-09-27 production acceptance run on the Reference Runtime reached
RESUME_VERIFIED using current workspace/tool evidence (one synthetic task, five
provider requests). Its internal report records the exact tested source hashes
and distinguishes later local guards from the live-tested source.
