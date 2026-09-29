# Architecture

Yohakuの対外的な製品カテゴリは **Proactive Context Compaction Manager**
である。内部の中核概念には **Verified Context Transition** を置く。長時間
動作するAgentがcontextを切り替える前に、安全なboundaryかを確認し、復旧に
必要な状態をdurableに保存する。続いて、Runtime固有のtransitionが完了した
ことと、通常作業を再開する前のtask stateがcurrentであることを検証する。

CompactionはTransition Strategyの一つであり、アーキテクチャ全体を指すもの
ではない。Yohakuは、契約を満たす限りRuntime標準のcompaction、compression、
memory、history、archiveを再利用する。圧縮アルゴリズム自体を競うのではなく、
control layerとして次を管理・検証する。

- transitionを開始できる時機
- 現在地点が安全なboundaryか
- transition前にdurableに保存すべき状態
- 要求したtransitionが実際に完了したか
- recovery時の観測がcurrent task stateを表しているか
- 未完了workだけを重複なく継続できるか

本書は、Yohakuのcomponent責務、control flow、trust boundaryについて、公開文書
上の正本となる。現在の実装に加えて、profile固有または未実装の境界も示す。
本書の記述によってRuntime、Support Profile、CoverageProfile、Capability Verdict
を昇格させることはない。

## アーキテクチャモデル

Yohakuの責務は、次の四層に分かれる。

```text
Agent / Runtime
    │ boundaryを提案し、task workを実行する
    ▼
Runtime integration
    │ lifecycle、work、Runtime identityを観測する
    │ Runtime固有のtransitionとdeliveryを実行する
    ▼
Verified Context Transition Core
    │ boundary、freshness、authority、ambiguity、
    │ completion、handoff、resumeの不変条件を検証する
    ▼
Durability and task integration
      checkpoints / handoffs / archive
      trusted task observer / task assessor
```

矢印は、各層を同じ強さで信頼することを意味しない。Agentの提案はcandidateに
すぎない。Runtime eventをEvidenceとして解釈できるのは、その意味を定義した
fixed profile内だけである。Task observerとassessorはtrusted integration code
として扱う。永続化済みの情報は、fresh observationによってcurrent stateと照合
されるまでhistorical inputである。

現在のコードは、一部だけがRuntime-neutralである。`Controller`は共有stateと
safety gateを持ち、`CompletionPolicy`は狭いRuntime固有seamを提供する。一方、
durable snapshot schema、restart経路、`CompanionController`、既定backend、複数の
lifecycle名はCodex Reference integrationに由来する。したがって、HermesとClaude
のadapterが存在しても、cross-Runtimeのhost、persistence、restart frameworkが
一般化済みとは扱わない。

## Componentの責務と実装状態

以下の表では、実装状態を次のように区別する。

- **Shared implementation**: 共通の制御またはdata contractとして使うコード
- **Runtime-specific implementation**: event、identity、transport、storage、hostの
  前提が一つのRuntime integrationに属するコード
- **Bounded-profile implementation**: fixed Support Profile、task、tool集合、workflow
  の範囲でのみacceptedとなるコード
- **Design concept only**: アーキテクチャ上の役割はあるが、一般製品componentは
  実装されていない
- **Future / Deferred**: 現在の実装対象外として明示的に保留している

Coreの判断を共有していても、判断に必要な観測やI/OがRuntimeまたはtask固有で
あれば、一つのcomponentに複数の状態を付ける。

### 制御と安全性

