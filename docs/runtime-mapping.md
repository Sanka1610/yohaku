# Runtime Mapping

This document maps Yohaku roles to fixed Runtime Support Profiles and Transition
Strategies. It owns profile-specific facts: Runtime and surface, lifecycle
primitives, identity, work observation, completion proof, delivery, current-state
observation, continuation, and known limits.

The [architecture](architecture.md) owns component responsibilities and trust
boundaries. [Transition Strategies](transition-strategies.md) owns the taxonomy
and common semantics of Context Transition methods. Runtime-specific contracts
remain in the [Codex](reference/codex.md), [Hermes](reference/hermes.md), and
[Claude Code](reference/claude-cli.md) references.

This mapping does not create support by documentation. Implementation presence,
retained Evidence, and Verdict are separate facts, and every claim remains
limited to the named profile. Evidence Verdicts remain those defined by the
[support policy](../SUPPORT_POLICY.md). The mapping also uses the following
descriptive cell states; `UNIMPLEMENTED` and `UNKNOWN` are not new Verdicts:

- **UNIMPLEMENTED**: no implementation exists for the stated role or path.
- **UNSUPPORTED**: the fixed profile excludes or rejects the path.
- **NOT_RUN**: the path may exist or be specified, but no qualifying run is
  claimed for this profile.
- **UNKNOWN**: the available record does not establish the value.

An implementation can therefore coexist with `NOT_RUN`, and a bounded `PASS`
can coexist with an overall `PARTIAL` Verdict. Empty cells are not used.

## Fixed profile register

The mapping keys are document-local shorthand, not new Support Profile IDs.
Probe, adapter, operational lifecycle, and task support are intentionally split
even when they use the same Runtime version.

| Key | Fixed profile or retained record | What the row establishes | Implementation / Evidence / Verdict |
|---|---|---|---|
| `C-REF-M` | Codex historical Reference profile, `0.155.0-alpha.16.4` / Manual In-place Compaction | Historical proactive manual path, archive, and Core persistence behavior | Implemented reference integration; retained local/synthetic and bounded live Runtime Evidence; historical Phase 14 overall **PARTIAL** |
| `C-REF-A` | Same historical Reference profile / Native Automatic Compaction emergency recovery | Historical Scenario G native race recovery; not proactive transition success | Bounded emergency implementation and Evidence; Scenario G **PASS**, historical Phase 14 overall **PARTIAL** |
| `C-OP` | `codex-operational-0.158` | Current-version owned App Server lifecycle without inference or task transition | Operational lifecycle implemented and measured **PASS**; task transition **NOT_RUN**; experimental |
| `C-DRR` | `codex-document-review-report-v1` / Task Profile `document-review-report-v1` | One current-version real document-review workflow with one manual compact and one report | Bounded implementation; lab/live-Runtime/nonfixture real-task Evidence; profile **PASS**, overall product coverage **PARTIAL**; quality `NOT_ASSESSED` |
| `H-PROBE` | Hermes `H-CLI-01` Stage 2 Probe | Capability observation of one fixed native CLI workflow before the connected adapter | Probe package and measured workflow only; one bounded workflow **PASS**, overall **PARTIAL**; not an adapter or operational host |
| `H-ADAPTER` | `hermes-h-cli-01` / retained Stage 4 adapter profile | Embedded adapter path for one fixed tool and one manual compression | Bounded adapter implemented; live synthetic Evidence; accepted bounded workflow **PASS**, overall **PARTIAL** |
| `H-OP` | `hermes-operational-h-cli-01` | Owned native CLI/store lifecycle with inference and transition adapter disabled | Operational lifecycle implemented and measured **PASS**; task/tool/transition path **NOT_RUN**; experimental |
| `CL-SUB-C` | `C-CLI/2.1.280/Linux/print-stream-json/command-hooks` completion profile | External Anthropic subscription CLI manual-compaction completion through `ROLLOVER_OBSERVED` | Bounded completion adapter implemented; external live-Runtime synthetic Evidence; manual completion **PASS**, overall **PARTIAL** |
| `CL-SUB-R` | Same fixed C-CLI surface with the recovery adapter | Handoff, receipt, continuation, and resume contract for the subscription surface | Recovery implementation exists, but qualifying external subscription recovery is **NOT_RUN**; no recovery Verdict is inherited from local Ollama |
| `CL-LOCAL-FULL` | `C-CLI-OLLAMA-LOCAL/2.1.280/0.34.1/spark-x2.5-4b-uncensored/e1646156c204` | Local maintainer full-identity receipt and recovery comparison | Bounded maintainer adapter; local-live synthetic Evidence; one `RESUME_VERIFIED` and one pre-adapter failure; repeatability **FAIL**, overall **PARTIAL** |
| `CL-LOCAL-NONCE` | `claude-c-cli-local-nonce` / `host-nonce-v1` | Local maintainer recovery using a host-bound one-time nonce receipt | Bounded maintainer implementation; local-live synthetic Evidence; one workflow **PASS**, overall **PARTIAL**; quality and repeatability `NOT_ASSESSED` |

