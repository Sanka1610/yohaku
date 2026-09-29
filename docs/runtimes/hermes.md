# Hermes Runtime

本書は、YohakuのHermes Runtime integrationに関する公開canonical pageである。Hermes
family全体の対応を宣言せず、Stage 2 Probe、Stage 4 connected adapter、current operational
lifecycleを別profileとして扱う。

[Architecture](../architecture.md)はcomponentとtrust boundary、
[Runtime Mapping](../runtime-mapping.md)はRuntime間のprofile比較、
[Transition Strategies](../transition-strategies.md)はStrategy taxonomy、
[Evidence Model](../evidence-model.md)はEvidence / Coverage / Verdict、
[Support Policy](../../SUPPORT_POLICY.md)はmaturity / release policyを所有する。本書は、
これらのroleをHermes固有primitiveへ対応付ける。

## Runtimeの位置付け

HermesはYohakuのTarget Runtimeである。Hermes `0.21.0`を対象とするnative Hermes CLI hostの
profileには、bounded live Probe、Yohaku Coreへ接続したbounded adapter、
inferenceを無効にしたoperational lifecycleがある。同じRuntime versionとsource commitを
使っていても、成立するclaimは異なる。

`H-PROBE`のPASSはadapter acceptanceではなく、`H-ADAPTER`のPASSはoperational launcherや
Hermes全体のsupportではない。`H-OP`のlifecycle PASSからtask inference、manual compression、
handoff、`RESUME_VERIFIED`を推定しない。

## Supported / measured profiles

`H-PROBE`、`H-ADAPTER`、`H-OP`は[Runtime Mapping](../runtime-mapping.md)のmapping keyであり、
Support Profile IDやEvidence Record IDではない。Runtime / source / surface / OSとprovider /
backend / modelは別のprofile dimensionとして保持する。

| Mapping key | Support Profile ID | Evidence Record ID | 位置付け | Accepted endpoint |
|---|---|---|---|---|
| `H-PROBE` | `H-CLI-01`（internal Probe profile） | Separate public IDは未割当。Stage 2 retained recordを参照 | Probe instrumentationによるbounded live measurement。Product adapterではない | Host / DB reflection、fresh task-state read、非重複continuationを含むProbe workflow PASS。Explicit receiptはPARTIAL、overall PARTIAL |
| `H-ADAPTER` | `hermes-h-cli-01`（product registry）／historical retained labelは`H-CLI-01` | `H-CLI-01-STAGE4` | Yohaku checkpoint、manual compression、handoff、receipt、resumeを接続したbounded adapter | Fixed synthetic workflowがCore `RESUME_VERIFIED`までPASS。Overall PARTIAL |
| `H-OP` | `hermes-operational-h-cli-01` | `S5-OP-HERMES` | Native Hermes CLIとstoreを所有するlifecycle-only operational profile | Install / configure後のstart、status、stop、clean stop後のfresh lifecycle。Lifecycle PASS、task / transition NOT_RUN |

Stage 2 EvidenceをStage 4へ自動継承していない。Stage 4は、Stage 2で選択したRuntime pinと
completion strategyを入力として再利用し、connected adapter、durable checkpoint / handoff、
explicit receipt、fresh reconciliation、Core resume gateを別のlive runで追加受入した。

## Runtime / version / surface / OS

| Key | Runtime / source | Surface | OS / Python |
|---|---|---|---|
| `H-PROBE` | Hermes `0.21.0` / `c5594ec4b34097cafbe24deb6dfd9ac4b21d411d` | Instrumented native `HermesCLI` host。Probe sourceをpinned WSL hostへ送って実行 | Ubuntu-Hermes on WSL2 / Python `3.11.16` |
| `H-ADAPTER` | 同じHermes version / source commit | Embedded native in-process CLI host＋`HermesCLIAdapter` | Ubuntu-Hermes on WSL2。LiveはPython `3.11.16`でcopied Yohaku sourceをimportし、local checkはPython `3.14.4` |
| `H-OP` | 同じHermes version / source commit | Native in-process CLI construction＋Hermes DB＋Yohaku store lifecycle | WSL2 Linux / Hermes venv Python `3.11.16` |

