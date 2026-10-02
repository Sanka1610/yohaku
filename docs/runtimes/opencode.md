# OpenCode Runtime

`OpenCodeAdapter`はserver/client APIを使う限定adapterです。試した対象は
`@opencode/cli@2.0.21`、公式tag `v2.0.21`、Linux / WSL2、fresh Session、
foreground text task一つ、native compact一回です。追加compaction plugin、DCP、
subagentは使用していません。Local Ollama `0.34.1` / `qwen3.5:4b`、native
auto compaction無効、keep tokens 0で確認しました。他versionは未検証で、
adapterは観測したAPI・event・SQLite projectionとの対応を保つためserver `2.0.21`を要求します。

Hostはfresh Sessionと専用`SessionStore`を用意し、Sessionの排他的利用、設定、
task boundaryの検証とworkspaceのfresh readを担当します。Adapterの順序は
`work()` → `checkpoint()` → `compact()` → `continue_task()`です。
公開CLIのlauncherや一般Task Profileはありません。

`compact()`はYohaku checkpointをcommitした後、Coreのleaseを消費し、requestを
journalへ記録してから`POST /api/session/:id/compact`を一回発行します。
戻り値はadmissionです。Completionは、そのnative IDの`session.compaction.started`、
同Sessionの`session.compaction.ended`、同IDのcompleted message、別read-only SQLite
connectionで取得したprojection、その後に新しく取得したactive contextを照合します。
`ended`にはinput IDがないため単独ではcompletionにしません。Native summaryは置換しません。
R3 compact proofに追加pluginは不要です。

限定live acceptanceはnative transitionとbounded task workflowがともに`PASS`でした。
Task fidelityはRuntime completionから独立して評価しています。これで一般taskの正しさは保証しません。
R3のaccepted endpointは`ROLLOVER_OBSERVED`です。R3の次promptはreceiptを作りません。
R4の限定receiptには以下の専用adapterを使います。

`OpenCodeReceiptAdapter`は`2.0.21`のfresh owned Session、single owner、one foreground
bounded text task、native compact一回、handoff一回、known terminal `http.request` observer、
後続body mutatorなし、retry無効に限定してreceiptと別inputのbounded continuationを接続します。
確認したprovider形式はOllamaのOpenAI-compatible HTTP `messages` / exact user textです。
Local controlled provider fixtureによる実OpenCode acceptanceで、許可前dispatch 0件、
許可後のhandoff dispatch 1件、terminal body hashとendpoint raw bytes hashの一致を確認しました。
Fixtureは実model inferenceやcontent qualityの評価を行いません。

このprofileはnative configの`permissions: [{action: "*", resource: "*", effect: "deny"}]`と
既存builtin `opencode.config.agent`を必要とします。Adapterはeffective build agentの最後のruleが
deny-allであることを毎回確認し、terminal HTTP bodyにtool定義があれば送信前に拒否します。
Native tool snapshotは`execute`を含む全handlerを除外するため、modelが未advertiseのtoolを要求しても
実行できません。Receipt responseが意図的に`execute`を要求するlive negativeで、native tool error、
`executed=false`、side-effect fileなしを確認しました。後続model stepもgateで拒否して停止します。
Tool callを観測した後の`_no_tools()`だけを事前抑止の根拠にはしていません。

Embedding hostは`OpenCodeReceiptHost`を先に起動し、同梱の`opencode_receipt_hook.mjs`を
専用plugin directoryへコピーし、そのdirectoryと`host.options`をnative configへ登録します。
Optionsの認証tokenはprivate temporary configで扱います。Hostはqualified builtin graph、
terminal位置、後続mutatorなし、専用Session/server/configの所有を保証し、
`known_terminal_graph=True`として明示します。Adapterはactive plugin catalogとobserverの
file bytesを再照合します。Catalogはcallback順序を列挙するAPIではないため、末尾位置の
保証を置き換えません。Unknown graphではreceiptを有効にできません。

