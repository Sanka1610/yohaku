# Runtime Adapter Contract

Adapterは、Runtime固有のlifecycle、identity、work observation、completion proofをShared Coreへ接続します。Profileには試した環境、実際のworkflowと結果、Known Limitationsを記載し、内部APIへ依存するhard requirementをtested configurationから区別します。

設計とtrust boundaryは[Architecture](../architecture.md)、保存とrestartは[Storage and Recovery](../storage-and-recovery.md)を参照してください。以下は既存の安全条件をadapterへ適用する契約であり、完成した共通plugin APIではありません。

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

### 相関に使うidentity

実装で使うidentityのownerとauthorityを説明する。Runtimeが提供しないidentityを
別分類の値で補わない。

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

共有seamは[`CompletionPolicy`](../../src/yohaku/completion.py)です。Policyはbindingと蓄積eventを評価し、trigger、transport、event capture、storage readbackはadapter / hostが所有します。具体的なpredicateは[Codex](../runtimes/codex.md)、[Hermes](../runtimes/hermes.md)、[Claude Code CLI](../runtimes/claude-code-cli.md)、[OpenCode](../runtimes/opencode.md)、[DSH](../runtimes/dsh.md)を参照してください。

DSHは同processのnative serviceへ[`dsh_host.mjs`](../../src/yohaku/dsh_host.mjs)から接続します。Python ownerへ渡す`observe` / `work` / `compact` / `project`のtransportはembedding hostが用意し、操作を直列化します。DSH binding / completionをschema-1 snapshot journalへ保存せず、既存checkpointとadapter固有decision recordだけを保存します。限定profileのcompletionとfresh projectionの条件は[DSH](../runtimes/dsh.md)を参照してください。

## Storage contract

Adapterは、保存dataを次の四層に分ける。

| 層 | 内容 | Authorityと制限 |
|---|---|---|
| Shared durable primitives | Verified checkpoint value、append-only decision record、durable handoff、必要に応じたYohaku archive | Coreの関係とcommit順序を保持する。Current native state、lease、receipt、公開supportを単独では証明しない |
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

## 新Runtimeの追加

最初に対象source / APIから、native lifecycle、identity、completion、readback、receipt、failure挙動を調べます。不明な点は、その質問に答える最小のProbeで確認し、profileのworkflowとowner条件を固定します。測定したprimitiveだけをadapterへ接続し、正常経路と主要な拒否経路を検証します。

`document-review-report-v1`は任意選択の固定taskです。新Runtimeへそのtool、出力形式、Codex event列を要求しません。二つ目のreal Task Profileが必要になるまでは、generic Task Profile frameworkを追加しません。

## 変更に必要な検証

変更した条件を確認できる既存の最小テストを選びます。Source testはsrc-layoutのため、例えば次のように実行します。

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_completion_policy.py' -q
```

| 対象 | 確認する正常・拒否経路 |
|---|---|
| Boundary / admission | Active / pendingがsettleした正常boundary。未観測work、gate外workを安全と推定しない |
| Freshness / authority | Current revisionから一回だけdispatch。Stale workspace、lease、checkpoint、generationは拒否 |
| Completion | Exact request / sessionと全predicate。Missing、foreign、conflicting、late、duplicate eventを確認 |
| Handoff / receipt | Deliveryとreceiptを分ける。Wrong identity / nonce / owner、missing tool resultを拒否 |
| Continuation | Receipt後のfresh read、未完了workの一回実行。Completed work、stale input、duplicate writeを拒否 |
| Uncertain outcome | Dispatch / write / submission timeoutでauthorityを戻さず、blind retryしない |
| Persistence | Atomic publish、必要なfsync、integrity readback。Partial write、corrupt record、journal gapを停止扱いにする |
| Resume | Same task、current revision、actual Runtime item、取込済みresult、nonduplicationを照合 |

Offline fixtureやsynthetic testは、そこで確認したfailure分類の根拠です。Live Runtimeのenforcementやreal-task成功を実測したことにはなりません。文書だけの変更や無変更Runtimeに追加live acceptanceを慣例的に要求しません。

## 試した内容の記録

Workspaceのメモにはdate / Yohaku version、Runtime / version、OS / Python、結果に影響するprovider / model / owner条件、実際のworkflow、結果、失敗・未実行範囲を残します。Resultは`PASS` / `PARTIAL` / `NOT_RUN`を区別し、実測した失敗は`FAIL`と理由を記載します。公開supportでは機能を`supported` / `unsupported` / `untested`で示します。

Transitionを確認した記録には、task identity、boundary / revision、Runtime固有completion、delivery / receipt、receipt後のfresh state、未完了workの非重複continuationをたどれる観測を残します。ACK、起動、PID、最終文章だけでは`RESUME_VERIFIED`の根拠になりません。Content qualityを評価しなければ`NOT_ASSESSED`とします。

外部testerの記録は任意です。Manifest、source hash inventory、reviewer chain、多層IDを必須のframeworkにせず、具体的な調査を追跡する必要があれば短いrun labelを使います。Credential、private transcript、task本文、raw tool argument / resultは公開summaryへ含めません。