Historical Probe / Stage 4 live acceptanceはsource-oriented executionの実行条件を保持する。
当時のStage 4は、Yohaku packageがPython `>=3.14`を宣言していた時点で、copied sourceを
Hermes venvのPython `3.11.16`から実行した。この記録をcurrent installation supportへ
書き換えない。

その後、package minimumはPython `>=3.11`となり、同じnormal wheelをPython `3.11.16`と
`3.14.4`へinstallできるようになった。Hermes venvへのnon-editable wheel install、
`pip check`、provider request 0件のoffline synthetic rehearsalは確認済みだが、installed
wheelを使った新しいlive acceptanceは`NOT_RUN`である。Current installabilityはHistorical
Probe / Stage 4 Evidenceの実行条件を変更しない。

## Provider / backend / model

| Key | 扱い |
|---|---|
| `H-PROBE` | Existing `openai-codex` route、`gpt-5.6-luna`、reasoning lowをmain / compressionに固定した |
| `H-ADAPTER` | Stage 4 retained profileも同じprovider / model / effortを固定した。別provider、model、subscription surfaceへEvidenceを継承しない |
| `H-OP` | Native host construction時に固定値を渡すが、inference agentを初期化せずprovider requestを発行しない。このlifecycle runはprovider / model capability Evidenceではない |

`H-PROBE`と`H-ADAPTER`のlive routeは既存credentialを使ったが、credential value、request /
response body、会話本文は公開Evidenceへ含めていない。Subscription quotaと金額はretained
record上`UNKNOWN`である。

## Transition Strategy

`H-PROBE`と`H-ADAPTER`が扱うStrategyはManual In-place Compactionである。同じnative
session内でHermesのmanual `/compress`を一回実行し、compressed / summarized historyへ
置き換わったことをRuntime固有Evidenceで確認する。Fresh-context Rollover、Session
Migration、Native Automatic Compactionはaccepted Hermes Strategyではない。

`H-PROBE`はStrategy選定に必要なcapabilityを測定した。`H-ADAPTER`はverified boundary、
Yohaku checkpoint、lease、request、Runtime固有completion、handoff、receipt、fresh read、
resume verificationへ接続した。`H-OP`はStrategyを有効化せず、native compression entrypoint
を拒否する。

<a id="lifecycle-observation"></a>
## Lifecycle observation

`H-PROBE`はnative `HermesCLI` hostをinstrumentし、公式`PluginContext`、Responses send gate、
native `chat` / `_manual_compress`、`run_conversation` terminal result、`SessionDB` readbackを
観測した。このinstrumentationはProbeの測定面であり、product adapterではない。

`H-ADAPTER`ではembedding hostが同じ観測点を`HermesCLIAdapter`へ接続する。Native
`pre_tool_call` / `post_tool_call` callbackはadapterの`pre_tool` / `post_tool`へ渡され、実handler
入口は`require_tool()`でadmissionを再確認する。Responses send gateは`observe_request()`へ
actual bodyを渡すが、body自体を保存しない。Native foreground returnは
`observe_terminal()`でsession / turn / successを確認する。`chat()` returnだけではidleや
terminal completionを証明しない。

`H-OP`はnative CLI construction、fresh session / DB、Yohaku store、status、shutdownだけを
観測する。Lazy inference agent、Plugin Hook、work observer、H-CLI-01 transition adapterは
接続しない。

## Work observation / admission / gate

H-CLI-01のaccepted work planeは、一つのfresh dedicated sessionにおけるsingle sequential
foreground fixture toolである。Native `pre_tool_call`でsession、turn、API request、tool call、
tool nameを対応付け、normal denyではhandlerを実行しないことを観測した。Stage 4 adapterは
fixed tool以外、同時active / pending work、identity不一致を拒否する。

