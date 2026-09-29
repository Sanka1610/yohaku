# Runtime Adapter Contract

本書は、新しいRuntime Adapter、または既存Runtimeの新しいSupport Profileを追加する際の
公開開発contractである。Adapterは、一つのfixed Runtime / version / surface / OSと一つの
Transition Strategyに属するRuntime固有primitiveを、Verified Context Transition Coreの
trusted callへ対応付ける。

共通化する対象は、安全なboundary、freshness、one-shot authority、ambiguity、handoff、
resume verificationなどのsemanticsである。Runtime event名、completion signalの数、receiptの
wire format、native storageを共通APIに見せることは本contractの目的ではない。Codex、Hermes、
Claude Code CLIの既存実装も、三Runtimeの最小公倍数となる完成済みplugin frameworkを構成して
いない。

Componentとtrust boundaryは[Architecture](../architecture.md)、Strategy taxonomyは
[Transition Strategies](../transition-strategies.md)、EvidenceとCapability Verdictは
[Evidence Model](../evidence-model.md)、保存とrestartは
[Storage and Recovery](../storage-and-recovery.md)を正本とする。本書は、それらを新しい
Runtime integrationへ適用するための責務と導入条件を定める。

## Contractの適用単位

Adapterの適用単位はRuntime family全体ではなく、固定したSupport Profileである。同じRuntimeでも、
version、surface、OS、provider、backend、model、Transition Strategy、Hook構成、tool集合、owner条件が
異なれば別profileとして扱う。既存profileに新しいStrategyやtool coverageを追加する場合も、Evidenceを
自動継承せず、新しいclaimとしてreviewする。

Adapterのsourceが存在するだけではRuntime supportは成立しない。少なくとも次の三点を別々に示す。

- **Implementation**: 対象profileのevent、identity、I/O、failure semanticsを実装した範囲
- **Acceptance**: bounded live workflowで観測し、accepted endpointまで到達した範囲
- **Support claim**: Evidence、Coverage、Known Limitations、maturity / release判断をreviewした範囲

Probe、local / synthetic test、live acceptance、Field Evidenceも同じ評価ではない。ある段階の成功を、
後の段階の`PASS`へ読み替えない。

## Shared CoreとRuntime Adapterの境界

Shared Coreは、Runtimeから独立して表現できる安全semanticsを所有する。Adapterは、そのsemanticsを
判断するためのRuntime固有観測を生成し、Coreの決定に従ってRuntime I/Oを一回だけ実行する。

| Shared Coreの責務 | Runtime Adapterの責務 |
|---|---|
| Candidateとverified semantic / execution boundaryを区別する | Runtime / profileで利用できるlifecycle eventとtask observationを取得する |
| Intent / execution / control / workspace revisionとfreshnessを検査する | どのnative mutation、result、workspace changeを観測できるか定義する |
| Checkpoint commit前にtransition authorityを発行しない | Profile固有storageへcheckpointをcommitし、必要なreadbackを行う |
| Boundary、checkpoint、revision、workspace、generationへ結び付くone-shot leaseを発行・consumeする | LeaseをRuntime requestへ一回だけ対応付け、送信直前にcurrent stateを再検査する |
| Dispatch、completion、side effectが不明なら`AMBIGUOUS`として通常作業とblind retryを止める | Timeout、transport error、late event、duplicate、observation lossをRuntime固有に検出・相関する |
| Durable handoff、deliveryとreceiptの分離、fresh observation、resume gateを要求する | HandoffをRuntimeへdelivery / injectionし、profile固有のexplicit receiptとfresh readを観測する |
| Duplicate completion / receiptから新しいauthorityを作らない | Native duplicateを同定し、二重dispatchや二重continuationを起こさない |
| `ResumeProof`のidentity、freshness、nonduplication、same-task整合性を検査する | Trusted Observer / Task Assessorからprofileに必要な観測とproofを受け取る |
| Evidence referenceとCoverage contractを必須にする | Profile固有Evidenceを、native / host-local / Core identityへ相関して記録する |

