# Codex Runtime

本書は、YohakuのCodex Runtime integrationに関する公開canonical pageである。Codex
family全体の対応を宣言する文書ではなく、固定したhistorical Reference、current
operational、current real-task profileを分けて説明する。

[Architecture](../architecture.md)はcomponentとtrust boundary、
[Runtime Mapping](../runtime-mapping.md)はRuntime間のprofile比較、
[Transition Strategies](../transition-strategies.md)はStrategy taxonomy、
[Evidence Model](../evidence-model.md)はEvidence / Coverage / Verdict、
[Support Policy](../../SUPPORT_POLICY.md)はmaturity / release policyを所有する。本書は
これらの定義をCodex固有primitiveへ対応付ける。

<a id="controller-core"></a>
## Runtimeの位置付け

CodexはYohakuのhistorical Reference Runtimeである。同時に、Codex
`0.158.0-alpha.2.1`には、task transitionを無効にしたoperational lifecycle profileと、
一つのfixed Task Profileを有効にしたreal-task profileがある。この三つはEvidenceと
accepted endpointが異なる。

Shared Coreが同じでも、Codex `0.155.0-alpha.16.4`のReference EvidenceをCodex
`0.158.0-alpha.2.1`へ継承しない。Current Operationalのlifecycle PASSからtransitionを
推定せず、Current Real-taskのbounded PASSからgeneral document、coding、Codex family
全体のsupportを推定しない。

## Supported / measured profiles

`C-REF-M`、`C-REF-A`、`C-OP`、`C-DRR`は
[Runtime Mapping](../runtime-mapping.md)内のmapping keyであり、Support Profile IDやEvidence
Record IDではない。Runtime version / surface / OSとprovider / backend / modelは、IDではなく
profileを固定するdimensionである。

| Mapping key | Support Profile ID | Evidence Record ID | 位置付け | Accepted endpoint |
|---|---|---|---|---|
| `C-REF-M` | `codex-reference-0.155` | `PHASE14`配下のmanual scenario record | Historical Reference。Phase 14までのretained Reference Evidence | Completion scenarioは`ROLLOVER_OBSERVED`、accepted recovery scenarioは`RESUME_VERIFIED`。各original Verdictを維持する |
| `C-REF-A` | `codex-reference-0.155` | `PHASE14`のScenario G record | 同じSupport Profileのbounded emergency recovery。Manual pathとは別Strategy | Same-turn `RESUME_VERIFIED`。Scenario G PASS、Phase 14 overall PARTIAL |
| `C-OP` | `codex-operational-0.158` | `S5-OP-CODEX-0158` | Current Operational。Inferenceとtask transitionを無効にしたowned lifecycle | Dedicated App Server startup、fresh thread、status、stop、clean stop後のfresh-session start |
| `C-DRR` | `codex-document-review-report-v1` | `DRR-V1-CODEX-0158-LIVE-01` | Current Real-task。Task Profile `document-review-report-v1`を有効にしたbounded workflow | `RESUME_VERIFIED`とmechanical completion PASS。Writing qualityは`NOT_ASSESSED` |

`C-REF-M`と`C-REF-A`は同じhistorical Runtime versionを使うが、trigger、completion proof、
checkpointの意味、continuation、restart contractが異なる。二つを一つのCodex compact
Verdictへ集約しない。

## Runtime / version / surface / OS

| Key | Runtime / version | Surface | OS / host runtime |
|---|---|---|---|
| `C-REF-M` / `C-REF-A` | Codex CLI `0.155.0-alpha.16.4` | Exclusively owned App Server connection | WSL2 Ubuntu / CPython `3.14.4` |
| `C-OP` | Codex `0.158.0-alpha.2.1` | Dedicated App Server over stdio | WSL2 Linux / CPython `3.14.4` |
| `C-DRR` | Codex `0.158.0-alpha.2.1` | Dedicated App Server over stdio、profile-owned dynamic tools | WSL2 Linux / CPython `3.14.4` |

他のCodex version、GUI / SDK surface、Windows-native host、他OSはこの表からsupportを
推定できない。

## Provider / backend / model

