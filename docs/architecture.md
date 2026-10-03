# Architecture

Yohakuは、Runtimeのcontext切替前後に安全なboundary、保存状態、完了、task再開を検証します。CompactionそのものはRuntimeに委ねます。Coreは外部I/Oを行わず、trusted hostが観測とdispatchを直列化します。

## Coreとintegration

| 部分 | 責務と現在の制限 |
|---|---|
| `Controller` / `model` | Verified boundary、revision / freshness、checkpoint-before-authority、one-shot lease / request、stale / duplicate rejection、ambiguity、resume gate |
| `CompletionPolicy` | Runtime固有bindingとeventからcompletionを評価する。Core構築時に固定するtrusted policyで、I/Oは行わない |
| `YohakuSupervisor` | 提供されたnative session identityとownership factsから一つのtriggerを選び、既存adapterへroutingする。Process内の登録だけを扱うinternal module |
| Runtime adapter / host | Native identityとworkを観測し、Runtime dispatch、completion readback、handoff delivery、receiptを相関する |
| Persistence / recovery | Journal、checkpoint、handoff、archiveをdurableに保存する。Schema-1とrestart codecはCodex由来で、cross-Runtime restartは一般化されていない |
| Task observer / assessor | Task固有のworkspace変更と未完了work、same-task / nonduplicationを評価する。Adapterが検証結果から`ResumeVerification`を構成する |

Work ledgerのactiveは実行中、pendingは完了resultの取込待ちです。Tool成功を取込完了とみなさず、関連workがsettleしてからboundaryを検証します。観測とgateが及ぶ範囲はadapterごとに異なります。

## Minimal Supervisor

CLIを組み込むhostまたはembedding hostは、`YohakuSupervisor`へsessionとadapterを登録できます。Supervisorは`harness`と`provider_session_id`でprovider-native sessionを相関します。Codexではprocessではなくthread IDを使います。同じsessionを観測するmeta adapterも、childのharnessとnative IDに登録します。新しい汎用IDは作りません。

契約は**1 trigger / N observers**です。`SessionProfile`は`harness`、`provider_session_id`、任意の`trigger_authority`と`ownership_source`だけを持ちます。Hostがsessionごとのauthorityとその出所を明示し、選んだadapterが`TRIGGER`として登録されている場合に限りroutingします。`OBSERVER`は複数登録でき、trigger自身がobserverを兼ねることもできます。Roleはそのsessionにだけ適用します。

`resolve()`はselected registrationを返し、`request_transition()`はrequesterがselected triggerであることを確認して既存transition methodを呼びます。複数のtrigger claimは、明示されたsession-specific authorityで一つに絞ります。そのfactがない競合、ownerが不明、trigger不在、native identityの不一致はdispatch前に拒否します。Adapterの優先順位表や実行ファイルの存在からownerを決めません。

Yohakuの一つのinstallationにはCodex、Hermes、DSH、OpenCodeのbuilt-in adapterが含まれます。登録には既にattachしたinstanceを使い、関係するadapterだけをsessionごとに有効にします。`register_builtin()`でsessionを省略する呼び出しは、hostによる明示的なstandalone宣言です。そのadapterをtriggerとobserverに登録します。Ownership discoveryやRuntime起動は行いません。

```python
from yohaku.supervisor import YohakuSupervisor

# companion is an already attached Codex CompanionController.
supervisor = YohakuSupervisor()
registration = supervisor.register_builtin("codex", companion)
request = supervisor.request_transition(
    registration.session, lease, read_current, requester="codex")
```

Codexは`request_compact()`、Hermesは`compress()`、DSHとOpenCodeは`compact()`へroutingします。既存adapterを直接呼ぶ経路も維持します。SupervisorはCoreのboundary、checkpoint、lease、receipt、continuation、late binding、resume verificationを変更せず、Core authorityを新たに発行しません。Observerの登録はlifecycle観測、identity確認、補助Evidenceのためのmetadataです。Supervisorからobserverのtransitionやcontinuationを呼ばず、そのEvidenceをCore proofへ昇格しません。Hostもobserverを読み取り専用で扱う必要があります。

同じsessionと既存checkpoint IDでtransition methodへ一度入った後は、例外の場合も含めて二重dispatchを拒否します。実行中の同じsessionへの再入も拒否します。次のtransitionにはfreshなCore checkpointが必要で、既存adapterのfreshnessとauthorization検証を通る必要があります。Supervisorの記録はdurable leaseではありません。Direct adapter callや別Supervisor instance、別processを調停する仕組みではなく、協調するhostが全requestを同じSupervisorへ渡す必要があります。

