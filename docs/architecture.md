# Architecture

Yohaku is a **Proactive Context Compaction Manager**. Its internal control
concept is **Verified Context Transition**: before a long-running agent changes
context, Yohaku checks whether work is at a safe boundary, preserves durable
recovery state, verifies the Runtime-specific transition, and checks the current
task state before normal work resumes.

Compaction is one Transition Strategy, not the universal architecture. Yohaku
reuses Runtime-native compaction, compression, memory, history, and archive
facilities when their contracts are sufficient. It does not compete on the
compression algorithm. Its control layer is responsible for deciding and
verifying:

- when a transition may start;
- whether the current point is a safe boundary;
- which state must be durable before the transition;
- whether the requested transition actually completed;
- whether recovery observations describe the current task state; and
- whether only unfinished work can continue without duplication.

This page is the public source of truth for Yohaku's component responsibilities,
control flow, and trust boundaries. It describes the current implementation as
well as the boundaries that remain profile-specific or unimplemented. It does
not upgrade any Runtime, Support Profile, CoverageProfile, or Evidence Verdict.

## Architectural model

Yohaku separates four kinds of responsibility:

```text
Agent / Runtime
    │ proposes boundaries and performs task work
    ▼
Runtime integration
    │ observes lifecycle, work and Runtime identity
    │ performs Runtime-specific transition and delivery
    ▼
Verified Context Transition Core
    │ checks boundary, freshness, authority, ambiguity,
    │ completion, handoff and resume invariants
    ▼
Durability and task integration
      checkpoints / handoffs / archive
      trusted task observer / task assessor
```

The arrows do not imply equal trust. An Agent proposal is a candidate. Runtime
events are evidence only within the fixed profile that defines their meaning.
Task observers and assessors are trusted integration code. Persistent data is
historical input until fresh observations reconcile it with the current state.

The current code is only partly Runtime-neutral. `Controller` contains shared
state and safety gates, and `CompletionPolicy` is a narrow Runtime-specific seam.
The durable snapshot schema, restart path, `CompanionController`, default backend,
and several lifecycle names remain derived from the Codex reference integration.
Hermes and Claude adapters therefore do not establish a general cross-Runtime
host, persistence, or restart framework.

## Component responsibilities and implementation status

The status labels in the following tables have a limited meaning:

- **Shared implementation**: code used as a common control or data contract.
- **Runtime-specific implementation**: code whose event, identity, transport,
  storage, or host assumptions belong to one Runtime integration.
- **Bounded-profile implementation**: code accepted only for a fixed Support
  Profile, task, tool set, or workflow.
- **Design concept only**: an architectural role exists, but no general product
  component implements it.
- **Future / Deferred**: deliberately outside the current implementation.

A component may have more than one label when its Core decision is shared but the
observations or I/O needed to reach that decision are Runtime- or task-specific.

### Control and safety

