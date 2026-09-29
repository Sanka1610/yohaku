# Claude Code CLI Runtime

本書は、Claude Code CLIに対するYohaku integrationのcurrent public canonicalである。
対象はClaude Code CLI `2.1.280`、Linux、`claude -p`、stream-json、synchronous command
Hooksに固定する。Runtime family全体、Claude Desktop、Cowork、Agent SDK/API、別version、別OS、
別provider / backend / modelへsupportを一般化しない。

[Architecture](../architecture.md)はcomponentとtrust boundary、[Runtime Mapping](../runtime-mapping.md)は
profile固有事実、[Transition Strategies](../transition-strategies.md)はStrategy taxonomy、
[Evidence Model](../evidence-model.md)はEvidence / Coverage / Verdict、
[Support Policy](../../SUPPORT_POLICY.md)はmaturity / release policyを所有する。本書はこれらを
再定義せず、Claude Code CLI固有primitiveとYohaku roleの対応を示す。

## Runtimeの位置付け

Claude Code CLIはTarget Runtimeであり、manual compact completionまでのbounded adapterと、
同じprocess内で一回だけrecoveryするopt-in adapterが実装されている。Completion-onlyの外部
subscription profileは`ROLLOVER_OBSERVED`までlive acceptedされている。一方、Anthropic
subscription上のrecoveryは実装とoffline / local検証が存在するだけで、live acceptanceは
`NOT_RUN`である。

Local Ollamaを使う二つのmaintainer profileにはrecovery Evidenceがある。ただし、これらは
Claude Code Runtime、Ollama backend、固定model、runner、prompt、context、owner条件を組み合わせた
限定profileである。Local EvidenceからAnthropic subscription recoveryやClaude Code全体の能力を
導出しない。

Codex / Hermesと同等の正式operational launcherは存在しない。Adapter implementation、固定fixtureを
所有するmaintainer runner、正式operational supportは別の状態であり、架空のoperational profileを
設けない。Agent SDK/APIも別surfaceであり、現在は未実装である。

## Supported / measured profiles