`work()` → `checkpoint()` → `compact()`の後、existing `HandoffDocument`を
`offer_receipt()`へ渡します。既存storeへdurable commitし、`resume:false`でnative inboxへ
admitしたID / Session / payload hashをAPIと独立SQLiteで確認して`HANDOFF_OFFERED`にします。
Core handoffは`offer_handoff(None, expected_snapshot=...)`で未束縛にし、
`continuation_turn_id == ""`を保持します。ReceiptはCore continuation permitを消費しません。
ここではreceiptを発行しません。`promote_receipt()`はsame native inputをnative flowで
contextへ昇格します。Terminal observerがactual provider Requestをbytesへコピーして待ち、
`observed`通知後にownerがcurrent candidate IDを`authorize_receipt()`へ渡します。
`observe_current`は毎回新しく読んだ既存`CurrentContext`を返し、`owner_alive`は専用ownerの
継続所有を検査します。Target endpointは`provider_request_url`へexactに固定します。

Gateはnative message / context / handoff / task revision / workspaceを新しく照合し、
current host-local epoch/counterへ一回だけauthorizationを結び付けます。このIDはnative HTTP
attempt IDではありません。Hook内でbodyを再照合して以前のRequest参照から切り離し、
terminal sealでfresh stateを再確認した後、既存`receive_handoff()`へreceipt evidenceを渡します。
Receiptのauthorityは送信直前のexact request incorporationです。Model受領や意味理解の証明では
ありません。Receipt判定はSSEとmodel outputに依存しません。Task continuationは後述のfresh
reconciliation後に別inputで実行します。

Abort、replacement、retry、identity/hash/body不一致、unknown graph、stale state、owner loss、
deadline、disposal、duplicate releaseでcandidateを失効させ、dispatchを拒否します。
Provider failureによるnative retryも停止します。Receipt後の失敗ではhistorical evidenceを保持して
`RECOVERY_REQUIRED`とし、old observationやauthorizationを新attemptへ流用しません。
R3 CompletionPolicyは保持し、late bindingには既存Core semanticsを使います。
Adapter固有のCore / schema変更はありません。

Receiptがsettledした後、`qualify_resume(reassess=...)`でSession APIとcurrent contextを新しく読み、
独立SQLite transactionのtranscript / inbox / pendingと照合します。Task / workspaceも新しく読み、
trusted bounded-task observerが完了済みか、historical next actionがまだ必要かを再評価します。
`reassess(document, current, state)`は実task stateを読み、必要なnext actionか、完了済みなら`None`を返します。
再評価後にもAPI / SQLite / taskを読み直し、状態が変わればauthorityを失効させて停止します。
Receipt gateのpre-dispatch observationやSSEの接続状態をfreshness proofへ流用しません。

R4-R2では、未完了workのqualification後に`continue_task(next_action)`がfresh stateを再確認し、
post-receipt `claim_continuation(expected_snapshot=...)`を既存append-only evidenceへ保存してから
新しいpromptを一回送ります。Nativeが発行したactual input IDをadmission、current context、
独立SQLiteで観測し、task専用terminal gateで待ちます。Receiptのinput ID、authorization、
attempt ID、body hashはtaskへ流用しません。

Ownerは`task_observed`を待ち、current task attempt IDを`authorize_continuation()`へ渡します。
Adapterはactual native IDを`bind_continuation()`へ渡し、そのSnapshotを保存した後、fresh state / revisionを
再確認してgateをauthorizeします。Terminal sealでもbody / current bindingを再照合してからreleaseします。
`complete_continuation()`は新しいAPI / SQLiteでcompletionを確認します。Hostがtask-specific assessmentを
行った後、`final_observation()`でtask / workspace、settled context、active / pendingなしを再確認します。

Local controlled providerによるfresh acceptanceで、stage one、receipt、stage twoのnative markerを
各一回、task provider execution一回、binding保存後のdispatch、final fresh stateを確認しました。
R4-P-Iでは、この限定profileで`verify_resume(assess=...)`まで接続し、既存の
`Controller.verify_resume()`による`RESUME_VERIFIED`を確認しました。既存`ResumeProof`は使用せず、
Coreのmodel・verification semantics・保存形式も変更していません。