| Key | 扱い |
|---|---|
| `C-REF-M` / `C-REF-A` | Retained historical profileはOpenAI provider、`gpt-5.6-luna`、reasoning low。別provider / modelのclaimはない |
| `C-OP` | Inferenceを無効化する。`yohaku-no-inference` modelと到達不能なloopback providerを設定し、credentialを読み込まない |
| `C-DRR` | 実装は`gpt-5.6-luna`、reasoning lowを選択する。Public Evidence上のprovider / backend / model値は`UNKNOWN`であり、再利用可能な互換性claimとして別構成へ継承しない |

Current Operationalのdisabled providerはtask backendではなく、inferenceを起こさないための
拒否構成である。Current Real-taskは既存credentialを使うが、その事実からsubscription、
account、provider全体のsupportを推定しない。

<a id="bounded-native-automatic-compaction-recovery"></a>
## Transition Strategy

Codexで測定済みのStrategyは、Manual In-place Compactionとbounded Native Automatic
Compaction emergency recoveryである。Fresh-context RolloverとSession Migrationは
accepted Codex Strategyではない。

### Manual In-place Compaction

Manual pathでは、Yohakuがverified boundaryを取得し、current checkpointをcommitし、
revision-bound leaseを発行した後に、Codexへmanual compact requestを一回送る。Historical
`C-REF-M`とCurrent Real-task `C-DRR`はこのStrategyを使う。`C-OP`はtrigger、inference、
transitionを有効にしない。

### Native Automatic Compaction / emergency recovery

Native-auto pathでは、Codex自身のpolicyがactive turn内でcompactionを開始する。Yohakuは
事前のmanual requestやleaseを持たないため、このpathをproactive transition成功とは
扱わない。Historical `C-REF-A` / Scenario Gだけがaccepted scopeであり、current Codex
`0.158`へEvidenceを継承しない。

| 契約 | Manual In-place Compaction | Native Automatic Compaction |
|---|---|---|
| Trigger | Verified boundaryとcurrent checkpointの後、Yohaku / hostが発行 | Codex Runtimeがactive turn内で発火 |
| Request / lease | One-shot Yohaku requestとleaseあり | Manual requestとleaseなし。`origin=native_auto`のobservation identityを作る |
| Checkpoint | Dispatch前のcurrent verified checkpoint | Prior checkpointはstale historical dataのまま |
| Emergency data | なし | `EmergencyDelta(delta_status=unverified)`を別recordとして保持 |
| Completion | Compaction item、`PostCompact`、compact turn completionの三要素 | Correlated compaction itemと`PostCompact`。Active turn completionはresume verificationに使う |
| Continuation | Durable permit後にowned continuation turnを一回開始 | 同じactive turn内でbounded continuation。新しい`turn/start`を送らない |
| Restart | Limited historical manual reconciliation。Consumed authorityは復元しない | `UNSUPPORTED` |

Scenario Gの成功は、stale checkpointやemergency deltaをcurrent / verifiedへ昇格させない。
Same-turn recoveryが成功しても、proactive順序が成立したことにはならない。

## Lifecycle observation

Codex integrationはApp ServerのJSONL messageを、exclusively owned connectionのordered
streamとして観測する。HostはApp Server processの起動、`initialize` / `initialized`、
`thread/start`、reader、shutdownを所有し、`RuntimeHost`は受け取ったturn、item、Hook関連
eventをsingle owner loopでCore、completion policy、recoveryへ渡す。

Historical Referenceは、hostから渡されたinitialized connectionを前提とし、adapter自身は
process、authentication、subscriptionを所有しない。`C-OP`と`C-DRR`はdedicated stdio
connectionを起動する。`C-OP`は`initialize`、`initialized`、`thread/start`以外のworkを
拒否し、unexpected `turn/*` / `item/*`をoperational failureとする。

Synchronous command HookはApp Server JSONLとは別の観測面である。`PreToolUse`、
`PostToolUse`、`PreCompact`、`PostCompact`、`SessionStart`のpayloadをprivate local bridgeへ
渡し、owner loopがRuntime eventとのcorrelationを判断する。Hook payloadだけでRuntime
turn completionやtask completionを証明しない。

<a id="bounded-work-plane-integration"></a>
## Work observation / admission / gate

Historical Referenceでは、測定対象の`Bash` / `apply_patch`を`PreToolUse`と`PostToolUse`
で観測し、owned thread、active turn、cwd、tool-use IDを対応付ける。Armed barrier中の
新しいmeasured workには明示的なdenyを返す。ただし、Hook failure pathが`FAIL_OPEN`で
あるため、このdenyはRuntime-wide atomic freezeではない。