このgateは全Runtime work barrierではない。`PluginContext`外のwork、parallel、detached、
background process、subagent、external writer、別clientを停止しない。Normal denyのPASSから、
Hook例外、timeout、欠落時にHermes Runtimeが必ず停止するとは推定しない。

`H-OP`はtask workを開始せず、native `chat`、`_manual_compress`、agent initializationを拒否する。
これはgeneral work gateの受入ではなく、lifecycle-only profileの拒否構成である。

## Active / pending / incorporated

| Phase | H-CLI-01での意味 |
|---|---|
| Active | Matching `pre_tool_call`後、admitされたhandlerが実行中。Session、turn、API request、tool call、tool nameがfixed profileと一致する |
| Handler completion | Matching `post_tool_call`でterminal statusとtext resultを観測した状態。Result incorporationはまだ成立しない |
| Pending | Handler completion後、exact result text / hashが同じnative turnの後続outgoing requestへ`function_call_output`として入るまで保持する |
| Incorporated | Send gateでmatching call ID、turn、result hashを確認し、pendingから除いた状態。Semantic understandingを証明するものではない |

Boundary、compression、continuation terminalではactive / pendingが0であることを要求する。
Single foreground workのledgerから、複数tool、parallel execution、background completion、外部effect
のincorporationを推定しない。

## Native identity / host-local identity

Hermes native identity、Yohaku Core identity、host-local correlation identityを分ける。

| 種類 | 例 | Authority |
|---|---|---|
| Hermes native identity | Native session ID、turn ID、API request ID、tool call ID、`SessionDB` row / active state | Hermes内のrequest、tool、history、storage projectionを識別する |
| Yohaku Core identity | Boundary ID、checkpoint ID、lease ID、compression request ID、Core generation、handoff ID、continuation permit | Core authority、durability、deduplication、state transitionを識別する |
| Host-local correlation identity | Probe / adapter run ID、adapter event sequence、readback sequence、embedded owner ID | Native host / DB observationとCore requestをfixed owner内で対応付ける。Hermes native identityやCore authorityを置き換えない |

HermesはYohaku compression request IDやCore generationをnative completion eventとして返さない。
H-CLI-01は、一つのexclusive fresh session、一つのmanual request、ordered host instrumentation、
request前後のsession一致を組み合わせてcorrelateする。Host-local generationをHermes native
generationとして表示しない。

## Trigger

H-ADAPTERでは、trusted current-state observerを使ってboundaryをverifyし、Yohaku checkpointを
commitした後、Coreがleaseと一つのcompression requestを発行する。Adapterはrequestを
`compress_requested` metadataとしてdurableに記録し、`HermesManualBinding`をCoreへbindしてから
native `_manual_compress('/compress')`を一回呼ぶ。

Hermesの`ContextEngine`はnative context lifecycleのabstractionであり、fixed sourceの
`ContextCompressor`がそのinterfaceを実装する。`/compress`はnative compressorを起動するが、
`ContextEngine` / compressor returnや`compression_count`だけではYohaku completionにならない。

`H-PROBE`ではProbe-local request / correlationを使い、product leaseやadapter requestを主張
しない。`H-OP`はmanual compression triggerを有効化しない。

## Completion proof

Stage 2はhost / DB readbackを使うcompletion proof shapeを測定し、Stage 3で
`HermesManualCompletionPolicy`としてCoreから分離した。Stage 4のH-ADAPTERはこのpolicyを変更せず
使用した。Codexのthree-signal predicateやClaude Code Hook sequenceを要求せず、次の条件を
一つのcorrelated `HermesManualCompletion`として検証する。

1. Hermes `0.21.0`と固定source commitを使うexclusive fresh sessionである
2. `HermesManualBinding`のCore request、session、request sequence、generationが一致する
3. Manual compression request、compressor count、independent readbackが各一回である
4. Compression前後でnative sessionが変わらず、host historyが実際に変化する
5. 別に開いたread-only `SessionDB`からactive conversation projectionを読む
6. Host projectionとDB projectionのpayload、hash、countが一致する
7. Compression前のold history rowがinactiveになり、archived rowが存在する
8. Readback sequenceがrequest記録より後である

