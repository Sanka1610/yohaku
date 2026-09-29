# Runtime Mapping

本書は、Yohakuのroleをfixed Runtime Support ProfileとTransition Strategyへ対応付ける。
Runtime / surface、lifecycle primitive、identity、work observation、completion proof、
delivery、current-state observation、continuation、Known Limitationsなど、profile固有の
事実を所有する。

[Architecture](architecture.md)はcomponent責務とtrust boundaryを所有する。
[Transition Strategies](transition-strategies.md)はContext Transition方式のtaxonomyと
共通semanticsを所有する。Runtime固有contractの詳細は[Codex](runtimes/codex.md)、
[Hermes](runtimes/hermes.md)、[Claude Code CLI](runtimes/claude-code-cli.md)の各pageに
残す。

文書に記載しただけではsupportは成立しない。実装の存在、retained Evidence、Verdict
は別の事実であり、各claimはnamed profileの範囲に限定する。Capability Verdictは
[Evidence Model](evidence-model.md)の定義を維持する。本書ではcellの状態を表すため、
次の語も使う。`UNIMPLEMENTED`と`UNKNOWN`は新しいVerdictではない。

- **UNIMPLEMENTED**: 記載したroleまたはpathの実装が存在しない
- **UNSUPPORTED**: fixed profileがそのpathを除外または拒否する
- **NOT_RUN**: pathの実装や仕様は存在し得るが、このprofileで必要な評価を実行して
  いない
- **UNKNOWN**: retained recordから値を確定できない

したがって、実装の存在と`NOT_RUN`は両立する。bounded `PASS`とoverall `PARTIAL`も
両立する。値のないcellは空欄にせず、該当する状態を記載する。

## Fixed profile一覧

Mapping keyは本書内だけで使う略称であり、Support Profile IDやEvidence Record IDではない。
Runtime / version / surface / OS、provider / backend / modelもprofile dimensionであり、IDと
して扱わない。同じRuntime versionを使っていても、Probe、adapter、operational lifecycle、
task supportを分ける。

| Mapping key | Support Profile ID | Evidence Record ID | このrowが示す範囲 | Implementation / Evidence / Verdict |
|---|---|---|---|---|
| `C-REF-M` | `codex-reference-0.155` | `PHASE14`配下のmanual record | historical proactive manual path、archive、Core persistence behavior | Reference integration実装済み。retained local / syntheticとbounded live Runtime Evidenceあり。historical Phase 14 overall **PARTIAL**。 |
| `C-REF-A` | `codex-reference-0.155` | `PHASE14` Scenario G | 同じSupport Profileのnative race recovery。proactive transition成功ではない | Bounded emergency implementationとEvidenceあり。Scenario G **PASS**、historical Phase 14 overall **PARTIAL**。 |
| `C-OP` | `codex-operational-0.158` | `S5-OP-CODEX-0158` | inferenceやtask transitionを含まないcurrent-version owned App Server lifecycle | Operational lifecycle実装・測定済み **PASS**。task transition **NOT_RUN**。experimental。 |
| `C-DRR` | `codex-document-review-report-v1`。Task Profile IDは`document-review-report-v1` | `DRR-V1-CODEX-0158-LIVE-01` | current versionで、一つのmanual compactと一つのreportを含むreal document-review workflow | Bounded implementation。lab / live-Runtime / nonfixture real-task Evidence。profile **PASS**、overall product coverage **PARTIAL**、quality `NOT_ASSESSED`。 |
| `H-PROBE` | `H-CLI-01`（internal Probe profile） | Separate public ID未割当。Stage 2 retained recordを参照 | connected adapter実装前のfixed native CLI workflowに対するcapability observation | Probe packageと測定workflowのみ。bounded workflow **PASS**、overall **PARTIAL**。adapterやoperational hostではない。 |
| `H-ADAPTER` | Product registryは`hermes-h-cli-01`。Retained profileは`H-CLI-01` | `H-CLI-01-STAGE4` | 一つのfixed toolと一つのmanual compressionを扱うembedded adapter path | Bounded adapter実装済み。live synthetic Evidenceあり。accepted bounded workflow **PASS**、overall **PARTIAL**。 |
| `H-OP` | `hermes-operational-h-cli-01` | `S5-OP-HERMES` | inferenceとtransition adapterを無効にしたowned native CLI / store lifecycle | Operational lifecycle実装・測定済み **PASS**。task / tool / transition path **NOT_RUN**。experimental。 |
| `CL-SUB-C` | Product registryは`claude-c-cli`。Retained profile labelは`C-CLI/2.1.280/Linux/print-stream-json/command-hooks` | `C-CLI-COMPLETION` | external Anthropic subscription CLIのmanual-compaction completionから`ROLLOVER_OBSERVED`まで | Bounded completion adapter実装済み。external live-Runtime synthetic Evidence。manual completion **PASS**、overall **PARTIAL**。 |
| `CL-SUB-R` | Separate IDは未割当。`claude-c-cli` surface上のrecovery capability row | Qualifying external recordなし | subscription surfaceのhandoff、receipt、continuation、resume contract | Recovery implementationは存在するが、external subscription recovery Evidenceは **NOT_RUN**。local OllamaのVerdictを継承しない。 |
| `CL-LOCAL-FULL` | `C-CLI-OLLAMA-LOCAL/2.1.280/0.34.1/spark-x2.5-4b-uncensored/e1646156c204` | `C-CLI-OLLAMA-LOCAL-REPEAT-2026-09-29` | local maintainer full-identity receipt / recovery比較 | Bounded maintainer adapter。local-live synthetic Evidence。`RESUME_VERIFIED`一回、pre-adapter failure一回。repeatability **FAIL**、overall **PARTIAL**。 |
| `CL-LOCAL-NONCE` | `claude-c-cli-local-nonce` | `C-CLI-NONCE-QWEN35-9B` | `host-nonce-v1`を使うlocal maintainer recovery | Bounded maintainer implementation。local-live synthetic Evidence。一つのworkflow **PASS**、overall **PARTIAL**。qualityとrepeatabilityは`NOT_ASSESSED`。 |

これらはRuntime family全体のaliasではない。`H-PROBE`、`H-ADAPTER`、`H-OP`は別々の
claimである。`CL-SUB-C`はrecoveryを含まず、local Ollama recoveryはAnthropic
subscription recoveryを成立させない。`C-DRR`がTask Profileを追加しても、`C-OP`
がgeneral task supportを持つことにはならない。

## Codex profiles

### `C-REF-M` / `C-REF-A` — historical Reference profile