Coreは外部I/Oを行わず、Runtime eventの真正性を独力で証明しない。Adapterを含むtrusted hostが、
native eventのcapture、順序、coverage、correlationを正しく報告する必要がある。一方、AdapterはCoreの
lease、checkpoint順序、ambiguity gate、resume gateを独自判断で省略しない。

## Adapterが定義する責務

新しいAdapterまたはprofileは、次の項目を実装し、Runtime canonicalに対応関係と制限を記載する。
未実装の項目は別Runtimeのeventやhost-local IDで補わず、`UNIMPLEMENTED`、`UNSUPPORTED`、`NOT_RUN`、
`UNKNOWN`のいずれかとして範囲を固定する。

| 項目 | Adapterが定義する内容 |
|---|---|
| Lifecycle event mapping | Native eventの発生源、順序、terminal条件、欠落時の扱いと、どのCore callへ対応付けるか |
| Runtime-native identity | Runtimeが所有・発行するsession、thread、turn、tool、itemなどのidentityと、そのauthority |
| Host-local correlation identity | Native observationとCore requestを一つのowner内で対応付けるattachment、sequence、run、nonceなど |
| Work taxonomy | Profileがadmitするtool / operation、state-changing / read-only区分、foreground / background / delegated workの扱い |
| Work observation | `admitted`、`active`、`pending`、`incorporated`、`observation lost / unknown`の判定条件 |
| Work admission / gate | Barrier中に拒否するoperation、gateを通らないsurface、deny / failure / timeout時のenforcement範囲 |
| Transition trigger | Operator、host、Runtimeのどれが、何を、どのone-shot authorityで開始するか |
| Completion proof | Requestとnative lifecycle / storageを相関し、requested transitionが完了したと判断するpredicate |
| Runtime-native storage readback | 何を独立して読み戻し、どのidentity / revision / contentを比較するか |
| Handoff delivery / injection | Handoffをどのtarget contextへ、何回、どのtransport evidence付きで提示するか |
| Explicit receipt | Targetがhandoffを受け取ったことを、deliveryや後続workと別にどう確認するか |
| Fresh current-state observation | Receipt後にどのRuntime / task / workspace stateを新しく読み、stalenessをどう検出するか |
| Continuation | Continuation permitをどのnative / host-local dispatchへ一回だけ対応付けるか |
| Visible-turn extraction | 完了済みvisible turnをどのauthorityで選択・redactし、Runtime-native historyから区別するか |
| Failure handling | Runtime固有のrefusal、defer、invalidation、timeout、uncertain result、late、duplicate、restartの扱い |

Visible-turn extractionを実装しないprofileは、その欠落を明記する。Runtime-native transcript、history、
database rowをYohaku archiveへ自動変換しない。Extraction、selection、redaction、archive commit、retrievalは、
transition completionとは別のcapabilityである。

## 共通化してよいsemantics

新しいRuntime integrationは、次のsemanticsを共有できる。共有とは、同じ安全条件を満たすことであり、
同じevent名やwire representationを使うことではない。

- Semantic boundary gate: Model / Agentの提案はcandidateであり、trusted observationが揃うまで
  verified boundaryにしない。
- Revision / freshness: Historical observationとcurrent observationを区別し、stale evidenceから
  authorityを作らない。
- Checkpoint-before-authority: Current checkpointのdurable commit後にだけtransitionをauthorizeする。
- One-shot lease: 一つのboundary、checkpoint、revision集合、workspace、generationに一つのrequestを
  結び付ける。
- Ambiguity handling: Side effectの可能性を除外できないunknown outcomeでは通常作業を停止する。
- No blind retry: Consumed authority、unknown dispatch、unknown write、unknown continuationを再送しない。
- Handoff semantics: Historical dataをinstructionやpermissionへ昇格させず、一つのcompleted requestと
  continuationへ相関する。
