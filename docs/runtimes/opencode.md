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
後続body mutatorなし、retry無効に限定して`HANDOFF_RECEIVED`まで接続します。
確認したprovider形式はOllamaのOpenAI-compatible HTTP `messages` / exact user textです。
Local controlled provider fixtureによる実OpenCode acceptanceで、許可前dispatch 0件、
許可後のhandoff dispatch 1件、terminal body hashとendpoint raw bytes hashの一致を確認しました。
Fixtureは実model inferenceやtask continuationの評価を行いません。

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
ありません。Receipt判定はSSEとmodel outputに依存せず、receipt後の追加promptは送りません。

Abort、replacement、retry、identity/hash/body不一致、unknown graph、stale state、owner loss、
deadline、disposal、duplicate releaseでcandidateを失効させ、dispatchを拒否します。
Provider failureによるnative retryも停止します。Receipt後の失敗ではhistorical evidenceを保持して
`RECOVERY_REQUIRED`とし、old observationやauthorizationを新attemptへ流用しません。
R3 CompletionPolicyとShared Core / schemaは変更していません。

Receiptがsettledした後、`qualify_resume(reassess=...)`でSession APIとcurrent contextを新しく読み、
独立SQLite transactionのtranscript / inbox / pendingと照合します。Task / workspaceも新しく読み、
trusted bounded-task observerが完了済みか、historical next actionがまだ必要かを再評価します。
`reassess(document, current, state)`は実task stateを読み、必要なnext actionか、完了済みなら`None`を返します。
再評価後にもAPI / SQLite / taskを読み直し、状態が変わればauthorityを失効させて停止します。
Receipt gateのpre-dispatch observationやSSEの接続状態をfreshness proofへ流用しません。

限定R4-R acceptanceではfresh post-receipt stateとunresolved workの再評価を確認しました。
Stage one marker一回、receipt一回、stage two未実行をtask fileとnative SQLiteで確認しています。
R4-Iは唯一のCore continuation permitをreceipt inputへ消費済みで、handoffのcontinuation IDも
そのinputに固定されています。Receipt後の別inputをauthorizeする既存Core semanticsがないため、
`HANDOFF_RECEIVED`で安全停止します。`continue_task()`は送信前に拒否します。
`RESUME_VERIFIED`は`NOT_REACHED`です。別attemptのcontinuation、ResumeProof接続、stage two完了、
continuation send ambiguityは`NOT_RUN`です。Content qualityは評価していません。

R3 completionのSSEはvolatileです。切断・必要event欠落・identity競合時は`AMBIGUOUS`または
attachment停止とし、再送やcompletionの推測をしません。OpenCode proofはin-memoryで、
Runtime固有の証跡は別recordに保持します。Schema-1 journalへ保存するのはcheckpointと
dispatch前のCore requestまでです。Restart、proof restore、observation-loss reconciliationは
`UNSUPPORTED`です。Native transcriptはYohaku checkpointやarchiveへ変換しません。

R4のretry-enabled path、restart、cross-process recovery、unknown plugin graph、later mutator、
parallel / background / subagent、external client、DCPはunsupportedです。
General tool incorporation、external client conflict、background / parallel work、
plugin conflict、crash / power-loss durabilityは`NOT_RUN`です。Hostの排他的利用条件は
Runtime-wide atomic freezeを意味しません。共有契約は[Adapter Contract](../development/adapter-contract.md)を参照してください。