Codex App Serverのdynamic toolsは別のsurfaceである。Historical archive adapterは
read-onlyな`search_archive` / `read_archive`をdynamic toolsとして公開できる。`C-DRR`は
Task Profile固有の`read_review_inputs` / `publish_review_report`だけを公開し、他のbuilt-in
toolを`PreToolUse`で拒否する。Dynamic tool call / resultはApp Server eventとして観測し、
task-specific ledgerがincorporationを判断する。

`C-OP`はtask workをadmitせず、work observer、Hook registration、transition gateを持たない。
これは「全workを安全にgateできる」という意味ではなく、profile自体がtask executionを
開始しないという制限である。

## Active / pending / incorporated

| Profile | Active | Pending | Incorporated |
|---|---|---|---|
| Historical Reference | Matching `PreToolUse`後のadmitted foreground operation | `PostToolUse`後も、terminal executionと全effectの反映を独立確認するまで残る | Trusted hostがterminal state、partial effect、workspace / revision更新を確認し、evidence reference付きでledgerを更新した状態 |
| `C-DRR` | Admit済みprofile-owned dynamic toolの実行中 | Runtime resultとtask stateへの反映が確認されるまで残る | Task-specific observerがexact read / publish resultとworkspace stateを確認した状態 |
| `C-OP` | 該当なし | 該当なし | 該当なし。Task workを実行しない |

`PostToolUse`、tool success、turn completionはいずれも、それだけでincorporatedを意味しない。
Historical work ledgerはin-memoryであり、restart時に再構成しない。

## Native identity / host-local identity

Codexから観測するnative identity、Yohaku Core identity、host-local correlation identityを
分ける。同じ文字列を複数の欄に保存してもauthorityは統合されない。

| 種類 | 例 | Authority |
|---|---|---|
| Codex native identity | Thread / session ID、turn ID、item ID、Hook run ID、dynamic tool call ID | App Server / Hook stream内の対象を識別する |
| Yohaku Core identity | Boundary ID、checkpoint ID、lease ID、request ID、Core generation、handoff ID、continuation permit | Core authority、durability、deduplication、state transitionを識別する |
| Host-local correlation identity | Companion / connection owner ID、attachment / run ID、ordered event sequence、task-ledger entry | Native observationとCore requestをfixed owner内で対応付ける。Codex native authorityにもCore authorityにもならない |

Codex notificationはYohaku request IDやCore generationをnative fieldとして提供しない。
Historical manual mappingは、一つのexclusively owned thread、一つのoutstanding request、
ordered stream、persisted turn / item bindingに依存する。Core generationをCodex native
context generationと表示しない。

<a id="manualcompactbackend-and-owner-api"></a>
## Trigger

Manual triggerでは、Companionがcheckpoint fileとcurrent authorityを確認し、requestを
journalへ保存してcurrent stateを再読した後、`ManualCompactBackend`が次のRPCを一回送る。

```text
thread/compact/start(threadId=<owned-thread>)
```

RPC responseの`{}`はrequest acceptanceであり、completionではない。Pre-dispatchの
revision、workspace、lease、checkpoint不一致はrequestを送らず`INVALIDATED`とする。
Transport outcomeが不明なら`AMBIGUOUS`とし、blind retryしない。

Native-auto triggerではCodex自身がcompactionを開始する。Correlated
`PreCompact(trigger=auto)`を受けてemergency observationを保存するが、Yohakuから
`thread/compact/start`を送らない。Manual request中のnative-auto conflict、二回目のnative
compact、identity mismatchはrecoveryを停止する。

## Completion proof

Codex manual completionは、同じbound compact turn / requestに対する次の三要素をすべて
要求する。

1. `contextCompaction` itemのsuccessful `item/completed`
2. Successful `PostCompact`（App Server上ではcorrelated `hook/completed` /
   `run.eventName=postCompact`）
3. Errorなしのsuccessful compact `turn/completed`

RPC acceptance、`item/started`、`PostCompact`単独、assistant self-reportはcompletion proofに
ならない。この三要素はCodex manual profile固有のpredicateであり、HermesやClaude Codeの
共通仕様ではない。