These are not aliases for whole Runtime families. In particular, `H-PROBE`,
`H-ADAPTER`, and `H-OP` are three different claims. `CL-SUB-C` does not include
recovery, and local Ollama recovery does not establish Anthropic subscription
recovery. `C-DRR` adds one Task Profile; it does not turn `C-OP` into general
task support.

## Codex profiles

### `C-REF-M` and `C-REF-A` — historical Reference profile

These mapping rows share one frozen Runtime Support Profile but not one
Transition Strategy or Evidence claim. The common profile facts are listed once;
the Strategy-specific contract follows the table.

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Codex CLI `0.155.0-alpha.16.4`; owned App Server; WSL2 Ubuntu; Python `3.14.4` host |
| Provider / backend / model | OpenAI provider; `gpt-5.6-luna`, low reasoning, in the retained profile |
| Implementation status | Historical Runtime-specific reference implementation. It is not the current Codex operational baseline. |
| Evidence provenance / level | Retained local/synthetic records plus bounded live-Runtime scenarios under the frozen Phase 14 CoverageProfile |
| Verdict / maturity | Historical Phase 14 overall `PARTIAL`; experimental; individual covered scenarios retain their recorded results |
| Transition Strategy | `C-REF-M` is Manual In-place Compaction. `C-REF-A` is a separate bounded Native Automatic Compaction emergency-recovery path. Experimental `new_context` is `UNSUPPORTED`. |
| Lifecycle observation | Ordered App Server notifications and responses under one owned thread and one outstanding transition request |
| Work taxonomy | Declared Bash and `apply_patch` paths plus fixed archive tools; general MCP, detached/background, external, and parallel work are outside accepted coverage |
| Active / pending / incorporated | Active means an admitted foreground operation is still executing. Pending means its result has not yet been independently observed as terminal and incorporated. Incorporation requires trusted host observation; tool success alone is insufficient. |
| Work-plane gate | Local barrier and allow/deny rules for the declared work plane; not an atomic Runtime-wide freeze |
| Trigger owner | Strategy-specific: Yohaku/host for `C-REF-M`; Codex Runtime for `C-REF-A` |
| Request identity | `C-REF-M` uses one Yohaku `Request`, Core generation, and ordered owner. `C-REF-A` records native-auto origin and recovery correlation without reconstructing a proactive lease. |
| Native session / turn / generation / attachment identity | Native session/thread and active-turn evidence are observed where available. App Server events do not provide a native Yohaku request or generation ID. |
| Host-local identity | Yohaku request ID, generation, attachment/correlation state, and ordered owner mapping |
| Completion proof | Strategy-specific correlated native evidence; RPC acknowledgement alone is insufficient. See the Strategy split below. |
| Checkpoint / journal | POSIX `SessionStore` and Core records. `C-REF-M` commits the current checkpoint before authority; `C-REF-A` preserves the prior checkpoint as stale and records the emergency delta separately. |
| Runtime-native storage | Codex transcript/history is Runtime-native data, not the Yohaku checkpoint or archive. |
| Handoff creation / delivery / injection | Core creates a durable handoff. The Codex companion injects it through the bounded recovery path, including compact-origin `SessionStart` where specified. |
| Explicit receipt | Correlated `YOH_ACK:<handoff-id>:<generation>` in the accepted reference path |
| Fresh current-state observation | Trusted post-transition observation and declared workspace read; old checkpoint state cannot satisfy freshness |
| Continuation owner | Owned Companion/App Server continuation for the same task and correlated transition |
| Task assessor / resume verification | Bounded scenario/fixture assessor plus Core resume gates; not a general task assessor |
| Archive / native history | Yohaku archive stores trusted, selected visible turns. It does not adopt the full Codex native history. |
| Restart | `C-REF-M` has limited ordinary manual reconciliation. `C-REF-A` restart is `UNSUPPORTED`. Consumed leases are never restored. |
| Timeout / late / duplicate / ambiguous behavior | Unknown dispatch or missing/conflicting completion enters `AMBIGUOUS` and suppresses blind retry. A late matching manual completion may reconcile while ownership remains mapped. Duplicates are no-ops. Native-auto missing proof requires recovery rather than proactive success. |
| Known limitations | Hook failure paths are `FAIL_OPEN`; no Runtime-wide atomic freeze; no native context generation identity; general MCP, active `apply_patch`, detached/parallel/external work, power loss, and several repeat/restart paths are not accepted |

| Strategy-specific field | `C-REF-M` | `C-REF-A` |
|---|---|---|
| Authorization and trigger | A current verified boundary and committed checkpoint precede one host-triggered manual compact request. | The Runtime initiates automatic compaction before the current proactive checkpoint/lease sequence completes. No proactive authority is inferred afterward. |
| Durable source state | Current verified checkpoint plus the normal journal ordering. | Prior checkpoint remains stale historical data; bounded emergency observations are separate unverified delta, not a replacement checkpoint or archive. |
| Completion and recovery proof | Correlated compaction item, successful `PostCompact`, and successful compact turn completion, followed by the normal handoff/receipt/fresh-state chain. | Bounded correlated native completion, same-turn delivery/receipt, and fresh current-state recovery for the active turn. Missing completion remains `AMBIGUOUS`. |
| Continuation and restart | Owned continuation of unfinished work; limited ordinary manual restart reconciliation exists, without restoring consumed authority. | Same-turn bounded continuation only; native recovery restart is `UNSUPPORTED`. |
| Evidence / Verdict | Retains the historical manual scenarios and their original per-scenario Verdicts; this document creates no new aggregate manual Verdict. | Historical Scenario G **PASS** under its frozen scope; Phase 14 overall remains **PARTIAL**. |
| Accepted scope | Historical manual reference scenarios under their recorded scopes. | Scenario G only: one native compaction per attachment, one foreground Bash operation, one active turn, and no general repeat/race/restart claim. |