| Component | Responsibility | Inputs → outputs | Trust and Runtime boundary | Current status |
|---|---|---|---|---|
| Semantic Boundary Policy | Distinguish a boundary candidate from a verified semantic and execution boundary. Require declared-scope evidence and quiescence before authorization. | Candidate ID, task observation, revisions, workspace revision, evidence profile → `CANDIDATE`, `VERIFIED`, `DEFERRED`, or rejection | A model or Agent may propose a candidate but cannot verify it. The task/host supplies trusted observations. Yohaku does not ship an autonomous general boundary detector. | **Shared implementation** for the Core gate; **bounded-profile implementation** for concrete observations; broader policy is **design concept only**. |
| Core State Machine | Serialize transition decisions and preserve ordering from work through verification, checkpoint, transition, handoff, and resume. | Trusted calls and immutable observations → state changes and one-shot authorities | `Controller` performs no external I/O. Its owner must serialize every call and supply truthful observations. Existing `ROLLOVER_*` names are current implementation vocabulary, not a claim that all strategies are rollovers. | **Shared implementation** in [`controller.py`](../src/yohaku/controller.py) and [`model.py`](../src/yohaku/model.py). |
| Revision / Freshness | Keep intent, execution, control, archive, and workspace observations distinct; reject stale evidence and prevent an old observation from authorizing current work. | Revision counters, `WorkspaceRevision`, verification evidence, fresh recovery observation → accepted current state or invalidation | Runtime and task integrations define what mutations and results they can observe. Equal counters do not compensate for missing coverage. | **Shared implementation** for values and gates; observation coverage is **Runtime-specific** or **bounded-profile**. |
| Lease / Ambiguity handling | Bind short-lived transition authority to one boundary, checkpoint, revision set, workspace, and generation. Suppress blind retry after an uncertain dispatch or completion. | Committed checkpoint and current observation → `Lease`, one `Request`, `AMBIGUOUS`, `INVALIDATED`, or `RECOVERY_REQUIRED` | A lease is local authority, not a Runtime-wide lock. It is consumed before transport and is never restored after restart. | **Shared implementation** in the Core. Final enforcement remains limited by each Runtime's dispatch surface. |
| Completion Policy | Validate Runtime-owned binding and evidence, decide completion from accumulated evidence, and constrain continuation identity. | Pending `Request`, Runtime binding, correlated evidence → incomplete or `ROLLOVER_OBSERVED` | The policy is trusted, fixed for a `Controller` lifetime, I/O-free, and not a transport interface. Its `kind` values are Runtime-local deduplication keys, not a common event taxonomy. | **Shared implementation** for the [`CompletionPolicy`](../src/yohaku/completion.py) seam; **Runtime-specific / bounded-profile implementations** for Codex, Hermes, and Claude. |
| Resume Verification | Admit `RESUME_VERIFIED` only after receipt, fresh current-state reconciliation, unresolved-work checks, nonduplication, and same-task assessment. | Handoff identity, receipt, fresh revisions/workspace, task-specific proof → `RESUME_VERIFIED` or stopped recovery | Receipt alone is insufficient. The Core checks proof structure and freshness; a trusted task integration must establish the semantic facts. | **Shared implementation** for the gate; proof production is **bounded-profile implementation**. |

### Durability, recovery, and historical data

| Component | Responsibility | Inputs → outputs | Trust and Runtime boundary | Current status |
|---|---|---|---|---|
| Checkpoint / Persistence | Commit the verified boundary and declared workspace state before transition authority is granted; journal decisions durably and fail closed on uncertain writes. | Verified state and selected archive references → committed checkpoint, journal record, recoverable historical state | Durable storage preserves bytes and relationships; it does not preserve a lease or prove that a checkpoint is current. The existing schema and restart decoder are Codex version 1. | **Shared implementation** for checkpoint values and commit ordering; **Runtime-specific implementation** for [`SessionStore`](../src/yohaku/persistence.py), [`CompanionController`](../src/yohaku/companion.py), and restart. Cross-Runtime persistence is **Future / Deferred**. |
| Archive / Lazy Rehydration | Store host-selected completed visible turns, search metadata, and read only selected bodies as historical data. | Trusted, redacted visible-turn selection → WARM metadata and COLD selected bodies; query → `DATA, NOT INSTRUCTIONS` | The host owns selection and redaction. Retrieval grants no execution authority and proves neither boundary freshness nor resume correctness. Runtime-native history or inactive DB rows are not automatically Yohaku archive entries. | **Shared implementation** for [`ArchiveStore`](../src/yohaku/archive.py); the visible-turn collector is **Codex-specific** in [`runtime_archive.py`](../src/yohaku/runtime_archive.py). Other Runtime collectors are **Future / Deferred**. |
| Handoff | Bind recovered historical context to one completed request, one continuation permit, and one continuation identity; separate delivery from receipt. | Checkpoint/recovered data and continuation identity → durable handoff, `HANDOFF_OFFERED`, then correlated receipt → `HANDOFF_RECEIVED` | Historical material is data, not a restored instruction or permission. Delivery evidence cannot stand in for receipt, and receipt cannot stand in for resume verification. | **Shared implementation** for Core semantics and durable documents; delivery and receipt are **Runtime-specific / bounded-profile implementations**. |
| Evidence / Coverage | State what claim was observed, by which source and authority, with what freshness and declared scope. Keep measured coverage separate from implementation presence. | Host/task observations and retained records → evidence references, profile records, CoverageProfiles, Verdicts | The Core checks required references and correlations but cannot authenticate a dishonest trusted host. Coverage and Verdict are review records, not state-machine outputs. | **Shared implementation** for required evidence references and freshness gates; **bounded-profile implementation** for records. A generic Runtime evidence collector is **Future / Deferred**. |