Engine / compressor return、`compression_count=1`、provider response success、host historyだけ、
DB row countだけではcompletion proofにならない。Host historyが変わらない、independent readが
ない、projection / hash / countが違う、old rowがinactiveでない、request / session /
generationが違う場合、policyはcompletionを拒否する。

Policyは一つのcompletion eventだけを受理し、exact duplicateから二つ目のcontinuation permitを
作らない。Mismatched proofの拒否とlocal late / duplicate挙動はlocal checksに含まれるが、live
late completion recovery、stale event recovery、duplicate raceの受入は`NOT_RUN`である。

<a id="checkpoint--yohaku-storage"></a>
## Checkpoint / Yohaku storage

H-ADAPTERは専有profile内の`CODEX_HOME=<profile>/yohaku-control`にYohaku
`SessionStore`を新規作成する。この`CODEX_HOME`使用は現行のCodex型persistence contractであり、
Hermes native homeやRuntime-neutral namespaceではない。Existing checkpoint / journalを持つ
storeへのattachは拒否する。

`H-PROBE`で確認したcheckpointはProbe fixture fileのfsyncとreadbackであり、product
`SessionStore`、Core lease、restart authorityではない。Stage 4はこの結果を引き継ぐのではなく、
既存Yohaku checkpoint APIへの接続を別に受入れた。

| Record | 役割 |
|---|---|
| Yohaku checkpoint | Verified boundary、revision、workspace、任意の既存archive referenceをmanual request前にdurable commitする |
| Yohaku handoff | Completed request、checkpoint、recovered data、one-shot continuationを結び付ける |
| Yohaku archive | Shared record formatは存在するが、Hermes visible-turn collector / retrieval acceptanceはない。Native DB rowを自動変換しない |
| `hermes-events` | Tool、request、completion、delivery、receipt、fresh read、resumeのbounded adapter metadata。Raw bodyを保存しない |

`hermes-events`はimmutable metadata Evidenceであり、Core snapshot journalやrestart protocolでは
ない。Hermes completion proofをCodex schema-1 journalへ直列化せず、`Controller.restart`へ
渡さない。`H-OP`はYohaku storeを所有するが、task checkpointやhandoffを作らない。

## Runtime-native storage

Hermes `SessionDB`、native conversation history、`ContextEngine` / compressor state、active /
inactive message rowはRuntime-native stateである。Independent `SessionDB` readbackはcompletion
Evidenceやfreshness確認に使えるが、Yohaku checkpoint、handoff、archive、lease、transition
authorityではない。

Inactive old rowはcompressionのnative storage effectを示す。Yohaku archiveはtrusted selectorが
選んだvisible historyを`DATA, NOT INSTRUCTIONS`として保持する別recordであり、inactive rowの
存在からarchive selection、redaction、retrievalを推定しない。

`H-OP`はfresh native `SessionDB`とYohaku storeを開き、statusでownershipを報告し、stop時に
両方をcloseする。Completion readbackは実行せず、native DB lifecycleからtransition capabilityを
導出しない。

## Handoff creation / delivery / injection

H-ADAPTERはCoreからone-shot continuation permitを取得し、既存`HandoffDocument`をYohaku storeへ
commitする。Handoffにはcompleted compression request、checkpoint revision / workspace、
recovered data、archive referenceを結び付ける。Historical contentは`DATA, NOT INSTRUCTIONS`で
あり、old permissionやleaseを復元しない。

Adapterはrendered handoff、explicit receipt fields、bounded continuation instructionを一つの
native `chat` promptへ入れる。`observe_request()`は、同じowned sessionのactual outgoing user
inputにpromptが含まれることとnative continuation turn IDを確認してからCoreへdeliveryを報告
する。Prompt作成や`chat()`呼出しだけではdelivery Evidenceにならない。