`final_observation()`の後、ownerが`verify_resume()`を一回呼びます。Adapterは保存済みの
claim、actual inputのbinding、task専用observation・authorization・seal・completion、final observationを
照合します。Receipt inputとtask inputは別identityであり、receiptのbody hash・attempt・authorization・
terminal observationをtask completionの証拠へ流用しません。Bindingがauthorizationとsealに先行して
保存されたことも確認します。新しいAPI readで取得したcontextを独立SQLiteのtranscript・queueと照合し、
同じSession・bound input、`finish="stop"`、successful idle、active / pendingなしを要求します。

`assess(document, current, state)`はtrusted embedding hostのbounded task assessorです。
毎回task fileとprovider側の観測を読み、同じ未完了actionの完了とnonduplicationを検査します。
Model output、callerが指定したPASS、cached assessmentを渡す入口ではありません。戻り値は
既存recordへ保存する小さな辞書で、次の値を持ちます。

| Field | このprofileで照合する値 |
|---|---|
| `status` | task assessmentの`PASS` |
| `current` | 新しく読んだtask / workspaceに基づく`encode(current)` |
| `task_input_id` / `terminal_id` | actual taskのnative user input / successful assistant message ID |
| `provider_attempts` | provider側で観測した全task実行。`native_id`、`host_local_attempt_id`、`body_sha256`を持つ一件だけのlist |
| `task_observation_ref` | trusted hostが保存したtask assessmentの参照 |
| `stage_one_count` / `receipt_count` / `stage_two_count` | 独立transcriptで数えた`STAGE_ONE_DONE` / `RECEIPT_ONLY` / `STAGE_TWO_DONE`が各1回 |
| `tool_execution_count` | run全体で0回 |

Marker名はこのbounded taskのcriteriaです。Adapterのnative terminal判定はmarker文字列に依存しません。
Assessorは保存recordの参照先も保持し、actual task state・revisionと各countの根拠を検査する責務を持ちます。
Markerだけ、またはbooleanだけではverificationになりません。

Adapterはassessment前後のfresh readが一致することを確認し、既存`_record()`で
`runtime_resume_verification`を保存します。新しいrecordはHandoff、receiptとtaskのidentity、claim、
task attempt、各保存recordへの参照、final revision、assessmentとnonduplicationを持ちます。
既存transcriptやbodyの全payloadは複製しません。保存後にもassessor、API / SQLite / task read、
保存済みchainとCore Snapshotを再確認し、既存`ResumeVerification`を構成してCoreへ渡します。
成功時は`resume_verified`を記録します。最終検証もSSEをauthorityにしません。

Send / completion / durable writeが不確かな場合はclaim / bindingを戻さず停止し、blind retryしません。
最終検証の失敗やCoreからの拒否でもadapterはstateを修復せず、ownerを停止します。
Verification recordの保存に失敗した場合、Coreのverifyは呼びません。Core成功後の成功記録保存に
失敗した場合はCoreのin-memory stateが`RESUME_VERIFIED`でもownerを停止し、成功を返しません。
二回目のverifyは拒否します。

R3 completionのSSEはvolatileです。切断・必要event欠落・identity競合時は`AMBIGUOUS`または
attachment停止とし、再送やcompletionの推測をしません。OpenCode proofはin-memoryで、
Runtime固有の証跡は別recordに保持します。Schema-1 journalへ保存するのはcheckpointと
dispatch前のCore requestまでです。Restart、proof restore、observation-loss reconciliationは
`UNSUPPORTED`です。Native transcriptはYohaku checkpointやarchiveへ変換しません。

R4のretry-enabled path、restart、cross-process recovery、unknown plugin graph、later mutator、
tools-enabled receipt、parallel / background / subagent、external client、DCPはunsupportedです。
General tool incorporation、external client conflict、background / parallel work、
plugin conflict、crash / power-loss durabilityは`NOT_RUN`です。Hostの排他的利用条件は
Runtime-wide atomic freezeを意味しません。共有契約は[Adapter Contract](../development/adapter-contract.md)を参照してください。
Hostは宣言したtask / workspace scopeに対する外部変更を最終検証中も排除し、各observerで新しく読みます。
今回のPASSは実OpenCodeとlocal controlled providerによる一回のbounded acceptanceです。
実model inference、一般taskの品質、installed wheelでの今回の経路は`NOT_RUN`です。