| Component | 責務 | 入力 → 出力 | Trust boundaryとRuntime境界 | 現在の状態 |
|---|---|---|---|---|
| Semantic Boundary Policy | boundary candidateと、検証済みのsemantic / execution boundaryを区別する。authorization前に、宣言scopeのEvidenceとquiescenceを要求する。 | Candidate ID、task observation、revision、workspace revision、evidence profile → `CANDIDATE`、`VERIFIED`、`DEFERRED`、または拒否 | ModelやAgentはcandidateを提案できるが、検証はできない。trusted task/hostが観測を供給する。Yohakuは自律的な汎用boundary detectorを提供しない。 | Core gateは **Shared implementation**。具体的な観測は **Bounded-profile implementation**。より一般的なpolicyは **Design concept only**。 |
| Core State Machine | work、verification、checkpoint、transition、handoff、resumeの判断を直列化し、順序を保持する。 | Trusted callとimmutable observation → state transitionとone-shot authority | `Controller`自身は外部I/Oを行わない。ownerが全callを直列化し、正しい観測を渡す必要がある。既存の`ROLLOVER_*`名は実装上の語彙であり、全Strategyがrolloverであるという意味ではない。 | [`controller.py`](../src/yohaku/controller.py)と[`model.py`](../src/yohaku/model.py)の **Shared implementation**。 |
| Revision / Freshness | intent、execution、control、archive、workspaceの観測を分け、stale evidenceがcurrent workをauthorizeしないようにする。 | Revision counter、`WorkspaceRevision`、verification evidence、fresh recovery observation → current stateとして受理、またはinvalidate | どのmutationとresultを観測できるかはRuntime / task integrationが定める。counterが一致しても、coverage不足は補えない。 | 値とgateは **Shared implementation**。観測coverageは **Runtime-specific** または **Bounded-profile**。 |
| Lease / Ambiguity handling | 短命なtransition authorityを一つのboundary、checkpoint、revision集合、workspace、generationへ結び付ける。dispatchやcompletionが不明な場合はblind retryを止める。 | Committed checkpointとcurrent observation → `Lease`、一つの`Request`、`AMBIGUOUS`、`INVALIDATED`、または`RECOVERY_REQUIRED` | Leaseはlocal authorityであり、Runtime-wide lockではない。transport前にconsumeし、restart後に復元しない。 | Coreの **Shared implementation**。最終的なenforcement範囲は各Runtimeのdispatch surfaceに依存する。 |
| Completion Policy | Runtime固有bindingとEvidenceを検証し、蓄積したEvidenceからcompletionを判断する。continuation identityも制約する。 | Pending `Request`、Runtime binding、correlated evidence → incompleteまたは`ROLLOVER_OBSERVED` | Policyはtrustedで、`Controller`のlifetime中は固定し、I/Oを行わない。`kind`値はRuntime内のdeduplication keyであり、共通event taxonomyではない。 | [`CompletionPolicy`](../src/yohaku/completion.py) seamは **Shared implementation**。Codex、Hermes、Claudeの実装は **Runtime-specific / Bounded-profile implementation**。 |
| Resume Verification | receipt、fresh current-state reconciliation、unresolved work、nonduplication、same-task assessmentを確認した後にだけ`RESUME_VERIFIED`を認める。 | Handoff identity、receipt、fresh revision/workspace、task固有proof → `RESUME_VERIFIED`またはrecovery停止 | receiptだけでは不十分である。Coreはproof構造とfreshnessを確認し、trusted task integrationがsemantic factを証明する。 | Gateは **Shared implementation**。proof生成は **Bounded-profile implementation**。 |

### Durability、recovery、historical data