登録、resolution、dispatchはhostの既存event loopで直列化します。複数sessionは登録できますが、parallel executionは保証しません。Stateはprocess-localでnon-durableです。Restart recoveryは`NOT_SUPPORTED`で、Snapshot、Handoff、journal、SessionStore、codecにSupervisor metadataを保存しません。

Embedding hostは`doctor.render(supervisor=supervisor)`または`cli.main(["doctor"], supervisor=supervisor)`で、登録済みsessionのharness、trigger、observersを表示できます。表示はprovided factsに限定し、native session IDやownership sourceの内容は出しません。Supervisorを渡さない`yohaku doctor`は従来のlocal inspectionを維持します。Live ownership discoveryは行いません。

Orca production adapterとdaemon、server、MCP、cross-process registryはBeta supervisorの範囲外です。

## Control flow

### 通常作業とboundary proposal

```text
Agent / Runtime task work
    → Runtime固有のwork observation
    → Trusted Observer
    → Semantic Boundary Candidate
    → Coreによるquiescence、freshness、Evidenceの検証
```

Agentは意味のある区切りを提案できるが、その提案で確定するのは`CANDIDATE`まで
である。hostが利用可能なwork-plane gateを有効にし、関係するactive / pending
workを観測し、宣言workspace scopeを取得してEvidenceを渡す。Coreだけが
`VERIFIED`へ遷移できる。

### Verified transition

```text
Verified Boundary (`VERIFIED`)
    → durable checkpoint
      (`CHECKPOINT_PREPARING` → `CHECKPOINT_COMMITTED`)
    → revision-bound leaseと一つのrequest
      (`ROLLOVER_AUTHORIZED` → `ROLLOVER_REQUESTED`)
    → Runtime固有のTransition Strategy
    → correlated completion proof (`ROLLOVER_OBSERVED`)
    → 一つのcontinuation permitとRuntime continuation identity
    → durable handoff delivery (`HANDOFF_OFFERED`)
    → explicit receipt (`HANDOFF_RECEIVED`)
    → fresh task / workspace observation
    → 未完了workだけを継続
    → task固有のassessment
    → `RESUME_VERIFIED`
```

公開アーキテクチャでは上位概念をContext Transitionと呼ぶが、実装は互換性の
ため`ROLLOVER_*` state名を維持する。Strategyは、そのRuntime contractが実装・
検証した場合に限り、in-place compaction、fresh contextへのrollover、session
migrationを実行できる。一つのStrategyのaccepted結果から、他Strategyの対応を
推定しない。

### Unsafeまたはuncertainな経路

次の結果は意味が異なるため、一つのfailureへ統合しない。

| 条件 | 必要な結果 |
|---|---|
| verification前に関係するactive workまたはpending resultを観測した | Core stateを`DEFERRED`とし、barrierを解除して通常作業へ戻る。新しいcandidateを提案してから再試行する。契約文では動作を「DEFER」と表現できるが、実装state名は`DEFERRED`である。 |
| boundary、revision、workspace、lease、pre-dispatch authorityがstale | 拒否するか`INVALIDATED`へ遷移する。そのauthorityからrequestを送らず、current stateから再検証する。 |
| dispatchされた可能性がある一方、completionが欠落・競合・未照合のlate eventなどで不明 | `AMBIGUOUS`へ遷移する。correlated evidenceを照合するまで通常作業とblind retryを止める。 |
| completionは既知だが、handoff、receipt、current-state reconciliation、resume proofを安全に完了できない | `RECOVERY_REQUIRED`へ遷移する。古いauthorityは復元しない。 |
| fixed Task Profileが、undeclared input、stale output、duplicate write、disallowed workをuncertain side effect前に拒否した | task / operation layerで`REFUSED`を返す。`REFUSED`はCoreの`State`ではない。writeやresultがuncertainになった場合は、profileが`AMBIGUOUS`を返すことがある。 |
| Durable recordが破損・不整合、またはwrite結果が不明 | ownerを停止してrecoveryを要求する。古いcheckpointへ黙ってfallbackしない。 |

## Trust boundary

### Model / Agent output

Model outputはuntrusted task contentである。bounded protocolが必要とするboundary
proposal、receipt marker、task artifactを出力できるが、自己申告だけでは
quiescence、completion、receipt identity、correctnessを証明できない。

### Yohaku trusted host