Keyは[Runtime Mapping](../runtime-mapping.md#fixed-profile一覧)のmapping keyであり、Support
Profile ID、Evidence Record ID、Runtime family aliasではない。Runtime version / surface /
OSとprovider / backend / modelも、それぞれprofileを固定するdimensionでありIDではない。

| Mapping key | Support Profile ID | Evidence Record ID | 実装・測定範囲 | Current claim |
|---|---|---|---|---|
| `CL-SUB-C` | Product registryは`claude-c-cli`。Retained external profile labelは`C-CLI/2.1.280/Linux/print-stream-json/command-hooks` | `C-CLI-COMPLETION` | Anthropic subscriptionを使うexternal completion profile。一つのfresh exclusive sessionと一つのmanual `/compact` | `ManualRequest`から`ROLLOVER_OBSERVED`までlive `PASS`、overall `PARTIAL`。Recovery / `RESUME_VERIFIED`は含まない |
| `CL-SUB-R` | Separate Support Profile IDは未割当。`claude-c-cli` surface上のrecovery capability row | Qualifying external recordはなし。Verdictは`NOT_RUN` | Same-process handoff、receipt、fresh read、continuation、Task Assessorの製品実装とoffline / local検証 | External subscription recovery acceptanceは`NOT_RUN`。Local Ollama Evidenceを継承しない |
| `CL-LOCAL-FULL` | `C-CLI-OLLAMA-LOCAL/2.1.280/0.34.1/spark-x2.5-4b-uncensored/e1646156c204` | `C-CLI-OLLAMA-LOCAL-REPEAT-2026-09-29` | Spark-X2.5-4Bとfull-identity receiptによるmaintainer local recovery | `RESUME_VERIFIED`成功runとpre-adapter失敗runを保持。Repeatability `FAIL`、overall `PARTIAL` |
| `CL-LOCAL-NONCE` | `claude-c-cli-local-nonce` | `C-CLI-NONCE-QWEN35-9B` | Qwen3.5 9B、single owner、single pending handoff、`host-nonce-v1` | Bounded workflowは`RESUME_VERIFIED`まで`PASS`、overall `PARTIAL`。Parallel / multi-pendingは`UNSUPPORTED` |

`CL-SUB-C`のcompletion `PASS`を`CL-SUB-R`のrecoveryへ拡張しない。`CL-LOCAL-FULL`と
`CL-LOCAL-NONCE`もreceipt方式、model、Evidence chainが異なるため、一つのlocal profileへ統合しない。

## Runtime / version / surface / OS

| Key | Runtime / version | Surface / transport | OS / owner条件 |
|---|---|---|---|
| `CL-SUB-C` | Claude Code CLI `2.1.280` | `claude -p`、stream-json、synchronous command Hooks | Linux、fresh exclusive session、one manual request |
| `CL-SUB-R` | Claude Code CLI `2.1.280` | 同じprint processをcompletion後も保持するopt-in recovery path | Linux、trusted hostが一つのprocessとcollectorを直列所有。External liveは`NOT_RUN` |
| `CL-LOCAL-FULL` | Claude Code CLI `2.1.280` | 同じprint / stream-json / command-Hooks surface | Linux、maintainer-owned local runner、single writer |
| `CL-LOCAL-NONCE` | Claude Code CLI `2.1.280` | 同じsurface、nonce-bound recovery tool observation | Linux、single owner、single pending handoff、generation 1 |

Version、surface、Hook type、output format、OS、process lifetimeのいずれかを変えた場合は別profileとして
評価する。Completion-only hostはcompact result後にstdinを閉じてprocess終了を待つ。Recovery hostは
successful terminal resultでlogical collection windowを閉じ、同じprocessを保持する。このprocess
lifetimeの差もEvidence非継承の対象である。

## Provider / backend / model

`CL-SUB-C` / `CL-SUB-R`はAnthropic subscription surfaceに固定する。公開retained recordからexact
provider / backend / modelを確定できない箇所は`UNKNOWN`であり、名称を推定して補わない。

`CL-LOCAL-FULL`はOllama client / server `0.34.1`と
`spark-x2.5-4b-uncensored:latest`、4.1B `Q4_K_M`、digest
`e1646156c20479fe89690bad3f6a38062f4888cc33e03fcbb7a4944556be417f`を固定する。
`CL-LOCAL-NONCE`はOllama `0.34.1`と`qwen3.5:9b`、`Q4_K_M`、digest
`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`を固定し、
accepted runのobserved contextは`32768`である。

ここでは次の三つを分ける。

- Runtime capability: 固定したClaude Code CLI surfaceが必要なlifecycleを観測・制御できるか
- Backend compatibility: Claude Code CLIとAnthropic subscriptionまたはOllama endpointの組合せが、
  固定message / tool protocolを処理できるか
- Model instruction / tool fidelity: 固定modelが必要なtool名と引数を正確に生成できるか

Spark、MiMo、Qwenの成功・失敗は、この三層のどこで停止したかを示すprofile Evidenceであり、
Claude Code全体のmodel benchmarkではない。詳細比較は本書の
[Model comparisonの扱い](#model-comparisonの扱い)とretained Evidenceで確認する。

## Transition Strategy

四profileはいずれも[Manual In-place Compaction](../transition-strategies.md#manual-in-place-compaction)を
使う。Trusted hostがverified boundaryとcommitted checkpointを確立し、同じnative sessionへmanual
`/compact`を一回だけ送る。

`CL-SUB-C`のaccepted endpointは`ROLLOVER_OBSERVED`である。`CL-SUB-R`と二つのlocal profileは、
manual completion後に同じprocessへhandoffを送るsame-process recovery contractを持つ。このrecoveryは
別Strategyを意味せず、completion後のdelivery、receipt、fresh observation、continuation、resume
verificationを追加する。

Native automatic compaction、Fresh-context Rollover、Session Migrationはaccepted coverageに含まれない。
`SessionStart(source="compact")`を観測しても、新sessionへ移行したことを意味しない。

## Lifecycle observation

Claude Code CLI固有の観測面は、`claude -p`のstream-jsonとsynchronous command Hooksである。Hostの
collectorは、起動時の`SessionStart(source="startup")`、fixed foreground toolの
`PreToolUse` / `PostToolUse`、manual compactionの`PreCompact(trigger="manual")`、
`PostCompact(trigger="manual")`、`SessionStart(source="compact")`をallowlisted metadataとして
順序付きで収集する。

Command Hooksはcollectorへ同期的に通知するRuntime primitiveであり、Yohakuのreceiptやcompletionを
自動的に成立させるAPIではない。Collectorは一つのattachmentを所有し、eventをcaptureした時点で
host-local request、generation、sequenceを対応付ける。過去eventへ後からidentityを付け足さない。

`SessionStart(compact)`と`PostCompact(manual)`は、どちらも`PreCompact(manual)`より後でなければ
ならない。ただし、両者の相互順序は固定しない。Retained external runで一つの順序を観測した事実を、
Runtime contractの唯一の順序へ変更しない。

## Work observation / admission / gate

`CL-SUB-C`で観測したworkはfixed synthetic workflowのsingle foreground operationに限定される。
`PreToolUse`と対応する`PostToolUse`、fixture effect、terminal resultを照合できるが、general task、
arbitrary tool、background / subagent workをadmitするgeneral C-CLI gateはない。

Recovery adapterはreceipt、fresh read、actionをこの順で各一件だけadmitする。各operationはnative
tool ID、same-process continuation binding、collector sequenceと対応しなければならず、次のoperationへ
進む前にmatching handler resultとsuccessful `PostToolUse`を必要とする。このsequencingはfixed
recovery work planeに対するgateであり、Runtime全work planeのatomic freezeではない。

`classify_hook_result`はcollectorが観測したHook outcomeを`NORMAL_DENY`、`HOOK_FAILURE`、`UNKNOWN`へ
分類する。Intentional denyの分類だけでRuntime enforcementを証明せず、matching tool ID、successful
`PostToolUse`の不在、fixture counterを別に確認する。Hook exception、timeout、malformed / missing output
時にRuntime全体がfail closedになる保証は未受入である。

## Active / pending / incorporated

Fixed recovery operationは、admitted `PreToolUse`からhandler実行とmatching successful
`PostToolUse` resultの観測まで`active`である。Handlerが返っただけでは完了にせず、native tool ID、
result hash、collector sequenceを照合する。

`pending`は、次のgateが必要とするprior resultまたはfresh tokenをまだ確認していない状態を表す。
`incorporated`はprofile固有の機械的条件である。たとえばreceipt完了後にだけfresh readを許可し、
fresh readのtokenをexactにechoしたactionだけを許可する。これはfixed fixture内のresult propagationを
示すが、modelがtool resultの意味を理解し、推論へ利用したことを示さない。

Successful `PostToolUse`はtool executionのEvidenceである。Receipt、semantic incorporation、fresh
observation、current-state再検証、continuation、Task Assessorによるresume判定はそれぞれ別の段階で
あり、semantic incorporationは`NOT_ASSESSED`のままである。

## Native identity / host-local identity

Claude Code native identity、Yohaku Core identity、host-local correlation identityを分ける。
Native Hook payloadから保持するのはClaude Codeの`session_id`とtool eventのnative tool IDである。
Claude Code CLIはYohaku request、generation、attachment、continuation turnをatomicなnative identity
として提供しない。

| 種類 | 例 | Authority |
|---|---|---|
| Claude Code native identity | Native `session_id`、tool eventのnative tool ID | Claude Code Hook / session内の対象を識別する |
| Yohaku Core identity | Boundary ID、checkpoint ID、lease ID、compact request ID、Core generation、handoff ID、continuation permit | Core authority、durability、deduplication、state transitionを識別する |
| Host-local correlation identity | Attachment ID、collector sequence、recovery request ID、continuation turn ID、logical task ID、runner / owner ID | Native observationとCore identityをserialized collector内で対応付ける。Claude Code native identityやCore authorityにはならない |

`ClaudeContinuationBinding.turn_id`は一つのrecovery inputに対してhostが生成するdispatch identityであり、
native CLI turn IDではない。

Correlationは、fresh exclusive session、one request、trusted serialized collector、capture時のbindingに
依存する。Native `session_id`とhost-local IDを両方照合してもauthorityは統合されず、malicious host、
別client、検出不能なsame-session replayに対するauthentication boundaryにはならない。

## Trigger

Trusted operatorまたはrunnerが、verified boundaryとcommitted checkpointの後にmanual `/compact`を
一回だけ発行する。Yohaku library自体はClaude Code CLIを起動せず、Hooksやauthenticationを設定せず、
subscription / billing状態を検証しない。

`ClaudeCLIAdapter.compact()`はCore leaseとcurrent revisionを確認し、bindingを永続化してから
`dispatch("/compact", binding)`を一回呼ぶ。Dispatchが不明になった場合やcompletion Evidenceが不足
した場合はblind retryしない。二回目のcompact requestも拒否する。

## Completion proof

Claude CLI completion policyの実装classは`ClaudeManualCompletionPolicy`である。
`ClaudeCLICompletionPolicy`というclassは現行実装に存在しない。Policyは一つの
`ClaudeManualCompletion`として閉じたcollection windowを受け取り、次の条件を同時に要求する。

- Fresh exclusive session内のmanual compact requestが一回だけである
- Native `session_id`がstartup、request、三つのHook observationで一致する
- Attachment、request、generation 1、collector sequence、Evidence referenceが一致し、各sequenceと
  referenceが一意である
- `PreCompact(manual)`がmanual requestより後に一回だけ現れる
- `PostCompact(manual)`と`SessionStart(compact)`が、どちらもその`PreCompact`より後に一回ずつ現れる
- `PostCompact(manual)`と`SessionStart(compact)`の相互順序はどちらでもよい
- Collectionがclose / drain済みで、transport成功、positive `closed_seq`、全eventがclosureより前である
- Coreへ提出するcompletion eventが一件だけで、binding内のrequestと一致する

CLI processの終了、successful result envelope、model self-report、`PreCompact`単独、
`SessionStart(compact)`単独はcompletion proofにならない。Missing、failed、stale、duplicate、foreign
session、automatic trigger、extra compact observationはproofを拒否し、ownerを`AMBIGUOUS`として停止する。

`CL-SUB-C`ではこのproofが`ROLLOVER_OBSERVED`のendpointである。Recovery adapterは同じpredicateと
両方の許可順序を維持し、completion後に別のrecovery chainを開始する。

## Checkpoint / Yohaku storage

Yohaku checkpointはmanual requestより前のtask / revision / workspace stateを固定するdurable recordで
ある。Dedicated `SessionStore`へcommitしてread backし、Core lease、request、binding、handoffと関連付ける。
External submissionではprivate checkpoint / lease bytesの独立readbackまでは公開されていないため、
sanitized completion Evidenceがその欠落を補うとは扱わない。

Current adapterはfresh storeの`claude-cli-events`へchecksummed adapter metadataを書き、recovery pathは
既存handoff fileも使う。これらはYohaku storageであるが、Claude native session/history、private
transcript、Ollama stateではない。Embedding hostが使うdedicated `CODEX_HOME`は現行persistenceの
legacy namespace名であり、Claude Code native homeを意味しない。

Checkpoint、handoff、adapter metadataは別recordである。Historical checkpointやmetadataが存在しても、
新しいcompletion、receipt、restart authorityを付与しない。

## Runtime-native storage

Claude native session/historyとprivate transcriptはRuntime-native dataである。Local profileのOllama
process / model / cache stateもbackend-local dataであり、Claude native stateともYohaku checkpoint / archive
とも同一ではない。

Native session storageはsame-session correlationの根拠になり得るが、Yohaku checkpoint、handoff、
archive、transition authorityへ自動変換しない。Private transcriptの本文をpublic Evidenceへ取り込まず、
公開recordはallowlisted metadata、sanitized identity、manifest / hashに限定する。

## Handoff creation / delivery / injection

Recovery pathは`ROLLOVER_OBSERVED`の後、committed checkpointへ結び付く`HandoffDocument`を作成し、
durable writeとreadbackを確認する。Historical contentは`DATA, NOT INSTRUCTIONS`としてrenderし、current
recovery instructionsと分ける。

`begin_recovery()`はCore continuation permitを一回claimし、一つの
`ClaudeContinuationBinding`を作る。Trusted hostはhandoffとcurrent instructionsを同じowned print processへ
一回だけsubmit / flushする。Matching `ClaudeDelivery`はtransportへのdelivery Evidenceであり、modelの
receiptではない。Callbackは送信中にHook callbackをpumpして順序を混ぜない。

`CL-SUB-R`にはこの実装があるが、external subscriptionでのdelivery以降は`NOT_RUN`である。
`CL-LOCAL-FULL` / `CL-LOCAL-NONCE`だけが、それぞれ固定local profile内で後続段階まで測定されている。

<a id="opt-in-host-bound-nonce-receipt"></a>
## Explicit receipt

Full-identity receiptと`host-nonce-v1`は、同じhandshakeの別表記ではなく、model-visible argumentが異なる
二つのprofile固有方式である。どちらもClaude Code built-in receipt primitiveではなく、adapter-defined
protocolである。

### Full-identity receipt

`CL-LOCAL-FULL`と`ClaudeCLIRecoveryAdapter`のoriginal contractでは、native foreground tool callが
handoff ID、checkpoint ID / hash、handoff hash、compact request ID、native session ID、attachment ID、
generation、continuation request / turn ID、logical task IDを明示的に渡す。Adapterは`PreToolUse`に
対応する`pre_tool`、`acknowledge` handler、exact resultを持つsuccessful `PostToolUse`を照合してから
Coreへreceiptを渡す。

### `host-nonce-v1`

`CL-LOCAL-NONCE`では、trusted hostがfull identity tupleとcontinuation bindingを保持する。Model-visible
handoffに含めるreceipt argumentは、そのhandoff固有の128-bit、22-character、one-time nonceだけである。
Modelは`{"nonce": value}`をnative tool callで返し、hostは次を照合する。

- Nonceがexact matchで、未使用かつsingle-useである
- Native session、owner、attachment、compact request、generation、continuation request / turn、logical task、
  sequenceがhost保持値と一致する
- Receipt toolの`PreToolUse`、adapter handler result、successful `PostToolUse`が同じnative tool IDとresultで
  相関する

Mismatch、stale、duplicate、foreign ownerは拒否する。Nonceを補正・再発行せず、uncertain submissionを
retryしない。引数なし`ack_handoff()`、hidden storageから自動取得したnonce、printed ACK、handoff送信、
後続workの成功はreceiptにならない。

どちらの方式でもsuccessful tool callが示すのは、固定identityに相関したexplicit acknowledgmentである。
Handoff contentを意味的に理解・利用したことまでは証明せず、semantic incorporationは`NOT_ASSESSED`である。

## Fresh current-state observation

Receiptがmatching `PostToolUse`まで完了した後にだけ、native observation toolは`observe_fresh()`を呼べる。
Trusted observerはoptional task descriptionの前後でcurrent task、intent / execution revision、workspaceを二回
読み、同一性と安定性を確認する。Reconciliationにはcheckpointではなくこのfresh stateを使う。

Adapterは一回限りのfresh-read tokenを返し、matching native tool resultを記録する。次のactionはそのtokenを
exactにechoしなければならず、adapterは実行直前にもcurrent stateが変わっていないことを再検証する。
Receipt、fresh read、token echo、pre-action recheckは互いを代用しない。

## Continuation

Recovery continuationは、compactを行った同じowned `claude -p` processへcontrollerが一つのrecovery inputを
送るsame-process continuationである。Continuation ownerは一つのserialized collector / runnerで、fixed
Task Assessorが許可するactionを一回だけ実行できる。

Core continuation permitはtransport implementationではない。Completion-only policyは
`permits_continuation()`を常にfalseにし、`CL-SUB-C`を`ROLLOVER_OBSERVED`で停止させる。Recovery policyだけが
matching `ClaudeContinuationBinding`を許可する。

Action成功だけでsame-task continuationを成立させない。Receipt後のfresh read、token-bound action、native
terminal、independent assessmentが揃うまで`RESUME_VERIFIED`へ進めない。

## Task Observer / Task Assessor

Current implementationはgeneral Task Observer / Task Assessorを提供しない。`checkpoint()`が受け取る
`CurrentContext`と、recovery中のfresh observerはtrusted host callbackである。Adapterは観測値の型、identity、
revision、workspace stabilityを検査するが、任意taskの意味や安全な次actionを判定しない。

Local accepted workflowはfixture固有assessorを使う。Assessorはactual task effect、read / action tool ID、
unresolved work、next actionの再評価、completed workの非反復、historical instructionの非再実行、same-task
continuationを照合する。別taskへ転用するには、別のTask Profileとobserver / assessor acceptanceが必要である。

## Resume verification

`verify_resume()`はreceipt、fresh observation、token-bound action、successful recovery terminalが完了した後に
だけ呼べる。Task Assessorは`ResumeProof`を返し、assessment前後のcurrent stateが一致し、logical task、
intent revision、read item、action item、Evidence referenceが相関しなければならない。

Coreはこのproofを検査して初めて`RESUME_VERIFIED`へ遷移する。`CL-LOCAL-FULL`の成功runと
`CL-LOCAL-NONCE`のaccepted runはこのendpointへ到達した。`CL-SUB-R`は同じ実装pathを持つが、Anthropic
subscriptionでのhandoffからresumeまでのacceptanceは`NOT_RUN`である。

Mechanical `RESUME_VERIFIED`は文章・コード・事実品質やgeneral semantic understandingを評価しない。
Tool success、receipt、fresh read、continuation terminalも単独ではResumeProofにならない。

## Archive / native history

Claude Code CLI integrationには、visible-turn selection、sanitization、Yohaku archive write、search / retrievalを
一体化したaccepted archive adapterがない。Archive capabilityは`UNIMPLEMENTED`、live evaluationは
`NOT_RUN`である。

Claude native historyとprivate transcript、Ollama local stateはarchiveではない。Yohaku checkpointから参照
可能なhistorical dataがあっても、自動的にarchive化せず、resume authorityやcurrent instructionへ昇格しない。

## Failure / timeout / late / duplicate

| 条件 | Claude Code CLI integrationの扱い |
|---|---|
| Completion eventの欠落、失敗、stale、duplicate、foreign identity、unexpected extra event | `AMBIGUOUS`としてownerを停止し、handoffとblind retryを拒否 |
| CLI resultは成功したが三Hookまたはcollector closureが不足 | Completion不成立。Result envelopeで補完しない |
| Compact dispatchまたはhandoff submissionの成否が不明 | Retry / resendしない。Ownerを停止 |
| Timeout後のlate completion | Close済みownerを再開しない。Late eventから新authorityを作らない |
| Receipt / native tool result / owner / nonce mismatch | Recoveryを停止し、fresh read / actionへ進まない。Nonceを補正・再発行しない |
| Fresh state変化、stale token、assessment不成立 | `RESUME_VERIFIED`を拒否 |
| Exact duplicate receipt / completion | 二つ目のreceipt、handoff、continuation permit、dispatchを作らない |
| Hook timeout、process failure、malformed / missing output | Collector outcomeは`HOOK_FAILURE`。Runtime全体のfail-closed保証は未受入 |

成功runだけをcurrent stateとして上書きしない。Sparkのpre-adapter failure、Qwenのreceipt mismatch、
low-context runの`AMBIGUOUS`は、どのgateが成立しなかったかを示すEvidenceとして保持する。

## Restart / reconnect

Current adaptersはfresh store、fresh exclusive native session、one attachmentだけを受け入れる。Existing
sessionへのreattach、Core snapshot restart、inflight collector / work ledger再構成、compact後recoveryの
process reconnectは`UNSUPPORTED`である。

Claude completion bindingはCodex codec / schemaへserializeせず、Core restartはそのbindingを拒否する。
Interrupted ownerのcheckpoint、handoff、metadataをinspectできても、それらからconsumed lease、completion、
receipt、continuation permitを復元しない。Manual review後に新profile runを開始することは、transition restart
acceptanceではない。

## Evidence provenance

個別runのevent一覧は本書へ複製しない。公開status summaryは
[Runtime support](../runtime-support.md#target-runtime-status)、retained detailsは各`RESULT.md`、
`COVERAGE.json`、`SUPPORT_PROFILE.json`、manifest、hash付きEvidence indexで保持する。

| Key | Provenance / Evidence level | Accepted endpoint | Verdict / mixed result | Overall limitation |
|---|---|---|---|---|
| `CL-SUB-C` | `C-CLI-COMPLETION`、external / live-runtime / synthetic、sanitized event recordとtester report | `ManualRequest` → `ROLLOVER_OBSERVED` | Manual completion `PASS`、overall `PARTIAL`。Older Probeの`TIME_LIMIT`も別recordとして保持 | Recovery、private checkpoint / lease独立readback、Runtime authenticityの独立証明を含まない |
| `CL-SUB-R` | Product implementation、local synthetic tests、fake CLI＋real local command-Hook IPC | External accepted endpointなし | Anthropic subscription recovery `NOT_RUN` | Handoff → receipt → fresh read → resumeをexternal subscriptionで受入れていない |
| `CL-LOCAL-FULL` | `C-CLI-OLLAMA-LOCAL-REPEAT-2026-09-29`、maintainer / local-live / synthetic | 成功runは`RESUME_VERIFIED` | 成功一回、matching repeatはfirst command不一致で`FAIL`、recovery stages `NOT_RUN`。Earlier incomplete completionは`AMBIGUOUS`として保持 | Repeatability `FAIL`、overall `PARTIAL`。Stress / diagnostic用途に限定 |
| `CL-LOCAL-NONCE` | `C-CLI-NONCE-QWEN35-9B`、maintainer / local-live / synthetic | Accepted runは`RESUME_VERIFIED` | Bounded workflow `PASS`、overall `PARTIAL`。Earlier low-context attemptは`AMBIGUOUS`で保持 | Single owner / single pending handoff。Repeatabilityとsemantic incorporationは未成立 / `NOT_ASSESSED` |

Stage 4 external completion Evidenceをsubscription recoveryへ自動継承しない。Local full-identity successを
nonce receiptへ再解釈せず、nonce successをfull-identityやsubscriptionへ移さない。成功、`FAIL`、
`AMBIGUOUS`、`NOT_RUN`を同じrunへ潰さず、各recordを追記で保持する。

### Model comparisonの扱い

次のrecordはすべてmaintainer / local-live / syntheticである。成功runだけを残さず、
failure、`AMBIGUOUS`、後段`NOT_RUN`も保持する。

| Evidence Record | Fixed backend / model | 観測結果 | Verdict / 非継承 |
|---|---|---|---|
| `C-CLI-OLLAMA-LOCAL-REPEAT-2026-09-29` | Ollama `0.34.1`、Spark-X2.5-4B digest `e1646156c204…`、context 131072 | `recovery-04`は7 requests / 294.11秒で`RESUME_VERIFIED`。Matching `recovery-05`は最初のcommand引数欠落でadapter前に停止 | Historical bounded run `PASS`、repeatability check `FAIL`、overall `PARTIAL` |
| `C-CLI-OLLAMA-MIMO-COMPARE-2026-09-29` | MiMo-V2.6-Distill-Qwen-9B-Ablitrated digest `616953773b51…` | 二attemptとも最初のcommand引数欠落で`FAIL`。一attemptは別にupstream `TimeoutError`も記録。Compact以降`NOT_RUN` | SparkやsubscriptionのVerdictを変更しない |
| `C-CLI-OLLAMA-QWEN-COMPARE-2026-09-29` | Qwen3.5-4B-abliterated digest `4ce045509cfb…` | 二attemptともbackend template HTTP 500。Tool callなし、recovery stages `NOT_RUN` | Backend / template compatibility `FAIL`。Model tool semanticsは未評価 |
| `C-CLI-OLLAMA-QWEN35-4B-2026-09-29` | `qwen3.5:4b` digest `2a654d98e6fb…`、context 32768 | 二attemptともcompletion / handoff submission後、full-identity receiptの一文字不一致で停止 | 二workflow `FAIL`。Fresh observation以降`NOT_RUN` |
| `C-CLI-OLLAMA-QWEN35-9B-2026-09-29` | `qwen3.5:9b` digest `6488c96fa5fa…`、context 32768 | 一attemptはreceipt `session_id`不一致で`FAIL`、一attemptは7 requests / 128.37秒で`RESUME_VERIFIED` | Bounded success一回。Repeatability未成立、subscriptionへ非継承 |
| `C-CLI-NONCE-QWEN35-9B` | 同じQwen 9B、`host-nonce-v1` | Accepted runは7 requests / 100.01秒で`RESUME_VERIFIED`。Earlier context 4096 attemptは`PreCompact`だけで`AMBIGUOUS` | Fixed workflow `PASS`、overall `PARTIAL`。Earlier failureも保持 |

Full-identity receiptと`host-nonce-v1`は別protocolである。Nonce profileの成功をfull-identity
receipt、Anthropic subscription、Claude Code family全体へ適用しない。Elapsed timeの差から
speed improvementを推定せず、一成功からreliabilityを推定しない。

## Verdict / maturity

| Key | Capability Verdict / coverage | Maturity | Release channel |
|---|---|---|---|
| `CL-SUB-C` | Manual completion `PASS`、overall `PARTIAL` | experimental | undeclared |
| `CL-SUB-R` | External subscription recovery `NOT_RUN` | experimental | undeclared |
| `CL-LOCAL-FULL` | Retained bounded recovery success、repeatability `FAIL`、overall `PARTIAL` | experimental | undeclared |
| `CL-LOCAL-NONCE` | Fixed bounded workflow `PASS`、overall `PARTIAL`、semantic incorporation / quality `NOT_ASSESSED` | experimental | undeclared |

Completion PASS、one-run recovery PASS、overall CoverageProfile、maturity、release channelは別のclaimである。
本書は既存Evidence、CoverageProfile、Capability Verdictを再採点しない。正式operational launcherやpublic
release channelも宣言しない。

## Known Limitations

- Overall CoverageProfileは`PARTIAL`
- Anthropic subscription上のrecovery acceptanceは`NOT_RUN`
- Hook exception、timeout、malformed / missing output時のRuntime-wide fail-closedは未受入
- Background、subagent、parallel、detached、external writer coverageは未受入
- General work-plane barrierとRuntime-wide atomic freezeは成立していない
- Restart、reconnect、existing-session attachmentは`UNSUPPORTED`
- Repeated transition、repeated / automatic compaction、manual-native競合は未受入
- Receiptのsemantic incorporationは`NOT_ASSESSED`
- Local modelのrepeatabilityは成立しておらず、`CL-LOCAL-FULL`ではmatching repeatが`FAIL`
- Local backend EvidenceはAnthropic subscription Evidenceではない
- Agent SDK/APIは別profileで未実装
- General Task Observer / Task Assessorはない
- Field Evidenceはない
- Native generation / attachment / continuation turn identityがなく、host-local correlationに依存する
- Claude native history / private transcript / Ollama stateをYohaku checkpoint / archiveとして扱えない
- 正式operational launcher、installation / auth / billing verificationはない
- Runtime version、surface、OS、provider、backend、model、receipt protocol、Task Profileを越えてEvidenceを継承しない

## Unsupported / NOT_RUN scope

| Scope | 状態 |
|---|---|
| `CL-SUB-C` recovery、handoff receipt、fresh read、continuation、`RESUME_VERIFIED` | Profile外 / `NOT_RUN` |
| `CL-SUB-R` external Anthropic subscription recovery acceptance | `NOT_RUN` |
| `CL-LOCAL-NONCE` parallel owner / multiple pending handoff | `UNSUPPORTED` |
| All profilesのrestart / reconnect / existing-session attachment | `UNSUPPORTED` |
| Repeated / automatic compaction、native-auto recovery、manual-native race | `NOT_RUN` |
| Background / subagent / detached / external work barrier | Accepted coverageなし / `NOT_RUN` |
| General Task Observer / Assessor | `UNIMPLEMENTED`、acceptance `NOT_RUN` |
| Arbitrary task quality、receipt semantic incorporation | `NOT_ASSESSED` |
| Visible-turn archive selection / retrieval | `UNIMPLEMENTED`、live acceptance `NOT_RUN` |
| Claude Code Agent SDK/API、GUI、Desktop、Cowork | 別surface。Adapter `UNIMPLEMENTED`、`NOT_RUN` |
| Other CLI versions、OS、output format、Hook type、provider、backend、model、context | `NOT_RUN` |
| Hook-fault Runtime enforcement、power loss、late-event live recovery | `NOT_RUN` |
| Field Evidence、stable support、release readiness | `NOT_RUN` |

`NOT_RUN`は実装が存在しないという意味ではない。特に`CL-SUB-R`はrecovery implementationを持つが、
external subscriptionで必要なlive acceptanceを実行していない。`UNSUPPORTED`としたrestart、nonce profileの
parallel / multi-pendingはfixed contractが明示的に拒否する範囲である。

## 旧資料との関係

旧path [docs/reference/claude-cli.md](../reference/claude-cli.md) は、既存public linkとhistorical anchorを
保つ互換案内として残す。Current public canonicalは本書である。External completion、local recovery、
model comparison、nonce receiptのretained Evidence、CoverageProfile、RESULT、manifest、hash、source
associationは移動・改名せず、成功・失敗・`AMBIGUOUS`のchainを維持する。