二つのmapping rowは同じfrozen Runtime Support Profileを使うが、Transition Strategyと
Evidence claimは別である。共通するprofile factを一度だけ示し、その後にStrategy
固有contractを分ける。

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | Codex CLI `0.155.0-alpha.16.4`、owned App Server、WSL2 Ubuntu、host Python `3.14.4` |
| Provider / backend / model | retained profileではOpenAI provider、`gpt-5.6-luna`、reasoning low |
| Implementation status | Historical Runtime-specific Reference implementation。current Codex operational baselineではない。 |
| Evidence provenance / level | frozen Phase 14 CoverageProfile内のretained local / synthetic recordとbounded live-Runtime scenario |
| Verdict / maturity | Historical Phase 14 overall `PARTIAL`、experimental。個別scenarioはrecorded resultを維持する。 |
| Transition Strategy | `C-REF-M`はManual In-place Compaction。`C-REF-A`は別契約のbounded Native Automatic Compaction emergency recovery。experimental `new_context`は`UNSUPPORTED`。 |
| Lifecycle observation | 一つのowned threadと一つのoutstanding transition requestを前提とするordered App Server notification / response |
| Work taxonomy | 宣言したBash、`apply_patch`、fixed archive tool。general MCP、detached / background、external、parallel workはaccepted coverage外。 |
| Active / pending / incorporated | Activeはadmit済みforeground operationの実行中を表す。Pendingはresultが独立にterminalかつincorporatedと観測されるまで残る。incorporationにはtrusted host observationが必要で、tool successだけでは足りない。 |
| Work-plane gate | 宣言work planeに対するlocal barrierとallow / deny rule。Runtime-wide atomic freezeではない。 |
| Trigger owner | `C-REF-M`はYohaku / host、`C-REF-A`はCodex Runtime。 |
| Yohaku Core identity | `C-REF-M`は一つのYohaku `Request`、boundary / checkpoint / lease、Core generation、handoffを使う。`C-REF-A`はnative-auto originを記録し、proactive leaseを再構成しない。 |
| Native session / turn / generation / attachment identity | 利用可能なnative session / threadとactive-turn evidenceを観測する。App Server eventはnative Yohaku request / generation IDを提供しない。 |
| Host-local correlation identity | Attachment / correlation state、connection owner、ordered stream mapping。Core request / generationをnative IDへ変換しない。 |
| Completion proof | Strategy固有のcorrelated native evidence。RPC acknowledgementだけでは不十分。下表で分ける。 |
| Checkpoint / journal | POSIX `SessionStore`とCore record。`C-REF-M`はauthority前にcurrent checkpointをcommitする。`C-REF-A`はprior checkpointをstaleのまま保持し、emergency deltaを別recordにする。 |
| Runtime-native storage | Codex transcript / historyはRuntime-native dataであり、Yohaku checkpoint / archiveではない。 |
| Handoff creation / delivery / injection | Coreがdurable handoffを作る。Codex Companionがbounded recovery pathでinjectする。profileが定める場合はcompact-origin `SessionStart`を使う。 |
| Explicit receipt | accepted Reference pathでは`YOH_ACK:<handoff-id>:<generation>`をcorrelateする。 |
| Fresh current-state observation | transition後のtrusted observationとdeclared workspace read。old checkpointではfreshnessを満たせない。 |
| Continuation owner | 同じtaskとtransitionへcorrelateしたowned Companion / App Server continuation |
| Task assessor / resume verification | Bounded scenario / fixture assessorとCore resume gate。general Task Assessorではない。 |
| Archive / native history | Yohaku archiveはtrusted hostが選んだvisible turnを保存する。Codex native history全体を取り込まない。 |
| Restart | `C-REF-M`にはlimited ordinary manual reconciliationがある。`C-REF-A` restartは`UNSUPPORTED`。consumed leaseは復元しない。 |
| Timeout / late / duplicate / ambiguous behavior | dispatch不明、missing / conflicting completionは`AMBIGUOUS`としblind retryを止める。owner mappingが保たれていればlate matching manual completionをreconcileできる。duplicateはno-op。native-auto proof欠落はproactive成功ではなくrecoveryを要求する。 |
| Known Limitations | Hook failure pathは`FAIL_OPEN`。Runtime-wide atomic freezeとnative context generation identityはない。general MCP、active `apply_patch`、detached / parallel / external work、power loss、複数のrepeat / restart pathは未受入。 |

| Strategy固有field | `C-REF-M` | `C-REF-A` |
|---|---|---|
| Authorization and trigger | current verified boundaryとcommitted checkpointの後に、hostがmanual compact requestを一つ発行する。 | Runtimeがcurrent proactive checkpoint / lease sequenceより先にautomatic compactionを開始する。後からproactive authorityを推定しない。 |
| Durable source state | current verified checkpointと通常のjournal ordering。 | prior checkpointはstale historical dataのまま。bounded emergency observationは別のunverified deltaであり、replacement checkpointやarchiveではない。 |
| Completion and recovery proof | correlated compaction item、successful `PostCompact`、successful compact turn completionの後、通常のhandoff / receipt / fresh-state chainを通す。 | active turnに対するbounded correlated native completion、same-turn delivery / receipt、fresh current-state recovery。completion欠落は`AMBIGUOUS`。 |
| Continuation and restart | owned continuationでunfinished workを継続する。limited ordinary manual restart reconciliationはあるが、consumed authorityは復元しない。 | Same-turn bounded continuationのみ。native recovery restartは`UNSUPPORTED`。 |
| Evidence / Verdict | Historical manual scenarioと各original Verdictを維持する。本書ではnew aggregate manual Verdictを作らない。 | Historical Scenario G **PASS**。frozen scope内だけに適用し、Phase 14 overallは **PARTIAL** のまま。 |
| Accepted scope | historical manual reference scenarioの各recorded scope。 | Scenario Gのみ。attachmentあたりnative compaction一回、foreground Bash一つ、active turn一つ。general repeat / race / restart claimはない。 |

### `C-OP` — current operational lifecycle profile

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | Codex `0.158.0-alpha.2.1`、dedicated App Server over stdio、WSL2 / Linux host |
| Provider / backend / model | inference無効。loopback provider / model設定は意図的にtaskを実行できない。 |
| Implementation status | Runtime-specific operational launcher、Companion、storeを実装済み。Task Observer、inference、tool、compact trigger、continuationは有効化しない。 |
| Evidence provenance / level | `S5-OP-CODEX-0158`、native lifecycle、no inference |
| Verdict / maturity | Lifecycle **PASS**、task transition `NOT_RUN`、experimental、release undeclared。 |
| Transition Strategy | `NOT_RUN`。lifecycle-only profileではStrategyを有効化しない。 |
| Lifecycle observation | dedicated App Server connectionによるowned startup、fresh thread、status、shutdown |
| Work taxonomy; active / pending / incorporated | task workをadmitしない。このprofileのtask-work値はすべて`UNSUPPORTED`。 |
| Work-plane gate | task gateを主張するのではなく、lifecycle profileとしてtask executionを拒否する。 |
| Trigger owner / Yohaku Core identity | Lifecycle-only profileで無効。Capability evaluationは`NOT_RUN`。 |
| Native identity | lifecycle ownership用のfresh native thread / session identityを観測する。turn / generation / attachmentのtransition identityは`NOT_RUN`。 |
| Host-local correlation identity | Operational runとCompanion / store identity。native Runtime request / generationではない。 |
| Completion proof | `NOT_RUN`。lifecycle startup / shutdownはcompaction proofではない。 |
| Checkpoint / journal | Companion / store lifecycleは存在するが、task checkpointはcommitしない。 |
| Runtime-native storage | owned App Server配下のfresh Codex thread state。Yohaku checkpoint / archiveとは扱わない。 |
| Handoff / receipt / fresh observation / continuation | Lifecycle-only profileで無効。Capability evaluationは`NOT_RUN`。 |
| Task assessor / resume verification | Profileに接続しない。Task Profileなしのtask transitionは拒否し、Capability evaluationは`NOT_RUN`。 |
| Archive / native history | `NOT_RUN`。 |
| Restart | operational process restartでは新しいowned lifecycleを開始できる。transition restart semanticsは`NOT_RUN`。 |
| Timeout / late / duplicate / ambiguous behavior | launcher lifecycle errorはoperational failure。transition ambiguity policyは実行していない。 |
| Known Limitations | current-version lifecycle compatibilityだけを示す。`C-REF-M` / `C-REF-A`のtransition / archive Evidenceを継承しない。 |