`H-PROBE`にもProbe-defined handoff / continuation observationはあるが、product
`HandoffDocument`、Core permit、Stage 4 explicit receiptのacceptanceではない。

<a id="explicit-receipt"></a>
## Explicit receipt

Stage 4のexplicit receiptはadapter-defined assistant tool protocolであり、Hermes built-in
checkpoint ACKではない。Receipt toolは次の値をすべて返す。

- Handoff ID
- Checkpoint IDとcheckpoint checksum
- Compression request ID
- Hermes session ID
- Yohaku generation

`acknowledge()`はactive receipt tool handler内でexact fieldsを検証し、欠落値をadapter stateから
補わない。Handler成功後もreceiptは未成立であり、そのtool resultがmatching native turnの次の
outgoing requestへincorporateされた時点でCore `receive_handoff`を呼ぶ。後続readやactionの成功、
modelの成功宣言、handoff injectionだけでreceiptを成立させない。

Stage 2のexplicit receiptは`PARTIAL`だった。Stage 4のseparate live adapter Evidenceが
H-ADAPTERのbounded receiptをPASSにしたのであり、Stage 2 record自体は変更していない。

このprotocolをCodex `YOH_ACK`やClaude `host-nonce-v1`の共通仕様として扱わない。共有されるのは、
deliveryとreceiptを分け、receipt単独でresumeを許可しないsemanticsだけである。

## Fresh current-state observation

Receipt成立後、実際のread tool handlerが`reconcile_fresh(observe)`を呼ぶ。Trusted observerは
`CurrentContext`としてlogical task、intent revision、execution revision、workspaceをdiskから
読み直す。Adapterはlogical taskをhandoffと比較し、Coreへfresh contextをreconcileする。

Fresh readのtool resultもsame-turn outgoing requestへincorporateされるまでpendingである。
`require_action()`はreceipt済みstateとincorporated fresh readを要求する。Checkpoint時のread、
SessionDB completion readback、model self-reportはpost-handoff fresh task readの代わりにならない。

`H-PROBE`のfresh readはProbe instrumentationによるbounded observationである。Stage 4はadapterの
receipt後gateとCore reconciliationを別に実行し、Probe resultだけで成立させていない。

## Continuation

H-ADAPTERのcontinuation ownerは、compression前から同じexclusive embedded hostとfresh dedicated
sessionを所有するadapterである。Core permit一回につきnative `chat`一回だけを開始し、actual
outgoing handoff、native continuation turn、terminal resultをcorrelateする。

これはHermes固有のcontroller-driven continuationである。Continuationはfixed scenarioで
残っているworkだけをadmitする。Completed workを再実行せず、
active / pendingを0にしてterminal successを観測する。Native automatic continuation、別session
へのmigration、restart後のcontinuation、general retryはaccepted scopeに含まれない。

`H-PROBE`のcontinuationはProbe-owned hostによるmeasurement、`H-ADAPTER`のcontinuationはCore
permitとdurable handoffに接続したproduct adapter pathである。`H-OP`にはtask continuationがない。

## Task Observer / Task Assessor

H-PROBEとH-ADAPTERのTask Observer / Task Assessorはfixed synthetic fixture専用である。
H-PROBEではProbe instrumentationがfixture stateを評価した。H-ADAPTERではObserverがfixture
stateを読み、boundary、freshness、revision、workspaceを提供し、Assessorがactual continuation
tool recordsとdisk effectからfresh read、remaining work、nonduplication、same-task continuationを
判定した。

これはgeneral Hermes Task Observer / Assessorではない。Runtime supportだけでは任意taskの
semantic boundary、completion、文章・コード・事実品質を判断できない。`H-OP`にはTask Observer /
Assessorを接続しない。

## Resume verification

H-ADAPTERはhandoff delivery、explicit receipt、fresh read、fresh-read result incorporation、allowed
action、native terminal successの後に`ResumeProof`を生成する。Coreへ渡す前に、assessment前後の
current stateが一致し、read / action itemが同じcontinuation turnのsuccessful / incorporated
toolであることを確認する。

