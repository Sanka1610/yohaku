# Hermes Runtime

HermesはBetaで既存検証経路をSupportedとします。対象はlifecycle-only launcherと、single fixture tool、manual compression一回、receipt、fresh continuationで`RESUME_VERIFIED`へ到達した限定adapterです。CLI registryのprofile maturityは両方とも`experimental`を保持します。Profileごとの対応機能と制限は[Runtime support](../runtime-support.md)に記載します。

## Source pinとtested configuration

Hermes `0.21.0`、source `c5594ec4b34097cafbe24deb6dfd9ac4b21d411d`、native `HermesCLI`のin-process integrationを対象とします。Current launcherはsource root、clean tree、`<source>/venv`を要求します。

Source pinを維持する理由は、`_manual_compress`、`_session_db`、`conversation_history`、`_resumed`、agent initialization、dotenv discoveryなど非公開の内部実装へ直接依存しているためです。Clean treeはversion表示だけでは確認できない実行コードの変更を拒否します。Host venvは同じprocessからnative dependenciesを使うため必要です。Package/plugin APIの互換rangeが確認できた時点で再評価します。

試したhostはWSL2 / Python `3.11.16`です。WSL2とexact Python patchはhard requirementではありません。Historical adapterのlive実行はcopied sourceでした。その後non-editable wheelの導入とoffline synthetic rehearsalを確認しましたが、installed wheelによる新しいlive transitionはuntestedです。

Historical live workflowは`openai-codex` / `gpt-5.6-luna` / reasoning lowでした。Lifecycle launcherはagentを初期化せず、networkとchild processを拒否し、native `chat` / `_manual_compress`も拒否します。

## Workとidentity

Accepted adapterはfresh dedicated sessionで一つのforeground fixture toolを逐次実行します。`pre_tool_call`でsession、turn、API request、tool call、tool nameを相関し、fixed tool以外や並行active / pendingを拒否します。

Matching `post_tool_call`後も、exact result text / hashが同じnative turnの後続outgoing requestへ`function_call_output`として入るまでpendingです。Boundary、compression、continuation terminalではactive / pending 0を要求します。Result取込は意味理解の証明ではありません。

Native identityはsession、turn、API request、tool call、DB rowです。Core request / generation、host-local event / readback sequenceとは別です。HermesはYohaku request IDやgenerationを返さないため、一つのexclusive session、一つのmanual request、ordered instrumentationとrequest前後のsession一致で相関します。

## Completion proof

Adapterはverified boundary、committed checkpoint、one-shot authorityからrequestを作り、`compress_requested`を保存し、`HermesManualBinding`をCoreへbindした後にnative `_manual_compress('/compress')`を一回呼びます。

`HermesManualCompletionPolicy`は次を確認します。

- Core request、session、request sequence、generationがbindingと一致する。
- Request、compression、独立readbackが各一回で、readback sequenceはrequestより後。
- Compression前後でsessionが不変、host historyが変化する。
- 別に開いたread-only `SessionDB`のactive projectionとhost projectionのpayload / hash / countが一致する。
- Old history rowがinactiveになり、archived rowが存在する。

Compressor return、provider成功、`compression_count=1`、DB row count単独はcompletionではありません。Unchanged history、不一致readback、identity mismatch、不明なoutcomeはcompletionを拒否し、`AMBIGUOUS`として停止します。Exact duplicateから追加permitを作りません。Live late / stale / duplicate raceはuntestedです。

## Receipt、fresh read、continuation

Coreのpermitへdurable `HandoffDocument`を結び付け、rendered handoffとcurrent instructionsを一回のnative `chat` promptへ入れます。`observe_request()`がactual outgoing user inputとnative continuation turnを確認してdeliveryを報告します。Prompt作成や`chat()`呼出しだけではdeliveryにしません。

ReceiptはHermes built-in ACKではなく、adapter-defined tool protocolです。Handoff ID、checkpoint ID / checksum、compression request ID、native session ID、Core generationをactive receipt handlerでexactに照合します。欠落値を補完せず、tool resultがmatching native turnの次のoutgoing requestへincorporateされた後にだけCoreへreceiptを渡します。

Receipt後のread toolからtrusted observerがdisk上のlogical task、intent / execution revision、workspaceを新しく読みます。そのread resultも取込済みになるまでactionを許可しません。Completion時のDB readbackはfresh task readの代わりにはなりません。

Fixture固有assessorはactual read / action items、effect、unresolved work、nonduplication、same-taskを確認します。Assessment前後のstateが一致し、native terminal成功とreceiptが揃った場合に`ResumeProof`を提出します。Connected adapterの限定live workflowは`RESUME_VERIFIED`へ到達しました。先行Probeだけではproduct Coreやexplicit receiptの成功を証明していません。

## Storageと制限

CheckpointとhandoffはYohaku `SessionStore`へ保存し、native historyはHermes `SessionDB`に残ります。Inactive rowsはYohaku archiveではなく、visible-turn collectorは未実装です。

Adapterはfresh store / sessionだけを受け入れ、existing owner attach、Core snapshot restart、inflight ledger再構成はunsupportedです。Interrupted ownerは保持してmanual reviewし、compressionをresendしません。Lifecycle launcherのclean stop後のfresh sessionは、transition restartとは別です。

Normal tool denyを確認していても、Hook exception / timeout / missing callback時のRuntime全体の強制停止は未検証です。General tools、反復compression、parallel / background / detached work、native-auto、power-loss recoveryは検証範囲に含みません。共通の制限は[Runtime support](../runtime-support.md#共通のknown-limitations)、保存は[Storage and Recovery](../storage-and-recovery.md)を参照します。