### `C-DRR` — `document-review-report-v1`

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | Codex `0.158.0-alpha.2.1`、profile所有dynamic toolを持つdedicated App Server、WSL2 / Linux host |
| Provider / backend / model | retained run configurationで固定したが、public Evidenceは再利用可能なprovider / model claimを成立させないため`UNKNOWN`。 |
| Implementation status | Bounded Task Profileとtask-enabled runnerを実装済み。general task frameworkではない。 |
| Evidence provenance / level | `DRR-V1-CODEX-0158-LIVE-01`、lab / live-Runtime / nonfixture real task |
| Verdict / maturity | fixed workflow / profile **PASS**、overall product coverage **PARTIAL**、experimental。文章・事実品質は`NOT_ASSESSED`。 |
| Transition Strategy | 一つのfresh session内でManual In-place Compactionを一回実行する。 |
| Lifecycle observation | owned App Server lifecycle、正確なdynamic-tool event、manual compact lifecycle |
| Work taxonomy | `read_review_inputs`と`publish_review_report`だけをadmitする。shell、file change、MCP、undeclared、stale、duplicate、追加workは拒否する。 |
| Active / pending / incorporated | Activeはadmit済みprofile toolの実行中。Pendingはsuccessful resultが必要なoutgoing / current task stateへ反映されたと独立観測するまで残る。Incorporatedはexact read / publish resultのprofile observationであり、model self-reportではない。 |
| Work-plane gate | profile所有のtwo-tool gate、transition barrier、create-only output contract |
| Trigger owner | Trusted Observerがverified boundaryを成立させた後、Yohaku task runnerがtriggerする。 |
| Yohaku Core identity | Single manual compact用のboundary、checkpoint、lease、request、Core generation、handoff |
| Native session / turn / generation / attachment identity | fresh Codex threadとRuntime turn observation。native Yohaku generation identityはない。 |
| Host-local correlation identity | Runner、attachment、ordered event sequence、task ledger。Native tool-call / resultとCore identityを対応付ける。 |
| Completion proof | Codex manualの三要素。compaction item、`PostCompact`、successful compact turn completion。 |
| Checkpoint / journal | request前にCore checkpointとprofile task stateをcommitする。profile recordはexact input / output identityを保持する。 |
| Runtime-native storage | native Codex context / historyとtask checkpoint / Yohaku storeを分ける。 |
| Handoff creation / delivery / injection | owned Codex recovery pathがdurable Core handoffをdeliveryする。 |
| Explicit receipt | profile contractに従うexact correlated handoff / generation receipt |
| Fresh current-state observation | continuationがdeclared inputを再読し、publish前にoutput不在を確認する。assessorが作成後のoutput hashをreadbackする。stale hashやworkspace変更は拒否する。 |
| Continuation owner | 同じowned task runner。unfinished profile workだけを継続できる。 |
| Task assessor / resume verification | fresh read一回、create-only publish一回、disallowed / pending / duplicate workなしをprofile assessorが検証し、その後Coreが`RESUME_VERIFIED`へ遷移できる。 |
| Archive / native history | このTask Profileでは`UNSUPPORTED`。general Codex archive coverageを主張しない。 |
| Restart | accepted workflowでは`UNSUPPORTED`。 |
| Timeout / late / duplicate / ambiguous behavior | uncertain side effect / completionは`AMBIGUOUS`。stale / duplicate / undeclared workは`REFUSED`。blind retryを行わない。 |
| Known Limitations | 一つのinput contract、fresh session一つ、compact一回、output一つ、exact tool plane一つに限定する。arbitrary document work、repeated transition、restart、quality assessmentはscope外。 |

## Hermes profiles

三つのHermes rowはすべて、Hermes `0.21.0`、source
`c5594ec4b34097cafbe24deb6dfd9ac4b21d411d`を使うが、成立するclaimは異なる。

### `H-PROBE` — H-CLI-01 Stage 2 Probe

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | Hermes `0.21.0`、instrumented native CLI host、Ubuntu-Hermes on WSL2、Python `3.11.16` |
| Provider / backend / model | `openai-codex`、`gpt-5.6-luna`、reasoning low |
| Implementation status | Probe harnessとfixed workflowのみ。connected product adapterとoperational launcherはこのrowから成立しない。 |
| Evidence provenance / level | H-CLI-01 Stage 2 lab / live-Runtime / synthetic Probe。八request、一manual compression、bounded workflow。 |
| Verdict / maturity | fixed Probe workflow **PASS**、overall **PARTIAL**、experimental。 |
| Transition Strategy | Manual In-place Compaction / Hermes manual compression |
| Lifecycle observation | Probe instrumentationがfixed CLI request / compression pathを観測する。 |
| Work taxonomy | fixed foreground tool workflow一つ。general toolとbackground workは`NOT_RUN`。 |
| Active / pending / incorporated | Activeはadmit済みfixture handlerの実行区間。`post_tool`後、exact textが同一turnの次のoutgoing requestへ`function_call_output`として入るまでpendingを維持する。bounded propagationのproofであり、semantic understandingやreusable product ledgerではない。 |
| Work-plane gate | Probe sequencing。product gateはこのStageでは`UNIMPLEMENTED`。 |
| Trigger owner / Yohaku Core identity | Probe hostがmanual compressionを一回triggerする。Product Core identityはなく、Probe-local correlationだけを使う。 |
| Native identity | instrumentationが利用可能なHermes session / turn / request / tool identityを観測する。 |
| Host-local correlation identity | Probe run / correlation ID。native Hermes IDやProduct Core identityの代わりにはならない。 |
| Completion proof | host historyが変化し、独立read-only `SessionDB` connectionでactive projectionとinactive rowの一致を確認した。Probe instrumentation / Evidenceであり、この時点ではproduct Completion Policyやadapter実装ではない。 |
| Checkpoint / journal | fixture / Probe checkpoint behaviorのみ。product persistenceは成立していない。 |
| Runtime-native storage | Probe内でnative history / storeを観測した。Yohaku checkpoint / archiveではない。 |
| Handoff / receipt | handoff behaviorを実行したが、explicit receipt coverageは部分的なままである。adapter supportへ昇格させない。 |
| Fresh observation / continuation / assessor | bounded Probeのfresh read / nonduplication check。general Task Assessorはない。 |
| Archive / restart | `UNIMPLEMENTED` / `NOT_RUN`。 |
| Timeout / late / duplicate / ambiguous behavior | Runtime timeout、late completion、replay、restart pathは`NOT_RUN`。 |
| Known Limitations | Capability Probeのみ。installed adapter、operational lifecycle、general Hermes support、task supportとして表示しない。 |

