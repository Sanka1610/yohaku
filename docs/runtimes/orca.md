# Orca structured Codex

現在の判定はProduction adapter prototype — transition-onlyです。限定profileのtransitionを既存Coreへ接続し、`ROLLOVER_OBSERVED`まで確認しています。Recovery on Orca structured Codex: unsupported/unqualifiedです。

## Role and qualified profile

`yohaku.orca_adapter`をpackageへ同梱しています。Embedding hostがattached sessionとWindows RPC/process readersを渡した場合にだけactivateします。

| 項目 | Exact条件 |
|---|---|
| Profile | `orca/structured/codex/local` |
| Orca | `1.4.218`、Windows native / local |
| Workspace | Windows-local、`executionHostId=local`、`wslDistro=null` |
| Integration / owner | Orca structured Codex session / Orca |
| Codex | `0.159.0-alpha.12.1` |
| Request | 一つのfresh owned thread、一回のcompact、retry disabled |

内部surfaceのidentity、journal、native event契約に依存するため、exact versionはhard requirementです。別versionを自動的にqualifiedとしません。

## Ownership and authority

Supervisorには`SessionProfile(harness='codex', provider_session_id=<native thread>, trigger_authority='orca', ownership_source='orca-structured-session')`を登録します。OrcaはTRIGGERとOBSERVER、CodexはOBSERVERです。一つのControllerとSessionStoreを共有し、Codexへの直接triggerや第二の接続は使いません。

Adapter-private bindingはOrca runtime/PID/start、worktree、Orca session、provider handle/thread、Codex child/PID/start/parent、fence、journal epochを保持します。Cursorの後退とidentity変更は拒否します。Executableの存在だけでownershipとはしません。

## Host contract

`OrcaLocalHost`にはruntime metadata path、session index path、一つのnative rollout path、Orca session IDと、trusted embedding hostの`rpc(method, params)` / `inspect(runtime, record)`を渡します。RPC readerはrequest IDとresponse runtime identityを検査し、mutationをretryしません。Inspectorは実processのPID/start/parent/executable、actual executable versions、selected worktreeをfreshに読み、`orcaVersion`, `codexVersion`, `platform`, `structured`, `processes`, `worktree`を返します。Worktreeは`id`, `path`, `workspaceId`, `executionHostId`, `wslDistro`、processは`pid`, `parentPid`, `startedAtMs`, `executable`を持ちます。

`adapter.register(supervisor)`でqualified sessionを登録します。Semantic boundaryを観測するhostはCurrentContextとBoundaryVerificationを`adapter.checkpoint()`へ渡し、durable checkpoint後に`supervisor.request_transition(session, requester='orca', observe=<current reader>, now=<clock>)`を呼びます。ObserverはこのCoreを共有します。Static `yohaku doctor`はlive sessionを探索しません。登録済みSupervisorを渡したdoctorはownership、trigger、observers、exact profileを表示できます。

既存SessionStoreはPOSIX persistenceを要求します。今回のexternal Yohaku host/storeはLinux側に置き、Orca/Codexとtask workspaceはWindows native/localです。Windows-native SessionStoreは実装していません。

## Verified path

Fresh complete structured history、native previous turn terminal、tool / approval / queued input / known background workの不存在、same ownership/fenceを確認します。Hostのsemantic boundary evidenceと既存Core policyでcheckpointを作り、dispatch直前にもfresh stateを照合します。

一回の`agentSession.conversationCommand(command='compact')`後、一つのnew native turn、durable `compacted`、`ContextCompaction` item completion、`task_complete`、Orca completed/successとfresh readbackを検査します。このpositive proofが成立した場合だけ、既存Coreの`ROLLOVER_OBSERVED`へ進みます。RPC受付、ledger success、prepared/completed文字列だけでは成功としません。

Orcaのadmissionは`expectedRuntimeFence`を検査しないため、adapterがrequest前後にruntime/fenceを照合します。Orca operation IDはnative compaction requestへ伝播しません。一つのowned session、一つのrequestとfresh native prefix/sequenceで相関し、複数compactionや相関不足ではAMBIGUOUSへ停止します。再compactは送りません。

## Recovery and limitations

Phase 5-Rでは固定sourceとfresh sessionのtools-free入力一回でsend orderingを確認しました。Orca structured sendはmessage保存後にdelivery loopを自動起動し、native `turn/start`へ渡します。Sendのpending受付にはnative turn/input identityがなく、そのidentityを後から観測することはできますが、観測に対するclient acknowledgementを待つ経路はありません。`agentSession.hold/release`もこの版ではno-opです。

既存early-bound Core offerはactual turn identityを必要とします。Stock structured surfaceにはnative turnを確保してからbound Handoffを作成し、その後にpayload deliveryをreleaseする経路がありません。Input送信後の事後bindや観測時間差をgateとして使うことはqualificationしません。既存late-bound経路に必要なnon-effectful native receiptとbind-before-effectも成立しません。

従ってこのprofileのrecoveryはUNSUPPORTEDです。`offer_handoff()`はinput送信、Handoff作成、continuation claimの前に既存の`ORCA_RECOVERY_UNQUALIFIED`で停止します。Ordering probeでnative payloadの一致とtools-free terminalを確認したことは、Core receiptやresumeの成功を意味しません。Providerの最終serialized request membershipやHTTP開始時点を取得した証拠でもありません。

`HANDOFF_RECEIVED`はNOT_REACHED、continuationと`RESUME_VERIFIED`はNOT_RUNです。Core semantics、persistent schema、ResumeProof / ResumeVerificationは変更していません。

別provider、generic terminal、WSL workspace、SSH/remote、orca serve、restart/reconnect、auto-compaction race、複数transition、parallel/background/subagent、managed-hook generic integrationは対応範囲外です。Orca plugin、UI、hook installer、provider/config変更は含みません。

既知のMCP startup failureはenvironment issueとしてsupport判定と分離します。今回のtools-free pre-taskとcompactionにはnon-blockingでした。MCPを必要とするtaskは未検証です。