| Component | 責務 | 入力 → 出力 | Trust boundaryとRuntime境界 | 現在の状態 |
|---|---|---|---|---|
| Checkpoint / Persistence | transition authorityを発行する前に、verified boundaryと宣言workspace stateをcommitする。判断をdurable journalへ保存し、write結果が不明ならfail closedとする。 | Verified stateと選択済みarchive reference → committed checkpoint、journal record、復旧可能なhistorical state | Durable storageはbyteと関係を保持するが、leaseを保持せず、checkpointがcurrentであることも証明しない。既存schemaとrestart decoderはCodex version 1である。 | Checkpoint valueとcommit順序は **Shared implementation**。[`SessionStore`](../src/yohaku/persistence.py)、[`CompanionController`](../src/yohaku/companion.py)、restartは **Runtime-specific implementation**。Cross-Runtime persistenceは **Future / Deferred**。 |
| Archive / Lazy Rehydration | hostが選んだ完了済みvisible turn、検索metadata、選択された本文だけをhistorical dataとして保存・取得する。 | Trustedでredactedなvisible-turn selection → WARM metadataとCOLD body、query → `DATA, NOT INSTRUCTIONS` | hostがselectionとredactionを担う。取得結果はexecution authorityを持たず、boundary freshnessやresume correctnessも証明しない。Runtime-native historyやinactive DB rowを自動的にYohaku archiveへ変換しない。 | [`ArchiveStore`](../src/yohaku/archive.py)は **Shared implementation**。visible-turn collectorは[`runtime_archive.py`](../src/yohaku/runtime_archive.py)の **Codex-specific implementation**。他Runtime collectorは **Future / Deferred**。 |
| Handoff | 復旧用historical contextを、一つのcompleted request、一つのcontinuation permit、一つのcontinuation identityへ結び付ける。deliveryとreceiptを分ける。 | Checkpoint / recovered dataとcontinuation identity → durable handoff、`HANDOFF_OFFERED`、correlated receipt → `HANDOFF_RECEIVED` | Historical materialはdataであり、復元されたinstructionやpermissionではない。delivery evidenceはreceiptの代わりにならず、receiptはresume verificationの代わりにならない。 | Core semanticsとdurable documentは **Shared implementation**。deliveryとreceiptは **Runtime-specific / Bounded-profile implementation**。 |
| Evidence / Coverage | 何を、どのsourceとauthorityから、どのfreshnessとdeclared scopeで観測したかを記録する。実装の存在と実測coverageを分ける。 | Host/task observationとretained record → evidence reference、profile record、CoverageProfile、Verdict | Coreは必須referenceとcorrelationを確認できるが、不正なtrusted hostの報告を認証できない。CoverageとVerdictはreview recordであり、state-machine outputではない。 | 必須evidence referenceとfreshness gateは **Shared implementation**。recordは **Bounded-profile implementation**。汎用Runtime evidence collectorは **Future / Deferred**。 |

### Runtimeとtaskのintegration

| Component | 責務 | 入力 → 出力 | Trust boundaryとRuntime境界 | 現在の状態 |
|---|---|---|---|---|
| Runtime Adapter | 一つのfixed Runtime / surface / Strategy lifecycleをtrusted Core callへ変換し、identityやeventを捏造せずにRuntime I/Oを行う。 | Native lifecycle event、host-local correlation、Core decision → normalized proof、dispatch、delivery、continuation | Lifecycle event名、identity強度、request semantics、Hook挙動、storage readbackはRuntime固有である。 | Codex Reference、Hermes H-CLI-01、Claude C-CLIに **Runtime-specific / Bounded-profile implementation** がある。完全な共通adapter interfaceやregistryはない。 |
| Runtime Host / Companion | Runtime connectionと直列化されたevent loopを所有し、observation、durable state、dispatch、timeout、recoveryを接続する。 | Runtime messageとtrusted callback → ordered Core mutationとpersisted decision | ownerが観測の直列化とcorrelationを担う。`RuntimeHost`と`CompanionController`はCodex指向のままである。Hermes / Claudeはneutral Companionではなく、別のbounded wiringを使う。 | Codexには **Runtime-specific implementation** がある。Hermes / Claudeのconnection pathは **Bounded-profile implementation**。neutral cross-Runtime hostは **Future / Deferred**。 |
| Work observation / active-pending ledger | admitted work、active operation、incorporation待ちのcompleted result、observation lossを記録する。 | Runtime tool lifecycleとtrusted result incorporation → active / pending / uncertain work state | Tool taxonomyと「incorporated」の意味はRuntime / task固有である。tool resultが成功しても、Agentがtask stateへ反映したことは証明できない。 | Codexには **Runtime-specific bounded ledger** がある。Hermes、Claude、document reviewには別々の **Bounded-profile ledger** がある。universal ledgerはない。 |
| Work-plane gate | transition barrier中の新しいstate-changing workを拒否し、関係するactive / pending workがsettleするまで待つ。 | Proposed operation、barrier state、observed ledger → allow、deny、`DEFERRED`、ambiguity、またはrecovery停止 | local gateが対象にできるのは、そこを通るoperationだけである。全Runtime tool、background process、external client、workspace writerをatomicに停止するものではない。 | 宣言したoperationに対する **Runtime-specific / Bounded-profile implementation**。Runtime-wide atomic freezeは未実装。 |
| Task Profile | logical taskを、allowed work plane、input/output contract、Trusted Observer、Task Assessor、Transition Strategy、refusal ruleへ結び付ける。 | Fixed task configurationとcurrent task state → admitted task workflowまたは拒否 | Runtime supportはlifecycle capabilityを提供し、task supportはtask semanticsを提供する。どちらからも他方を推定できない。 | `document-review-report-v1`の **Bounded-profile implementation**。general task frameworkは **Design concept only**。 |
| Trusted Observer | boundary、freshness、active / pending work、resume checkに使うcurrent task observationを生成する。 | Declared input、workspace、observed Runtime result → versioned task observationと`WorkspaceRevision` | model outputではなくtrusted integration codeである。宣言scope内だけを主張でき、unobserved external writerの不在は証明できない。 | document reviewとfixture固有integrationの **Bounded-profile implementation**。general observerはない。 |
| Task Assessor | 固定taskのpermitted continuationが、stale、duplicate、undeclared、pending workを残さずmechanicalに完了したか判断する。 | Fresh observation、continuation item、task contract → task固有resume proofまたは拒否 | general quality oracleではない。mechanical completionを検証しても、content correctnessやqualityは未評価のままにできる。 | **Bounded-profile implementation**。`document-review-report-v1`が評価するのはmechanical completionだけである。 |
| Operational Host / launcher | reviewed Runtime processを起動・所有し、stateを分離し、profile設定を適用する。status / stopを提供し、profileがtask integrationを持つ場合だけ接続する。 | Explicit configurationとfixed profile → owned Runtime lifecycleまたはtask-enabled run | lifecycle-only hostは意図的にinference、Task Observer、work observation、transition authorityを持たない。Runtimeの起動はtransition acceptanceではない。 | CodexとHermesのlifecycle-only profileに **Runtime-specific implementation** がある。document reviewには **bounded Codex task runner** がある。Claude operational launcherは **Future / Deferred**。 |

