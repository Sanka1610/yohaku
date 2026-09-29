# Runtime Mapping

本書は、Yohakuのroleをfixed Runtime Support ProfileとTransition Strategyへ対応付ける。
Runtime / surface、lifecycle primitive、identity、work observation、completion proof、
delivery、current-state observation、continuation、Known Limitationsなど、profile固有の
事実を所有する。

[Architecture](architecture.md)はcomponent責務とtrust boundaryを所有する。
[Transition Strategies](transition-strategies.md)はContext Transition方式のtaxonomyと
共通semanticsを所有する。Runtime固有contractの詳細は[Codex](runtimes/codex.md)、
[Hermes](runtimes/hermes.md)、[Claude Code](reference/claude-cli.md)の各pageに
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

Mapping keyは本書内だけで使う略称であり、新しいSupport Profile IDではない。同じ
Runtime versionを使っていても、Probe、adapter、operational lifecycle、task supportを
分ける。

| Key | Fixed profileまたはretained record | このrowが示す範囲 | Implementation / Evidence / Verdict |
|---|---|---|---|
| `C-REF-M` | Codex historical Reference profile、`0.155.0-alpha.16.4` / Manual In-place Compaction | historical proactive manual path、archive、Core persistence behavior | Reference integration実装済み。retained local / syntheticとbounded live Runtime Evidenceあり。historical Phase 14 overall **PARTIAL**。 |
| `C-REF-A` | 同じhistorical Reference profile / Native Automatic Compaction emergency recovery | historical Scenario Gのnative race recovery。proactive transition成功ではない | Bounded emergency implementationとEvidenceあり。Scenario G **PASS**、historical Phase 14 overall **PARTIAL**。 |
| `C-OP` | `codex-operational-0.158` | inferenceやtask transitionを含まないcurrent-version owned App Server lifecycle | Operational lifecycle実装・測定済み **PASS**。task transition **NOT_RUN**。experimental。 |
| `C-DRR` | `codex-document-review-report-v1` / Task Profile `document-review-report-v1` | current versionで、一つのmanual compactと一つのreportを含むreal document-review workflow | Bounded implementation。lab / live-Runtime / nonfixture real-task Evidence。profile **PASS**、overall product coverage **PARTIAL**、quality `NOT_ASSESSED`。 |
| `H-PROBE` | Hermes `H-CLI-01` Stage 2 Probe | connected adapter実装前のfixed native CLI workflowに対するcapability observation | Probe packageと測定workflowのみ。bounded workflow **PASS**、overall **PARTIAL**。adapterやoperational hostではない。 |
| `H-ADAPTER` | `hermes-h-cli-01` / retained Stage 4 adapter profile | 一つのfixed toolと一つのmanual compressionを扱うembedded adapter path | Bounded adapter実装済み。live synthetic Evidenceあり。accepted bounded workflow **PASS**、overall **PARTIAL**。 |
| `H-OP` | `hermes-operational-h-cli-01` | inferenceとtransition adapterを無効にしたowned native CLI / store lifecycle | Operational lifecycle実装・測定済み **PASS**。task / tool / transition path **NOT_RUN**。experimental。 |
| `CL-SUB-C` | `C-CLI/2.1.280/Linux/print-stream-json/command-hooks` completion profile | external Anthropic subscription CLIのmanual-compaction completionから`ROLLOVER_OBSERVED`まで | Bounded completion adapter実装済み。external live-Runtime synthetic Evidence。manual completion **PASS**、overall **PARTIAL**。 |
| `CL-SUB-R` | 同じfixed C-CLI surfaceとrecovery adapter | subscription surfaceのhandoff、receipt、continuation、resume contract | Recovery implementationは存在するが、external subscription recovery Evidenceは **NOT_RUN**。local OllamaのVerdictを継承しない。 |
| `CL-LOCAL-FULL` | `C-CLI-OLLAMA-LOCAL/2.1.280/0.34.1/spark-x2.5-4b-uncensored/e1646156c204` | local maintainer full-identity receipt / recovery比較 | Bounded maintainer adapter。local-live synthetic Evidence。`RESUME_VERIFIED`一回、pre-adapter failure一回。repeatability **FAIL**、overall **PARTIAL**。 |
| `CL-LOCAL-NONCE` | `claude-c-cli-local-nonce` / `host-nonce-v1` | host-bound one-time nonce receiptを使うlocal maintainer recovery | Bounded maintainer implementation。local-live synthetic Evidence。一つのworkflow **PASS**、overall **PARTIAL**。qualityとrepeatabilityは`NOT_ASSESSED`。 |

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
| Request identity | `C-REF-M`は一つのYohaku `Request`、Core generation、ordered ownerを使う。`C-REF-A`はnative-auto originとrecovery correlationを記録し、proactive leaseを再構成しない。 |
| Native session / turn / generation / attachment identity | 利用可能なnative session / threadとactive-turn evidenceを観測する。App Server eventはnative Yohaku request / generation IDを提供しない。 |
| Host-local identity | Yohaku request ID、generation、attachment / correlation state、ordered owner mapping |
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
| Trigger owner / request identity | transition triggerとtransition request identityは`UNIMPLEMENTED`。 |
| Native identity | lifecycle ownership用のfresh native thread / session identityを観測する。turn / generation / attachmentのtransition identityは`NOT_RUN`。 |
| Host-local identity | operational runとCompanion / store identity。native Runtime request / generationではない。 |
| Completion proof | `NOT_RUN`。lifecycle startup / shutdownはcompaction proofではない。 |
| Checkpoint / journal | Companion / store lifecycleは存在するが、task checkpointはcommitしない。 |
| Runtime-native storage | owned App Server配下のfresh Codex thread state。Yohaku checkpoint / archiveとは扱わない。 |
| Handoff / receipt / fresh observation / continuation | lifecycle-only runでは`UNIMPLEMENTED`。 |
| Task assessor / resume verification | `UNIMPLEMENTED`。Task Profileなしのtask transitionは拒否する。 |
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
| Request identity | single manual compact用のYohaku request一つとCore generation |
| Native session / turn / generation / attachment identity | fresh Codex threadとRuntime turn observation。native Yohaku generation identityはない。 |
| Host-local identity | runner、attachment、request、generation、tool-call / result、declared workspace identity |
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
| Trigger owner / request identity | Probe hostがmanual compressionを一回triggerし、Probe-local correlationを使う。 |
| Native identity | instrumentationが利用可能なHermes session / turn / request / tool identityを観測する。 |
| Host-local identity | Probe run / correlation ID。native Hermes IDの代わりにはならない。 |
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
| Request identity | Yohaku request / generationとowned native compression callをcorrelateする。 |
| Native identity | Hermes session、turn、API request、tool call / result identity |
| Host-local identity | adapter request / generationとowner mapping。native identityを置き換えず、並べて保持する。 |
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
| Trigger / request / completion | このprofileでは`UNIMPLEMENTED`。 |
| Native identity | native lifecycle / session / store identity。task turn / compression identityは実行していない。 |
| Host-local identity | operational run identity。native Hermes request / turnではない。 |
| Checkpoint / journal / native storage | operational store lifecycleのみ。transition checkpointはない。native storeはYohaku persistenceではない。 |
| Handoff / receipt / fresh observation / continuation / assessor | `UNIMPLEMENTED`。 |
| Archive | `UNIMPLEMENTED`。 |
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
| Active / pending / incorporated | Activeはadmit済みPre / PostToolUse間のfixed foreground fixture operation。collectorとfixture effectでterminal executionを確認できる。general pending-result incorporationとsemantic incorporationは`NOT_RUN`であり、Hook / CLI successから推定しない。 |
| Work-plane gate | fixed collector / runner sequencing。general C-CLI work gateはない。 |
| Trigger owner | external operator / runnerがmanual compactを一回発行する。 |
| Request identity | Yohaku host-local attachment / request / generationとclosed collector sequence |
| Native identity | native Claude `session_id`。native Yohaku request、generation、attachment IDはない。 |
| Host-local identity | attachment、request、generation、collector sequence。明示的にhost-localとして保持する。 |
| Completion proof | correlated `PreCompact`、compact handler / `PostCompact`、compact-origin `SessionStart`、successful CLI completion、collector closure。CLI successやHook一つだけでは不十分。 |
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
| Trigger / request / identities | 同じnative `session_id`とhost-local attachment / request / generation / collector identity。continuation dispatch identityはhost-localであり、native Claude turn IDではない。 |
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
| Trigger owner / request identity | maintainer runner、host-local attachment / request / generation / collector identity |
| Native identity | Claude native `session_id`。native request / generation / attachment identityはない。 |
| Host-local identity | adapterがfull identity setを保持しreceiptへ要求する。native identityではない。 |
| Completion proof | fixed C-CLI Hook sequence、successful CLI completion、collector closure |
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
| Trigger owner / request identity | maintainer runner、一つのhost-local request / generation / collector owner |
| Native identity | native Claude `session_id`。receipt tool前後のnative Pre / handler / Post observationを要求する。 |
| Host-local identity | hostがfull identity tupleを保持し、modelは128-bit・22文字のnonce一つだけを返す。host-local IDをnative IDへ読み替えない。 |
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
| Completion proof | `C-REF-M`: correlated compaction item＋`PostCompact`＋compact turn completion。`C-REF-A`: Scenario G固有bounded native sequence。 | host history mutation＋independent read-only `SessionDB` projection / archived-row readback | correlated Hook / handler / compact-origin startup evidence＋CLI completion＋collector closure |
| Handoff delivery | Companionがdurable handoffをowned recovery pathへinjectする。 | embedded hostがdurable handoff一つをdeliveryする。 | same-process recovery adapterがdurable handoff一つをinjectする。external subscription recoveryは`NOT_RUN`。 |
| Receipt | handoff / generationにcorrelateした`YOH_ACK` | native / Yohaku correlationを含むadapter-defined assistant tool receipt | full-identity receiptまたは`host-nonce-v1`。どちらもClaude built-in receipt primitiveではない。 |
| Fresh observation | delivery後のtrusted Runtime / task / workspace read | independent current native / task read | fresh recovery token / current-state observation |
| Continuation | owned App Server continuation。`C-DRR`ではunfinished profile workだけを許可する。 | 同じexclusive embedded host / session | host-owned continuation dispatch。IDはhost-localであり、native CLI turn IDではない。 |
| Resume verification | Core＋bounded scenario assessor。`C-DRR`はpackaged mechanical assessorを持つ。 | Core＋fixed fixture / task assessor | Core＋fixed fixture assessor。external subscription recoveryは`NOT_RUN`。 |
| Archive | historical Reference profileのselected visible-turn archive。`C-DRR`はcoverageを主張しない。 | `UNIMPLEMENTED`。`SessionDB`はnative historyのみ。 | `UNIMPLEMENTED`。Claude session storageはnative historyのみ。 |