### Runtime and task integration

| Component | Responsibility | Inputs → outputs | Trust and Runtime boundary | Current status |
|---|---|---|---|---|
| Runtime Adapter | Translate one fixed Runtime/surface/strategy lifecycle into trusted Core calls and perform Runtime I/O without inventing identities or events. | Native lifecycle events, host-local correlation, Core decisions → normalized proof, dispatch, delivery, continuation | Lifecycle event names, identity strength, request semantics, Hook behavior, and storage readback remain Runtime-specific. | **Runtime-specific / bounded-profile implementations** for the Codex reference, Hermes H-CLI-01, and Claude C-CLI. There is no full common adapter interface or registry. |
| Runtime Host / Companion | Own the Runtime connection and serialized event loop; connect observation, durable state, dispatch, timeout, and recovery. | Runtime messages and trusted callbacks → ordered Core mutations and persisted decisions | The owner is trusted to serialize and correlate observations. `RuntimeHost` and `CompanionController` remain Codex-oriented. Hermes and Claude adapters use separate bounded wiring rather than a neutral Companion. | Codex has a **Runtime-specific implementation**. Hermes/Claude connection paths are **bounded-profile implementations**. A neutral cross-Runtime host is **Future / Deferred**. |
| Work observation / active-pending ledger | Record admitted work, active operations, completed results awaiting incorporation, and loss of observation. | Runtime tool lifecycle and trusted result incorporation → active/pending/uncertain work state | Tool taxonomy and “incorporated” have Runtime- and task-specific meanings. A successful tool result does not prove that the Agent incorporated it into task state. | Codex has a **Runtime-specific bounded ledger**; Hermes, Claude, and document review have separate **bounded-profile** ledgers. No universal ledger exists. |
| Work-plane gate | Refuse new state-changing work while a transition barrier is active and require relevant active/pending work to settle. | Proposed operation, barrier state, observed ledger → allow, deny, `DEFERRED`, ambiguity, or recovery stop | A local gate covers only operations routed through it. It is not an atomic freeze of every Runtime tool, background process, external client, or workspace writer. | **Runtime-specific / bounded-profile implementation** for declared operations. Runtime-wide atomic freeze is not implemented. |
| Task Profile | Bind a logical task to an allowed work plane, input/output contract, trusted observer, assessor, transition strategy, and refusal rules. | Fixed task configuration and current task state → admitted task workflow or refusal | Runtime support supplies lifecycle capability; task support supplies task semantics. Neither implies the other. | **Bounded-profile implementation** for `document-review-report-v1`; a general task framework is **design concept only**. |
| Trusted Observer | Produce current task observations used for boundary, freshness, active/pending work, and resume checks. | Declared inputs, workspace and observed Runtime results → versioned task observation and `WorkspaceRevision` | It is trusted integration code, not model output. It can claim only its declared scope and cannot exclude an unobserved external writer. | **Bounded-profile implementation** for document review and fixture-specific integrations. No general observer exists. |
| Task Assessor | Decide whether the permitted continuation mechanically completed the fixed task without stale, duplicate, undeclared, or pending work. | Fresh observation, continuation items, task contract → task-specific resume proof or refusal | The assessor is not a general quality oracle. It may verify mechanics while leaving content correctness and quality unassessed. | **Bounded-profile implementation**. `document-review-report-v1` assesses mechanical completion only. |
| Operational Host / launcher | Start and own a reviewed Runtime process, isolate state, apply profile configuration, expose lifecycle status/stop, and attach task integration only when that profile supplies it. | Explicit configuration and fixed profile → owned Runtime lifecycle or task-enabled run | A lifecycle-only host deliberately has no inference, task observer, work observation, or transition authority. Starting a Runtime is not transition acceptance. | **Runtime-specific implementation** for Codex and Hermes lifecycle-only profiles; a **bounded Codex task runner** exists for document review. A Claude operational launcher is **Future / Deferred**. |