## Control flow

### 通常作業とboundary proposal

```text
Agent / Runtime task work
    → Runtime固有のwork observation
    → Trusted Observer
    → Semantic Boundary Candidate
    → Coreによるquiescence、freshness、Evidenceの検証
```

Agentは意味のある区切りを提案できるが、その提案で確定するのは`CANDIDATE`まで
である。hostが利用可能なwork-plane gateを有効にし、関係するactive / pending
workを観測し、宣言workspace scopeを取得してEvidenceを渡す。Coreだけが
`VERIFIED`へ遷移できる。

### Verified transition

```text
Verified Boundary (`VERIFIED`)
    → durable checkpoint
      (`CHECKPOINT_PREPARING` → `CHECKPOINT_COMMITTED`)
    → revision-bound leaseと一つのrequest
      (`ROLLOVER_AUTHORIZED` → `ROLLOVER_REQUESTED`)
    → Runtime固有のTransition Strategy
    → correlated completion proof (`ROLLOVER_OBSERVED`)
    → 一つのcontinuation permitとRuntime continuation identity
    → durable handoff delivery (`HANDOFF_OFFERED`)
    → explicit receipt (`HANDOFF_RECEIVED`)
    → fresh task / workspace observation
    → 未完了workだけを継続
    → task固有のassessment
    → `RESUME_VERIFIED`
```

公開アーキテクチャでは上位概念をContext Transitionと呼ぶが、実装は互換性の
ため`ROLLOVER_*` state名を維持する。Strategyは、そのRuntime contractが実装・
検証した場合に限り、in-place compaction、fresh contextへのrollover、session
migrationを実行できる。一つのStrategyのaccepted結果から、他Strategyの対応を
推定しない。

### Unsafeまたはuncertainな経路

次の結果は意味が異なるため、一つのfailureへ統合しない。