Native-autoでは、`PreCompact(auto)`とactive-turn identityでnative originを分類した後、
correlated `contextCompaction` item completionとsuccessful `PostCompact`をcompletion proofに
使う。Active turnのterminal eventを架空のcompact turn completionとして消費せず、後の
receipt / ResumeProofに使う。

Missing、mismatched、conflicting completionは`AMBIGUOUS`またはrecovery停止となる。Exact
duplicate Evidenceは新しいcompletionやdispatchを作らない。

<a id="production-architecture-and-persistence"></a>
## Checkpoint / Yohaku storage

Historical ReferenceのPOSIX `SessionStore`は、absolute `CODEX_HOME`の下に
`yohaku/sessions/<thread-id>/`を作る。`C-OP`と`C-DRR`はrunごとにisolated Codex homeを作り、
その下のYohaku storeを別runから分離する。Yohaku storageはRuntime-native storageとは
別である。

| Record | 役割 |
|---|---|
| Checkpoint | Verified boundary、revision、workspace、選択済みarchive referenceをdispatch前にdurable commitする |
| Journal | Core state、request intent、acceptance、binding、completion、ambiguity、handoff、receipt、resumeをhash chain付きappend-only recordへ保存する |
| Handoff | Completed requestと一つのcontinuation identityへ、recovered dataをdurableに結び付ける |
| Archive / archive-index | Trusted hostが選択したhistorical visible dataをCOLD bodyとWARM metadataへ分ける |
| Emergency record | Native-autoで観測した`EmergencyDelta`を、checkpointとは別のunverified dataとして保存する |
| Adapter / operational metadata | Runtime event projection、operation status、task ledger、run metadata。Core checkpointやjournal authorityの代わりにはならない |

Checkpoint、handoff、archiveはschema-versioned envelopeとSHA-256を使い、temporary write、
file fsync、atomic rename、parent directory fsyncの順で保存する。Journalはraw provider body、
Hook output、secret、tool bodyを保存しない。Write outcomeが不明なstoreはpoisonedとして停止し、
古いrecordへ黙ってfallbackしない。

## Runtime-native storage

Codex自身のthread、turn、active context、transcript / history、App Server側のsession stateは
Runtime-native stateである。これらをYohaku checkpoint、journal、handoff、archiveと同一視
しない。Runtime-native readbackやeventはEvidenceになり得るが、Yohaku authorityを保存
するわけではない。

Codex home、config、authenticationもprofileごとに分ける。

- Historical Reference libraryはhostからinitialized connectionを受け取り、process、config、
  authを変更しない
- `C-OP`はfresh per-run homeを作り、credentialを置かず、updates、web search、analytics、
  feedback、hooks、plugins、apps、memories、shell snapshotを無効化する
- `C-DRR`はfresh per-run Codex homeと別のruntime homeを作り、固定configとtrusted Hook hashを
  保存する。既存credential homeの`auth.json`だけをrun homeへsymlinkし、credential valueを
  Evidenceへ複製しない

`CODEX_HOME`はCodex config / authのisolationと、現行Yohaku POSIX storeのroot選択の両方に
使われる。これはhistorical Codex型persistence contractであり、Runtime-neutral storage
namespaceではない。

<a id="production-recovery-and-continuation"></a>
## Handoff creation / delivery / injection

Manual pathでは、`ROLLOVER_OBSERVED`後にRecoveryLifecycleがdurable handoffを作り、
continuation permitをjournalへ保存する。Ownerは一つのcontinuation `turn/start`を送り、
correlated `SessionStart(compact)` Hook（native payloadでは`source=compact`）に
`hookSpecificOutput.additionalContext`としてhandoffをinjectする。

Deliveryしたhistorical materialは`DATA, NOT INSTRUCTIONS`であり、old instruction、permission、
leaseを復元しない。Repeated matching `SessionStart(compact)`はpersisted delivery limit内で
同じhandoffを再提示できるが、別のcontinuation turnを作らない。

Native-autoは同じactive turnへhandoffをinjectし、新しい`turn/start`を送らない。Handoffは
prior checkpointをhistorical / stale、emergency deltaをunverifiedと明示する。

## Explicit receipt

Accepted Reference recoveryでは、successful handoff injectionに加え、bound continuation
turnのcompleted assistant itemに次のexact markerを要求する。

```text
YOH_ACK:<handoff-id>:<generation>
```

