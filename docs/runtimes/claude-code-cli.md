# Claude Code CLI Runtime

Claude Code CLIのadapterはexperimentalです。Formal operational launcherはありません。Subscription manual completionとlocal Ollama recoveryを分けて扱い、現在の一覧は[Runtime support](../runtime-support.md)に記載します。

## Tested configuration

Claude CLI `2.1.280`、Linux、`claude -p` / stream-json / synchronous command Hooks、fresh exclusive sessionを試しています。LibraryはCLI起動、authentication、billingを管理しません。

Subscriptionではmanual completionを確認し、handoff以降のrecoveryはuntestedです。Local Ollama `0.34.1`ではSpark-X2.5-4Bのfull-identity recoveryに成功一回とmatching repeat失敗一回があります。Qwen3.5 9Bのfull-identity recoveryにも成功とreceipt不一致があり、別の`host-nonce-v1` profileでbounded recovery一回を確認しました。Repeatabilityやsubscription互換性はこの成功から確定しません。

## Native eventとcompletion

Collectorはstartupの`SessionStart`、foreground toolの`PreToolUse` / `PostToolUse`、manual `PreCompact` / `PostCompact`、`SessionStart(source=compact)`をordered metadataとして捕捉します。捕捉時にattachment、request、generation、sequenceをbindし、過去eventへ後からidentityを付け足しません。

Native identityは`session_id`とnative tool IDです。Continuation turn、attachment、request、Core generationはhost-local / Core identityであり、native identityへ読み替えません。相関は一つのexclusive session、一つのrequest、serialized collectorを前提とします。

`ClaudeCLIAdapter.compact()`はverified boundaryとcheckpoint後にbindingを保存し、manual `/compact`を一回dispatchします。`ClaudeManualCompletionPolicy`は次を同時に確認します。

- Startup、request、三Hookのnative sessionが一致する。
- Attachment、request、generation 1、sequence、evidence referenceがbindingと一致し、一意である。
- Manual requestの後に`PreCompact(manual)`が一回。
- その後に`PostCompact(manual)`と`SessionStart(compact)`が各一回。両者の相互順序は固定しない。
- Collection windowがclose / drain済み、transport成功、全eventがpositive `closed_seq`より前。
- Coreへ提出するcompletion eventが一件でrequestと一致する。

CLI result、process終了、各Hook単独はcompletionではありません。Missing / failed / stale / foreign / extra eventはproofを拒否し、ownerを`AMBIGUOUS`として停止します。Timeout後のlate eventでclose済みownerを再開しません。

Completion-only policyはcontinuationを許可せず、`ROLLOVER_OBSERVED`で停止します。Recovery hostは同じowned print processを保持し、successful terminalでlogical collection windowだけを閉じます。

## Handoffと二つのreceipt方式

Recoveryはcompleted requestとcheckpointへdurable handoffを結び付け、readbackを確認します。One-shot permitから一つの`ClaudeContinuationBinding`を作り、handoffとcurrent instructionsを同じprint processへ一回submit / flushします。`ClaudeDelivery`はtransport deliveryであり、receiptではありません。Submit中にHook callbackをpumpして順序を混ぜません。

Full-identity receiptはhandoff、checkpoint / hash、handoff hash、compact request、native session、attachment、generation、continuation request / turn、logical taskをtool引数で返します。Adapterはmatching `PreToolUse`、handler result、successful `PostToolUse`を照合します。

`host-nonce-v1`はhostがfull identity tupleを保持し、modelにはhandoff固有の128-bit、22-character nonceだけを返させます。Exact match、未使用、native session、owner、attachment、request、generation、continuation、tool ID / result / sequenceを照合します。Mismatch、stale、foreign owner、duplicateは拒否し、nonceの補正・再発行やuncertain submissionのretryは行いません。

両方ともadapter-defined protocolです。引数なしACK、hidden storageからのnonce取得、printed ACK、後続work成功はreceiptにしません。Semantic understandingは評価していません。

## Fresh stateとresume

Receiptがmatching `PostToolUse`まで完了した後に、`observe_fresh()`がcurrent task、intent / execution revision、workspaceを二回読み、安定性を確認します。一回限りのfresh-read tokenを返し、actionはexact tokenをechoします。Action直前にもcurrent stateを再検査します。

Fixed recovery gateはreceipt → fresh read → actionの順で各一件だけadmitします。Handler returnだけでは取込済みにせず、native tool ID、result hash、collector sequence、successful post eventを確認します。

Fixture固有assessorはactual effect、read / action items、unresolved work、completed workの非反復、same-taskを照合します。Receipt、fresh observation、token-bound action、native terminalとassessment前後のstate一致を確認してから`ResumeProof`を提出します。Local成功runの`RESUME_VERIFIED`は、この限定workflowだけの結果です。

## Failure、storage、restart

Compact dispatch、handoff submission、writeの成否が不明ならresendしません。Receipt不一致、stale token、changed state、assessment不足ではresumeを拒否します。Normal deny、Hook failure、unknown outcomeは区別し、Hook timeout / malformed / missing outputの分類だけでRuntime全体のfail-closedを主張しません。

Checkpoint / handoffはYohaku store、event projectionはadapter metadata、native session / transcriptはClaude側storageです。Native transcriptをYohaku archiveへ自動importせず、visible-turn collectorも未実装です。

Adaptersはfresh store、fresh exclusive session、一つのattachmentだけを受け入れます。Process restart、general reconnect、existing-session attach、inflight collector再構成はunsupportedです。Claude completion bindingはCodex schema-1 codecへserializeせず、old leaseやpermitを復元しません。

## Local modelで残った問題

Sparkのmatching repeatとMiMo試行では最初のcommand引数不足でadapter前に停止しました。Qwen3.5 4Bの別backendにはHTTP 500、official 4Bにはfull-identity receipt不一致がありました。Qwen 9Bの低context nonce試行は`PreCompact`だけで`AMBIGUOUS`でした。成功一回を信頼性の証明や必須自動gateにしません。

共通の制限は[Runtime support](../runtime-support.md#共通のknown-limitations)、durabilityは[Storage and Recovery](../storage-and-recovery.md)を参照してください。