`ResumeProof`は、unresolved workの確認、next actionの再評価、completed workの非反復、historical
instructionの非再実行、same-task continuationをfixture scope内で証明する。Coreはこれらを確認して
初めて`RESUME_VERIFIED`へ遷移する。Receipt、fresh read、action successのいずれも、単独では
resume verificationにならない。

`H-PROBE`はProbe-defined continuationを測定したが、connected product Coreの
`RESUME_VERIFIED`を主張しない。`H-ADAPTER`だけがseparate Stage 4 Evidenceでこのendpointへ到達
した。`H-OP`はresume verificationを実行しない。

## Archive / native history

H-ADAPTERにはHermes visible-turn selector / collector、WARM index、model-facing archive retrievalの
accepted implementationがない。Checkpoint / handoffが既存Yohaku archive referenceを保持できても、
それはHermes historyの選択・redaction・retrieval acceptanceではない。

Hermes `SessionDB`のactive / inactive rowsとnative conversation historyはRuntime-native historyの
ままである。Yohaku archiveへ自動importせず、inactive rowをCOLD archiveやverified historical
recordへ読み替えない。Live visible-turn archive / retrievalは`NOT_RUN`である。

`H-PROBE`と`H-ADAPTER`のどちらにもaccepted visible-turn archive pathはなく、`H-OP`もarchiveを
構築・取得しない。

## Failure / timeout / late / duplicate

| 条件 | 扱い |
|---|---|
| Pre-dispatchのcurrent state変化 | Manual requestを発行せず拒否する |
| Native compression / DB readback outcomeが不明 | Ownerを停止し`AMBIGUOUS`。Blind retryしない |
| Engine returnのみ、host不変、DB不一致、identity mismatch | Completionを拒否し`AMBIGUOUS` |
| Receipt欠落 | `RESUME_VERIFIED`へ進まず`RECOVERY_REQUIRED` |
| Receipt field / result identity mismatch | Ownerを停止し、read / actionへ進まない |
| Fresh read未取込、stale assessment、completed workの反復 | Resume verificationを拒否する |
| Exact duplicate completion | 二つ目のcompletion、handoff、continuation permitを作らない |

Local policy checkにはmatching late readbackとduplicate suppressionがあるが、live timeout後のlate
recovery、stale / duplicate race、Runtime再接続は受入れていない。Native Hookの通常denyを測定
しても、Hook exception / timeout / missing callback時のRuntime強制停止保証にはならない。

## Restart / reconnect

`H-ADAPTER`はfresh store / sessionだけを受け入れ、existing ownerへのattach、Core snapshot
restart、inflight work ledger再構成を実装しない。Interrupted ownerはrecordを保持してmanual
reviewし、自動resumeやcompression resendを行わない。Accepted transition restartは
`UNSUPPORTED`であり、power-loss recoveryは`NOT_RUN`である。

`H-OP`はclean stop後に新しいfresh operational lifecycleを開始できるが、これはH-CLI-01
transition restartではない。Native DBとYohaku recordを削除して成功扱いにしない。

## Evidence provenance

個別runのevent一覧は本書へ複製しない。公開summaryは[Runtime support](../runtime-support.md)、
retained detailsはStage 2 / Stage 4の`RESULT.md`、`CoverageProfile.json`、manifest、hash付き
Evidence indexで保持する。

| Key | Provenance / Evidence level | Accepted endpoint | Capability Verdict | Overall limitation |
|---|---|---|---|---|
| `H-PROBE` | H-CLI-01 Stage 2 / lab / live-Runtime / synthetic Probe | Probe-defined host / DB reflection、fresh read、nonduplicate continuation | Bounded workflow PASS、explicit receipt PARTIAL、overall PARTIAL | Probe instrumentationのみ。Product adapter、restart、Strong Transition Assuranceではない |
| `H-ADAPTER` | `H-CLI-01-STAGE4` / lab / live-Runtime / synthetic / connected adapter | Core `RESUME_VERIFIED` | Bounded workflow PASS、overall PARTIAL | Fixed tool一つ、manual compression一回、fresh exclusive session一つ |
| `H-OP` | `S5-OP-HERMES` / lab tested / native lifecycle / no inference | Native CLI / DB / Yohaku store lifecycle、start / status / stop | Lifecycle PASS、task / tool / transition NOT_RUN | Inference agent、H-CLI-01 adapter、Task Observerを有効化しない |