この対応から、identityとstorageには次の三原則を適用する。

1. Runtime-native databaseやtranscriptはprofile-scoped evidenceになり得るが、Yohaku
   checkpoint / archiveではない。
2. Host-local attachment、request、generation、collector、continuation IDは、native
   eventとcorrelateしてもhost-localのままである。
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

## Mappingで確認した未分離箇所

次は文書整理で確認したアーキテクチャ上の差であり、今回実装する提案ではない。

- adapter実装は一つのneutral Runtime Adapter / host interfaceに揃っていない
- persistenceとrestartはCodex型のままで、Hermes / Claudeはbounded adapter固有
  metadataを持つ
- active / pending / incorporated workはprofile-local ledgerごとに異なり、共有capability
  descriptionがない
- native identityとhost-local identityがtype system全体で一貫して分離されていない
- Task Observer / Task Assessor registrationは`document-review-report-v1`とfixtureだけに
  packageされている
- completionにはshared policy seamがあるが、trigger、transport、delivery、continuation、
  visible-turn extractionにはない
- profile declaration、public support table、Evidence indexの整合を手動で維持している

これらはrefactor候補であり、新しいabstractionがすでに存在するという記述ではない。

## 文書境界と後続資料

本書では、native eventやEvidence itemをすべて列挙しない。[Evidence Model](evidence-model.md)
がEvidence authority、provenance、freshness、retention、CoverageProfile composition、
Verdict derivationを定義する。Runtime固有pageは、exact event sequence、version /
configuration、timeout値、field名、profileごとのoperational diagnosticを保持する。
Installation、operation command、storage layoutは、それぞれの専用文書が所有する。