## Control flow

### Normal work and boundary proposal

```text
Agent / Runtime task work
    → Runtime-specific work observation
    → trusted task observer
    → Semantic Boundary Candidate
    → Core quiescence, freshness and evidence verification
```

The Agent may identify a meaningful stopping point, but that proposal only creates
`CANDIDATE`. The host arms the available work-plane gate, observes relevant active
and pending work, captures the declared workspace scope, and supplies evidence.
Only the Core can enter `VERIFIED`.

### Verified transition

```text
Verified Boundary (`VERIFIED`)
    → durable checkpoint
      (`CHECKPOINT_PREPARING` → `CHECKPOINT_COMMITTED`)
    → revision-bound lease and one request
      (`ROLLOVER_AUTHORIZED` → `ROLLOVER_REQUESTED`)
    → Runtime-specific Transition Strategy
    → correlated completion proof (`ROLLOVER_OBSERVED`)
    → one continuation permit and Runtime continuation identity
    → durable handoff delivery (`HANDOFF_OFFERED`)
    → explicit receipt (`HANDOFF_RECEIVED`)
    → fresh task/workspace observation
    → only unfinished work continues
    → task-specific assessor
    → `RESUME_VERIFIED`
```

The implementation retains `ROLLOVER_*` state names for compatibility even when
the public architecture calls the larger process a Context Transition. A strategy
may compact in place, roll into a fresh context, or migrate a session only if its
own Runtime contract implements and verifies that path. Current acceptance of one
strategy does not establish the others.

### Unsafe or uncertain paths

These outcomes have different meanings and must not be collapsed into one generic
failure:

| Condition | Required outcome |
|---|---|
| Relevant active work or pending result is observed before verification | Enter Core state `DEFERRED`, release the barrier, and return to ordinary work before a new candidate is proposed. Contract prose may describe the action as “DEFER”; the implemented state name is `DEFERRED`. |
| Boundary, revision, workspace, lease, or pre-dispatch authority is stale | Reject or enter `INVALIDATED`; no request is sent from that authority. Reverification is required. |
| Dispatch may have occurred but completion is missing, conflicting, late without reconciliation, or otherwise unknown | Enter `AMBIGUOUS`; suppress normal work and blind retry while correlated evidence is reconciled. |
| Completion is known but handoff, receipt, current-state reconciliation, or resume proof cannot safely finish | Enter `RECOVERY_REQUIRED`; old authority is not restored. |
| A fixed Task Profile rejects undeclared inputs, stale output, duplicate write, or a disallowed work item before uncertain side effects | Report `REFUSED` at the task/operation layer. `REFUSED` is not a Core `State`. If a write or result becomes uncertain, the profile may instead report `AMBIGUOUS`. |
| Durable records are corrupt, inconsistent, or have an unknown write outcome | Stop the owner and require recovery; do not fall back silently to an older checkpoint. |

## Trust boundaries

### Model / Agent output

Model output is untrusted task content. It may propose a boundary, emit a receipt
marker required by a bounded protocol, or produce the task artifact, but its
self-report does not prove quiescence, completion, receipt identity, or correctness.

### Yohaku trusted host

The trusted host owns serialization, Runtime connection, observation adapters,
current-state reads, and durable calls. Core safety depends on these observations
being truthful and correctly scoped. Yohaku checks correlations and state
invariants; it cannot cryptographically prove that host instrumentation reported
the external Runtime faithfully.

### Runtime lifecycle evidence

Runtime events, Hooks, native history, and storage readback are accepted only under
the Transition Strategy that defines their identity, ordering, and coverage. An
RPC acknowledgement or successful tool return can prove a local operation result;
it does not by itself prove transition completion or semantic incorporation.

### Task workspace

