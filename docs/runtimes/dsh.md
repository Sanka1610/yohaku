# DSH Runtime

`DshAdapter`と`DshNativeCompletionPolicy`は、DSHのnative serviceへ
`dsh_host.mjs`から接続する限定adapterです。試した対象は`0.2.0-rc.2`、
公式tag `dsh-v0.2.0-rc.2`、Linux / WSL2、Node `22.22.1`、CPython `3.14.4`、
headless、fresh Session、single Agent、toolなしのforeground work一件、
stock BasicCompactionのmanual compact一回です。Local Ollama `0.34.1` /
`qwen3.5:4b`で確認しました。Native service API、event列、projectionとの
対応を保つためhostとadapterはDSH `0.2.0-rc.2`を要求します。他versionは未検証です。

Embedding hostはstock compactorを`auto:false`でmountし、専有Sessionと
`SessionStore`を用意します。Python ownerへのtransportと、task boundaryの
検証、workspaceのfresh read、直列実行はhostの責務です。
Adapterの順序は`work()` → `checkpoint()` → `compact()`です。
公開CLIや標準SDK transportのlauncherはありません。

AdapterはYohaku checkpointのdurable commitとreadbackを確認し、Coreの
one-shot lease / requestを消費してdispatch前にrecordを保存します。
Native maintenance内でstock `compactNow()`を一回だけ呼びます。
Completionは同じ`compactionId`のstart → summary → replacement → errorなしend、
resultのseq、`ctx.sessions.flush(session)`後の独立JSONL read handleを照合します。
API returnや単独eventではcompletionにしません。

Completionとreadback後に新しく`deriveMessages()`を呼び、同じSession、
end以後のseq、replacementの反映、shadowed messageの置換、current task /
workspaceの一致を確認します。Native summaryは置換しません。
Completion不明は`AMBIGUOUS`、completion後のpost-state不一致は
`RECOVERY_REQUIRED`で停止し、blind retryしません。

限定live acceptanceはnative transitionとfresh post-stateが`PASS`でした。
Coreのaccepted endpointは`ROLLOVER_OBSERVED`です。Receiptとrestartは
`UNSUPPORTED`、optional continuationは`NOT_RUN`、`RESUME_VERIFIED`は未成立です。
Native binding / completionはin-memoryで、schema-1 snapshot journalへ保存しません。
Yohaku checkpointとadapter decision record、DSH native persistenceは別です。

Parallel、background、subagent、alternate client、general tool incorporation、
installed-wheel live acceptance、crash recoveryは未検証です。
専有hostの条件はexternal writer排除やRuntime-wide atomic freezeを保証しません。
共有契約は[Adapter Contract](../development/adapter-contract.md)を参照してください。