`generation`はsaved Core bindingであり、Codex native context generationではない。Exact
duplicate ACKはno-opとする。Hook outputだけ、deliveryだけ、後続tool successだけでは
`HANDOFF_RECEIVED`を成立させない。

## Fresh current-state observation

Manual dispatch直前は、trusted `read_current` callbackが`CurrentState`としてintent revision、
execution revision、workspace、lease ID、rollover generation、checkpoint ID、idle stateを
読み直す。Receipt後のrecoveryでは、trusted observerが`CurrentContext`としてcurrent intent
revision、execution revision、workspace、logical taskを読み直し、unresolved workも別途確認
する。Assessmentの前後でも同じstateを観測し、stale、changed、unobservedな状態からresumeを
許可しない。

`C-DRR`ではTask Profile固有observerがcurrent task stateを供給する。現時点のretained
contractとEvidence参照は[Task Profile reference](../task-profiles/document-review-report-v1.md)に
あり、同文書をTask Profile詳細契約のcurrent public canonicalとする。本書が所有するのは、
current Codex profileのacceptanceにtask-specific fresh observationが必要だというRuntime境界
と、そのCodex-specific bindingである。

## Continuation

Manual pathのController continuationは、一つのdurable permitに一つのowned
`turn/start`を対応付ける。Dispatch outcomeが不明でもpermitは消費され、restartやduplicate
completionから別turnを自動送信しない。Continuationはunfinished workだけを対象とし、
historical commandやtask-specific actionをfixed handoff promptへ埋め込まない。

Native-autoでは、compaction前から続くactive turnをsame-turn continuationとして使う。
Manual pathの新規turn contractを適用しない。`C-OP`にはtask continuationがない。

## Task Observer / Task Assessor

Codex Runtime supportだけでは、semantic boundary、task freshness、task completionを判断
できない。Task-enabled profileにはtrusted Task ObserverとTask Assessorが必要である。

`document-review-report-v1`は、Current Real-task profileに存在し、Codex
`0.158.0-alpha.2.1`でlive acceptedされた。Task-specific observer / assessorを使って
`RESUME_VERIFIED`へ到達したが、この結果はmechanical completionだけを評価する。Task
Profileの詳細契約、retained contract、Evidence参照は
[専用canonical](../task-profiles/document-review-report-v1.md)に分離する。

Historical Referenceのscenario / fixture assessorもgeneral Task Assessorではない。
`C-OP`にはTask Observer / Task Assessorがなく、task transitionを拒否する。

## Resume verification

Task Assessorはimmutable handoff、bound continuationのactual tool item、fresh current stateを
使って`ResumeProof`を返す。ResumeProofは、少なくとも次をprofile scope内で証明する。

- Fresh observationとassessment前後のstate一致
- Same logical task
- Successful read / action item identity
- Unresolved workの確認
- Next actionの再評価
- Completed workの非反復
- Historical instructionの非再実行
- Same-task continuation

Coreはreceipt、terminal continuation、Runtime reconciliation、ResumeProofを確認して初めて
`RESUME_VERIFIED`へ遷移する。`YOH_ACK`、assistantの成功宣言、tool success、archive retrieval
のいずれも、単独ではresume verificationにならない。

<a id="archive-and-lazy-rehydration"></a>
<a id="reference-runtime-archive-adapter"></a>
## Archive / native history

Historical Referenceは、trusted selectorが選んだterminal visible turnをYohaku archiveへ
保存できる。COLD bodyとWARM indexを分け、`search_archive`はmetadataだけ、`read_archive`
は選択した一件だけを`DATA, NOT INSTRUCTIONS`として返す。Archive readはCore state、lease、
barrier、resume authorityを変更しない。

App Server dynamic archive toolsとCodex native transcript / historyは別物である。Native
history全体を自動的にYohaku archiveへ変換せず、hostがselectionとredactionを担当する。
`C-DRR`はarchive coverageを持たず`UNSUPPORTED`、`C-OP`は`NOT_RUN`である。

## Failure / timeout / late / duplicate