The task workspace is current mutable state, not part of Yohaku's trusted storage.
A `WorkspaceRevision` identifies a declared scope and mutation epoch. Profile locks
coordinate cooperating launchers, but they do not prevent other processes,
editors, Runtime clients, or users from writing. Detected changes invalidate stale
evidence; unobserved changes remain a coverage limit.

### Persistent Yohaku storage

Yohaku storage contains journals, checkpoints, handoffs, selected archive entries,
and profile metadata. Checksums, atomic replacement, synchronization, and a local
writer lock protect the implemented POSIX store against specified local failure
modes. They do not make a historical checkpoint current, restore a lease, or
exclude non-cooperating writers outside the store.

### Runtime-native storage

Runtime-native transcripts, histories, databases, or memory stores belong to the
Runtime trust domain. An adapter may use a fixed readback as completion evidence,
but Yohaku does not treat the entire native store as its checkpoint, archive, or
source of current authority. A native record must be correlated and interpreted
under its fixed profile.

### External writer / unobserved work

An external writer or work item outside the declared observer and gate is not made
safe by Yohaku's local state machine. A profile must disclose that limit. Yohaku
does not infer absence from missing events when the observer lacks complete
coverage.

The resulting rules are strict:

- a model's self-report alone never verifies a boundary;
- tool success alone never proves semantic incorporation;
- handoff delivery alone never proves receipt;
- receipt alone never proves resume correctness; and
- an old checkpoint is recoverable historical data, not current state or authority.

## Shared Core and Runtime-specific responsibilities

The following division is the architectural target and the safest current reading
of the implementation. It is not a claim that every item already has a stable,
Runtime-neutral interface.

| Shared safety condition or semantic | Runtime-specific responsibility | Current implementation exception |
|---|---|---|
| Boundary candidate identity and the distinction between candidate and verified boundary | Produce candidates and observe task-specific semantic completion | No autonomous general detector; the document-review observer is profile-specific. |
| Revision monotonicity, freshness comparison, and stale-evidence rejection | Decide which Runtime events and workspace changes advance revisions | Coverage differs by Runtime and task; unobserved writers remain outside the gate. |
| Quiescence must precede verification | Map tool taxonomy, active work, pending results, and result incorporation | Codex, Hermes, Claude, and document review use different bounded ledgers; there is no universal taxonomy. |
| Checkpoint must be committed before authority | Implement durable commit, namespace, locking, and readback on the host platform | Current journal/restart schema and Companion are Codex version 1; Hermes/Claude do not gain Core restart from their adapters. |
| Lease is bound to boundary, checkpoint, revisions, workspace, and generation | Revalidate at the actual dispatch point and enforce the available work gate | The local Core cannot eliminate every final-read-to-Runtime race or provide a Runtime-wide atomic freeze. |
| Unknown execution is not non-execution; ambiguity suppresses retry | Correlate late, duplicate, conflicting, and missing native evidence | Each strategy has its own evidence shape and acceptance scope. |
| Completion is distinct from request acceptance | Map lifecycle events and provide Runtime-specific completion proof | Only the completion predicate has a shared policy seam. Transport and lifecycle mapping are not generalized. |
| Handoff is data-bound, durable, and separate from receipt | Deliver the handoff and produce a correlated Runtime receipt | Codex, Hermes, and Claude use different bounded delivery/receipt mechanisms. |
| Resume requires fresh current state, nonduplication, and same-task continuation | Start or identify the continuation, perform fresh reads, and invoke a task assessor | A general assessor does not exist; current assessors are profile- or fixture-specific. |
| Archive data grants no authority | Extract, select, redact, and identify visible turns | Only the Codex visible-turn collector is implemented as a product archive adapter. |
| Evidence must name scope, authority, freshness, and coverage | Capture source/version/profile-specific records and native identities | Evidence records do not authenticate an external host and do not generalize beyond their fixed profile. |

The Runtime-specific side therefore owns at least lifecycle event mapping, tool
taxonomy, active/pending observation, work-plane enforcement, transition trigger,
completion proof, session/request/generation identity, delivery, continuation,
and visible-turn extraction. The Core must not manufacture a Codex-shaped event
sequence for another Runtime merely to fit the existing snapshot schema.

