# Transition Strategies

Yohakuでは、Agentがtaskを継続するcontextを切り替える処理を **Context Transition**
と総称する。Transition Strategyは、一つのsource contextをどのようにtarget context
へ移し、どのRuntime固有Evidenceで遷移を証明するかを定める。CompactionはStrategy
の一系統であり、それ自体がアーキテクチャの目的ではない。

本書は、Transition Strategyのtaxonomyと、各方式に共通するsemanticsを所有する。
[Architecture](architecture.md)はcomponent責務とtrust boundaryを所有する。
[Runtime Mapping](runtime-mapping.md)はfixed profileの事実、native primitive、実装状態、
Known Limitationsを所有する。[Evidence Model](evidence-model.md)はEvidence provenance、
CoverageProfile、Capability Verdict、非継承規則を所有する。

Strategy contractはRuntime Support Profileの代わりにならない。固定したRuntime、
version、surface、backend、owner構成が、trigger、completion proof、handoff、receipt、
fresh observation、continuation、failure behaviorを実装している場合に限り、その
Strategyを利用できる。文書に記載しただけではcapabilityは成立しない。

## Context Transitionの共通contract

ProactiveなStrategyは、Runtime eventが異なっても次の安全順序に従う。

```text
verified semantic and execution boundary
    → durable current checkpoint
    → revision-bound one-shot authority
    → Runtime固有のStrategy trigger
    → Strategy固有のcompletion proof
    → durable handoff delivery
    → explicit correlated receipt
    → current task stateのfresh observation
    → 未完了workだけを継続
    → task固有のassessment
    → RESUME_VERIFIED
```

現在のCoreは、transition部分の共通state名として`ROLLOVER_AUTHORIZED`、
`ROLLOVER_REQUESTED`、`ROLLOVER_OBSERVED`を使う。これらは互換性のために残す実装
語彙である。in-place compactionが新しいRuntime sessionを作るという意味ではなく、
fresh-contextやsession migrationが実装済みという意味でもない。

各Strategyでは、次の事実を分けて扱う。

- **source context**: transition前にcurrent workとrevisionを観測したcontext
- **target context**: Agentが実際にtaskを継続するcontext
- **generation and identity**: 一つのattemptを結び付けるRuntime-native identity、Yohaku
  Core identity、host-local correlation identity。Core / host-local IDをRuntime-nativeと
  扱わない
- **durable state**: transient process stateを失っても残るcheckpointとhandoff
- **completion**: Runtimeが要求を受理したことではなく、要求したtransitionを実行
  したことを示すproof
- **delivery and receipt**: recovery dataを提示したEvidenceと、対象continuationが受け
  取ったEvidence
- **fresh observation**: old checkpointの再生ではなく、transition後に取得したcurrent
  state
- **resume correctness**: stale effectやduplicate effectを生じさせず、未完了workだけを
  継続したことを示すtask固有proof

Model self-report、tool returnの成功、request acknowledgement、handoff delivery、
receipt、old checkpointのいずれも、それ単体で後続段階のproofにはならない。

## Taxonomyと現在の状態

| Strategy | Source → target | Triggerの種類 | 現在のYohakuでの状態 |
|---|---|---|---|
| Manual In-place Compaction | 一つのowned Runtime session / context → 同じsession / contextをcompactした形 | verification後に、Yohaku / host / operatorがRuntime-native compact / compress requestを一つ明示的に発行する | **Bounded profileだけに実装済み**。Codex historical Referenceと`document-review-report-v1`、Hermes H-CLI-01 adapter、Claude C-CLI completion / recovery variantに実装がある。Evidenceとaccepted endpointはprofileごとに異なる。 |
| Native Automatic Compaction | active Runtime context → 同じactive contextをRuntimeがcompactした形 | Runtime自身のautomatic threshold / policyが、Yohakuのproactive requestより先に、または独立して発火する | historical Codex Reference Scenario Gだけに **bounded emergency-recovery implementation** がある。通常のproactive成功経路ではない。他profileは`NOT_RUN`または`UNIMPLEMENTED`。 |
| Fresh-context Rollover | 既存context / thread → 新しく作成した空、または最小限に初期化したcontext / thread | Yohaku / hostが新しいRuntime contextを要求し、durable handoffを移す | **Design concept only**。Codex experimental `new_context`は測定済み構成で`UNSUPPORTED`。full pathを実装したaccepted current Runtime profileはない。 |
| Session Migration | 既存Runtime session / owner（同一hostの場合を含む）→ 別session / owner（別hostまたは別Runtimeの場合を含む） | Yohakuがexport、destination作成、delivery、receipt、continuationを調整する | **Future / Deferred**。general implementation、live Evidence、accepted profileはいずれも存在しない。 |

