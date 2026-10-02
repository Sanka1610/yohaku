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
既存profileのaccepted endpointは`ROLLOVER_OBSERVED`です。Stock pi-ai /
OpenAI-compatible経路のreceiptは`UNSUPPORTED`です。Restartは`UNSUPPORTED`、
optional task continuationは`NOT_RUN`、`RESUME_VERIFIED`は未成立です。
Native binding / completionはin-memoryで、schema-1 snapshot journalへ保存しません。
Yohaku checkpointとadapter decision record、DSH native persistenceは別です。

Parallel、background、subagent、alternate client、general tool incorporation、
installed-wheel live acceptance、crash recoveryは未検証です。
専有hostの条件はexternal writer排除やRuntime-wide atomic freezeを保証しません。
共有契約は[Adapter Contract](../development/adapter-contract.md)を参照してください。


Receiptは`messages-plain-text-owner-no-retry`を明示的に有効化した場合だけ
対応します。対象は公式DeepSeek Messages adapter、全request historyがplain text、
fresh Session、single Agent / single owner、toolなし、追加extension fieldなし、
既知のgate ordering、retry disabledです。Loopback protocol fixtureとstock HTTP
transportによるmechanical acceptanceで`HANDOFF_RECEIVED`まで確認しました。
外部DeepSeek API、実model、実taskの継続品質は検証していません。

Embedding ownerは公式`DeepSeekAdapter`の`prepareExtensions`へ
`host.prepareExtensions(request)`を接続し、fresh Sessionへのattach時に
`host.enableReceipt({ provider, adapter, DeepSeekAdapter, options, observeCurrent })`を
呼びます。`options`はadapter自身が使う同じresolved optionsで、
`retryPolicy.maxRetries`を`0`にします。Extension registryはreceipt gateだけを
mountします。Hostは返却fieldが空であることも確認します。Providerを切り替えたり、
別adapterから同じcallbackを呼んだりする構成は対応範囲に含みません。

`observeCurrent`はtask / workspaceを直接読み、Python側のtrusted observerと同じ
`CurrentContext`のJSON表現を返します。Gate中はAgentがrunningなので、
`observe()`や`whenIdle()`を呼びません。Session flushと独立read handle、task readを
行い、authorization直前にもtask / workspaceとSession seqを再確認します。

Python側では`compact()`成功後、既存`HandoffDocument`を
`offer_handoff(document, observe=...)`へ渡します。Durable commit / readback後、
`createUserMessage()` → `inject()`でnative MessageIdを取得し、non-wakingの
inbox spliceを照合します。この時点は`HANDOFF_OFFERED`です。
明示的な`receive_handoff(observe=...)`がreceipt検査用requestを一回だけ起動します。
次のnative turnは公開turn lifecycleから予約し、実際のstart frameとの一致を確認します。
既存Coreの`claim_continuation()`はこのrequest一回のbindingに消費し、
receipt後のtask continuationを許可するauthorityにはしません。

Hostはnative exact membership、MessageId、handoff text hash、native turn / step /
`LlmAttemptId`、host-local call ordinalとepoch / attempt counter、serialized body hashを
bindします。公式extension gateでbodyをfreezeし、追加fieldを返さず、fresh readと
one-shot authorization後にcurrent attemptだけをreleaseします。
公式adapterのHTTP成功後のacceptance transactionをreceipt proofとして保存し、
既存Coreの`receive_handoff()`へ接続します。Model outputやACKは使いません。
`LlmAttemptId`はHTTP attempt IDではなく、host-local identityもnative identityではありません。

Abort、identity / hash mismatch、stale observation、retry開始、owner loss、host disposal、
profile逸脱ではcandidateを失効させて停止します。Late authorizationは再開できません。
Receipt metadataはadapter decision recordに閉じ込め、native log全体を複製しません。
Receipt後に新しいturnを自動起動しません。`HANDOFF_RECEIVED`後のtask continuation
と`RESUME_VERIFIED`は未評価です。

Receiptはstock pi-ai / OpenAI-compatible経路、他provider adapter、追加extension fields、
file / image / tool projections、retry、restart、parallel / background / subagentでは
`UNSUPPORTED`です。DSH Desktopは未検証です。