### `C-OP` — current operational lifecycle profile

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Codex `0.158.0-alpha.2.1`; dedicated App Server over stdio; WSL2/Linux host |
| Provider / backend / model | Inference is disabled; loopback provider/model configuration is deliberately non-tasking |
| Implementation status | Runtime-specific operational launcher, Companion, and store are implemented. Task observer, inference, tools, compact trigger, and continuation are not activated. |
| Evidence provenance / level | `S5-OP-CODEX-0158`; native lifecycle, no inference |
| Verdict / maturity | Lifecycle **PASS**; task transition `NOT_RUN`; experimental and release undeclared |
| Transition Strategy | `NOT_RUN`; no strategy is activated by this lifecycle-only profile |
| Lifecycle observation | Owned startup, fresh thread, status, and shutdown through the dedicated App Server connection |
| Work taxonomy; active / pending / incorporated | No task work is admitted; all task-work values are `UNSUPPORTED` in this profile |
| Work-plane gate | Lifecycle profile refuses task execution rather than claiming a task gate |
| Trigger owner / request identity | Transition trigger and transition request identity are `UNIMPLEMENTED` for this profile |
| Native identity | Fresh native thread/session identity is observed for lifecycle ownership; turn/generation/attachment transition identity is `NOT_RUN` |
| Host-local identity | Operational run and Companion/store identity; not a native Runtime request or generation |
| Completion proof | `NOT_RUN`; lifecycle startup/shutdown is not compaction proof |
| Checkpoint / journal | Companion/store lifecycle is present; no task checkpoint is committed |
| Runtime-native storage | Fresh Codex thread state under the owned App Server; not treated as Yohaku checkpoint/archive |
| Handoff / receipt / fresh observation / continuation | `UNIMPLEMENTED` in the lifecycle-only run |
| Task assessor / resume verification | `UNIMPLEMENTED`; task transitions are refused without a Task Profile |
| Archive / native history | `NOT_RUN` |
| Restart | Operational process restart may start a new owned lifecycle; transition restart semantics are `NOT_RUN` |
| Timeout / late / duplicate / ambiguous behavior | Launcher lifecycle errors are operational failures. Transition ambiguity policy is not exercised. |
| Known limitations | Establishes current-version lifecycle compatibility only; it inherits no `C-REF-M` or `C-REF-A` transition or archive Evidence |

### `C-DRR` — `document-review-report-v1`

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Codex `0.158.0-alpha.2.1`; dedicated App Server with profile-owned dynamic tools; WSL2/Linux host |
| Provider / backend / model | Fixed by the retained run configuration; public Evidence does not establish a reusable provider/model claim, so the mapping value is `UNKNOWN` |
| Implementation status | Bounded Task Profile and task-enabled runner exist; this is not a general task framework |
| Evidence provenance / level | `DRR-V1-CODEX-0158-LIVE-01`; lab/live-Runtime/nonfixture real task |
| Verdict / maturity | Fixed workflow/profile **PASS**; overall product coverage **PARTIAL**; experimental; prose and factual quality `NOT_ASSESSED` |
| Transition Strategy | One Manual In-place Compaction in one fresh session |
| Lifecycle observation | Owned App Server lifecycle plus exact dynamic-tool events and manual compact lifecycle |
| Work taxonomy | Only `read_review_inputs` and `publish_review_report` are admitted; shell, file-change, MCP, undeclared, stale, duplicate, and additional work are refused |
| Active / pending / incorporated | Active is an admitted profile tool in execution. Pending is a successful result not yet independently observed in the required outgoing/current task state. Incorporated is profile-observed use of the exact read or publish result, not model self-report. |
| Work-plane gate | Profile-owned two-tool gate plus transition barrier and create-only output contract |
| Trigger owner | Yohaku task runner after the trusted observer establishes a verified boundary |
| Request identity | One Yohaku request and Core generation for the single manual compact |
| Native session / turn / generation / attachment identity | Fresh Codex thread and Runtime turn observations; no native Yohaku generation identity |
| Host-local identity | Runner, attachment, request, generation, tool-call/result, and declared workspace identities |
| Completion proof | The Codex manual three-part proof: compaction item, `PostCompact`, and successful compact turn completion |
| Checkpoint / journal | Core checkpoint and profile task state committed before the request; profile records bind exact input/output identities |
| Runtime-native storage | Native Codex context/history remains separate from the task checkpoint and Yohaku store |
| Handoff creation / delivery / injection | Durable Core handoff delivered by the owned Codex recovery path |
| Explicit receipt | Exact correlated handoff/generation receipt under the profile contract |
| Fresh current-state observation | The continuation re-reads the declared inputs and confirms output absence before publish; the assessor later reads back the created output hash. Stale hashes or workspace change are refused. |
| Continuation owner | Same owned task runner; exactly the unfinished profile work may continue |
| Task assessor / resume verification | Profile assessor verifies one fresh read and one create-only publish with no disallowed/pending/duplicate work, then Core may enter `RESUME_VERIFIED` |
| Archive / native history | `UNSUPPORTED` by this Task Profile; it does not claim general Codex archive coverage |
| Restart | `UNSUPPORTED` for the accepted workflow |
| Timeout / late / duplicate / ambiguous behavior | Uncertain side effect or completion becomes `AMBIGUOUS`; stale/duplicate/undeclared work is `REFUSED`; blind retry is suppressed |
| Known limitations | One input contract, one fresh session, one compact, one output, and one exact tool plane; arbitrary document work, repeated transitions, restart, and quality assessment are outside scope |