### `H-ADAPTER` — connected H-CLI-01 adapter

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | Hermes `0.21.0`、embedded native in-process CLI host、Ubuntu-Hermes / WSL2 |
| Provider / backend / model | retained Stage 4 profileでは`openai-codex`、`gpt-5.6-luna`、reasoning low |
| Implementation status | session一つ、foreground tool一つ、manual compression一回を扱うRuntime-specific bounded adapter |
| Evidence provenance / level | `H-CLI-01-STAGE4`、lab / live-Runtime / synthetic adapter run、九request（`4 / 1 / 4`） |
| Verdict / maturity | accepted bounded workflow **PASS**、overall **PARTIAL**、experimental。 |
| Transition Strategy | native Hermes compressionを使うManual In-place Compaction |
| Lifecycle observation | embedded `PluginContext`とhost instrumentationがnative session、turn、API request、tool-call identityを保持する。 |
| Work taxonomy | fixed sequential foreground tool一つ。general tool、background / detached work、parallelism、external writerはcoverage外。 |
| Active / pending / incorporated | admitted handler開始時にactiveとなる。tool completion後も、exact result textがoutgoing same-turn requestへ入るまでpendingを維持する。bounded propagationのproofであり、semantic understandingではない。 |
| Work-plane gate | embedded hostがfixed toolをadmitし、active / pending work中はtransitionをblockする。 |
| Trigger owner | Core authorization後、embedded Yohaku hostがmanual compressionを一回発行する。 |
| Yohaku Core identity | Boundary、checkpoint、lease、compression request、Core generation、handoffを使う。 |
| Native identity | Hermes session、turn、API request、tool call / result identity |
| Host-local correlation identity | Adapter event / readback sequenceとowner mapping。Core request / generationとnative identityを置き換えず、対応付ける。 |
| Completion proof | host history mutationと、independent read-only `SessionDB`によるexact projection / archived-row readback。engine return / countだけでは不十分。 |
| Checkpoint / journal | Core checkpointとhandoff recordを保持する。Hermes adapter event metadataはbounded diagnostic stateであり、general restart journalではない。 |
| Runtime-native storage | Hermes `SessionDB`とnative history / compression state。Completion readback sourceであり、Yohaku `SessionStore`内のcheckpoint / archiveではない。 |
| Handoff creation / delivery / injection | Coreがdurable handoffを作り、embedded hostがfixed continuation pathでdeliveryする。 |
| Explicit receipt | 必須Runtime / Yohaku correlationを含むadapter-defined assistant tool receipt。Hermes built-in receipt primitiveではない。 |
| Fresh current-state observation | delivery後、assessment前のindependent current native / task read |
| Continuation owner | 同じexclusive embedded hostとfresh dedicated session |
| Task assessor / resume verification | fixed fixture / task assessorとCore gateで`RESUME_VERIFIED`へ到達する。general Hermes Task Assessorではない。 |
| Archive / native history | Yohaku archiveは`UNIMPLEMENTED`。inactive / native DB rowはRuntime-native historyのまま。 |
| Restart | accepted profileでは`UNSUPPORTED`。 |
| Timeout / late / duplicate / ambiguous behavior | missing / uncertain dispatch / proofは`AMBIGUOUS`。late、repeat、race pathは`NOT_RUN`。blind retryしない。 |
| Known Limitations | fixed tool一つ、compression一回、exclusive in-process owner、embedded instrumentationに限定。restart、general tool plane、repeated / racing transition、general archiveはない。 |

### `H-OP` — operational lifecycle profile

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | Hermes `0.21.0`、native in-process CLI construction / store、Ubuntu-Hermes / WSL2 |
| Provider / backend / model | inference無効。provider / model requestは発行しない。 |
| Implementation status | native CLI / store lifecycle用Runtime-specific operational launcher。lazy inference agentとH-CLI-01 transition adapterは意図的に無効。 |
| Evidence provenance / level | `S5-OP-HERMES`、native lifecycle、no inference |
| Verdict / maturity | Lifecycle **PASS**、task / tool / transition `NOT_RUN`、experimental。 |
| Transition Strategy | `NOT_RUN`。 |
| Lifecycle observation | native CLI construction、session / store ownership、status、shutdown |
| Work taxonomy; active / pending / incorporated | task workをadmitしない。lifecycle-only profileでは`UNSUPPORTED`。 |
| Work-plane gate | Stage 4 gateで観測するのではなく、profileがtask operationを拒否する。 |
| Trigger / request / completion | このlifecycle-only profileで無効。Capability evaluationは`NOT_RUN`。 |
| Native identity | native lifecycle / session / store identity。task turn / compression identityは実行していない。 |
| Host-local correlation identity | Operational run identity。native Hermes request / turnではない。 |
| Checkpoint / journal / native storage | operational store lifecycleのみ。transition checkpointはない。native storeはYohaku persistenceではない。 |
| Handoff / receipt / fresh observation / continuation / assessor | Profileに接続しない。Capability evaluationは`NOT_RUN`。 |
| Archive | Profileに接続しない。Capability evaluationは`NOT_RUN`。 |
| Restart | transition restart semanticsは`NOT_RUN`。 |
| Timeout / late / duplicate / ambiguous behavior | operational lifecycle failureはlauncher error。transition ambiguityは実行していない。 |
| Known Limitations | lifecycle ownershipだけを示す。`H-PROBE` / `H-ADAPTER`のtask / transition Evidenceを継承しない。 |

## Claude Code profiles

すべてのC-CLI rowは、Claude Code CLI `2.1.280`、Linux、`claude -p`、stream-json、
synchronous command Hooksを固定する。Completion / recovery contractで`PreCompact`、
`PostCompact`、`SessionStart`を使うのは、fixed profileが実際に観測した場合だけで
ある。CodexやHermes向けにこれらのevent名を合成しない。