| 条件 | Codex integrationの扱い |
|---|---|
| Pre-dispatchのstale revision / workspace / lease / checkpoint | Requestを送らず`INVALIDATED`、fresh boundaryから再検証 |
| Dispatchされた可能性がありresultが不明 | `AMBIGUOUS`。Ordinary workとblind retryを停止 |
| Completionは既知だがdelivery / receipt / current-state proofが不足 | `RECOVERY_REQUIRED` |
| Matching late manual completion | Persisted owner mappingが完全な場合だけ一回reconcile可能 |
| Exact duplicate completion / ACK | No-op。新しいhandoff、continuation、dispatchを作らない |
| Missing / conflicting / foreign identity | Completionへ採用せず、ambiguityまたはrecovery停止 |
| Task Profileのstale / duplicate / undeclared work | Profile layerで`REFUSED`。Uncertain side effect後は`AMBIGUOUS`になり得る |

Hook timeout、nonzero exit、malformed output、missing outputの測定済み経路は
`FAIL_OPEN`である。Ownerが通常作業を止めても、Codex Runtime process、external client、
detached processが停止したことにはならない。

## Restart / reconnect

| Profile / path | 状態 |
|---|---|
| Historical manual | Committed checkpointとpersisted bindingを使うlimited reconciliationがある。Leaseとcontinuation permitを復元せず、identityを新eventから推定しない |
| Historical native-auto | `UNSUPPORTED`。In-turn compaction後のitem provenanceをthread readだけで再構成できない |
| `C-OP` | Confirmed clean stop後にfresh dedicated sessionを開始できる。Transition restartやexisting-session attachmentではない |
| `C-DRR` | Accepted workflowのrestartは`UNSUPPORTED`。Retained stateはinspect-only |

Historical work ledgerはdurableでなく、inflight ledgerをrestart後に再構成しない。Unknown
continuationやowner lossをnon-executionと推定せず、自動resendしない。

<a id="focused-verification"></a>
## Evidence provenance

個別runの一覧は本書へ複製しない。Retained Evidence、CoverageProfile、historical source
associationは[Runtime support](../runtime-support.md)とprivate Evidence indexで保持する。

| Key | Evidence provenance | Accepted endpoint | Overall limitation |
|---|---|---|---|
| `C-REF-M` | Historical Phase 14までのlocal / synthetic、bounded live-Runtime Reference Evidence | Manual completionは`ROLLOVER_OBSERVED`、accepted recoveryは`RESUME_VERIFIED`。各original Verdictを維持 | Codex `0.155`、declared tools、exclusive owner、historical configurationに限定 |
| `C-REF-A` | Historical Scenario G、lab / live-Runtime / synthetic | Same-turn `RESUME_VERIFIED`、Scenario G PASS | One native compact、one foreground Bash、one active turn。Phase 14 overall PARTIAL |
| `C-OP` | `S5-OP-CODEX-0158`、lab tested / native lifecycle / no inference | Owned startup、fresh thread、status、stop | Task inference、transition、resumeはNOT_RUN |
| `C-DRR` | `DRR-V1-CODEX-0158-LIVE-01`、lab / live-Runtime / nonfixture real task | `RESUME_VERIFIED`、mechanical completion PASS | One fixed Task Profile。Writing quality NOT_ASSESSED、overall product coverage PARTIAL |

新しい文書commitはhistorical scenarioの再実行ではない。`C-REF-M` / `C-REF-A`のEvidenceを
`C-OP` / `C-DRR`へ継承せず、`C-DRR`のresultを別Task Profileへ継承しない。

`C-DRR`のfinal accepted runより前に、task dynamic toolをHookが拒否してtransition前に
`REFUSED`となったrunを保持する。Exact allowlist修正後のaccepted runと、既存outputを
`STALE_OUTPUT_PRESENT`で拒否したrepeat checkも別結果である。成功runだけでfailure recordを
置き換えていない。

## Verdict / maturity

Stage 5 review（2026-10-01）でCandidate Aだけをalphaへ昇格した。Product channelはAlpha、
publicationはBLOCKED_EXTERNAL。Historical Reference、Hermes、ClaudeをAlpha scopeへ含めない。

| Key | Capability Verdict / coverage | Maturity | Release channel |
|---|---|---|---|
| `C-REF-M` | Original scenario Verdictを維持。Historical Phase 14 overall `PARTIAL` | experimental | undeclared |
| `C-REF-A` | Scenario G `PASS`、Historical Phase 14 overall `PARTIAL` | experimental | undeclared |
| `C-OP` | Lifecycle `PASS`、task transition `NOT_RUN` | alpha | Alpha |
| `C-DRR` | Fixed workflow `PASS`、overall product coverage `PARTIAL`、quality `NOT_ASSESSED` | alpha | Alpha |