- Delivery / receipt separation: Transportへのdeliveryをtargetのreceiptとみなさない。
- Fresh observation requirement: Receipt後にcurrent task / Runtime / workspace stateを読み直す。
- Nonduplication: Exact duplicate completion、receipt、continuationから新しいeffectを作らない。
- `ResumeProof` / resume verification: Receipt、freshness、未解決work、same-task continuation、
  nonduplication、task assessmentが揃ってから`RESUME_VERIFIED`とする。
- Evidence / Coverage contract: Implementation、観測範囲、accepted endpoint、未測定範囲を分ける。

次の事項は共通化しない。

- Runtime固有event名と、その順序・欠落条件
- Completion signalの種類と必要数
- Receipt tool、nonce、ACKなどのwire format
- Runtime-native session / transcript / history / database schema
- Native storageのretention、reconnect、compaction後の表現
- Runtime固有trigger、transport、Hook enforcement、continuation dispatch
- Runtime固有restart / reconnect codec

一つの共通interfaceへ値を詰め替えられても、authorityやacceptanceが同一になるわけではない。
情報を落とす正規化によって、native identityやfailure stateを捏造してはならない。

## Identity contract

### 三種類のidentity

すべてのAdapterは、identityを次の三種類に分類する。

| 分類 | Owner | Authority |
|---|---|---|
| Runtime-native identity | 対象Runtime | Native session、thread、turn、tool、item、requestなど、Runtime内の対象を識別する。Runtimeが提供しないidentityをhostが補ってnativeと呼ばない |
| Yohaku Core identity | Verified Context Transition Coreとdurable Yohaku record | Boundary、checkpoint、lease、request、generation、handoff、continuation permit、revisionを識別し、Core state transitionとdeduplicationを制約する |
| Host-local correlation identity | Adapterを所有するtrusted host / collector / runner | Native observationとCore identityを、固定ownerとprofile内で対応付ける。Runtime authorityにもCore authorityにもならない |

三種類の値がすべて`str`であり、偶然同じ文字列でも、相互代入しない。たとえば、Core request IDを
native request IDとして記録せず、collector attachment IDをnative session IDの欠落補完に使わず、native
turn IDからCore continuation permitを再構成しない。対応関係はprofileのcorrelation ruleとして明示し、
owner、capture時点、generation、sequence、freshnessを検査する。

### Identity inventory

Support Profileには、少なくとも次のinventoryを置く。Runtimeに該当identityがない場合は「なし」と記載し、
別分類の値で欄を埋めない。

| Identity | Ownerを明示する対象 | Authorityを明示する対象 |
|---|---|---|
| Session / thread | Native Runtimeか、Yohaku logical taskか、host ownerか | Eventとstorageの所属、source / target contextの区別 |
| Turn / item | Native lifecycleか、host dispatchか | Work、completion、continuationの順序とterminal条件 |
| Tool / operation | Native Runtime、Adapter、Task Profileのどれか | Admission、effect、result、duplicate判定 |
| Request | Native transport request、Core transition request、host-local requestのどれか | Acceptanceとcompletionの相関、retry禁止の範囲 |
| Generation | Native generation、Core rollover generation、host-local attemptのどれか | Stale / late eventの排除。欠落するnative generationをCore generationで偽装しない |
| Attachment / collector sequence | 通常はtrusted host | Event capture windowとclosure。Runtime-native identityにはならない |
| Continuation | Native turn / input、Core permit、host dispatchのどれか | Target context、one-shot send、same-task binding |
| Handoff | Yohaku durable documentとdelivery instance | Completed request、checkpoint、target continuation、receiptの対応 |

Identity強度もprofileの制約である。Fresh exclusive sessionとserialized ownerによって曖昧性を減らす
profileは、その運用前提をSupport Profileへ含める。Native IDが不足するprofileを、同名fieldだけを
揃えて強いidentity profileとして扱わない。