Stage 4はStage 2のRuntime / source pin、provider / model、single-owner条件、manual compression
strategy、host / DB completion requirementsを再利用した。Stage 4で新たに受入れたのは、product
adapter wiring、Yohaku checkpoint / handoff、explicit receipt、fresh reconciliation、Core
`RESUME_VERIFIED`である。Stage 2のVerdictをadapterへコピーしたものではない。

## Verdict / maturity

| Key | Verdict / coverage | Maturity | Release channel |
|---|---|---|---|
| `H-PROBE` | Fixed Probe workflow `PASS`、overall `PARTIAL` | experimental | undeclared |
| `H-ADAPTER` | Fixed connected workflow `PASS`、overall `PARTIAL` | experimental | undeclared |
| `H-OP` | Lifecycle `PASS`、task / transition `NOT_RUN` | experimental | undeclared |

Bounded workflow PASS、overall CoverageProfile、maturity、release channelは別のclaimである。本書は
既存Evidence、CoverageProfile、Capability Verdictを再採点しない。

## Known Limitations

- Overall CoverageProfileは`PARTIAL`
- Strong Transition Assuranceは未成立
- Accepted work planeはsingle sequential foreground fixtureに限定され、full Runtime work barrierではない
- Hook exception、timeout、missing callback時のRuntime強制停止保証は未受入
- Parallel、background、detached、subagent、general tool workは未受入
- External writerを排除せず、final observationからnative dispatchまでのraceが残る
- Live late / stale / duplicate completion recoveryは`NOT_RUN`
- Transition restartは`UNSUPPORTED`、power-loss recoveryは`NOT_RUN`
- Repeated transitionとmanual compression raceは`NOT_RUN`
- Native automatic continuationは`NOT_RUN`
- Visible-turn archive selection / retrievalは未実装・`NOT_RUN`
- Task Observer / Task Assessorはfixture固有で、general implementationはない
- Field Evidenceは成立していない
- Hermes version、source commit、provider、backend、model、surface、OSを越えてEvidenceを継承しない
- Installed wheelの新しいlive acceptanceは`NOT_RUN`
- Runtime supportからTask Profile supportを推定しない

## Unsupported / NOT_RUN scope

| Scope | 状態 |
|---|---|
| `H-PROBE` product adapter / operational launcher claim | Probe外。Stage 2からは成立しない |
| `H-ADAPTER` interrupted-owner restart / existing-session attachment | `UNSUPPORTED` |
| Power loss、live late / stale / duplicate recovery | `NOT_RUN` |
| Repeated compression、manual/native race、Native Automatic Compaction | `NOT_RUN` |
| Parallel / background / detached / external work barrier | Accepted coverageなし / `NOT_RUN` |
| Hermes visible-turn archive collector / retrieval | `UNIMPLEMENTED`、live acceptance `NOT_RUN` |
| General Task Observer / Assessor、arbitrary task quality | `UNIMPLEMENTED` / `NOT_RUN` |
| Other Hermes versions、source commits、provider / model / backend、surface、OS | `NOT_RUN` |
| Field Evidence、release readiness、stable support | `NOT_RUN` |
| `H-OP` inference、task tool、manual compression、handoff、resume | Profileで無効。Capability evaluationは`NOT_RUN` |

## 旧資料との関係

旧path [docs/reference/hermes.md](../reference/hermes.md) は、既存public linkとhistorical headingを
維持する互換案内として残す。Current public canonicalは本書である。Stage 2 / Stage 4の
retained Evidence、CoverageProfile、RESULT、manifest、hash、source associationは移動・改名
しない。
