# Transition Strategies

Yohaku uses **Context Transition** as the category for changing the context from
which an Agent continues a task. A Transition Strategy defines how one source
context becomes one target context and which Runtime-specific evidence can prove
that change. Compaction is one family of strategies; it is not the architectural
goal by itself.

This page owns the Strategy taxonomy and the common semantics of each method.
The [architecture](architecture.md) owns component responsibilities and trust
boundaries. [Runtime Mapping](runtime-mapping.md) owns fixed-profile facts,
native primitives, implementation status, Evidence provenance, and Verdict.

The Strategy contract does not replace a Runtime Support Profile. A strategy is
usable only when a fixed Runtime/version/surface/backend/owner configuration
implements its trigger, completion proof, handoff, receipt, fresh observation,
continuation, and failure behavior. Documentation alone does not establish any
of those capabilities.

## Common Context Transition contract

All proactive strategies follow the same safety ordering even though their
Runtime events differ:

```text
verified semantic and execution boundary
    → durable current checkpoint
    → revision-bound one-shot authority
    → Runtime-specific strategy trigger
    → strategy-specific completion proof
    → durable handoff delivery
    → explicit correlated receipt
    → fresh observation of the current task state
    → continuation of unfinished work only
    → task-specific assessment
    → RESUME_VERIFIED
```

The implemented Core currently uses `ROLLOVER_AUTHORIZED`,
`ROLLOVER_REQUESTED`, and `ROLLOVER_OBSERVED` for the generic transition portion
of this flow. Those state names are compatibility vocabulary. They do not mean
that an in-place compaction creates a new Runtime session, and they do not make
fresh-context or session-migration support exist.

Every Strategy must keep these facts distinct:

- **source context**: the context whose current work and revisions were
  observed before the transition;
- **target context**: the context from which continuation actually runs;
- **generation and identity**: the native and host-local identities that bind
  one attempt without pretending that host-local IDs are Runtime-native;
- **durable state**: the checkpoint and handoff that survive loss of transient
  process state;
- **completion**: proof that the Runtime performed the requested transition,
  not merely that it accepted a request;
- **delivery and receipt**: evidence that recovery data was offered, followed
  by evidence that the intended continuation received it;
- **fresh observation**: a current read after transition, not a replay of an
  old checkpoint; and
- **resume correctness**: task-specific proof that only unfinished work
  continued without stale or duplicate effects.

No Strategy converts model self-report, a successful tool return, request
acknowledgement, handoff delivery, receipt, or an old checkpoint into a later
proof by itself.

## Taxonomy and current status

| Strategy | Source → target | Trigger class | Current Yohaku status |
|---|---|---|---|
| Manual In-place Compaction | One owned Runtime session/context → compacted form of that same session/context | Yohaku/host/operator issues one explicit Runtime-native compact/compress request after verification | **Implemented only in bounded profiles**: Codex historical reference and `document-review-report-v1`, Hermes H-CLI-01 adapter, and Claude C-CLI completion/recovery variants. Evidence and accepted endpoints differ by profile. |
| Native Automatic Compaction | Active Runtime context → Runtime-compacted form of the same active context | Runtime crosses its own automatic threshold before or independently of Yohaku's proactive request | **Bounded emergency-recovery implementation only** for the historical Codex Reference Scenario G. It is not the normal proactive success path. Other profiles are `NOT_RUN` or `UNIMPLEMENTED`. |
| Fresh-context Rollover | Existing context/thread → newly created empty or minimally initialized context/thread | Yohaku/host requests a new Runtime context and transfers a durable handoff | **Design concept only**. Codex experimental `new_context` is `UNSUPPORTED` in the measured configurations. No accepted current Runtime profile implements the full path. |
| Session Migration | Existing Runtime session/owner, possibly on one host → different session/owner, possibly on another host or Runtime | Yohaku coordinates export, destination creation, delivery, receipt, and continuation | **Future / Deferred**. No general implementation, live Evidence, or accepted profile exists. |

“Implemented” in this table means that code exists for at least one bounded
profile. It does not mean that the Strategy is shared across Runtimes or that
every endpoint through `RESUME_VERIFIED` has live Evidence. The Runtime Mapping
records those differences.

## Manual In-place Compaction

### Purpose and identity

Manual In-place Compaction reduces or rewrites the Runtime's active context while
retaining the owned session/task relationship. Yohaku does not implement the
compressor. It verifies a safe boundary, invokes the Runtime's native operation,
and validates the resulting lifecycle under one fixed profile.