## Work observation / admission contract

Adapterは、profileが対象とするwork planeについて次の状態を判定する。これらは共通の安全語彙であり、
全Runtimeへ適用できる共有enumや単一ledgerを要求しない。

| 状態 | Profileが定義する判定 |
|---|---|
| `admitted` | Fixed Support Profileと、Task Profileがある場合はその両方が許可し、対象gateを通過したoperation。提案またはtool callの出現だけではadmissionにならない |
| `active` | Admitted operationをdispatchし、profileが定めるterminal outcomeとresult identityをまだ完全には観測していない |
| `pending` | Handler / provider / toolのresultは観測したが、必要なRuntime inputまたはcurrent task stateへ取り込まれたことをまだ確認していない |
| `incorporated` | Exact result identity / hashが後続native inputに含まれた、またはTrusted ObserverがTask Profile固有effectをfreshに確認した状態 |
| `observation lost / unknown` | Required callback、terminal event、result identity、sequence、readbackの欠落・競合により、上記いずれかを確定できない状態 |

`incorporated`は、modelが結果の意味を理解したことを一般に証明しない。Native outgoing requestへの
exact result取込、fixture effect、Task Observerのfresh readなど、profileが受入れた機械的条件だけを表す。
Semantic incorporationを評価しない場合は`NOT_ASSESSED`のままにする。

Work gateのcoverageも固定する。対象gateが一つのtool dispatcherだけを制御する場合、別client、background
process、subagent、external writer、別tool surfaceまで停止したとは扱わない。`active=0`、`pending=0`は、
宣言した観測面に対する結果であり、Runtime-wide atomic barrierを意味しない。Observationが失われた状態で
quiescenceを推定せず、`AMBIGUOUS`またはprofile固有のrecovery停止とする。

## Transition Strategy contract

新しいAdapterまたはprofileは、採用するStrategyを一つ明示する。

- Manual In-place Compaction
- Native Automatic Compaction
- Fresh-context Rollover
- Session Migration
- その他のFuture Strategy

Future Strategyには、source / target context、trigger、identity、durable state、completion、delivery、
receipt、fresh observation、continuation、failure / retry、late / duplicate、restartを新しく定義する。
既存Strategyに似ているという理由だけで、既存Evidenceやaccepted endpointを継承しない。

Strategyごとにsourceとtargetの関係が違う。In-place compactionのsame-session Evidenceはfresh contextの
作成を証明せず、fresh-context rolloverのdestination receiptはsource retirementを必要とするsession
migrationのproofにならない。同じCore checkpoint型やhandoff型を使っても、Strategy-specific claimは
別々にreviewする。

## Completion Policy contract

新しいtransition profileは、Runtime固有completion proofを定義する。Completion proofは、要求した
transitionが対象Runtimeで完了したことを、request、native identity、generation、ordering、storage
readbackなどから判定するpredicateである。

次の結果はcompletionではない。

- Request acceptance。RPC ACKやcommand受理は、処理開始以前に返る場合がある。
- Provider / backend success。Model responseやcompressor returnは、Runtime hostへの反映とdurable readbackを
  証明しない。
- Model self-report。Assistantの「完了した」という出力はtrusted lifecycle Evidenceではない。
- 一つのHook、counter、row、process exit。Profileが要求する他の相関条件を補わない。

Requestをdispatchした可能性があり、completion proofが不足、欠落、競合、または不一致なら
`AMBIGUOUS`とする。通常作業、handoff作成、blind retryへ進まない。Late Evidenceは、保存済みrequest、
native session / thread / turn、Core generation、host-local correlationへ一意に対応し、profileがlate
reconciliationを定義した場合だけ再照合できる。Timeout時にownerをcloseするprofileは、late eventを
受理してownerを再開しない。

Exact duplicate completionはidempotentなno-opとして扱い、二つ目のhandoff、continuation permit、
continuation dispatchを作らない。異なるnative operationを同じcompletionのduplicateと推定することも、
同じeventを新しいgenerationのcompletionへ転用することも認めない。

