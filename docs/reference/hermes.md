# Hermes H-CLI-01 adapter

`HermesCLIAdapter` is an experimental, embedded native CLI adapter for Hermes
0.21.0, source `c5594ec4b34097cafbe24deb6dfd9ac4b21d411d`. Its supported shape is
one fresh dedicated session, one owner, sequential foreground tool calls and
one manual `/compress`. It uses `HermesManualCompletionPolicy` unchanged.
Install Yohaku as a normal wheel into the existing Hermes venv using the
[installation guide](../installation.md). Authentication setup and a general CLI
launcher remain host responsibilities.

## Host integration

The embedding host must initialize Hermes with automatic compression disabled,
verify the pinned source/version, expose only the declared text-result tool,
and exclusively own the fresh session. Configure a **dedicated** `CODEX_HOME`
inside the isolated host profile before creating `SessionStore(session_id,
create=True)`. Never use a regular Codex store. The adapter rejects existing
checkpoint/journal state and does not reopen or resume a Hermes owner.

Supply that store, initialized host, native DB path, declared tool name and
`exclusive_fresh_session=True` to `HermesCLIAdapter`. The boolean is a trusted
host attestation, not discovery or enforcement of other clients' absence.

Connect these operations in the serialized foreground host:

1. Register `pre_tool` and `post_tool` through Hermes `PluginContext`. Native
   session, turn, API request and tool call IDs must be preserved. Call
   `require_tool()` at handler entry because Hermes can swallow Hook exceptions.
2. At the actual Responses send gate, call `observe_request(body)` before sending
   and abort on failure. The gate must separately enforce the allowed route,
   provider/model/effort, request/time/body budget and no retry policy. It must
   not persist request bodies. A completed tool remains pending until its exact
   text result is present in an outgoing request on the same native turn.
3. Wrap the native `run_conversation` return to call `observe_terminal`, passing
   the actual turn/session IDs and native completion/failure/interruption result.
   A `chat()` return alone is insufficient. Route foreground calls through
   adapter `chat()` so the owner can check the ledger and terminal evidence.
4. At an idle task boundary, call `checkpoint` with a trusted `CurrentContext`
   observer and boundary evidence. For this initial bounded profile, the first
   observed execution revision is 1 and intent revision is 0. Archive references
   are optional and must already exist in the same `SessionStore`.
5. Call `compress` with a monotonic clock and a fresh observation. The Core
   consumes the lease; the adapter durably records the request before calling
   native `_manual_compress('/compress')` once. Independent read-only SessionDB
   and SQLite reads collect completion evidence for the existing policy.
6. Call `continue_task` with `RecoveredData`, an absolute working directory and
   current controller instructions. The Core grants one dispatch permit. The
   adapter persists the existing `HandoffDocument`, checks that its archive
   references match the checkpoint and delivers it through native `chat`.

The host uses private Hermes APIs and the Responses wire representation. Changes
to either require a new profile review. The package declares Python >=3.11.
The native host uses Python 3.11.16; normal wheel installation in that venv and
a connected native rehearsal have been checked. Stage 4 used copied source only
as a Probe technique. That historical live record does not become an
installed-wheel live acceptance record. Use the explicit startup configuration
to gate owner construction and Hook registration.

## Receipt and current task state

The control envelope requests an explicit tool receipt containing the handoff ID,
checkpoint ID and checksum, compression request ID, session ID and generation.
The tool handler passes the received fields to `acknowledge`. It must not fill
missing fields from adapter state. The adapter checks every field; after the
successful tool result is incorporated, it calls Core `receive_handoff`.
This is an adapter-defined acknowledgement via a native assistant tool call,
not a built-in Hermes checkpoint acknowledgement or proof of model understanding.

The task's read handler calls `reconcile_fresh(observe)` after receipt. The trusted
observer reads current task state from disk. Before a remaining action, its
handler calls `require_action`; this requires successful incorporation of the
fresh read. After the native continuation finishes, `verify_resume(observe,
assess)` consumes a task-specific `ResumeProof`. Read/action IDs must identify
successful, incorporated tools from that continuation. The assessor must check
disk effects, current intent, remaining work and nonduplication. Model claims
or a successful next action never substitute for receipt or task verification.

## Storage and limits

Checkpoint, archive references and handoff files retain their existing format,
integrity checks and `DATA, NOT INSTRUCTIONS` semantics. `hermes-events` stores
immutable metadata observations separately from the Codex schema-1 journal.
It is evidence, not a restart protocol; `Controller.restart` and Codex snapshot
serialization remain unchanged. An interrupted owner requires external review.

Missing or mismatched completion stops the owner with Core `AMBIGUOUS`.
Missing receipt cannot reach `RESUME_VERIFIED`. Local owner stop is not a
runtime-wide work barrier. Parallel/background work, races, repeated compression,
restart, power loss and late completion recovery are outside this adapter.
Native DB inactive rows are not Yohaku selected visible-turn archives; no Hermes
visible-turn collector or live archive selection/retrieval is implemented.