## Hermes profiles

All three Hermes rows use Hermes `0.21.0` from source
`c5594ec4b34097cafbe24deb6dfd9ac4b21d411d`, but they establish different
claims.

### `H-PROBE` — H-CLI-01 Stage 2 Probe

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Hermes `0.21.0`; instrumented native CLI host; Ubuntu-Hermes on WSL2; Python `3.11.16` |
| Provider / backend / model | `openai-codex`; `gpt-5.6-luna`, low reasoning |
| Implementation status | Probe harness and fixed workflow only. Connected product adapter and operational launcher are not established by this row. |
| Evidence provenance / level | H-CLI-01 Stage 2 lab/live-Runtime/synthetic Probe; eight requests, one manual compression, bounded workflow |
| Verdict / maturity | Fixed Probe workflow **PASS**; overall **PARTIAL**; experimental |
| Transition Strategy | Manual In-place Compaction / Hermes manual compression |
| Lifecycle observation | Probe instrumentation observes the fixed CLI request/compression path |
| Work taxonomy | One fixed foreground tool workflow; general tools and background work are `NOT_RUN` |
| Active / pending / incorporated | Active spans the admitted fixture handler. After `post_tool`, the result remains pending until its exact text appears as `function_call_output` in the next outgoing request on the same turn. That proves bounded propagation, not semantic understanding; no reusable product ledger is claimed. |
| Work-plane gate | Probe sequencing; product gate `UNIMPLEMENTED` at this stage |
| Trigger owner / request identity | Probe host triggers one manual compression and uses Probe-local correlation |
| Native identity | Available Hermes session/turn/request/tool identifiers are observed by instrumentation |
| Host-local identity | Probe run and correlation IDs; not substitutes for native Hermes IDs |
| Completion proof | Host history changed and an independent read-only `SessionDB` connection matched the active projection and inactive rows. This was Probe instrumentation and Evidence, not yet a product completion-policy or adapter implementation. |
| Checkpoint / journal | Fixture/Probe checkpoint behavior only; product persistence is not established |
| Runtime-native storage | Native history/store observed within the Probe; not Yohaku checkpoint/archive |
| Handoff / receipt | Handoff behavior was exercised; explicit receipt coverage remained partial and is not promoted to adapter support |
| Fresh observation / continuation / assessor | Bounded Probe fresh-read and nonduplication checks; no general task assessor |
| Archive / restart | `UNIMPLEMENTED` / `NOT_RUN` |
| Timeout / late / duplicate / ambiguous behavior | Runtime timeout, late completion, replay, and restart paths are `NOT_RUN` |
| Known limitations | Capability Probe only; it must not be represented as installed adapter, operational lifecycle, general Hermes support, or task support |

### `H-ADAPTER` — connected H-CLI-01 adapter

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Hermes `0.21.0`; embedded native in-process CLI host; Ubuntu-Hermes/WSL2 |
| Provider / backend / model | `openai-codex`; `gpt-5.6-luna`, low reasoning, in the retained Stage 4 profile |
| Implementation status | Runtime-specific bounded adapter for one session, one foreground tool, and one manual compression |
| Evidence provenance / level | `H-CLI-01-STAGE4`; lab/live-Runtime/synthetic adapter run, nine requests (`4 / 1 / 4`) |
| Verdict / maturity | Accepted bounded workflow **PASS**; overall **PARTIAL**; experimental |
| Transition Strategy | Manual In-place Compaction using native Hermes compression |
| Lifecycle observation | Embedded `PluginContext` and host instrumentation preserve native session, turn, API request, and tool-call identities |
| Work taxonomy | One fixed sequential foreground tool. General tools, background/detached work, parallelism, and external writers are outside coverage. |
| Active / pending / incorporated | Active begins when the admitted handler starts. Pending persists after tool completion until the exact result text appears in the outgoing same-turn request. This proves bounded propagation, not semantic understanding. |
| Work-plane gate | Embedded host admits the fixed tool and blocks transition while active/pending work exists |
| Trigger owner | Embedded Yohaku host issues one manual compression after Core authorization |
| Request identity | Yohaku request/generation correlated with the owned native compression call |
| Native identity | Hermes session, turn, API request, and tool call/result identities |
| Host-local identity | Adapter request/generation and owner mapping; retained alongside, not instead of, native identities |
| Completion proof | Host history mutation plus independent read-only `SessionDB` readback of the exact projection and archived rows. Engine return/count alone is insufficient. |
| Checkpoint / journal | Core checkpoint and handoff records exist. Hermes adapter event metadata is bounded diagnostic state, not a general restart journal. |
| Runtime-native storage | `SessionDB` / `SessionStore`; completion readback source only, not Yohaku checkpoint or archive |
| Handoff creation / delivery / injection | Core creates the durable handoff; embedded host delivers it through the fixed continuation path |
| Explicit receipt | Adapter-defined assistant tool receipt carrying the required Runtime and Yohaku correlations; not a built-in Hermes receipt primitive |
| Fresh current-state observation | Independent current native/task read after delivery and before assessment |
| Continuation owner | Same exclusive embedded host and fresh dedicated session |
| Task assessor / resume verification | Fixed fixture/task assessor plus Core gates reaches `RESUME_VERIFIED`; no general Hermes task assessor |
| Archive / native history | Yohaku archive `UNIMPLEMENTED`; inactive/native DB rows remain Runtime-native history |
| Restart | `UNSUPPORTED` for the accepted profile |
| Timeout / late / duplicate / ambiguous behavior | Missing/uncertain dispatch or proof enters `AMBIGUOUS`; late, repeated, and race paths are `NOT_RUN`; no blind retry |
| Known limitations | One fixed tool, one compression, exclusive in-process owner, embedded instrumentation, no restart, no general tool plane, no repeated/racing transition, and no general archive |