ここでいう「実装済み」は、少なくとも一つのbounded profileにコードが存在することを
表す。StrategyがRuntime間で共有されていることや、`RESUME_VERIFIED`までの全endpoint
にlive Evidenceがあることは意味しない。差はRuntime Mappingに記録する。

## Manual In-place Compaction

### 目的とidentity

Manual In-place Compactionは、owned session / taskの関係を保ったまま、Runtimeの
active contextを縮約または再構成する。Yohakuはcompressorを実装しない。安全な
boundaryを検証し、Runtime-native operationを呼び出し、fixed profileのcontractで
lifecycleを検証する。

| 契約項目 | Strategyの意味 |
|---|---|
| 目的 | verified task boundaryと制御されたcontinuationを保ちながら、context capacityが不足する前にproactiveに余地を確保する。 |
| Source context | 関係するactive / pending workがsettleし、boundaryが`VERIFIED`になったowned Runtime session / context。 |
| Target context | 同じlogical session内でRuntimeが生成したcompacted / compressed representation。Runtime内部で新しいstorage recordが作られても、それだけでfresh-context rolloverにはならない。 |
| Trigger | checkpointがdurableでone-shot authorityがcurrentであることを確認した後、fixed host / operatorがmanual compact / compress requestを一つ発行する。 |
| Generation / identity | 一つのCore generationとrequestに、profileが実際に提供する最強のnative session / turn / request identityを組み合わせる。native generation identityがなければ制限として記録し、host-local IDから捏造しない。 |
| Durable state | dispatch前のcurrent Yohaku checkpointと、completed request / continuation identityに結び付いたdurable handoff。Runtime-native historyとは分ける。 |
| Completion proof | correlated lifecycle evidenceやstorage evidenceを組み合わせたRuntime固有proof。Codex、Hermes、Claudeは異なるpredicateを使う。request ACK、engine return、一つのHook / eventだけでは不十分。 |
| Handoff | durable stateからcompleted request専用に作成する。Historical contextはdataとしてdeliveryし、authorityとして復元しない。 |
| Receipt | handoffとcontinuationにcorrelateしたprofile固有のexplicit receipt。receiptはfresh stateもresume correctnessも証明しない。 |
| Fresh observation | transition後にtrusted hostがcurrent Runtime / task / workspace stateを読み、current revisionと比較する。 |
| Continuation | owned hostが、fixed Task Profileまたはbounded scenarioで許可された未完了workだけをadmitする。 |
| Failure / timeout | Pre-dispatchのstale stateは拒否またはinvalidateする。dispatch / completionがuncertainなら`AMBIGUOUS`、completion後のrecoveryが失敗したら`RECOVERY_REQUIRED`とする。Task contract違反は`REFUSED`になり得る。 |
| Retry policy | authorityをconsumeした後、またはdispatchされた可能性がある場合はblind retryしない。fixed profileが許す場合に限り、reconciliationまたは新しいverified boundaryからnew requestを作る。 |
| Late completion | profileがlive owner / correlationを保持し、reconciliationを明示的に定義する場合だけ受理できる。bounded adapterによってはtimeout時にownerを永久にcloseし、以後のlate evidenceを拒否する。 |
| Duplicate | exact duplicate evidenceをidempotentに扱えるのはadapterが定義した場合だけである。二つ目のcompact requestを安全とは推定せず、one-shot profileでは通常拒否する。 |
| Restart | Core persistenceから自動継承しない。historical Codexにはlimited manual restart behaviorがある。accepted Hermes / Claude adapter profileはtransition restartを成立させていない。 |
| Current implementation status | Runtime-specific / bounded。三Runtimeに共通するneutral trigger、transport、lifecycle map、receipt、continuation、restart implementationはない。 |