### 現行三Runtimeの比較例

| Profile固有実装 | Completion proofの要点 | 単独では不足するもの |
|---|---|---|
| Codex manual | Correlated compaction item completion、successful `PostCompact`、bound compact turnのterminal completion | RPC `{}`、`item/started`、`PostCompact`単独、assistant self-report |
| Hermes H-CLI-01 | Host historyの変化、独立した`SessionDB` readback、host / DB payload hashとcountの一致、archived row、exact request / session correlation | Engine / compressor return、`compression_count=1`、provider success、host historyだけ、DB rowだけ |
| Claude Code CLI manual | Fresh exclusive sessionで閉じたcollector window、correlated `PreCompact(manual)`、`PostCompact(manual)`、`SessionStart(compact)`、transport successとclosure | CLI result、process exit、各Hook単独、model self-report |

この表は共通event taxonomyを定義しない。必要signal数、相互順序、storage readback、closureはprofileごとに
異なる。現行shared seamは、bindingとeventを検証し、蓄積Evidenceからpredicateを評価する
[`CompletionPolicy`](../../src/yohaku/completion.py)である。PolicyはCore構築時に固定し、I/Oを行わない。
Trigger、event capture、transport、storage readbackはAdapter / hostが所有する。

## Storage contract

Adapterは、保存dataを次の四層に分ける。

| 層 | 内容 | Authorityと制限 |
|---|---|---|
| Shared durable primitives | Verified checkpoint value、append-only decision record、durable handoff、必要に応じたYohaku archive | Coreの関係とcommit順序を保持する。Current native state、lease、receipt、Capability Verdictを単独では証明しない |
| Runtime adapter metadata | Native event、collector sequence、request binding、delivery、receipt、readbackなどのprofile固有metadata | Correlation補助であり、Runtime-native storageや共通event schemaではない。Raw secret / transcriptを不用意に複製しない |
| Runtime-native storage | Runtime自身のsession、thread、history、transcript、database、provider / backend local state | Runtimeが所有する。Completion readbackに利用しても、Yohaku checkpoint、handoff、archiveへ自動変換しない |
| Runtime-specific restart codec | Durable Core / adapter recordとfresh native readを再照合し、安全に復元できるfieldと拒否条件 | Strategy / profile固有である。Codecがなければrestartは`UNSUPPORTED`または`UNIMPLEMENTED`とする |

Commit順序、integrity、poisoned handle、restart時に復元しないauthorityは
[Storage and Recovery](../storage-and-recovery.md)に従う。Adapter metadataがdurableでも、native
readbackとrestart codecがなければresumeできない。

現行persistenceはCodex Reference由来のschema-1と`CODEX_HOME`配下のnamespaceに依存する。
Hermes / Claude adapterが同じ`SessionStore`でcheckpointやhandoffを保存しても、Hermes / Claudeの
completion bindingをCodex restart schemaへ直列化したことにはならない。新Runtimeも自動的にはrestart
対応にならない。Neutral storage root、cross-Runtime codec、portable restartは現在未実装である。

## Handoff、receipt、continuation contract

Adapterは、recovery chainを次の別段階として実装する。

```text
handoff delivery / injection
    → explicit receipt
    → fresh current-state observation
    → continuation authorization
    → continuation
    → task-specific assessment
    → RESUME_VERIFIED
```

各段階は、直前の段階を含意しない。

- Deliveryは、target transportまたはnative inputへhandoffを提示したEvidenceである。Targetが受け取った
  ことや、意味を理解したことは証明しない。
- Explicit receiptは、handoffとtarget continuationに相関したacknowledgmentである。Delivery、printed
  ACK、assistant self-report、後続tool / workの成功をreceiptの代わりにしない。
- Fresh observationは、receipt後に取得したcurrent Runtime / task / workspace stateである。Checkpointの
  再生、completion readback、receipt payloadをfresh readの代わりにしない。
