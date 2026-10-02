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
このprofileのtask continuationは`NOT_RUN`です。下記のMessages限定profileでは
text continuationと`RESUME_VERIFIED`まで確認しています。
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
Receipt時点ではCore permitを消費せず、`Handoff.continuation_turn_id`は空文字です。
Receipt turn / MessageIdはadapter側で保持し、receipt interactionの一回性をhostが管理します。

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
Receipt後に新しいturnを自動起動しません。`post_receipt()`はHTTP acceptance後に
`whenIdle()`を待ち、正常な`turn/end`一件、empty inbox、独立readback、fresh
`deriveMessages()`、同じSessionとhandoff、current task / workspaceを照合します。
Gate中のdirect readをpost-receipt observationとして再利用しません。HTTP acceptance後の
request signal破棄はreceiptを取り消しませんが、error / abort terminal、retry、別attempt、
owner lossはresume qualificationを通過できません。

`qualify_resume(observe=..., reassess=...)`はdurable handoffを再読し、post-receipt stateと
declared workspace scopeを照合します。Trusted `reassess(document, current)`は実際のtask
readからhistorical unresolved workを再評価し、まだ必要なら`next_action_candidate`、
完了済みなら`None`を返します。別action、unknown、revision変更、pending workでは停止します。
再評価後の新しいobservationでstateが変わっていれば、continuationは停止対象です。

`continue_task(observe=...)`は成功したqualificationの後に明示的に呼びます。
新しいpost-receipt readとtask readを照合してから、current Snapshotで
`claim_continuation()`を一回だけ消費し、send前に記録します。
再評価済みactionから一件の新しいnative inputを開始し、実際の
`agent/assistant-stream` start frameのturnを`SessionId:turn`へ写像します。
開始前の予測値やHTTP attempt counterはtask turn identityにしません。

既存のnative membership検査と公式Messages serialized gateをtask interactionにも使い、
provider effectを保留します。Coreの`bind_continuation()`成功とbindingのdurable記録後、
current Snapshot、Session、Handoff、claim、actual turn、task/workspaceを再確認して
一回だけreleaseします。Claim後の保存・送信・binding不確実性は`RECOVERY_REQUIRED`で
停止し、permitもbindingも戻しません。二回目のcontinuationや同じHandoffの再利用は拒否します。

`post_task()`は正常な`turn/end`一件、Agent idle、empty inbox、task input一件、独立readback、
fresh projectionとcurrent task stateを照合します。この限定text-only profileのtask effectは
native assistant outputです。Declared workspaceは継続中も変化しないことを要求し、
任意のfile/tool mutationを許可する契約ではありません。

Loopback protocol fixtureとstock transportによるR4-R2 acceptanceでは、receipt turnと
別のactual task turnをbindし、task provider request一件、`FINALIZED`一回、正常な終端と
final fresh stateを確認しました。Task requestをendpoint受信後に切断する別fresh Sessionでも、
消費済みpermitとbindingを保持し、追加送信せず停止しました。実modelの品質評価ではありません。

R4-P-Iでは、`continue_task()`の後に`verify_finalized(observe=...)`を明示的に呼ぶと、
DSH固有の検証結果から既存`ResumeVerification`を構成し、
`Controller.verify_resume()`で`RESUME_VERIFIED`へ進みます。Core、`ResumeProof`、
codec、persistence schemaは変更していません。`continue_task()`単独の返却値は従来どおりで、
最終検証が成功するまでは`HANDOFF_RECEIVED`とbarrierを保持します。

対象taskは未完了項目`FINALIZE`と、再評価済みの入力
`Produce FINALIZED exactly once after current task reconciliation.`です。
`verify_finalized()`は、この固定taskのtext effectだけを評価します。
任意のtaskやfile/tool effectを扱うassessorではありません。

最終検証には、受領済みHandoff、一回だけ消費したclaim、current claimに属するactual turn、
binding保存後の一回のreleaseとHTTP acceptance、保存済みtask completionを要求します。
`final_task()`は既存`post_task()`のidle・empty inbox・flush・独立JSONL readbackを再利用し、
bound turnのstart、正常なend、outputのturn / step / seq / MessageIdとfresh projectionを照合します。
Input、turn、provider requestが各一件であり、send/completionに不確実性がないことも確認します。

Task assessmentは、同じbound turnのoutputが`FINALIZED`だけであり、native log全体でも
そのtextが一回であることを確認します。同じtask / workspace revision、再評価済みaction、
正常な終端、独立readbackを合わせて判定し、assistant textだけでは成功にしません。
この限定text effectでは、前のworkやreceiptを含む余分な出力も拒否します。

保存順序はtask completion → final observation → bounded assessment →
`resume_verified_evidence`です。最後のrecordには、Session、Handoff、claim、bound turn、
dispatch/completion record、terminal、final observation、current task / workspace revision、
assessmentとnonduplicationの参照を持たせます。既存`dsh-events`のchecksum付きrecordと
atomic write / `fsync`を使用します。Record名はadapter検証の根拠を示し、Core成功の記録ではありません。

Record保存後に`final_task()`をもう一度呼び、observation revision以外のnative stateが
同じこと、current Snapshot、durable Handoff、task / workspaceが変わっていないことを確認します。
この最終照合後に`ResumeVerification`を構成し、Coreを一回だけ呼びます。
保存失敗、stale / foreign evidence、不完全な終端、重複、Core拒否ではownerを停止し、
claimとbindingを保持します。再検証で新しいcontinuationを送ることはありません。

Fresh Session一回のloopback protocol fixtureとstock HTTP transportで、この順序から
`RESUME_VERIFIED`への到達とbarrier解除を確認しました。Task request一件、`FINALIZED`一回、
正常な終端とfinal fresh stateが成立しています。外部APIと実modelの品質は検証していません。

Receiptはstock pi-ai / OpenAI-compatible経路、他provider adapter、追加extension fields、
file / image / tool projections、retry、restart、parallel / background / subagentでは
`UNSUPPORTED`です。このreceipt/continuation profileのDSH Desktopは`UNSUPPORTED`です。