| Contract field | Strategy semantics |
|---|---|
| Purpose | Proactively preserve enough context capacity while retaining a verified task boundary and a controlled continuation path. |
| Source context | The currently owned Runtime session/context after relevant active and pending work has settled and the boundary is `VERIFIED`. |
| Target context | The Runtime-produced compacted/compressed representation in the same logical session. The Runtime may internally create new storage records, but that does not by itself make this a fresh-context rollover. |
| Trigger | One explicit manual compact/compress request issued by the fixed host/operator only after the checkpoint is durable and the one-shot authority is current. |
| Generation / identity | One Core generation and request plus the strongest native session/turn/request identities the profile actually exposes. Missing native generation identity is recorded as a limit, not fabricated from host-local IDs. |
| Durable state | A current Yohaku checkpoint before dispatch, followed by a durable handoff bound to the completed request and continuation identity. Runtime-native history remains separate. |
| Completion proof | A Runtime-specific conjunction of correlated lifecycle and/or storage evidence. Codex, Hermes, and Claude use different predicates; request ACK, engine return, or one Hook/event is insufficient. |
| Handoff | Created only for the completed request from durable state. Historical context is delivered as data, not restored authority. |
| Receipt | An explicit profile-specific receipt correlated to the handoff and continuation. Receipt proves neither fresh state nor resume correctness. |
| Fresh observation | A trusted post-transition read of the current Runtime/task/workspace state, compared with current revisions. |
| Continuation | The owned host admits only the unfinished work allowed by the fixed Task Profile or bounded scenario. |
| Failure / timeout | Pre-dispatch staleness is rejected or invalidated. Uncertain dispatch/completion becomes `AMBIGUOUS`. Known completion followed by failed recovery becomes `RECOVERY_REQUIRED`. Task-contract violations may be `REFUSED`. |
| Retry policy | No blind retry after authority is consumed or dispatch may have occurred. A new request requires reconciliation or a new verified boundary, as allowed by the fixed profile. |
| Late completion | Accepted only when the profile explicitly retains a live owner/correlation and defines reconciliation. Some bounded adapters permanently close the owner on timeout and reject all late evidence. |
| Duplicate | Exact duplicate evidence is idempotent only where the adapter defines it. A second compact request is not inferred to be safe and is commonly rejected by the one-shot profile. |
| Restart | Not inherited from Core persistence. Historical Codex has limited manual restart behavior; accepted Hermes and Claude adapter profiles do not establish transition restart. |
| Current implementation status | Runtime-specific/bounded. No neutral trigger, transport, lifecycle map, receipt, continuation, or restart implementation spans all three Runtimes. |