### `CL-SUB-C` — subscription external completion profile

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | Claude Code CLI `2.1.280`、Linux、print mode、stream-json、synchronous command Hooks |
| Provider / backend / model | Anthropic subscription surface。public retained recordからexact provider / backend / modelを確定できないため`UNKNOWN`。 |
| Implementation status | `ROLLOVER_OBSERVED`までのbounded external completion collector / adapterを実装済み。operational launcherはない。 |
| Evidence provenance / level | external live-Runtime synthetic record `C-CLI-COMPLETION`、sanitized event record / hash |
| Verdict / maturity | Manual completion **PASS**、overall C-CLI **PARTIAL**、experimental。 |
| Transition Strategy | Manual In-place Compaction。fresh process / session一つ、compact一回。 |
| Lifecycle observation | fixed collector contract内で、synchronous command Hooksからnative `SessionStart`、`PreCompact`、`PostCompact`、compact-origin `SessionStart`を観測する。 |
| Work taxonomy | fixed synthetic workflow。general task work、background work、arbitrary toolは`NOT_RUN`。 |
| Active / pending / incorporated | Activeはadmit済みPre / PostToolUse間のfixed foreground fixture operation。collectorとfixture effectでterminal executionを確認できる。general pending-result incorporationは`NOT_RUN`、semantic incorporationは`NOT_ASSESSED`であり、Hook / CLI successから推定しない。 |
| Work-plane gate | fixed collector / runner sequencing。general C-CLI work gateはない。 |
| Trigger owner | external operator / runnerがmanual compactを一回発行する。 |
| Yohaku Core identity | Boundary、checkpoint、lease、compact request、Core generation。Native Claude fieldではない。 |
| Native identity | native Claude `session_id`。native Yohaku request、generation、attachment IDはない。 |
| Host-local correlation identity | Attachmentとcollector sequence。Core request / generationとnative sessionをfixed owner内で対応付ける。 |
| Completion proof | Correlated `PreCompact(manual)`、`PostCompact(manual)`、`SessionStart(compact)`、transport成功、collector closure。CLI result envelopeやHook一つだけでは不十分。 |
| Checkpoint / journal | committed Yohaku checkpoint / leaseとC-CLI event metadata。external recordはprivate checkpoint / lease byteすべてを独立readbackしていない。 |
| Runtime-native storage | fresh Claude session storage。Yohaku checkpoint / archiveではない。 |
| Handoff / receipt / fresh observation / continuation | external subscription recoveryでは`NOT_RUN`。completion Verdictのendpointは`ROLLOVER_OBSERVED`。 |
| Task assessor / resume verification | `NOT_RUN`。 |
| Archive | `UNIMPLEMENTED`。 |
| Restart | fixed adapter contractでは`UNSUPPORTED`。 |
| Timeout / late / duplicate / ambiguous behavior | timeout時にownerを永久closeする。late evidenceでは再開できない。二回目のcompactは拒否し、uncertaintyは`AMBIGUOUS`。 |
| Known Limitations | compact一回、fixed Hooks、synthetic taskに限定。external recovery acceptance、launcher、general work gate、general task supportはない。 |

### `CL-SUB-R` — subscription recovery capability row

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | `CL-SUB-C`と同じfixed `2.1.280` Linux print / stream-json / command-Hooks surface |
| Provider / backend / model | Anthropic subscription surface。exact model / backendは`UNKNOWN`。 |
| Implementation status | same-process handoff、receipt、fresh observation、one continuation、assessor、Core resume verificationのrecovery adapter contractを実装済み。 |
| Evidence provenance / level | local synthetic recovery testとfake-CLI / real-Hook harnessあり。qualifying external subscription recovery Evidenceは`NOT_RUN`。 |
| Verdict / maturity | Recovery Verdictは`NOT_RUN`。local Ollama Verdictを継承しない。 |
| Transition Strategy | fixed external profileを実行した場合のManual In-place Compaction＋same-process recovery |
| Lifecycle observation / work taxonomy / gate | bounded collectorとfixed recovery work planeを実装済み。external subscription executionは`NOT_RUN`。 |
| Active / pending / incorporated | 実装済みrecovery adapterでは、foreground receipt / read / action handler一つが、matching successful native PostToolUse resultまでactiveとなる。後続gateはexact prior result / tokenを要求する。fixture-bounded incorporationであり、general semantic understandingではない。external subscription executionは`NOT_RUN`。 |
| Trigger / identities | Native `session_id`、Core request / generation、host-local attachment / collectorを別に保持する。Continuation dispatch identityはhost-localであり、native Claude turn IDではない。 |
| Completion proof | `CL-SUB-C`と同じbounded completion predicate。完了後にだけrecoveryを開始する。 |
| Checkpoint / journal / native storage | 実装済みYohaku recordとClaude-native session storageを分ける。external recovery readbackは`NOT_RUN`。 |
| Handoff creation / delivery / injection | durable handoffとsame-process injectionを実装済み。external subscription observationは`NOT_RUN`。 |
| Explicit receipt | full correlated receipt contractを実装済み。external subscription observationは`NOT_RUN`。 |
| Fresh observation / continuation / assessor | fresh token / read、task action一つ、assessor、`RESUME_VERIFIED` pathを実装済み。external subscription observationは`NOT_RUN`。 |
| Archive | `UNIMPLEMENTED`。 |
| Restart | `UNSUPPORTED`。 |
| Timeout / late / duplicate / ambiguous behavior | uncertain submissionはretryしない。missing / stale receipt、observation、assessmentは`RECOVERY_REQUIRED`。timeoutでcloseしたownerをlate eventで再開しない。 |
| Known Limitations | implementation rowであり、accepted external recovery profileではない。matching external live Evidenceを得るまで分けて扱う。 |

### `CL-LOCAL-FULL` — local maintainer full-identity recovery

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | Claude Code CLI `2.1.280`、Linux print / stream-json / command Hooks |
| Provider / backend / model | Ollama client / server `0.34.1`、`spark-x2.5-4b-uncensored:latest`、4.1B Q4_K_M、digest `e1646156c20479fe89690bad3f6a38062f4888cc33e03fcbb7a4944556be417f` |
| Implementation status | bounded maintainer recovery adapter / fixture。operational launcherやpublic subscription profileではない。 |
| Evidence provenance / level | `C-CLI-OLLAMA-LOCAL-REPEAT-2026-09-29`、maintainer / local-live / synthetic |
| Verdict / maturity | retained recovery一回が`RESUME_VERIFIED`。repeat runはadapter entry前に失敗。repeatability **FAIL**、overall **PARTIAL**、experimental。 |
| Transition Strategy | same-process recoveryを伴うManual In-place Compaction |
| Lifecycle observation | fixed command Hooksとcollector lifecycle |
| Work taxonomy | synthetic task一つとfixed recovery action。general task / tool / background workは`NOT_RUN`。 |
| Active / pending / incorporated | fixed receipt / read / action handlerはmatching native PostToolUseまでactive。次のgateはexact successful prior resultまたはfresh tokenを要求する。fixture固有のpropagationであり、semantic content qualityは未評価。 |
| Work-plane gate | fixture / runner sequencing。general Runtime gateではない。 |
| Trigger owner / Yohaku Core identity | Maintainer runnerがCore request / generation / handoffを所有する。 |
| Native identity | Claude native `session_id`。native request / generation / attachment identityはない。 |
| Host-local correlation identity | Attachment / collector / continuation dispatchを保持し、Core identityとnative sessionへ対応付ける。Full-identity receiptは三分類のfieldを列挙するがauthorityを統合しない。 |
| Completion proof | Fixed C-CLI三Hook、transport成功、collector closure。CLI result envelope単独はproofではない |
| Checkpoint / journal / native storage | Yohaku checkpoint / event recordとnative Claude / Ollama session dataを分ける。 |
| Handoff creation / delivery / injection | successful runでは、同じretained processへdurable handoffをinjectした。 |
| Explicit receipt | successful runのfull correlated identity receipt |
| Fresh current-state observation | successful runのfresh recovery token / current-state read |
| Continuation owner | 同じmaintainer runner。permitted task action一つ。 |
| Task assessor / resume verification | 一runでfixture assessorが`RESUME_VERIFIED`へ到達。general Task Assessorではない。 |
| Archive / restart | `UNIMPLEMENTED` / `UNSUPPORTED`。 |
| Timeout / late / duplicate / ambiguous behavior | uncertain submission後はretryしない。stale / missing evidenceはrecoveryを要求する。repeatability failureも削除せず保持する。 |
| Known Limitations | local backendと一成功に限定。subscription、別model、general task、restart、repeatabilityへ転用しない。 |

