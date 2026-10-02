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
TS pluginは不要です。

限定live acceptanceはnative transitionとbounded task workflowがともに`PASS`でした。
Task fidelityはRuntime completionから独立して評価しています。これで一般taskの正しさは保証しません。
Coreのaccepted endpointは`ROLLOVER_OBSERVED`です。次promptの実行を確認しても、
独立receiptは`UNSUPPORTED`で、`RESUME_VERIFIED`には進みません。

SSEはvolatileです。切断・必要event欠落・identity競合時は`AMBIGUOUS`または
attachment停止とし、再送やcompletionの推測をしません。OpenCode proofはin-memoryで、
Runtime固有の証跡は別recordに保持します。Schema-1 journalへ保存するのはcheckpointと
dispatch前のCore requestまでです。Restart、proof restore、observation-loss reconciliationは
`UNSUPPORTED`です。Native transcriptはYohaku checkpointやarchiveへ変換しません。

General tool incorporation、external client conflict、background / parallel work、
plugin conflict、crash / power-loss durabilityは`NOT_RUN`です。Hostの排他的利用条件は
Runtime-wide atomic freezeを意味しません。共有契約は[Adapter Contract](../development/adapter-contract.md)を参照してください。