trusted hostはserialization、Runtime connection、observation adapter、current-state
read、durable callを所有する。Coreの安全性は、hostが正しくscopeされた観測を
報告することに依存する。Yohakuはcorrelationとstate invariantを検査できるが、
host instrumentationが外部Runtimeを正確に報告したかを暗号学的には証明できない。

### Runtime lifecycle evidence

Runtime event、Hook、native history、storage readbackは、そのidentity、ordering、
coverageを定義したTransition Strategy内だけで受理する。RPC acknowledgementや
tool returnの成功から分かるのは、そのlocal operationの結果までである。それ
だけではtransition completionやsemantic incorporationを証明できない。

### Task workspace

task workspaceはcurrent mutable stateであり、Yohakuのtrusted storageではない。
`WorkspaceRevision`は宣言scopeとmutation epochを識別する。profile lockは協調する
launcherを調整するが、他process、editor、Runtime client、userのwriteを防がない。
検出した変更はstale evidenceをinvalidateする。観測できない変更はcoverage上の
制限として残る。

### Persistent Yohaku storage

Yohaku storageにはjournal、checkpoint、handoff、選択済みarchive entry、profile
metadataを保存する。checksum、atomic replacement、synchronization、local writer
lockは、実装済みPOSIX storeを宣言したlocal failure modeから保護する。ただし、
historical checkpointをcurrentにせず、leaseを復元せず、store外の非協調writerも
排除しない。

### Runtime-native storage

Runtime-native transcript、history、database、memory storeはRuntime側のtrust domain
に属する。adapterはfixed readbackをcompletion evidenceとして利用できるが、native
store全体をYohaku checkpoint、archive、current authorityとは扱わない。native record
はfixed profileの規則でcorrelateし、意味を解釈する必要がある。

### External writer / unobserved work

宣言したobserverとgateの外にあるexternal writerやwork itemは、Yohakuのlocal state
machineだけでは安全にならない。profileはこの制限を開示する。observerのcoverage
が不完全な場合、eventが存在しないことからworkの不在を推定しない。

以上から、次の原則を適用する。

- modelの自己申告だけでboundaryをverifyしない
- tool successだけでsemantic incorporationを証明しない
- handoff deliveryだけでreceiptを証明しない
- receiptだけでresume correctnessを証明しない
- old checkpointをcurrent stateやauthorityとして扱わない

## Transition方式

| 方式 | 現在の扱い |
|---|---|
| Manual In-place Compaction | 同じnative sessionを明示的にcompactする。Codex / Hermes / Claudeの限定profileに実装あり |
| Native Automatic Compaction | Runtime起点の切替。Historical Codexで一回のsame-turn emergency recoveryを確認。Proactive成功とは区別する |
| Fresh-context Rollover | 新しいdestination contextへのhandoff。General adapterは未実装、Codexのexperimental `new_context`はunsupported |
| Session Migration | Source retirementとdestination ownershipを含む別session / host / Runtimeへの移行。未実装 |

Native-autoがcheckpoint後に先行した場合、old checkpointはhistorical / stale、post-compactionの`EmergencyDelta`はunverifiedなdataとして保持します。Old authorityを再構成せず、freshなtask観測を要求します。

Fresh-context方式にはdestination identity、delivery、receipt、freshnessが必要です。Session migrationにはsource retirementと単一ownerの確認も必要です。Process起動やcheckpoint copyだけでは成立しません。In-place方式の成功を、未実装方式の対応根拠にしません。

## 固定document-review taskの位置付け

`document_review.py`は任意選択の`document-review-report-v1`に固有のinput / output、observer、assessorです。`document_review_runtime.py`はそのCodex bindingです。Alphaのreal-task検証に使い、CLIから利用できる製品機能でもあるため、単なる廃棄可能なacceptance harnessとは扱いません。

このprofileはShared Coreの一般機能ではありません。DSH / OpenCode adapterが文書reviewのtool名、Markdown形式、create-only report、Codexのevent列へ依存する必要はありません。具体的な契約は[Task Profile](task-profiles/document-review-report-v1.md)を参照します。

## 対応範囲

Coreの検証は、trusted hostが正しい範囲の観測を報告することに依存します。汎用task detector、quality oracle、Runtime-wide atomic freeze、external writer exclusion、general exactly-once、cross-Runtime snapshot migrationは提供しません。

Profileの対応範囲は[Runtime support](runtime-support.md)、adapterの契約と検証は[Adapter Contract](development/adapter-contract.md)、durabilityとrestartは[Storage and Recovery](storage-and-recovery.md)に記載します。