Lifecycle PASS、bounded workflow PASS、maturity、release channelは別のclaimである。この表は
既存VerdictやCoverageProfileを再採点しない。

## Known Limitations

- Hook timeout、nonzero、malformed、missing-output pathは`FAIL_OPEN`
- Work-plane gateはregistered pathだけを対象とし、Runtime-wide atomic freezeではない
- External writerを排除せず、workspace observationで検出できる範囲に依存する
- Parallel、detached、background、未登録tool / workはaccepted coverage外
- Historical work ledgerはin-memoryで、inflight ledger restartを支えない
- Native repeat、repeated manual compact、live manual-native競合は一般受入されていない
- Final-readからdispatchまでのraceと、native context-generation identityの欠落が残る
- Task-enabled transitionにはtask-specific Observer / Assessorが必要
- Archive selectorとredactionはtrusted host policyであり、自動secret classifierはない
- Codex `0.155` Evidenceを`0.158`へ、または別surface / provider / modelへ継承しない
- Runtime supportとTask Profile supportは別である
- Strong Transition Assurance、general exactly-once、power-loss recoveryは成立していない

## Unsupported / NOT_RUN scope

| Scope | 状態 |
|---|---|
| Historical Codex `new_context` / Fresh-context Rollover | Measured configurationで`UNSUPPORTED` |
| Session Migration | `UNIMPLEMENTED` / `NOT_RUN` |
| Native-auto recovery restart | `UNSUPPORTED` |
| `C-DRR` restart / repeated transition / archive | `UNSUPPORTED`またはprofile scope外 |
| `C-OP` task inference / compact / handoff / resume | `NOT_RUN`。Task Profileとtransition adapterを有効化しない |
| Other Codex versions、Windows-native、他OS / surface | `NOT_RUN` |
| General MCP、parallel / detached、external work、unregistered tool | Accepted coverageなし / `NOT_RUN` |
| Repeated native compact、power loss、general manual-native race | `NOT_RUN` |
| Field Evidence、writing / code / factual quality | Field Evidence未成立。QualityはTask Profileにより`NOT_ASSESSED` |

## 旧資料との関係

旧path [docs/reference/codex.md](../reference/codex.md) は、既存linkとhistorical anchorを保つ
互換案内として残す。Current public canonicalは本書である。Historical Evidence、private
record、CoverageProfile、source associationは移動・改名せず、既存hashとrelative linkを
維持する。

## Candidate A release review fields

次の表はCandidate Aに限定したrelease review用の検証対象である。Alpha候補の範囲を示し、
現在のmaturity / channelや個別EvidenceのVerdictを昇格させない。Fieldの意味、除外コード、
検証手順は[Candidate A review](../release/candidate-a.md)を参照する。

<!-- candidate-a:start -->
| field | C-OP | C-DRR |
|---|---|---|
| mapping_key | C-OP | C-DRR |
| support_profile_id | codex-operational-0.158 | codex-document-review-report-v1 |
| runtime_family | codex | codex |
| runtime_exact_version | 0.158.0-alpha.2.1 | 0.158.0-alpha.2.1 |
| surface | dedicated App Server / stdio | dedicated App Server / dynamic task tools / manual compact |
| task_profile_id | none | document-review-report-v1 |
| operational_launcher_support | true | true |
| task_runner_support | false | true |
| maturity | alpha | alpha |
| release_channel | Alpha | Alpha |
| accepted_endpoint | native-start-status-stop-fresh-lifecycle | RESUME_VERIFIED |
| evidence_record_id | S5-OP-CODEX-0158 | DRR-V1-CODEX-0158-LIVE-01 |
| known_exclusions | no-runtime-family-support, no-field-evidence, no-other-runtime-os-provider, no-general-parallel-background-external-work, no-strong-transition-assurance, no-inference-or-task-transition, no-reference-evidence-inheritance | no-runtime-family-support, no-field-evidence, no-other-runtime-os-provider, no-general-parallel-background-external-work, no-strong-transition-assurance, one-fresh-session-one-manual-compact-one-report, no-restart-or-repeated-transition, quality-not-assessed, no-general-document-coding-shell-mcp, external-writers-not-prevented |
<!-- candidate-a:end -->