### `H-OP` — operational lifecycle profile

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Hermes `0.21.0`; native in-process CLI construction and store; Ubuntu-Hermes/WSL2 |
| Provider / backend / model | Inference is disabled; no provider/model request is made |
| Implementation status | Runtime-specific operational launcher for native CLI/store lifecycle. Lazy inference agent and H-CLI-01 transition adapter are deliberately disabled. |
| Evidence provenance / level | `S5-OP-HERMES`; native lifecycle, no inference |
| Verdict / maturity | Lifecycle **PASS**; task/tool/transition `NOT_RUN`; experimental |
| Transition Strategy | `NOT_RUN` |
| Lifecycle observation | Native CLI construction, session/store ownership, status, and shutdown |
| Work taxonomy; active / pending / incorporated | No task work is admitted; `UNSUPPORTED` in this lifecycle-only profile |
| Work-plane gate | Task operations are refused by profile rather than observed through the Stage 4 gate |
| Trigger / request / completion | `UNIMPLEMENTED` in this profile |
| Native identity | Native lifecycle/session/store identity; no task turn/compression identity is exercised |
| Host-local identity | Operational run identity; not a native Hermes request or turn |
| Checkpoint / journal / native storage | Operational store lifecycle only; no transition checkpoint. Native store is not Yohaku persistence. |
| Handoff / receipt / fresh observation / continuation / assessor | `UNIMPLEMENTED` |
| Archive | `UNIMPLEMENTED` |
| Restart | Transition restart semantics `NOT_RUN` |
| Timeout / late / duplicate / ambiguous behavior | Operational lifecycle failures remain launcher errors; transition ambiguity is not exercised |
| Known limitations | Establishes lifecycle ownership only and inherits neither `H-PROBE` nor `H-ADAPTER` task/transition Evidence |

## Claude Code profiles

All C-CLI rows fix Claude Code CLI `2.1.280` on Linux using `claude -p`,
stream-json, and synchronous command Hooks. The completion and recovery contracts
use `PreCompact`, `PostCompact`, and `SessionStart` only where the fixed profile
actually observes them. These event names are not synthesized for Codex or Hermes.

### `CL-SUB-C` — subscription external completion profile

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Claude Code CLI `2.1.280`; Linux; print mode; stream-json; synchronous command Hooks |
| Provider / backend / model | Anthropic subscription surface; exact provider/backend/model value in the public retained record is `UNKNOWN` |
| Implementation status | Bounded external completion collector/adapter exists through `ROLLOVER_OBSERVED`; no operational launcher |
| Evidence provenance / level | External live-Runtime synthetic record `C-CLI-COMPLETION`; sanitized event records and hashes |
| Verdict / maturity | Manual completion **PASS**; overall C-CLI **PARTIAL**; experimental |
| Transition Strategy | Manual In-place Compaction; one fresh process/session and one compact |
| Lifecycle observation | Synchronous command Hooks observe native `SessionStart`, `PreCompact`, `PostCompact`, and compact-origin `SessionStart` within the fixed collector contract |
| Work taxonomy | Fixed synthetic workflow; general task work, background work, and arbitrary tools are `NOT_RUN` |
| Active / pending / incorporated | Active is the fixed foreground fixture operation between its admitted Pre/PostToolUse observations. The collector and fixture effect can establish terminal execution for that operation; general pending-result incorporation and semantic incorporation remain `NOT_RUN` and are not inferred from Hook or CLI success. |
| Work-plane gate | Fixed collector/runner sequencing; no general C-CLI work gate |
| Trigger owner | External operator/runner invokes one manual compact |
| Request identity | Yohaku host-local attachment/request/generation plus a closed collector sequence |
| Native identity | Native Claude `session_id`; no native Yohaku request, generation, or attachment ID |
| Host-local identity | Attachment, request, generation, and collector sequence. These remain explicitly host-local. |
| Completion proof | Correlated `PreCompact`, compact handler/`PostCompact`, compact-origin `SessionStart`, successful CLI completion, and collector closure under the adapter predicate. CLI success or one Hook alone is insufficient. |
| Checkpoint / journal | Committed Yohaku checkpoint/lease and C-CLI event metadata. The external record did not independently read back every private checkpoint/lease byte. |
| Runtime-native storage | Fresh Claude session storage; not the Yohaku checkpoint/archive |
| Handoff / receipt / fresh observation / continuation | `NOT_RUN` for external subscription recovery; completion Verdict stops at `ROLLOVER_OBSERVED` |
| Task assessor / resume verification | `NOT_RUN` |
| Archive | `UNIMPLEMENTED` |
| Restart | `UNSUPPORTED` in the fixed adapter contract |
| Timeout / late / duplicate / ambiguous behavior | Timeout permanently closes the owner; late evidence cannot reopen it; a second compact is rejected; uncertainty becomes `AMBIGUOUS` |
| Known limitations | One compact, fixed Hooks, synthetic task, no external recovery acceptance, no launcher, no general work gate, and no general task support |