- Continuation authorizationは、fresh stateとunresolved workを再検証してからconsumeするCoreのone-shot
  permitである。Transport implementationそのものではない。
- Continuationは、target identityへ一回だけdispatchする未完了workである。Completed、uncertain、
  undeclared workを再実行しない。
- Assessmentは、Task ProfileのTrusted Observer / Task Assessorがsame-task、nonduplication、current
  effect、unresolved workを評価する段階である。
- `RESUME_VERIFIED`は、上記を相関した`ResumeProof`をCoreが受理したstateである。Content qualityや
  general semantic understandingまで自動的に評価しない。

Receiptのwire protocolはRuntime / profile固有でよい。Modelに不要なopaque identity一式を転記させる
必要はない。Claude Code CLIの`host-nonce-v1` profileでは、trusted hostがfull identity tupleを保持し、
modelにはhandoff固有のone-time nonceだけを返させる。Hostはnonceとnative session、owner、attachment、
request、generation、continuation、tool lifecycleを照合する。この設計は、model-visible fieldを減らせる
profile固有例であり、nonce方式を共通仕様にするものではない。

Receipt submissionやcontinuation dispatchのoutcomeが不明なら、nonceやpermitを再発行せず
`AMBIGUOUS`として停止する。Outcomeは確定しているが、後続のrecovery chainを安全に完了できない場合は
`RECOVERY_REQUIRED`とする。

## Failure semantics

Failure resultは、発生した層とside effectの可能性で区別する。

| Result | 主に返す層 | 条件 | 次の扱い |
|---|---|---|---|
| `REFUSED` | Task Profile、operation gate、Adapter precondition | Known-disallowed、undeclared、stale、duplicate operationをside effect前に拒否した | 理由を修正する。Core `State`とは区別し、拒否をcompletionやretry成功として扱わない |
| `DEFERRED` | Core boundary gate | Relevant active workまたはpending resultが残り、安全なboundaryを確定できない | Barrierを解除し、settle後のcurrent stateから新しいcandidateを提案する。Old candidate / leaseを再利用しない |
| `INVALIDATED` | Core pre-dispatch gate | Revision、workspace、checkpoint、lease、generationがdispatch前にstaleになった | Requestを送らず、current stateから再検証する |
| `AMBIGUOUS` | CoreとAdapterのuncertain-outcome path | Dispatch、completion、write、receipt、continuation、task side effectが発生した可能性はあるが証明できない | 通常作業とblind retryを停止し、正しく相関できるlate Evidenceだけをprofile規則で照合する |
| `RECOVERY_REQUIRED` | Core、storage owner、recovery chain | Completionまたはretained stateは既知だが、delivery、receipt、fresh observation、continuation、assessment、restartを安全に完了できない | Old authorityを復元せず、profile固有recoveryまたはmanual reviewへ進む |

Adapterが独自のnative error分類を持つ場合も、この上位semanticsとの対応を示す。たとえばHook failure、
provider error、transport timeoutをすべて`REFUSED`へ変換してはならない。Side effectがあり得るunknown stateは
`AMBIGUOUS`であり、blind retryすると二重transition、二重write、二重continuationを生じ得る。

Late Evidenceは、正しいownerとidentity chainへ一意にcorrelateできる場合だけ照合する。Foreign、missing、
conflicting identity、close後のunsupported eventから新しいauthorityを作らない。Duplicate suppressionの
keyもRuntime内で定義し、別Runtimeのevent名を共通keyとして使わない。

## Support ProfileとEvidence contract

新しいprofileは、少なくとも次を固定する。