### `CL-LOCAL-NONCE` — `host-nonce-v1`

| 項目 | 固定値 |
|---|---|
| Runtime / version / surface / OS | Claude Code CLI `2.1.280`、Linux print / stream-json / command Hooks |
| Provider / backend / model | Ollama `0.34.1`、`qwen3.5:9b` Q4_K_M、digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`。accepted runのobserved contextは`32768`。 |
| Implementation status | host-bound one-time nonceを使うbounded maintainer recovery adapter。operational launcherはない。 |
| Evidence provenance / level | `C-CLI-NONCE-QWEN35-9B`、maintainer / local-live / synthetic |
| Verdict / maturity | 一つのfixed workflowが`RESUME_VERIFIED`まで **PASS**。overall **PARTIAL**。repeatabilityとqualityは`NOT_ASSESSED`。experimental。 |
| Transition Strategy | same-process recoveryを伴うManual In-place Compaction |
| Lifecycle observation | native C-CLI command Hooks、host collector、nonce-bound tool observation |
| Work taxonomy | fixed synthetic recovery action一つ。general work、parallel / multi-pending workは`NOT_RUN`。 |
| Active / pending / incorporated | fixed receipt / read / action handlerはmatching native PostToolUseまでactive。後続gateはexact prior result / tokenを要求する。nonceはcorrelated tool participationを証明するが、handoffのsemantic incorporationは`NOT_ASSESSED`。 |
| Work-plane gate | fixed runner / adapter sequencing。general Runtime gateではない。 |
| Trigger owner / Yohaku Core identity | Maintainer runner、一つのCore request / generation / handoff |
| Native identity | native Claude `session_id`。receipt tool前後のnative Pre / handler / Post observationを要求する。 |
| Host-local correlation identity | Hostがattachment / collector / continuationとfull identity tupleの対応を保持し、modelは128-bit・22文字のnonce一つだけを返す。Host-local IDをnative IDへ読み替えない。 |
| Completion proof | fixed C-CLI completion predicateの後、nonce receiptのnative Pre / handler / Post evidenceを検証する。 |
| Checkpoint / journal / native storage | Yohaku checkpoint / event recordとClaude / Ollama native dataを分ける。 |
| Handoff creation / delivery / injection | durable handoffとnonce challengeを同じretained processへdeliveryする。 |
| Explicit receipt | single-use host-bound nonceと必須native tool lifecycle。reissueやblind retryはない。 |
| Fresh current-state observation | receipt後のfresh recovery token / current-state observation |
| Continuation owner | 同じmaintainer runner。allowed action一つ。 |
| Task assessor / resume verification | fixture assessorとCoreが`RESUME_VERIFIED`へ到達。文章・task品質は`NOT_ASSESSED`。 |
| Archive / restart | `UNIMPLEMENTED` / `UNSUPPORTED`。 |
| Timeout / late / duplicate / ambiguous behavior | uncertain nonce submissionをretry / reissueしない。stale / duplicate / mismatched nonceは拒否またはrecovery要求。以前のlow-context ambiguous startupはaccepted comparisonから除外した。 |
| Known Limitations | local model / backend / configuration一つとrun一回に限定。subscription転用、repeatability claim、general semantic receipt、parallel work、restartはない。 |

## RoleからRuntime primitiveへの対応

次の表は、fixed integrationごとに実際に使用するprimitiveを示す。似たrowであっても
event semanticsが同じとは限らない。`C-OP`と`H-OP`はtask transitionを有効化しない
ため、transition用cellから除外する。

| Yohaku role | Codex（`C-REF-M`、必要箇所は`C-DRR`） | Hermes（`H-ADAPTER`） | Claude Code（`CL-SUB-C/R`、必要箇所はlocal recovery） |
|---|---|---|---|
| Lifecycle observation | owned App Server notification / responseとCompanion serialization | embedded native hostと`PluginContext` instrumentation | synchronous command Hooksとclosed host collector |
| Work admission / deny | declared Bash / patch / Reference tool gate。`C-DRR`はdynamic tool二つだけをadmitする。 | embedded hostがfixed foreground tool一つをadmitする。 | fixed runner / collector work plane。general C-CLI gateはない。 |
| Active-pending ledger | admitted foreground workとresult incorporationのhost ledger | handler active。exact result textがsame-turn outgoing requestへ入るまでpending。 | fixed workflow用adapter / fixture ledger。general semantic incorporationは`NOT_ASSESSED`。 |
| Boundary verification | Coreがhost / task evidenceを検証する。`C-DRR`はTrusted Observerを持つ。`C-REF-A`はnative raceで失われたboundaryを後付けしない。 | Coreがfixed adapter observationを検証する。 | adapterがfixed collector / fixture observationを受理する。completion profileのgeneral semantic boundary Evidenceは`NOT_RUN`。 |
| Checkpoint | `SessionStore`内のYohaku Core checkpoint。`C-REF-A`ではold checkpointをstale、emergency deltaを別recordにする。 | Yohaku Core checkpoint。`SessionDB`ではない。 | Yohaku Core checkpoint / event record。Claude session storageではない。 |
| Transition trigger | `C-REF-M`は`ManualCompactBackend`。別契約の`C-REF-A`だけがnative Runtime trigger。 | embedded hostがnative manual compressionを発行する。 | operator / runnerがmanual compactを一回発行する。 |
| Completion proof | `C-REF-M`: correlated compaction item＋`PostCompact`＋compact turn completion。`C-REF-A`: correlated compaction item＋`PostCompact`。Active turn completionは後段のresume verificationで使う。 | host history mutation＋independent read-only `SessionDB` projection / archived-row readback | `PreCompact(manual)`＋`PostCompact(manual)`＋`SessionStart(compact)`＋closed / drained collector。CLI result envelope単独はproofに含めない。 |
| Handoff delivery | Companionがdurable handoffをowned recovery pathへinjectする。 | embedded hostがdurable handoff一つをdeliveryする。 | same-process recovery adapterがdurable handoff一つをinjectする。external subscription recoveryは`NOT_RUN`。 |
| Receipt | handoff / generationにcorrelateした`YOH_ACK` | native / Yohaku correlationを含むadapter-defined assistant tool receipt | full-identity receiptまたは`host-nonce-v1`。どちらもClaude built-in receipt primitiveではない。 |
| Fresh observation | delivery後のtrusted Runtime / task / workspace read | independent current native / task read | fresh recovery token / current-state observation |
| Continuation | owned App Server continuation。`C-DRR`ではunfinished profile workだけを許可する。 | 同じexclusive embedded host / session | host-owned continuation dispatch。IDはhost-localであり、native CLI turn IDではない。 |
| Resume verification | Core＋bounded scenario assessor。`C-DRR`はpackaged mechanical assessorを持つ。 | Core＋fixed fixture / task assessor | Core＋fixed fixture assessor。external subscription recoveryは`NOT_RUN`。 |
| Archive | historical Reference profileのselected visible-turn archive。`C-DRR`はcoverageを主張しない。 | `UNIMPLEMENTED`。`SessionDB`はnative historyのみ。 | `UNIMPLEMENTED`。Claude session storageはnative historyのみ。 |

### Identityの三分類

Native identity、Yohaku Core identity、host-local correlation identityは、三Runtimeで同じ
authorityを持たない。次の表は型の共通化ではなく、意味の違いを比較するための対応である。

| 種類 | Codex | Hermes | Claude Code CLI |
|---|---|---|---|
| Runtime-native identity | Thread / session、turn、item、Hook run、dynamic tool call | Session、turn、API request、tool call、`SessionDB` row | Native `session_id`、native tool ID |
| Yohaku Core identity | Boundary、checkpoint、lease、request、Core generation、handoff、continuation permit | 同じCore value shape。Compression requestはCore requestでありHermes native requestではない | 同じCore value shape。Compact requestとgenerationはClaude native fieldではない |
| Host-local correlation identity | Companion / connection owner、attachment / run、ordered event sequence、task ledger | Probe / adapter run、adapter / readback sequence、embedded owner | Attachment、collector sequence、recovery request、host continuation turn、runner / owner |

Native IDが同名のCore fieldへ保存される場合も、RuntimeがそのCore authorityを発行したことには
ならない。Host-local IDはnative observationとCore identityをfixed owner内でcorrelateするために
使い、欠落したnative generationやturn identityを補ったことにはしない。

### Active / pending / incorporatedの差

三語は共通のbarrier guaranteeを表さない。各profileが観測できる範囲と、次のgateへ進むための
条件を記述する語である。

| Runtime / profile | Active | Pending | Incorporated | Barrier上の限界 |
|---|---|---|---|---|
| Codex Reference | Matching `PreToolUse`後のadmitted foreground operation | `PostToolUse`後もterminal effectとworkspace / revision反映を確認するまで残る | Trusted hostがterminal state、partial effect、workspace / revisionを確認した状態 | Registered Hook pathだけ。Hook failureは`FAIL_OPEN`で、Runtime-wide atomic freezeではない |
| Codex `C-DRR` | Profile-owned dynamic toolの実行中 | Exact resultとtask stateへの反映が確認されるまで残る | Task-specific observerがread / publish resultとworkspace stateを確認した状態 | 二つのprofile toolだけ。General task / tool barrierではない |
| Hermes H-CLI-01 | Matching native `pre_tool_call`後のfixture handler実行中 | `post_tool_call`後、exact resultがsame-turn outgoing requestへ入るまで残る | Send gateがmatching call / result hashを確認した状態 | Single sequential fixtureだけ。Semantic understandingやbackground workを保証しない |
| Claude recovery | Admitted `PreToolUse`からmatching handler resultとsuccessful `PostToolUse`まで | 次のgateが要求するprior resultまたはfresh tokenが未確認の状態 | Receipt後のread、token-bound action等、fixed fixtureの機械的sequencingを満たした状態 | General semantic incorporationは`NOT_ASSESSED`。General C-CLI gateはない |

### Completion proofとrecovery段階

共有するのは、Runtime固有proofが揃うまでcompletionを認めないというsafety semanticsだけで
ある。Proofのeventやstorage shapeは共有しない。

| Runtime path | Completion proof | Delivery | Receipt | Fresh observation | Continuation / ResumeProof |
|---|---|---|---|---|---|
| Codex manual | Bound compact turn / requestのcompaction item、`PostCompact`、compact turn completion | Durable handoffをowned recovery pathへinject | `YOH_ACK:<handoff-id>:<generation>` | Trusted Runtime / task / workspace read | New owned continuation turn。Task-specific proof後に`RESUME_VERIFIED` |
| Codex native-auto | Correlated compaction itemと`PostCompact`。Active turn completionはreceipt / ResumeProof側で使う | Same active turnへhandoffをinject | Manual pathと同じmarkerをnative-auto bindingへcorrelate | Stale checkpointとunverified emergency deltaを区別してcurrent stateを再読 | Same-turn continuation。New `turn/start`を送らない |
| Hermes adapter | Host history mutationとindependent `SessionDB` projection / archived-row readback | Same owned sessionのactual outgoing promptを確認 | Adapter-defined toolがhandoff / checkpoint / request / session / generationを返し、result incorporationを確認 | Receipt後のindependent current native / task read | Same exclusive embedded host。Fixture assessorのproof後に`RESUME_VERIFIED` |
| Claude subscription completion | 三Hookとcollector closure | Profile外 | Profile外 | Profile外 | `ROLLOVER_OBSERVED`で停止 |
| Claude local recovery | 同じ三Hookとcollector closure | Same retained processへhandoffを一回submit / flush | Full-identity tool receiptまたは別profileの`host-nonce-v1` | Receipt後のfresh token / current-state readとpre-action再確認 | Host-local continuation一回。Fixture assessorのproof後に`RESUME_VERIFIED` |

Delivery、receipt、fresh observation、continuation terminal、ResumeProofは順に必要な別contractで
ある。後段の成功から前段を推定せず、receipt単独からsemantic incorporationやresume correctnessを
推定しない。

### Storage、archive、Task Profile

| 種類 | Codex | Hermes | Claude Code CLI |
|---|---|---|---|
| Yohaku checkpoint | `SessionStore`のverified pre-dispatch state | `SessionStore`のverified pre-compression state | Dedicated storeのverified pre-compact state |
| Journal | Codex schema-1 hash-chain。Historical manual restartは限定的に対応 | Core snapshotへHermes completion proofをserializeせず、restartへ使わない | Claude bindingをCodex codecへserializeせず、restartへ使わない |
| Handoff | Durable completed-request / continuation binding | 同じCore documentをadapter固有deliveryへ渡す | 同じCore documentをsame-process deliveryへ渡す |
| Yohaku archive | Historical Referenceにselected visible-turn collector / retrievalのaccepted pathあり。`C-DRR`はcoverage外 | Shared record formatだけ。Hermes collector / retrievalは`UNIMPLEMENTED` / `NOT_RUN` | Collector / retrievalは`UNIMPLEMENTED` / `NOT_RUN` |
| Adapter metadata | Runtime event projection、operation / task ledger、run metadata | `hermes-events`とProbe / adapter sequence | `claude-cli-events`とcollector / recovery sequence |
| Runtime-native storage | Codex thread / context / transcript / history | `SessionDB`、active / inactive row、native conversation history | Claude native session / transcript、Ollama process / model / cache |
| Packaged Task Profile | `document-review-report-v1`だけ | なし。H-CLI-01 assessorはfixture固有 | なし。Local recovery assessorはfixture固有 |
| Formal lifecycle-only launcher | `C-OP`あり | `H-OP`あり | なし。Maintainer runnerやadapter implementationをoperational supportへ昇格させない |

この対応から、identityとstorageには次の三原則を適用する。

1. Runtime-native databaseやtranscriptはprofile-scoped evidenceになり得るが、Yohaku
   checkpoint / archiveではない。
2. Yohaku Core request / generationとhost-local attachment / collector / continuation IDを
   分ける。どちらもnative eventとcorrelateしただけではRuntime-native identityにならない。
3. 一つのRuntime固有eventを他Runtime用に捏造しない。共有Core stateには、異なる
   Completion PolicyとEvidence shapeを通って到達する。

## Profile固有の非継承例

[Evidence Model](evidence-model.md)の非継承規則を、本書のfixed profileへ適用すると
次の例になる。

- Codex manual-compaction `PASS`からnative automatic compaction `PASS`、fresh-context
  rollover、session migrationを推定しない。
- Claude local Ollama recoveryからAnthropic subscription recoveryを推定しない。
- Hermes H-CLI-01 `PASS`からHermesの全tool、session、version、operational profileを
  推定しない。
- `C-REF-M` manual Evidenceから`C-REF-A` native-auto pathを推定せず、Scenario Gから
  proactive manual成功を推定しない。
- Codex `0.155` Reference EvidenceからCodex `0.158` transition supportを推定しない。
  `C-OP`と`C-DRR`はそれぞれの狭いclaimを持つ。
- Runtime supportからTask Profile supportを推定しない。`document-review-report-v1`
  から任意のdocument、writing、coding task品質を推定しない。

Profile間で共有できるのは、Core state semantics、immutable value shape、freshness
rule、lease discipline、ambiguity rule、Evidence contractである。matching implementation
とEvidenceなしに、Verdict、lifecycle event、identity強度、completion proof、storage
authority、work taxonomy、delivery、receipt、continuation、restart behavior、Task
Assessorを共有しない。

## 横断reviewで確認した非対称性

次の分類は設計候補の優先度であり、実装済みcomponentや新しいacceptanceを示さない。
Alphaの対象profileを固定する前に、対象外の候補をblockerへ自動昇格させない。

| 分類 | 確認した事項 | 扱い |
|---|---|---|
| 文書上の不整合 | Mapping key、Support Profile ID、Evidence Record IDの欄が混在していた。IdentityもnativeとYohaku / host-localの二分類になっていた | 本Stageで名称と三分類を修正した。既存recordのID、schema、Verdictは変更していない |
| 文書上の不整合 | Claude completionをCLI successまで含む共通proofのように読める記述と、制定時の「他Runtime adapter未実装」がcurrent statusのように残っていた | Runtime固有completion predicateと時点を明記した |
| Harmless implementation asymmetry | Completion proof、trigger、transport、delivery、receipt、continuationはRuntime固有である。Active / pending / incorporatedもprofile固有の観測を表す | 意図的に維持する。event名やreceipt shapeを共通化するとEvidence authorityを失う |
| Harmless implementation asymmetry | Codexだけにaccepted visible-turn archive collectorがあり、Hermes / Claudeはnative historyだけを持つ | Archiveを宣言しないprofileでは許容する。Native DB / transcriptをYohaku archiveへ読み替えない |
| Alpha前に検討する価値がある候補 | Native、Core、host-local identityをtype levelで区別し、誤った代入を拒否する | 新しいRuntimeやreceipt方式をAlpha scopeへ追加する前に検討する。既存IDのrenameやschema migrationは別判断とする |
| Alpha前に検討する価値がある候補 | Product profile registry、public support table、retained Evidence indexの対応を機械的に検査する | 公開scopeのstatus drift防止に有用。Evidence自体を生成・再採点する仕組みにはしない |
| Alpha前に検討する価値がある候補 | Non-Codex profileが使うYohaku store rootをlegacy `CODEX_HOME`名から論理的に分離する | Data layout / compatibility設計を伴う。既存保存dataを暗黙移行しない。Alpha対象がCodexだけなら必須とは限らない |
| Alpha前に検討する価値がある候補 | `document-review-report-v1`のTask Profile canonical、Observer / Assessor registration、Runtime bindingを明示する | 現在唯一のpackaged Task Profileなので、次のTask Profile追加前に入力contractを固定する |
| Alpha scope依存 | Claude Code CLIの正式operational launcher | ClaudeをAlphaのoperational scopeに含めるなら事前に必要。Codex / Hermes限定Alphaでは後続にできる |
| Alpha後でよい候補 | Neutral Runtime Adapter / host interface、cross-Runtime persistence / restart framework | Current profilesはbounded wiringで成立し、Hermes / Claude restartを`UNSUPPORTED`としている。受入scopeを広げる時点で設計する |
| Alpha後でよい候補 | Universal active / pending ledger、portable snapshot、session migration coordinator | 未観測workやRuntime固有incorporationを一つの型で解決できない。必要な複数profileの実測後に検討する |
| Alpha後でよい候補 | Hermes / Claude visible-turn collectorとarchive retrieval | Archiveを各profileの公開scopeへ入れる時点で別Capabilityとして実装・受入する |

この分類は、すべてのRuntimeを同じarchitectureへ揃える計画ではない。Safety semanticsだけを
共有し、Runtime固有Evidenceを保持する。

## 文書境界と後続資料

本書では、native eventやEvidence itemをすべて列挙しない。[Evidence Model](evidence-model.md)
がEvidence authority、provenance、freshness、retention、CoverageProfile composition、
Verdict derivationを定義する。Runtime固有pageは、exact event sequence、version /
configuration、timeout値、field名、profileごとのoperational diagnosticを保持する。
Installation、operation command、storage layoutは、それぞれの専用文書が所有する。