## Task Profiles: Runtime support is not task support

Runtime support and task support answer different questions:

```text
Runtime support  = can this fixed Runtime profile observe and control a transition?
Task support     = can this fixed task profile determine safe boundary and completion?
```

A lifecycle-only Runtime profile may start, stop, and preserve state while
deliberately refusing inference and transitions because no task observer or
assessor is installed. Conversely, a task contract cannot compensate for missing
Runtime completion, identity, receipt, or continuation evidence.

`document-review-report-v1` is the first packaged Task Profile and remains a
bounded example, not a general task framework. It defines:

- an allowed work plane of two profile-owned dynamic tools,
  `read_review_inputs` and `publish_review_report`;
- a preflight input/output contract for declared UTF-8 Markdown/text inputs and
  one create-only Markdown output;
- a trusted observer for input identities, read/write lifecycle, result
  incorporation, active/pending work, and workspace freshness;
- a task assessor that accepts one successful fresh read and one successful
  publish in the continuation and refuses command, file-change, MCP, duplicate,
  stale, or pending work;
- mechanical completion as the assessed result; and
- fail-closed refusal for stale output, undeclared or duplicate inputs, changed
  workspace, duplicate write, and unsupported work.

The profile does not assess the factual correctness, completeness, editorial
quality, or prose quality of the report. Those qualities remain `NOT_ASSESSED`.
Its accepted workflow cannot be generalized to arbitrary document processing,
coding tasks, other tool sets, or other Runtimes.

## Non-goals and non-guarantees

Yohaku does not guarantee:

- correctness of an arbitrary task or task artifact;
- writing quality, code quality, or successful review of the produced content;
- correctness of model reasoning or model self-reports;
- an atomic freeze of every Runtime tool, background task, process, client, or
  external workspace writer;
- safety or support for a profile without matching Evidence and declared
  coverage;
- a general exactly-once guarantee for Runtime dispatch, delivery, or external
  side effects;
- preservation or recovery of hidden chain-of-thought;
- restoration of in-memory process state, database transactions, external
  service state, or arbitrary OS processes;
- a general task-success oracle, automatic secret classifier, or universal
  visible-turn selector;
- cross-Runtime restart, snapshot migration, or storage compatibility; or
- reimplementation of a Runtime's standard compressor, memory system, or archive
  when the native mechanism can be used under a sufficient contract.

Fresh-context rollover and session migration remain architectural Transition
Strategy categories rather than available general adapters. Support is declared
only for a fixed Runtime, surface, version, strategy, backend/model, tool set, and
owner assumption set.

## Relationship to other public documents

This page owns the current public component model, responsibility boundaries,
control flow, and trust boundaries. Other documents have narrower roles:

- the [README](../README.md) owns the product introduction and top-level current
  status;
- the [support policy](../SUPPORT_POLICY.md) defines Support Profiles, maturity,
  Evidence level, Verdict, and release-channel rules;
- [Runtime Mapping](runtime-mapping.md) owns fixed-profile facts and the mapping
  from Yohaku roles to Runtime-specific primitives;
- [Transition Strategies](transition-strategies.md) owns the taxonomy and common
  semantics of manual in-place compaction, native automatic compaction,
  fresh-context rollover, and session migration;
- [Runtime support](runtime-support.md) retains profile status, historical
  provenance, and known limitations pending its later profile-specific cleanup;
- the [Codex reference](reference/codex.md), [Hermes reference](reference/hermes.md),
  and [Claude CLI reference](reference/claude-cli.md) describe Runtime-specific
  contracts and limits;
- the [document-review profile](reference/document-review-report-v1.md) defines
  the current bounded Task Profile; and
- [Operations](operations.md) and [Installation](installation.md) describe
  launcher behavior and setup rather than architecture acceptance.

Source code remains authoritative for implemented behavior. Public support and
Evidence claims remain authoritative only within the fixed profiles and records
identified by the support documents. Historical design and acceptance material
informed this architecture but does not override current source or enlarge a
current profile's scope.