| 条件 | 必要な結果 |
|---|---|
| verification前に関係するactive workまたはpending resultを観測した | Core stateを`DEFERRED`とし、barrierを解除して通常作業へ戻る。新しいcandidateを提案してから再試行する。契約文では動作を「DEFER」と表現できるが、実装state名は`DEFERRED`である。 |
| boundary、revision、workspace、lease、pre-dispatch authorityがstale | 拒否するか`INVALIDATED`へ遷移する。そのauthorityからrequestを送らず、current stateから再検証する。 |
| dispatchされた可能性がある一方、completionが欠落・競合・未照合のlate eventなどで不明 | `AMBIGUOUS`へ遷移する。correlated evidenceを照合するまで通常作業とblind retryを止める。 |
| completionは既知だが、handoff、receipt、current-state reconciliation、resume proofを安全に完了できない | `RECOVERY_REQUIRED`へ遷移する。古いauthorityは復元しない。 |
| fixed Task Profileが、undeclared input、stale output、duplicate write、disallowed workをuncertain side effect前に拒否した | task / operation layerで`REFUSED`を返す。`REFUSED`はCoreの`State`ではない。writeやresultがuncertainになった場合は、profileが`AMBIGUOUS`を返すことがある。 |
| Durable recordが破損・不整合、またはwrite結果が不明 | ownerを停止してrecoveryを要求する。古いcheckpointへ黙ってfallbackしない。 |

## Trust boundary

### Model / Agent output

Model outputはuntrusted task contentである。bounded protocolが必要とするboundary
proposal、receipt marker、task artifactを出力できるが、自己申告だけでは
quiescence、completion、receipt identity、correctnessを証明できない。

### Yohaku trusted host

trusted hostはserialization、Runtime connection、observation adapter、current-state
read、durable callを所有する。Coreの安全性は、hostが正しくscopeされた観測を
報告することに依存する。Yohakuはcorrelationとstate invariantを検査できるが、
host instrumentationが外部Runtimeを正確に報告したかを暗号学的には証明できない。

### Runtime lifecycle evidence

Runtime event、Hook、native history、storage readbackは、そのidentity、ordering、
coverageを定義したTransition Strategy内だけで受理する。RPC acknowledgementや
tool returnの成功から分かるのは、そのlocal operationの結果までである。それ
だけではtransition completionやsemantic incorporationを証明できない。

### Task workspace

task workspaceはcurrent mutable stateであり、Yohakuのtrusted storageではない。
`WorkspaceRevision`は宣言scopeとmutation epochを識別する。profile lockは協調する
launcherを調整するが、他process、editor、Runtime client、userのwriteを防がない。
検出した変更はstale evidenceをinvalidateする。観測できない変更はcoverage上の
制限として残る。

### Persistent Yohaku storage

Yohaku storageにはjournal、checkpoint、handoff、選択済みarchive entry、profile
metadataを保存する。checksum、atomic replacement、synchronization、local writer
lockは、実装済みPOSIX storeを宣言したlocal failure modeから保護する。ただし、
historical checkpointをcurrentにせず、leaseを復元せず、store外の非協調writerも
排除しない。

### Runtime-native storage

Runtime-native transcript、history、database、memory storeはRuntime側のtrust domain
に属する。adapterはfixed readbackをcompletion evidenceとして利用できるが、native
store全体をYohaku checkpoint、archive、current authorityとは扱わない。native record
はfixed profileの規則でcorrelateし、意味を解釈する必要がある。

### External writer / unobserved work

宣言したobserverとgateの外にあるexternal writerやwork itemは、Yohakuのlocal state
machineだけでは安全にならない。profileはこの制限を開示する。observerのcoverage
が不完全な場合、eventが存在しないことからworkの不在を推定しない。

以上から、次の原則を適用する。

- modelの自己申告だけでboundaryをverifyしない
- tool successだけでsemantic incorporationを証明しない
- handoff deliveryだけでreceiptを証明しない
- receiptだけでresume correctnessを証明しない
- old checkpointをcurrent stateやauthorityとして扱わない

## Shared CoreとRuntime固有責務

次の表は、目標とする責務分担と、現在の実装を安全に読むための区分である。全項目
にstableなRuntime-neutral interfaceが存在するという意味ではない。