fixed completionの例は[RoleからRuntime primitiveへの対応](runtime-mapping.md#roleからruntime-primitiveへの対応)
にまとめる。正確なevent orderはRuntime reference pageが所有する。
共通contractが要求するのは「fixed profileごとにRuntime固有completion proofを定義し、
不足時に進めない」ことまでである。Codexの三要素、Hermesのhost / DB readback、Claudeの
Hook windowとcollector closureを、一つの共通event列や同一predicateへ変換しない。

### Proactive成功の条件

Manual compactionをproactive成功と呼べるのは、Yohakuがboundaryをverifyし、current
checkpointをdurableにcommitしてからmanual Runtime requestをauthorizeした場合だけ
である。Runtimeが先にcompactした場合は、後述するNative Automatic Compactionの
recovery contractで扱う。後からhandoffやcontinuationが成功しても、先行raceを
proactive transitionへ読み替えない。

## Native Automatic Compaction

### 目的とemergency recovery

Native Automatic Compactionは、Runtime自身のthresholdやpolicyによってcompactionが
始まる場合を扱う。Yohakuがcurrent proactive checkpointをcommitする前に発火すると、
通常のauthorization順序は失われる。この場合の目的はbounded emergency recoveryで
あり、通常のproactive成功ではない。

| 契約項目 | Strategyの意味 |
|---|---|
| 目的 | Runtimeがproactive transition protocolより先に開始したcompactionを検出・照合し、fixed profileに十分なEvidenceがある範囲で安全にrecoveryする。 |
| Source context | native compaction開始時のactive Runtime turn / context。最後にcommitしたYohaku checkpointより新しいworkを含む可能性がある。 |
| Target context | 同じactive native context / turnをRuntimeがcompactした形。 |
| Trigger | Runtime自身のautomatic threshold / policy。Yohakuはこのnative triggerに対するpre-dispatch leaseを持たない。 |
| Generation / identity | native active-turn / session evidenceとhost recovery attachment。native eventをYohaku manual requestとして扱わない。 |
| Durable state | old checkpointはstale historical dataのままである。新しく観測した事実をbounded emergency deltaとして別に記録できるが、verified checkpointやarchive entryへ昇格させない。 |
| Completion proof | completed compactionをpre-eventやpartial Hookから区別できるStrategy固有native sequence。historical Codex Scenario Gではbounded correlated completion evidenceを要求した。 |
| Handoff | last verified durable stateと、明示的に区別したemergency observationをfixed profileの規則で組み合わせる。unverified deltaをverified task stateとして黙って扱わない。 |
| Receipt | emergency originであっても、delivery後にexplicit receiptを要求する。correlation条件を弱めない。 |
| Fresh observation | stored checkpointがstaleであるため、同じowned recovery pathでcurrent stateを必ず読み直す。 |
| Continuation | fresh observationで未解決と確認したworkだけを継続する。proactive leaseを再構成しない。 |
| Failure / timeout | completion、delivery、receipt、current-state evidenceの欠落・競合は`AMBIGUOUS`または`RECOVERY_REQUIRED`とし、通常作業を止める。 |
| Retry policy | native completionがuncertainという理由だけで別のcompactをtriggerしない。先にcorrelated evidenceを照合する。blind retryすると二重compactになる可能性がある。 |
| Late completion | fixed adapterがnative session / turnを引き続き所有し、late evidenceを明示的に扱える場合だけreconcileできる。それ以外はclosed / ambiguousのままとする。 |
| Duplicate | duplicate native evidenceから二つ目のhandoffやcontinuationを作らない。二回目のnative compactionは別transitionであり、固有のsupported contractが必要となる。 |
| Restart | historical Codex native-race recoveryのrestartは`UNSUPPORTED`。他のaccepted profileにも実装はない。 |
| Current implementation status | historical Codex Reference Scenario Gに限定する。native auto compact一回、foreground Bash operation一つ、active turn一つ、same-turn recoveryだけを扱う。general native-auto supportは未実装。 |

Scenario Gが示したのは、historical fixed profile内のemergency path一件である。
proactive trigger control、general native-auto Strategy、別Runtime、restart、parallel work、
repeated compaction、current Codex versionは実証していない。

## Fresh-context Rollover

### Design contract

Fresh-context Rolloverは、新しいRuntime context / threadを作り、同じlogical taskを
そこで再開する。in-place compactionと違い、sourceとtargetを同じRuntimeが所有して
いても、targetがsource contextを継承したとは扱えない。Yohakuはdestination identity
を証明し、handoffをdeliveryし、continuation前にtargetのcurrent stateを観測する
必要がある。

| 契約項目 | Strategyの意味 |
|---|---|
| 目的 | in-place compactionが利用できない、不適切、または不十分な場合に、新しいcontextで同じtaskを継続する。 |
| Source context | verifyとcheckpoint commitが完了したowned source context / thread。 |
| Target context | 同じfixed Runtime profile内で作成した、sourceとは別のfresh context / thread。 |
| Trigger | source checkpoint commitとdestination policy checkの後、Yohaku / hostがdestination作成を要求する。 |
| Generation / identity | source native identity、new destination native identity、一つのCore generation、明示的なsource-to-target binding。host-local aliasはどちらのnative identityの代わりにもならない。 |
| Durable state | source checkpoint、source-to-target migration record、destination-bound handoffを、transient host state消失後も保持する必要がある。 |
| Completion proof | create requestのACKだけでなく、意図したfresh destinationが作成され、後続eventがそのdestinationに属することを示すEvidence。 |
| Handoff | 明示的なidempotencyとsingle-admission policyの下でdestination recovery pathへdeliveryする。一般的なexactly-once保証は仮定しない。 |
| Receipt | handoffとgenerationにcorrelateしたexplicit destination-bound receipt。 |
| Fresh observation | destinationのcurrent stateに対する最初のtrusted observationと、fresh task / workspace read。 |
| Continuation | receiptとreconciliationの後に、destination ownerが未完了workだけをadmitする。sourceには通常continuationのauthorityを残さない。 |
| Failure / timeout | destination creationが不明なら`AMBIGUOUS`、destinationは既知だがdelivery / receiptが未完了なら`RECOVERY_REQUIRED`。retry前にsourceと存在し得るdestinationの両方を照合する。 |
| Retry policy | 二つ目のdestinationをblindに作成しない。最初のdestinationが存在しないと証明するか、supported protocolで安全にadopt / retireできる場合だけretryする。 |
| Late completion | late destination-creation resultには、明示的なadoption / retirement ruleとdestination identity proofが必要である。現在は未実装。 |
| Duplicate | duplicate destination、delivery、receipt、continuationには、明示的なidempotencyとsingle-owner ruleが必要である。現在はacceptedではない。 |
| Restart | durable source / destination ownership reconciliationが必要となる。`UNIMPLEMENTED`。 |
| Current implementation status | **Design concept only**。Codex experimental `new_context`は`UNSUPPORTED`。HermesとClaudeにはaccepted fresh-context implementationもEvidenceもない。 |

このcategoryにManual In-place CompactionのEvidenceを継承しない。Coreのcheckpoint型や
handoff型を共有しても、destination creation、delivery、single ownership、continuation
は証明できない。

## Session Migration

### Deferred contract

Session Migrationは、logical taskを別のRuntime session、owner、host、またはRuntime
familyへ移す。destinationではnative identity、storage、tool、model、event lifecycle、
archive semanticsが異なる可能性があり、四方式の中でtrust / compatibility surfaceが
最も広い。

| 契約項目 | Strategyの意味 |
|---|---|
| 目的 | durable task state、provenance、一つのactive continuation authorityを保ちながら、verified taskを別session / ownerへ移す。 |
| Source context | durableでexport可能なcheckpointを持つ、verifiedかつquiescentなsource session。 |
| Target context | profileとTask Profileのcompatibilityを明示的に確認した別destination session。 |
| Trigger | migration coordinatorがadmitted source workをgateし、destinationを作成または選択してdurable dataを移し、ownershipを引き渡す。これはunobserved workのatomic freezeを意味しない。 |
| Generation / identity | source / destination native identity、migration generation、host identity、durable ownership-transfer record。似た文字列からcross-Runtime identityの同一性を推定しない。 |
| Durable state | versioned portable checkpoint / handoffとcompatibility / provenance metadata。現在のCodex型snapshotはportable migration formatではない。 |
| Completion proof | destination creationとownership acceptance、source retirement、delivery / receipt、両trust domainのcurrent-state reconciliation。 |
| Handoff | 明示的なschemaとredaction policyでexportし、destination profileへdurableに結び付ける。 |
| Receipt | trusted source / destination correlationを持つdestination-nativeまたはhost-mediated explicit receipt。 |
| Fresh observation | destination task / workspace observationと、sourceがstale authorityで並行継続できないことのproof。 |
| Continuation | ownership transfer完了後のdestination ownerを一つに限定する。これは目標contractであり、現在のexactly-once保証ではない。 |
| Failure / timeout | source retirementの一部完了、destination creation不明、transfer不明、split ownershipにはmigration固有のrecovery stateが必要となる。 |
| Retry policy | general policyはない。安全な設計では、retry前にsourceとdestinationの両方をreconcileする必要がある。 |
| Late completion | adoption、fencing、tombstone protocolは未実装。 |
| Duplicate | duplicate destinationやsplit-brainを防ぐprotocolは未実装。 |
| Restart | portable restart / reconciliation implementationはない。 |
| Current implementation status | **Future / Deferred**。shared migration coordinator、portable snapshot、compatibility negotiation、accepted Runtime profile、live Evidence、Verdictはいずれも存在しない。 |

新しいRuntime processの起動、checkpoint fileのcopy、transcriptのreplay、handoffのdelivery
だけではSession Migrationは成立しない。source retirement、destination identity、
receipt、freshness、ownership、resume verificationが不足するためである。

## Proactive transitionとemergency recovery

両経路ではauthorizationとEvidenceの意味が異なる。

```text
Proactive
  current observation
    → VERIFIED boundary
    → current durable checkpoint
    → one-shot authority
    → host-triggered Strategy
    → completion and recovery verification

Emergency after native auto compact
  current checkpointより先にRuntime-triggered compaction
    → proactive順序の喪失を検出
    → old checkpointをstaleとして保持
    → bounded emergency observationを別recordへ保存
    → native completionを証明
    → fresh current-state recoveryを要求
    → old authorityを再構成しない
```

Emergency pathをproactive transition成功として計上しない。反対に、emergency pathが
未完了でも、その事実だけで別に測定したmanual proactive pathを失敗とはしない。

## Strategy間で共通するfailure semantics

公開するoutcome語彙では、異なるhazardを次のように分ける。

| 条件 | 意味と動作 |
|---|---|
| `DEFERRED` | 関係するactive / pending workがboundary verificationを妨げている。通常作業へ戻り、new candidateを提案する。transition requestはauthorizeされていない。 |
| `INVALIDATED` | Pre-dispatch boundary、revision、checkpoint、workspace、leaseがstaleである。current stateから再検証する。 |
| `AMBIGUOUS` | dispatchまたはcompletionが発生した可能性はあるが、まだ証明できない。correlated evidenceを照合するまで通常作業とblind retryを止める。 |
| `RECOVERY_REQUIRED` | transition completionは既知またはretainedだが、delivery、receipt、fresh observation、continuation、assessmentを安全に完了できない。old authorityを復元しない。 |
| `REFUSED` | fixed Task Profileまたはoperation gateが、known-disallowed、stale、duplicate、undeclared workをuncertain side effect前に拒否した。Core stateではない。 |

Strategyはlate-eventやretry behaviorをさらに狭く定義できる。ただし、`AMBIGUOUS`を
「実行されなかった」とみなしたり、unobserved external side effectを安全にretry可能
と扱ったりはできない。

## Strategy境界へのEvidence規則の適用

[Evidence Model](evidence-model.md)で定める非継承規則を、Transition Strategyには次の
ように適用する。

- Manual In-place CompactionとNative Automatic Compaction
- in-place compaction、Fresh-context Rollover、Session Migration
- Codex、Hermes、Claude Code
- Runtime version、CLI / API surface、OS、owner model
- provider、backend、model、context configuration、Hook configuration
- lifecycle-only、transition、Task Profile

したがって、次の等式は成立しない。

- Codex manual compact `PASS` = native-auto `PASS`
- Claude local Ollama `PASS` = Anthropic subscription `PASS`
- Hermes H-CLI-01 `PASS` = Hermes全体 `PASS`
- Runtime support = `document-review-report-v1`または他のTask Profile support

Strategy間で共有できるのは、authority前のdurability、freshness、one-shot dispatch、
ambiguity中のretry抑止、delivery / receiptの分離、resume verificationなどの安全
semanticsである。Lifecycle evidence、completion predicate、identity、Verdict、restart
claim、task assessmentは、matching fixed profileとretained Evidenceなしに共有しない。

## Runtime固有文書で確定する事項

本taxonomyでは、正確なnative event名、field mapping、timeout、configuration、event
orderの選択肢をRuntime reference pageへ委ねる。後続整理では、各pageで次を明示する。

- 必須native identity fieldとhost-local correlation
- completion predicate全体と合法なevent-order variation
- profileごとのtimeout closure、late-event reconciliation、duplicate handling、retry拒否
- Runtime-native storage readbackのauthorityと制限
- restart / reconnect ownership
- delivery / injectionとcontinuationのprimitive
- task-enabled profileのTrusted Observer / Task Assessor境界

各observationの記録、attribution、retention、CoverageProfileへの集約、Verdictへの
反映方法は[Evidence Model](evidence-model.md)に従い、本書のStrategy分離とprofile分離を
維持する。