- Runtime family、exact version / source revision、surface、OS
- Yohaku source revision、Adapter / collector / plugin revision
- Provider、backend、model、reasoning / contextなど結果に影響する構成
- Transition Strategy、trigger、source / target context
- Tool / work coverage、admission gate、foreground / background / delegationの扱い
- Owner、session exclusivity、Hook / permission、storage、workspaceの前提
- Accepted endpoint（Probe observation、`ROLLOVER_OBSERVED`、`RESUME_VERIFIED`など）
- Evidence provenance、Evidence level、retained recordへの安定した参照
- Known Limitations、`UNSUPPORTED` / `NOT_RUN` / `UNKNOWN`の範囲

Evidence Modelに従ってCapabilityごとのCoverageとVerdictをreviewする。Adapterの存在、source inspection、
unit test、synthetic fixture、RPC ACK、engine returnはlive Runtime acceptanceの代わりにならない。Bounded
workflowが`PASS`でも、overall CoverageProfileは`PARTIAL`のままになり得る。

Runtime / version / surface / OS、provider / backend / model、Strategy、Task Profile、tool集合、owner条件、
receipt方式、Adapter revisionのいずれかを越えてEvidenceを継承しない。Strategyが同じでも、completion、
storage、receipt、continuationの契約が異なるなら別claimである。

## 新しいRuntime / profileの追加手順

導入は、次の順で狭いclaimから進める。

1. **Documentation / source調査**
   Official documentationと対象versionのsourceから、native lifecycle、identity、storage、Hook、trigger、
   completion候補、failure挙動を特定する。不明事項をhost-local IDや別Runtimeのeventで補わない。
2. **Bounded Capability Probe**
   一つのfresh owner、限定したtool / work、固定provider / backend / modelで、必要なprimitiveを測定する。
   Probe instrumentationと製品Adapterを区別し、accepted endpointをProbe scope内に限定する。
3. **Support Profile固定**
   Runtime / version / surface / OS、構成、owner条件、tool集合、Evidence provenance、Known Limitationsを固定する。
4. **Transition Strategy選択**
   Source / target、trigger、completion、handoff、receipt、fresh observation、continuation、restartを一つの
   Strategy contractとして定義する。他StrategyのEvidenceを継承しない。
5. **Adapter実装**
   測定済みprimitiveだけをCore semanticsへ接続する。Lifecycle mapping、identity、work gate、completion
   policy、storage readback、recovery chainをprofileの範囲で実装する。
6. **Negative case**
   Missing / stale / mismatched identity、timeout、unknown dispatch、duplicate、late event、storage failure、
   receipt不一致、freshness changeを、side effectの可能性に応じてfail closedで分類する。
7. **Bounded live acceptance**
   Fixed profileを実Runtimeで実行し、実際に到達したendpointだけを記録する。Probeやlocal testの成功を
   product Adapter acceptanceへ移さない。
8. **Evidence review**
   Provenance、manifest、Coverage、negative result、Known Limitationsをreviewし、Capability Verdictを
   accepted scopeに限定して決める。
9. **Runtime canonical更新**
   `docs/runtimes/`の章順に従い、profile固有primitive、identity、storage、failure、Evidence、Verdictを
   公開する。成功runだけで既知failureを上書きしない。
10. **Maturity / release判断**
    Evidenceから自動昇格させず、Support Policyに従ってmaturityとrelease channelを別に判断する。

最初からgeneral Adapter、全tool coverage、cross-Runtime storage、general restart、Runtime-wide barrierを
実装しない。Bounded Probeで観測した最小surfaceを固定し、negative caseとlive acceptanceを通過した範囲だけを
拡張する。

## Task Profileとの境界

Runtime Adapterは、Runtime lifecycleとtransitionを安全に接続する。Taskの正しさ、入力の妥当性、出力の
品質は判定しない。