| Shared safety condition / semantics | Runtime固有の責務 | 現在の実装上の例外 |
|---|---|---|
| boundary candidate identityとcandidate / verified boundaryの区別 | candidateを生成し、task固有のsemantic completionを観測する | 汎用の自律detectorはない。document-review observerはprofile固有である。 |
| revisionの単調性、freshness比較、stale-evidence拒否 | どのRuntime eventとworkspace変更でrevisionを進めるか決める | CoverageはRuntime / taskごとに異なる。unobserved writerはgate外に残る。 |
| quiescenceをverificationより先に確立する | tool taxonomy、active work、pending result、result incorporationを対応付ける | Codex、Hermes、Claude、document reviewは異なるbounded ledgerを使う。universal taxonomyはない。 |
| authorityを発行する前にcheckpointをcommitする | host platform上のdurable commit、namespace、locking、readbackを実装する | 現行journal / restart schemaとCompanionはCodex version 1である。Hermes / Claude adapterからCore restartを推定しない。 |
| leaseをboundary、checkpoint、revision、workspace、generationへ結び付ける | 実dispatch地点で再検証し、利用可能なwork gateをenforceする | local Coreはfinal readからRuntime dispatchまでの全raceを除去できず、Runtime-wide atomic freezeも提供しない。 |
| unknown executionをnon-executionと扱わず、ambiguity中のretryを止める | late、duplicate、conflicting、missing native evidenceをcorrelateする | Evidenceの形とaccepted scopeはStrategyごとに異なる。 |
| completionをrequest acceptanceから分離する | lifecycle eventを対応付け、Runtime固有completion proofを提供する | 共通seamがあるのはcompletion predicateだけである。transportとlifecycle mappingは一般化されていない。 |
| handoffをdata-boundかつdurableにし、receiptと分離する | handoffをdeliveryし、correlated Runtime receiptを生成する | Codex、Hermes、Claudeは別々のbounded delivery / receipt mechanismを使う。 |
| fresh current state、nonduplication、same-task continuationをresumeの条件にする | continuationを開始・識別し、fresh readとTask Assessorを実行する | general assessorはない。現在のassessorはprofileまたはfixture固有である。 |
| archive dataへauthorityを与えない | visible turnをextract、select、redact、identifyする | 製品archive adapterとして実装済みなのはCodex visible-turn collectorだけである。 |
| Evidenceにscope、authority、freshness、coverageを要求する | source / version / profile固有recordとnative identityを取得する | Evidence recordはexternal hostを認証せず、fixed profile外へ一般化できない。 |

Runtime固有側は、少なくともlifecycle event mapping、tool taxonomy、active / pending
observation、work-plane enforcement、transition trigger、completion proof、session / request /
generation identity、delivery、continuation、visible-turn extractionを所有する。既存
snapshot schemaへ合わせるために、Coreが他Runtime用のCodex型event列を捏造しては
ならない。

## Task Profile: Runtime supportとtask supportの区別

Runtime supportとtask supportは、別の問いに答える。

```text
Runtime support  = fixed Runtime profileでtransitionを観測・制御できるか
Task support     = fixed Task Profileで安全なboundaryと完了を判断できるか
```

lifecycle-only Runtime profileは、task observerやassessorを持たないため、起動、停止、
state保持だけを提供し、inferenceやtransitionを意図的に拒否できる。反対に、task
contractが存在しても、Runtime completion、identity、receipt、continuation evidenceの
不足は補えない。

`document-review-report-v1`は最初のpackaged Task Profileであり、general task
frameworkではない。定義する範囲は次のとおりである。

- profile所有のdynamic toolである`read_review_inputs`と
  `publish_review_report`だけをallowed work planeとする
- 宣言済みUTF-8 Markdown / text inputと、一つのcreate-only Markdown outputに
  preflight input/output contractを設ける
- input identity、read / write lifecycle、result incorporation、active / pending work、
  workspace freshnessをTrusted Observerが観測する
- continuation内のfresh read一回とpublish一回だけをTask Assessorが受理し、command、
  file change、MCP、duplicate、stale、pending workを拒否する