The fixed completion examples are summarized in
[Role to Runtime primitive mapping](runtime-mapping.md#role-to-runtime-primitive-matrix).
Exact event ordering remains in the Runtime reference pages.

### Proactive success criterion

A successful manual compaction is proactive only when Yohaku verified the
boundary and durably committed the current checkpoint before authorizing the
manual Runtime request. If the Runtime compacts first, the operation must be
handled by the Native Automatic Compaction recovery contract below. A later
handoff or successful continuation does not retroactively make that race a
proactive transition.

## Native Automatic Compaction

### Purpose and emergency character

Native Automatic Compaction covers the case where the Runtime initiates
compaction because of its own threshold or policy. When this happens before
Yohaku has committed a current proactive checkpoint, Yohaku has lost the normal
authorization order. The correct objective is bounded emergency recovery, not a
claim of normal proactive success.

| Contract field | Strategy semantics |
|---|---|
| Purpose | Detect and reconcile a Runtime-initiated compaction that raced ahead of the proactive transition protocol, preserving safety where the fixed profile has sufficient evidence. |
| Source context | The active Runtime turn/context at the moment native compaction begins. It may contain work newer than the last committed Yohaku checkpoint. |
| Target context | The Runtime-compacted form of that same active native context/turn. |
| Trigger | Runtime-owned automatic threshold/policy. Yohaku does not possess a pre-dispatch lease for this native trigger. |
| Generation / identity | Native active-turn/session evidence plus a host recovery attachment. The native event must not be relabeled as a Yohaku manual request. |
| Durable state | The old checkpoint remains stale historical data. A bounded emergency delta may record newly observed facts separately, but it is not promoted to a verified checkpoint or archive entry. |
| Completion proof | A strategy-specific native sequence strong enough to distinguish completed compaction from a pre-event or partial Hook. Historical Codex Scenario G required its bounded correlated completion evidence. |
| Handoff | Recovery handoff combines the last verified durable state with explicitly marked emergency observations under the fixed profile. Unverified delta is not silently treated as verified task state. |
| Receipt | Explicit receipt remains necessary after delivery; emergency origin does not weaken the correlation requirement. |
| Fresh observation | A current post-native-compaction read in the same owned recovery path is mandatory because the stored checkpoint is stale. |
| Continuation | Only unresolved work established by the fresh observation may continue. No proactive lease is reconstructed. |
| Failure / timeout | Missing/conflicting completion, delivery, receipt, or current-state evidence produces `AMBIGUOUS` or `RECOVERY_REQUIRED`; normal work stays suppressed. |
| Retry policy | Do not trigger another compact merely because native completion is uncertain. Reconcile correlated evidence first; blind retry could compact twice. |
| Late completion | May be reconciled only when the fixed adapter still owns the native session/turn and explicitly supports late evidence. Otherwise it remains closed/ambiguous. |
| Duplicate | Duplicate native evidence must not create a second handoff or second continuation. A second native compaction is a distinct transition and needs its own supported contract. |
| Restart | Historical Codex native-race recovery restart is `UNSUPPORTED`; no other accepted profile supplies it. |
| Current implementation status | Bounded to historical Codex Reference Scenario G: one native auto compact, one foreground Bash operation, one active turn, and same-turn recovery. General native-auto support is not implemented. |

Scenario G demonstrated one emergency path under its exact historical profile.
It did not demonstrate proactive trigger control, a general native-auto Strategy,
other Runtimes, restart, parallel work, repeated compaction, or current Codex
versions.

## Fresh-context Rollover

### Design contract

Fresh-context Rollover creates a new Runtime context or thread and resumes the
same logical task there. Unlike in-place compaction, the target does not inherit
the source context merely because the Runtime owns both objects. Yohaku would
need to prove destination identity, deliver the handoff, and observe the new
current state before continuation.

| Contract field | Strategy semantics |
|---|---|
| Purpose | Continue the same task in a newly created context when in-place compaction is unavailable, undesirable, or insufficient. |
| Source context | One verified and checkpointed owned source context/thread. |
| Target context | A distinct fresh context/thread created under the same fixed Runtime profile. |
| Trigger | Yohaku/host requests destination creation only after source checkpoint commit and destination policy checks. |
| Generation / identity | Source native identity, new destination native identity, one Core generation, and an explicit source-to-target binding. Host-local aliases cannot replace either native identity. |
| Durable state | Source checkpoint, source-to-target migration record, and destination-bound handoff must survive loss of transient host state. |
| Completion proof | Evidence that the Runtime created the intended fresh destination and that subsequent events belong to it, not merely an ACK for a create request. |
| Handoff | Delivered in the destination recovery path under an explicit idempotency and single-admission policy; a general exactly-once guarantee is not assumed. |
| Receipt | Explicit destination-bound receipt correlated to the handoff and generation. |
| Fresh observation | First trusted observation of the destination's current state plus a fresh task/workspace read. |
| Continuation | Destination owner admits unfinished work only after receipt and reconciliation; the source is no longer authorized for normal continuation. |
| Failure / timeout | Unknown destination creation is `AMBIGUOUS`; known destination with incomplete delivery/receipt is `RECOVERY_REQUIRED`. Both source and possible destination must be reconciled before retry. |
| Retry policy | No blind second destination creation. A retry requires proving that the first did not exist or safely adopting/retiring it under a supported protocol. |
| Late completion | A late destination-creation result needs explicit adoption or retirement rules and destination identity proof. None are currently implemented. |
| Duplicate | Duplicate destinations, delivery, receipts, and continuations require explicit idempotency and single-owner rules. None are currently accepted. |
| Restart | Would require durable source/destination ownership reconciliation. `UNIMPLEMENTED`. |
| Current implementation status | **Design concept only**. Codex experimental `new_context` was measured `UNSUPPORTED`; Hermes and Claude have no accepted fresh-context implementation or Evidence. |

This category must not inherit manual in-place compaction Evidence. Sharing the
Core's checkpoint or handoff types would not prove destination creation,
delivery, single ownership, or continuation.

## Session Migration

### Deferred contract

Session Migration moves a logical task to a different Runtime session, owner,
host, or Runtime family. It has the broadest trust and compatibility surface:
the destination may use different native identities, storage, tools, models,
event lifecycles, or archive semantics.

| Contract field | Strategy semantics |
|---|---|
| Purpose | Transfer a verified task to a distinct session/owner while preserving durable task state, provenance, and one active continuation authority. |
| Source context | One verified and quiescent source session with a durable exportable checkpoint. |
| Target context | A distinct destination session whose profile and Task Profile are explicitly compatible. |
| Trigger | A migration coordinator would gate admitted source work, create or select the destination, transfer durable data, and hand over ownership. This would not imply an atomic freeze of unobserved work. |
| Generation / identity | Source and destination native identities, migration generation, host identities, and a durable ownership-transfer record. Cross-Runtime identity equivalence must never be inferred from similar strings. |
| Durable state | Versioned portable checkpoint/handoff plus compatibility and provenance metadata; current Codex-shaped snapshots are not a portable migration format. |
| Completion proof | Destination creation and ownership acceptance, source retirement, delivery/receipt, and current-state reconciliation across both trust domains. |
| Handoff | Exported under an explicit schema and redaction policy, then durably bound to the destination profile. |
| Receipt | Destination-native or host-mediated explicit receipt with trusted source/destination correlation. |
| Fresh observation | Destination task/workspace observation plus proof that the source cannot continue concurrently under stale authority. |
| Continuation | Exactly one destination owner after a completed ownership transfer. This is an intended contract, not a current exactly-once guarantee. |
| Failure / timeout | Partial source retirement, unknown destination creation, uncertain transfer, or split ownership would require a migration-specific recovery state. |
| Retry policy | No general policy exists. A safe design must reconcile both source and destination before any retry. |
| Late completion | No implemented adoption, fencing, or tombstone protocol exists. |
| Duplicate | No implemented duplicate-destination or split-brain prevention protocol exists. |
| Restart | No portable restart/reconciliation implementation exists. |
| Current implementation status | **Future / Deferred**. No shared migration coordinator, portable snapshot, compatibility negotiation, accepted Runtime profile, live Evidence, or Verdict exists. |

Session Migration is not established by starting a new Runtime process, copying a
checkpoint file, replaying a transcript, or delivering a handoff. Those actions
omit source retirement, destination identity, receipt, freshness, ownership, and
resume verification.

## Proactive transition versus emergency recovery

The two paths have different authorization and Evidence meanings:

```text
Proactive
  current observation
    → VERIFIED boundary
    → current durable checkpoint
    → one-shot authority
    → host-triggered Strategy
    → completion and recovery verification

Emergency after native auto compact
  Runtime-triggered compaction before current checkpoint
    → detect lost proactive ordering
    → retain old checkpoint as stale
    → record bounded emergency observations separately
    → prove native completion
    → require fresh current-state recovery
    → no reconstruction of the old authority
```

The emergency path cannot be counted as proactive transition success. Conversely,
failure to complete an emergency path says nothing by itself about a profile's
separately measured manual proactive path.

## Failure semantics across strategies

The public outcome vocabulary keeps different hazards separate:

| Condition | Meaning and action |
|---|---|
| `DEFERRED` | Relevant active/pending work prevents boundary verification. Return to normal work, then propose a new candidate. No transition request was authorized. |
| `INVALIDATED` | Pre-dispatch boundary, revision, checkpoint, workspace, or lease is stale. Reverify from current state. |
| `AMBIGUOUS` | Dispatch or completion may have occurred but cannot yet be proved. Suppress normal work and blind retry while correlated evidence is reconciled. |
| `RECOVERY_REQUIRED` | Transition completion is known or retained, but delivery, receipt, fresh observation, continuation, or assessment cannot safely finish. Do not restore old authority. |
| `REFUSED` | A fixed Task Profile or operation gate rejects known-disallowed, stale, duplicate, or undeclared work before uncertain side effects. It is not a Core state. |

A Strategy may further narrow late-event and retry behavior. It may not weaken
`AMBIGUOUS` into presumed non-execution or treat an unobserved external side
effect as safely retryable.

## Evidence isolation

Strategy Evidence is not polymorphic. It does not inherit across:

- Manual In-place Compaction and Native Automatic Compaction;
- in-place compaction, Fresh-context Rollover, and Session Migration;
- Codex, Hermes, and Claude Code;
- Runtime versions, CLI/API surfaces, operating systems, or owner models;
- provider, backend, model, context configuration, or Hook configuration; or
- lifecycle-only, transition, and Task Profiles.

Consequently:

- Codex manual compact `PASS` is not native-auto `PASS`;
- Claude local Ollama `PASS` is not Anthropic subscription `PASS`;
- Hermes H-CLI-01 `PASS` is not Hermes-wide `PASS`; and
- Runtime support is not `document-review-report-v1` or any other Task Profile
  support.

Strategies may share safety semantics—durability before authority, freshness,
one-shot dispatch, ambiguity suppression, delivery/receipt separation, and
resume verification. They must not share lifecycle evidence, completion
predicates, identities, Verdicts, restart claims, or task assessment without a
matching fixed profile and retained Evidence.

## Deferred decisions for profile-specific documents

This taxonomy intentionally leaves exact native event names, field mappings,
timeouts, configuration, and event-order alternatives to the Runtime reference
pages. Those pages must next make explicit:

- which native identity fields are mandatory and which correlations are
  host-local;
- the full completion predicate and legal event-order variations;
- timeout closure, late-event reconciliation, duplicate handling, and retry
  refusal for each profile;
- Runtime-native storage readback authority and its limits;
- restart/reconnect ownership, if any;
- delivery/injection and continuation primitives; and
- the exact Task Observer and assessor boundary for task-enabled profiles.

The future `evidence-model.md` should define how each of those observations is
recorded, attributed, retained, combined into a CoverageProfile, and used for a
Verdict. It must preserve the Strategy and profile isolation rules above.