| Runtime Adapter / Support Profile | Task Profile |
|---|---|
| Native lifecycle、identity、transport、storage、tool eventを観測する | Input / output contractとlogical task identityを定義する |
| Profileのwork planeにoperationをadmitし、観測できる範囲を示す | Allowed work planeとtask固有operationを定義する |
| Runtime固有transition completion、delivery、receiptを確認する | Trusted Observerがcurrent task / workspace stateを生成する |
| Continuation permitを一回のRuntime dispatchへ対応付ける | Task Assessorがsame-task、nonduplication、mechanical completionを判定する |
| Runtime / Strategy failureを分類する | Task固有のrefusal、no-rerun、quality boundaryを定義する |

Task Profileは、少なくともinput / output contract、allowed work plane、Trusted Observer、Task Assessor、
quality boundaryを所有する。Runtime Adapterが`RESUME_VERIFIED`に必要なmechanical chainを接続できても、
文章、コード、事実、業務結果のqualityを自動判定しない。反対に、一つのTask Profileがacceptedでも、
Runtime family全体、別tool、別Strategyのsupportを推定しない。

## 現在の実装との差

本contractには、現在の実装から抽出したshared semanticsと、今後のAdapterが満たすべき公開要件が含まれる。
次の機能が完成済みであるとは扱わない。

| 項目 | 現在の実装 | 本contractから推定してはならないこと |
|---|---|---|
| Neutral Runtime Adapter interface | 未完成。Codex、Hermes、Claudeは別々のhost / adapter wiringを使う | 任意Runtimeを登録できるplugin API、共通launcher、共通event busがある |
| Completion seam | `CompletionPolicy`が比較的明確なshared seamである | Trigger、transport、storage readbackまでPolicyが抽象化する |
| Trigger / transport | Runtime / profile別の実装である | 共通dispatch protocolや同じrequest acceptance semanticsがある |
| Delivery / receipt / continuation | Runtime / bounded profile別の実装である | 共通wire format、exactly-once transport、全profileの`RESUME_VERIFIED`がある |
| Persistence / restart | Schema-1、`CODEX_HOME` namespace、`CompanionController`、restart codecがCodex寄りである | Hermes、Claude、新Runtimeが同じstoreからrestart / reconnectできる |
| Work observation | Codex ledger、Hermes / Claude / document reviewのbounded ledgerが別々にある | Universal work taxonomy、Runtime-wide atomic barrierがある |
| Task Profile | `document-review-report-v1`とfixture固有integrationがある | General Task Profile / Observer / Assessor registryがある |
| Visible-turn archive | Shared archive storeとCodex固有collectorがある | 全Runtimeのnative historyをextract / importできる |

したがって、本書は完成したplugin frameworkの利用説明ではない。新しいAdapterは、既存のshared Coreを
再利用しつつ、Runtime固有host、observation、transport、storage、recoveryをfixed profileとして実装・
検証する必要がある。Neutral interface、portable persistence、registryは、それぞれ別の設計変更と
acceptanceを必要とする。

## Adapter contract checklist

実装reviewでは、少なくとも次を確認する。

- [ ] Support ProfileとTransition Strategyが一意に固定されている
- [ ] Native / Core / host-local identityのownerとauthorityが分離されている
- [ ] Work taxonomyと`admitted` / `active` / `pending` / `incorporated` / unknownが定義されている
- [ ] Gateのcoverage外とRuntime-wide atomicityの欠如が記載されている
- [ ] Trigger前にcheckpoint、one-shot authority、final freshness checkがある
- [ ] Request acceptanceとcompletion proofが分離されている
- [ ] Runtime-native storage readbackとYohaku storageが分離されている
- [ ] Delivery、receipt、fresh observation、authorization、continuation、assessmentが別段階である
- [ ] Timeout、late、duplicate、unknown side effectでblind retryしない
- [ ] Restart codecがないprofileはrestart supportを主張していない
- [ ] Task correctnessとqualityをTask Profileへ委ねている
- [ ] Bounded live Evidence、Coverage、Verdict、Known Limitationsが同じscopeでreviewされている

Checklistへの適合は、live acceptance、Capability Verdict、maturity、release readinessを単独では
証明しない。各claimは固定Support ProfileのEvidenceで別に判断する。