- 評価対象をmechanical completionとする
- stale output、undeclared / duplicate input、workspace変更、duplicate write、
  unsupported workをfail closedで拒否する

このprofileはreportの事実性、完全性、編集品質、文章品質を評価しない。これらは
`NOT_ASSESSED`のままである。accepted workflowを任意のdocument processing、coding
task、別tool集合、別Runtimeへ一般化しない。

## Non-goals / Non-guarantees

Yohakuは次を保証しない。

- 任意taskやtask artifactの正しさ
- 文章品質、コード品質、生成内容のreview成功
- model reasoningやmodel self-reportの正しさ
- 全Runtime tool、background task、process、client、external workspace writerの
  atomic freeze
- 対応するEvidenceとdeclared coverageがないprofileの安全性またはsupport
- Runtime dispatch、delivery、external side effectに対する一般的なexactly-once保証
- hidden chain-of-thoughtの保存または復旧
- in-memory process state、database transaction、external service state、任意OS process
  の復元
- general task-success oracle、自動secret classifier、universal visible-turn selector
- cross-Runtime restart、snapshot migration、storage compatibility
- native mechanismが十分なcontractを満たす場合のRuntime標準compressor、memory system、
  archiveの再実装

Fresh-context rolloverとsession migrationは、利用可能なgeneral adapterではなく、
アーキテクチャ上のTransition Strategy categoryである。Supportは、fixed Runtime、
surface、version、Strategy、backend / model、tool集合、owner assumptionの組ごとに宣言
する。

## 公開文書のlanguage policy

Yohakuの公開文書は、日本語版をcanonicalとする。英語版を作る場合は、canonical
日本語版から生成・更新するderived documentationとして扱い、英語版だけで仕様、
Support Profile、Evidence、Verdictを変更しない。

`README.md`は将来、日本語canonicalへ移行する。英語版のファイル名は
`README.en.md`とする。詳細docsの英語版は、Alpha公開に必要な主要文書から段階的に
作成する。現在は、本書、[Runtime Mapping](runtime-mapping.md)、
[Transition Strategies](transition-strategies.md)、[Evidence Model](evidence-model.md)を
日本語canonicalとする。`README.md`の全面改稿や英語版の作成は、この整理に含めない。

Internal research、raw Evidence、historical / frozen資料は、provenanceとsource
associationを保つため原文を維持する。一律翻訳せず、公開用のderived documentが
必要になった場合だけ、正本と派生物の関係を明示して作成する。

## 他の公開文書との関係

本書は、現在の公開component model、責務境界、control flow、trust boundaryを所有
する。他文書の責務は次のとおりである。

- [README](../README.md)は製品紹介とtop-level current statusを所有する
- [Evidence Model](evidence-model.md)はEvidence、CoverageProfile、Capability Verdict、
  provenanceと非継承規則を定義する
- [Support Policy](../SUPPORT_POLICY.md)はRuntime / Support Profile maturityと
  release-channel ruleを定義する
- [Runtime Mapping](runtime-mapping.md)はfixed-profile factと、Yohaku roleから
  Runtime固有primitiveへの対応を所有する
- [Transition Strategies](transition-strategies.md)はManual In-place Compaction、
  Native Automatic Compaction、Fresh-context Rollover、Session Migrationのtaxonomyと
  共通semanticsを所有する
- [Runtime support](runtime-support.md)は、後続のprofile固有整理までprofile status、
  historical provenance、Known Limitationsを保持する
- [Codex reference](reference/codex.md)、[Hermes reference](reference/hermes.md)、
  [Claude CLI reference](reference/claude-cli.md)はRuntime固有contractと制限を説明する
- [document-review profile](reference/document-review-report-v1.md)は現在のbounded
  Task Profileを定義する
- [Operations](operations.md)と[Installation](installation.md)は、architecture acceptance
  ではなくlauncher behaviorとsetupを説明する

実装済みbehaviorの正本はsource codeである。公開supportとEvidence claimは、support
文書が識別するfixed profileとrecordの範囲でのみ正本となる。historical designと
acceptance資料は本Architectureの入力であるが、current sourceを上書きせず、current
profileのscopeも拡張しない。