### `CL-SUB-R` — subscription recovery capability row

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Same fixed `2.1.280` Linux print/stream-json/command-Hooks surface as `CL-SUB-C` |
| Provider / backend / model | Anthropic subscription surface; exact model/backend `UNKNOWN` |
| Implementation status | Recovery adapter contract exists: same-process handoff, receipt, fresh observation, one continuation, assessor, and Core resume verification |
| Evidence provenance / level | Local synthetic recovery tests and a fake-CLI/real-Hook harness exist; qualifying external subscription recovery Evidence is `NOT_RUN` |
| Verdict / maturity | Recovery Verdict `NOT_RUN`; no local Ollama Verdict is inherited |
| Transition Strategy | Manual In-place Compaction followed by same-process recovery, if the fixed external profile is executed |
| Lifecycle observation / work taxonomy / gate | Implemented bounded collector and fixed recovery work plane; external subscription execution `NOT_RUN` |
| Active / pending / incorporated | In the implemented recovery adapter, the one foreground receipt/read/action handler is active until its matching successful native PostToolUse result. Later gates require the exact prior result/token. This is fixture-bounded incorporation, not general semantic understanding; external subscription execution is `NOT_RUN`. |
| Trigger / request / identities | Same native `session_id` plus host-local attachment/request/generation/collector identities; continuation dispatch identity is host-local, not a native Claude turn ID |
| Completion proof | Same bounded completion predicate as `CL-SUB-C`; recovery starts only after it |
| Checkpoint / journal / native storage | Implemented Yohaku records and Claude-native session storage remain distinct; external recovery readback `NOT_RUN` |
| Handoff creation / delivery / injection | Durable handoff and same-process injection are implemented; external subscription observation `NOT_RUN` |
| Explicit receipt | Full correlated receipt contract is implemented; external subscription observation `NOT_RUN` |
| Fresh observation / continuation / assessor | Fresh token/read, one task action, assessor, and `RESUME_VERIFIED` path are implemented; external subscription observation `NOT_RUN` |
| Archive | `UNIMPLEMENTED` |
| Restart | `UNSUPPORTED` |
| Timeout / late / duplicate / ambiguous behavior | Uncertain submission is not retried; missing/stale receipt, observation, or assessment produces `RECOVERY_REQUIRED`; closed timeout owners cannot be reopened by late events |
| Known limitations | This is an implementation row, not an accepted external recovery profile; it must remain distinct until matching external live Evidence exists |

### `CL-LOCAL-FULL` — local maintainer full-identity recovery

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Claude Code CLI `2.1.280`; Linux print/stream-json/command Hooks |
| Provider / backend / model | Ollama client/server `0.34.1`; `spark-x2.5-4b-uncensored:latest`, 4.1B Q4_K_M, digest `e1646156c20479fe89690bad3f6a38062f4888cc33e03fcbb7a4944556be417f` |
| Implementation status | Bounded maintainer recovery adapter and fixture; not an operational launcher or public subscription profile |
| Evidence provenance / level | `C-CLI-OLLAMA-LOCAL-REPEAT-2026-09-29`; maintainer/local-live/synthetic |
| Verdict / maturity | One retained recovery reached `RESUME_VERIFIED`; repeat run failed before adapter entry; repeatability **FAIL**, overall **PARTIAL**; experimental |
| Transition Strategy | Manual In-place Compaction with same-process recovery |
| Lifecycle observation | Fixed command Hooks and collector lifecycle |
| Work taxonomy | One synthetic task and fixed recovery action; general tasks/tools/background work `NOT_RUN` |
| Active / pending / incorporated | Each fixed receipt/read/action handler is active through its matching native PostToolUse. The next gate requires the exact successful prior result or fresh token. This is fixture-specific propagation; semantic content quality is not assessed. |
| Work-plane gate | Fixture/runner sequencing, not a general Runtime gate |
| Trigger owner / request identity | Maintainer runner; host-local attachment/request/generation/collector identity |
| Native identity | Claude native `session_id`; no native request/generation/attachment identity |
| Host-local identity | Full identity set retained by the adapter and required in the receipt; still not native identity |
| Completion proof | Fixed C-CLI Hook sequence plus successful CLI completion and collector closure |
| Checkpoint / journal / native storage | Yohaku checkpoint/event records and native Claude/Ollama session data remain separate |
| Handoff creation / delivery / injection | Durable handoff injected in the same retained process in the successful run |
| Explicit receipt | Full correlated identity receipt in the successful run |
| Fresh current-state observation | Fresh recovery token/current-state read in the successful run |
| Continuation owner | Same maintainer runner; one permitted task action |
| Task assessor / resume verification | Fixture assessor reached `RESUME_VERIFIED` in one run; not a general task assessor |
| Archive / restart | `UNIMPLEMENTED` / `UNSUPPORTED` |
| Timeout / late / duplicate / ambiguous behavior | No retry after uncertain submission; stale/missing evidence requires recovery. Repeatability failure is retained rather than hidden. |
| Known limitations | Local backend only; one success does not transfer to subscription, other models, general tasks, restart, or repeatability |

