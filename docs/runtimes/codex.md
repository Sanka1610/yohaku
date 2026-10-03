# Codex Runtime

CodexはBetaで既存検証経路をSupportedとします。対象はcurrent lifecycle-only launcherと固定document-review taskで、CLI registryのprofile maturityは`alpha`を保持します。Profileごとの対応機能と制限は[Runtime support](../runtime-support.md)に記載します。Current launcherは`0.158.0-alpha.2.1`、Historical Referenceは`0.155.0-alpha.16.4`です。

## Version pinと実行surface

Current launcherは専用App Serverをstdioで起動し、fresh threadを作ります。Exact version pinを維持する理由は、App Serverのexperimentalなdynamic tools、Hook payloadとcompletion eventの形、起動時の設定keyに依存しており、互換version rangeをまだ確認していないためです。Version不一致を一般的な非互換性の実証とは扱いません。

試したhostはWSL2 Linux / CPython `3.14.4`です。Current preflightではLinuxとPython `>=3.11`を要求し、WSL2やpatchの一致は要求しません。

Lifecycle-only launcherは専用の到達不能loopback providerを設定し、credentialとHookを読み込まず、`initialize`、`initialized`、`thread/start`以外のwork送信を拒否します。Unexpected `turn/*` / `item/*`もfailureです。

Document-review runnerはprofile-owned dynamic toolsとsynchronous command Hooksを使います。実装は`gpt-5.6-luna`、reasoning lowを選択しますが、Alphaの公開記録だけではprovider / account全体の互換性を確定できません。Credential homeと`auth.json`のprivate permission、owner、file type、symlink、replacementを検査し、実行直前にも照合します。

## Workとidentity

Historical Referenceでは測定した`Bash` / `apply_patch`を`PreToolUse` / `PostToolUse`で観測します。Tool completion後もterminal effectとworkspace更新をtrusted hostが確認するまでpendingを残します。Hook timeout、nonzero exit、malformed / missing outputには`FAIL_OPEN`経路があり、normal denyはRuntime-wide freezeを証明しません。

Document-reviewは`read_review_inputs` / `publish_review_report`だけをadmitし、dynamic tool resultとcurrent workspaceを独自ledgerで照合します。`commandExecution`、`fileChange`、`mcpToolCall`の観測はtask acceptanceを拒否します。Task契約は[専用文書](../task-profiles/document-review-report-v1.md)を参照します。

Native identityはthread / session、turn、item、Hook run、dynamic callです。Coreのrequest、lease、generationと、host-local owner / attachment / sequenceは別です。Native notificationはYohaku request IDを提供しないため、一つのowned thread、一つのoutstanding request、ordered stream、persisted turn / item bindingで相関します。Core generationをnative context generationとして表示しません。

## Manual completion

Checkpoint commitとcurrent-state再検査の後、`thread/compact/start(threadId=...)`を一回送ります。RPC responseの`{}`はadmissionです。Completionには同じrequest / bound compact turnの次の三要素を要求します。

1. `contextCompaction` itemのsuccessful `item/completed`。
2. Successful `PostCompact`に対応する`hook/completed`。
3. Errorなしのcompact `turn/completed`。

`item/started`、Hook単独、assistant self-reportではcompletionにしません。Dispatchまたはcompletionが不明なら`AMBIGUOUS`です。Exact duplicateから新しいhandoffやcontinuationを作りません。Historical manualのlate reconciliationは保存済みowner mappingが完全な場合だけです。

## Handoffとresume

Manual pathではcompleted requestへdurable handoffを結び付け、one-shot continuation permitの消費を保存した後、一つの`turn/start`を送ります。Correlated `SessionStart(source=compact)` Hookへ`additionalContext`としてhandoffをinjectします。Matching Hookへ同じhandoffを再提示できる範囲でも、別continuation turnを作りません。

Receiptはbound continuationのcompleted assistant itemにあるexact `YOH_ACK:<handoff-id>:<generation>`です。Duplicate ACKはno-opです。Deliveryやtool成功だけでreceiptにしません。

Receipt後、trusted observerはcurrent task、intent / execution revision、workspace、unresolved workを読み直します。Assessorはactual continuation items、same task、未完了work、completed workの非反復を照合します。Assessment前後のstateが一致し、receiptとterminal completionも相関した場合だけCoreが`RESUME_VERIFIED`へ進みます。

## Historical native-auto

Codex起点の`PreCompact(auto)`をactive turnへ結び付け、compaction itemとsuccessful `PostCompact`で完了を確認します。Manual RPCは送りません。Active turnのterminal eventを架空のcompact turnへ変換しません。

同じactive turnへhandoffをinjectするsame-turn recoveryです。Prior checkpointはhistorical / stale、`EmergencyDelta`はunverifiedとして扱い、fresh task stateを読み直します。Manual requestとの競合、二回目のnative compact、identity mismatchは停止します。Native-auto restartはpost-compaction item provenanceをthread readだけで復元できないためunsupportedです。

## Storageと制限

Codexのjournal / restart経路はschema-1、`CompanionController`、`CODEX_HOME`由来です。Historical manualには保存済みbindingとfresh Runtime readを使う限定reconciliationがありますが、leaseやpermit、inflight work ledgerを復活させません。Current document-reviewのrestartはunsupported、retained stateはinspection用です。

Historical Referenceのvisible-turn collectorは、trusted selectorが選択・redactしたturnだけをYohaku archiveへ保存します。Native transcript全体の自動importではありません。Document-reviewにarchive機能はなく、lifecycle profileでも検証していません。

Alphaのdocument-reviewは公開文書2点、compact一回、report一つで`RESUME_VERIFIED`へ到達しました。Hookがtask toolを拒否した先行runもあり、allowlist修正後の成功とexisting-output拒否を別結果として保持しています。これは現在の未公開cleanupをlive retestした結果ではありません。共通の制限は[Runtime support](../runtime-support.md#共通のknown-limitations)、durabilityと復旧は[Storage and Recovery](../storage-and-recovery.md)を参照します。