### `CL-LOCAL-NONCE` — `host-nonce-v1`

| Property | Fixed value |
|---|---|
| Runtime / version / surface / OS | Claude Code CLI `2.1.280`; Linux print/stream-json/command Hooks |
| Provider / backend / model | Ollama `0.34.1`; `qwen3.5:9b` Q4_K_M, digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`; observed context `32768` in the accepted run |
| Implementation status | Bounded maintainer recovery adapter using a host-bound one-time nonce; no operational launcher |
| Evidence provenance / level | `C-CLI-NONCE-QWEN35-9B`; maintainer/local-live/synthetic |
| Verdict / maturity | One fixed workflow **PASS** through `RESUME_VERIFIED`; overall **PARTIAL**; repeatability and quality `NOT_ASSESSED`; experimental |
| Transition Strategy | Manual In-place Compaction with same-process recovery |
| Lifecycle observation | Native C-CLI command Hooks plus host collector and nonce-bound tool observation |
| Work taxonomy | One fixed synthetic recovery action; general work and parallel/multi-pending work `NOT_RUN` |
| Active / pending / incorporated | Each fixed receipt/read/action handler is active through its matching native PostToolUse; later gates require the exact prior result or token. The nonce proves correlated tool participation, not semantic incorporation of the handoff; that remains `NOT_ASSESSED`. |
| Work-plane gate | Fixed runner/adapter sequencing, not a general Runtime gate |
| Trigger owner / request identity | Maintainer runner; one host-local request/generation/collector owner |
| Native identity | Native Claude `session_id`; required native Pre/handler/Post observations around the receipt tool |
| Host-local identity | Host retains the full identity tuple; the model returns only one 128-bit, 22-character nonce. Host-local IDs are not reclassified as native IDs. |
| Completion proof | Fixed C-CLI completion predicate, then the nonce receipt's native Pre/handler/Post evidence |
| Checkpoint / journal / native storage | Yohaku checkpoint/event records separate from Claude/Ollama native data |
| Handoff creation / delivery / injection | Durable handoff and nonce challenge delivered in the same retained process |
| Explicit receipt | Single-use host-bound nonce plus required native tool lifecycle; no reissue or blind retry |
| Fresh current-state observation | Fresh recovery token/current-state observation after receipt |
| Continuation owner | Same maintainer runner; one allowed action |
| Task assessor / resume verification | Fixture assessor and Core reached `RESUME_VERIFIED`; prose/task quality remains `NOT_ASSESSED` |
| Archive / restart | `UNIMPLEMENTED` / `UNSUPPORTED` |
| Timeout / late / duplicate / ambiguous behavior | Uncertain nonce submission is not retried or reissued; stale/duplicate/mismatched nonce is refused or requires recovery; an earlier low-context ambiguous startup is excluded from the accepted comparison |
| Known limitations | One local model/backend/configuration and one run; no subscription transfer, no repeatability claim, no general semantic receipt, no parallel work, and no restart |

## Role to Runtime primitive matrix

The matrix names the actual primitive used by each fixed integration. Similar
rows do not imply equivalent event semantics. `C-OP` and `H-OP` are omitted from
transition cells because they intentionally activate no task transition.

| Yohaku role | Codex (`C-REF-M`; `C-DRR` where noted) | Hermes (`H-ADAPTER`) | Claude Code (`CL-SUB-C/R`, local recovery where noted) |
|---|---|---|---|
| Lifecycle observation | Owned App Server notifications/responses and Companion serialization | Embedded native host plus `PluginContext` instrumentation | Synchronous command Hooks and closed host collector |
| Work admission / deny | Declared Bash/patch/reference tool gate; `C-DRR` admits exactly two dynamic tools | Embedded host admits one fixed foreground tool | Fixed runner/collector work plane; no general C-CLI gate |
| Active-pending ledger | Host ledger for admitted foreground work and result incorporation | Handler active; pending until exact result text appears in same-turn outgoing request | Adapter/fixture ledger for the fixed workflow; general semantic incorporation `NOT_ASSESSED` |
| Boundary verification | Core verifies host/task evidence; `C-DRR` supplies a trusted Task Observer. `C-REF-A` does not retroactively manufacture the boundary lost to the native race. | Core verifies fixed adapter observations | Adapter accepts fixed collector/fixture observations; general semantic boundary Evidence is `NOT_RUN` for the completion profile |
| Checkpoint | Yohaku Core checkpoint in `SessionStore`; `C-REF-A` keeps the old checkpoint stale and its emergency delta separate | Yohaku Core checkpoint; not `SessionDB` | Yohaku Core checkpoint/event records; not Claude session storage |
| Transition trigger | `ManualCompactBackend` for `C-REF-M`; native Runtime trigger only for the separate `C-REF-A` emergency path | Embedded host invokes native manual compression | Operator/runner invokes one manual compact |
| Completion proof | `C-REF-M`: correlated compaction item + `PostCompact` + compact turn completion. `C-REF-A`: the separate bounded native completion sequence for Scenario G. | Host history mutation + independent read-only `SessionDB` projection/archived-row readback | Correlated Hook/handler/compact-origin startup evidence + CLI completion + collector closure |
| Handoff delivery | Companion injects one durable handoff into the owned recovery path | Embedded host delivers one durable handoff | Same-process recovery adapter injects one durable handoff; external subscription recovery `NOT_RUN` |
| Receipt | `YOH_ACK` correlated to handoff/generation | Adapter-defined assistant tool receipt with native and Yohaku correlations | Full-identity receipt or `host-nonce-v1`; neither is a built-in Claude receipt primitive |
| Fresh observation | Trusted Runtime/task/workspace read after delivery | Independent current native/task read | Fresh recovery token/current-state observation |
| Continuation | Owned App Server continuation; `C-DRR` permits only unfinished profile work | Same exclusive embedded host/session | One host-owned continuation dispatch; its ID is host-local, not a native CLI turn ID |
| Resume verification | Core plus bounded scenario assessor; `C-DRR` has the packaged mechanical assessor | Core plus fixed fixture/task assessor | Core plus fixed fixture assessor; external subscription recovery `NOT_RUN` |
| Archive | Yohaku selected visible-turn archive in the historical Reference profile; `C-DRR` does not claim it | `UNIMPLEMENTED`; `SessionDB` is native history only | `UNIMPLEMENTED`; Claude session storage is native history only |

Three identity and storage rules follow from this mapping:

1. Runtime-native databases and transcripts can supply profile-scoped evidence,
   but are not Yohaku checkpoints or archives.
2. Host-local attachment, request, generation, collector, and continuation IDs
   remain host-local even when they correlate native events.
3. A Runtime-specific event is not manufactured on another Runtime. Shared Core
   states are reached through different Completion Policies and evidence shapes.

## Evidence and support do not inherit

Evidence and Verdict never transfer automatically across Strategy, Runtime,
version, surface, backend/model, operating system, owner model, or Task Profile.
In particular:

- Codex manual-compaction `PASS` does not establish native automatic compaction
  `PASS`, fresh-context rollover, or session migration.
- Claude local Ollama recovery does not establish Anthropic subscription
  recovery.
- Hermes H-CLI-01 `PASS` does not establish all Hermes tools, sessions, versions,
  or operational profiles.
- `C-REF-M` manual Evidence does not establish the `C-REF-A` native-auto path,
  and Scenario G does not establish proactive manual success.
- Codex `0.155` reference Evidence does not establish Codex `0.158` transition
  support; `C-OP` and `C-DRR` state their own narrower claims.
- Runtime support does not establish Task Profile support, and
  `document-review-report-v1` does not establish arbitrary document, writing, or
  coding task quality.

Profiles may share the Core's state semantics, immutable value shapes, freshness
rules, lease discipline, ambiguity rules, and Evidence contract. They must not
share a Verdict or assume equivalent lifecycle events, identity strength,
completion proof, storage authority, work taxonomy, delivery, receipt,
continuation, restart behavior, or task assessor without matching implementation
and Evidence.

## Known mapping gaps

The mapping exposes current architectural gaps without proposing implementation
in this documentation stage:

- the adapter implementations do not conform to one neutral Runtime Adapter or
  host interface;
- persistence and restart remain Codex-shaped, while Hermes and Claude maintain
  bounded adapter-specific metadata;
- active/pending/incorporated work uses different profile-local ledgers and lacks
  a shared capability description;
- native and host-local identity types are not uniformly separated by the type
  system;
- task observer and assessor registration is packaged only for
  `document-review-report-v1` and fixtures;
- completion has a shared policy seam, but trigger, transport, delivery,
  continuation, and visible-turn extraction do not; and
- profile declarations, public support tables, and Evidence indexes still
  require manual reconciliation.

These are refactor candidates, not claims that new abstractions already exist.

## Document boundary and next records

This page intentionally does not enumerate every native event or Evidence item.
The future `evidence-model.md` should define Evidence authority, provenance,
freshness, retention, CoverageProfile composition, and Verdict derivation. The
Runtime-specific pages should retain exact event sequences, version/configuration
details, timeout values, field names, and per-profile operational diagnostics.
Installation, operation commands, and storage layout remain in their dedicated
documents.
