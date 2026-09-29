# Storage and Recovery

本書は、Yohakuが何をdurableに保存し、restart時に何を復活させず、保存済みstateから
recovery可否をどう判定するかを定める公開正本である。利用者が実行するcommandと拒否条件は
[Operations](operations.md)、Runtime固有のcompletion proof / receipt / reconnect primitiveは
[Codex](runtimes/codex.md)、[Hermes](runtimes/hermes.md)、
[Claude Code CLI](runtimes/claude-code-cli.md)を参照する。Task固有のinput / output、Trusted
Observer、Task Assessorは[Task Profile](task-profiles/document-review-report-v1.md)、Evidenceの
authority、retention、CoverageProfile、Verdictは[Evidence Model](evidence-model.md)が所有する。

Durable recordは、過去のbyte列とその関係を保持する。保存済みであることだけでは、現在の
workspace、task intent、Runtime state、completion、再実行の安全性を証明しない。

## Storage taxonomy

| 種類 | 保存する内容 | 保存しない意味・authority |
|---|---|---|
| Yohaku checkpoint | Verified boundary、transition / boundary identity、revisions、`WorkspaceRevision`、verification reference、commit evidence、選択したarchive reference | Current stateであること、Runtime completion、resume許可、lease |
| Append-only journal | Core snapshot、event、adapter cursor、必要なrecovery cursorをsequence順に保存したschema-1 record | Raw tool output、Runtime-native transcript、再利用可能なdispatch authority |
| Handoff | 一つのcompleted requestとcontinuation identityに結び付く、completed work、unresolved work、historical goal、workspace reference、archive reference | Current instruction、old permission、task完了、receipt、ResumeProof |
| Archive COLD | Hostが選択・redactしたterminal visible turnの本文とmetadata | Runtime-native history全体、未選択tool envelope、execution authority |
| Archive WARM index | Search用metadataと対応するCOLD recordのdigest | 本文、task current state、resume authority |
| Adapter metadata | Runtime固有のevent projection、binding、operation / task ledger、run metadata | 他Runtimeにも通用する共通event、Capability Verdict |
| Runtime-native storage | Codex thread / context / transcript / history、Hermes `SessionDB`、Claude native session / transcriptなど | Yohaku checkpoint、Yohaku archive、Task Profile completion |
| Task workspace | Taskのcurrent input、output、source tree、task固有artifact | Yohaku control journalやRuntime-native DBの代替 |
| Operational state | Config binding、owner lock、`last-run.json`、`runs/<run-id>/`、isolated native home | Verified transition checkpointやtask recovery authority |

これらは同じdirectoryに存在する場合があっても別のcontractである。Runtime-native DB /
transcript / historyはprofile固有Evidenceになり得るが、Yohaku checkpointやarchiveではない。
反対に、Yohaku checkpointはRuntimeがconversationを再構成できることを示さない。

## 現在のnamespaceとschema

Coreの`SessionStore`は現在、`CODEX_HOME`が設定されていればその値、未設定なら`~/.codex`を
基点とし、次のnamespaceを使う。

```text
<CODEX_HOME>/yohaku/sessions/<thread-or-session-id>/
```

このnamespace名はCodex Reference integrationに由来する。Hermes adapterも同じ
`SessionStore`を使うため、Non-Codex storageまで`CODEX_HOME`由来になる。Operational
launcherはrunごとにisolated homeを作り、Codexではそのhomeを`CODEX_HOME`に、Hermesでは
run内の`yohaku-control`を`CODEX_HOME`に設定する。これはlogicalなcross-Runtime namespaceが
一般化済みであることを意味しない。

Snapshot codec、checkpoint envelope、journal decoderはschema 1である。`Snapshot`は
Codex version-1 storage layoutを保持し、Codex以外のRuntime固有completion proofを無理に
serializeしない。`SessionStore.append()`はschema 1でround-tripできないsnapshotを拒否する。
Hermes / Claudeのadapter stateやcompletion proofは、それぞれのadapter metadata / in-memory
stateへ残り、Codex schema-1 restart contractへ合成されない。
現在のHermes / Claude adapterはcheckpointとhandoffを`SessionStore`へcommitできるが、
connected Core snapshotとRuntime固有proofをCodex schema-1 journalへappendしない。このため、
保存済みcheckpoint / handoffの存在からNon-Codex owner restartを許可しない。

Schema migrationは自動実行しない。Unknown field、schema mismatch、hash mismatch、identity
mismatch、journal gapを検出した場合は、古いrecordへ黙ってfallbackせずrecoveryを停止する。

## Yohaku checkpoint

Checkpointは、transition dispatch前に確認したverified boundaryをimmutable recordとして保存する。
主な内容は次のとおりである。

- `checkpoint_id`、`transition_id`、`boundary_id`
- Intent / execution / control / archive revisions
- Workspace mutation epoch、workspace stamp、relevant scope
- Boundary verification profile、result、Evidence reference
- Commit後に付く`checkpoint:<checkpoint-id>`形式のcommit evidence
- Checkpointが参照するarchive ID

Checkpointは再利用可能なauthorityではない。保存後にintent、execution、workspace、boundary、
generationが変わればstaleである。Restart時にcheckpointを読めても、fresh observationと
Runtime固有reconciliationなしにcurrent state、未実行、再送可能とは判定しない。

Checkpoint fileのrenameが完了し、対応する`checkpoint_committed` journal recordの前にprocessが
停止した場合、restartは`CHECKPOINT_PREPARING`に記録されたexact checkpoint IDと内容が一致する
recordだけをhistorical recovery candidateとして採用できる。このcandidateもleaseやdispatch
authorityを復元しない。

## Append-only journal

Journalは、連番のimmutable JSON fileをappendする。各recordは直前recordのenvelope hashを
`previous`に持ち、sequence、filename、previous hashが連続する場合だけloadする。Gap、順序違反、
corrupt recordがあれば、より古い正常そうなrecordへfallbackしない。Checkpointだけが残っていても、
pending requestがなかったことを証明できないため、journal欠落はrecovery失敗である。

Journalへ保存するsnapshotからはactive leaseとdeadlineを除き、leaseが存在した場合は失効済み
identityとして`revoked_lease_id`だけを残す。Transient raw tool outputはjournalへ保存しない。
Handoff bodyもjournalへ複製せず、immutable handoff documentへのreferenceだけを保持する。

JournalはCore stateの履歴であり、Evidence ModelのEvidence RecordやRuntime-native transcriptと
同じものではない。Hash chainはbyte-level integrityを検査するが、trusted hostの観測内容が
正しいことやRuntime capabilityを証明しない。

## Handoff

Handoffは、transition後のrecoveryに使うhistorical dataを、一つのrequest、checkpoint、
continuation identityへ結び付ける。少なくともlogical task、completed work、unresolved work、
historical goal、next-action candidate、workspace referenceを保持する。Archive IDを含む場合は、
保存時と読込時に対応するWARM indexを検査する。

Handoffのmaterial policyは常に`DATA, NOT INSTRUCTIONS`である。Recovered goal、next action、
assistant text、archive内容は、current user intentやpermissionを上書きしない。Continuation前に
current task / workspaceを再観測し、next actionを再評価する。Delivery、receipt、fresh
observation、continuation terminal、Task AssessorのResumeProofは別々の条件であり、handoffが
存在するだけではどれも成立しない。

Handoffはdispatch前にdurable commitする。Continuation permitを一回だけconsumeした事実も
Runtimeへのsendより前にjournalへ保存する。Sendが例外またはunknown outcomeになった場合は、
permitを戻さず`RECOVERY_REQUIRED`へ進み、同じcontinuationをblind resendしない。

## Archive / archive index

Yohaku archiveは、hostが明示的に選びredactしたterminal visible turnを保存する。COLD record
`archive/<archive-id>.json`をauthoritative body、WARM record
`archive-index/<archive-id>.json`をsearch用metadataとして扱う。

Commit順序はCOLD、WARMである。COLDをdurable commitしてから、そのCOLD envelope digestを
含むWARM indexをcommitする。COLDだけが残ったinterrupted commitでは、reopen時にCOLDを検査し、
不足したWARM indexを再構築できる。WARMだけ、owner違い、identity違い、digest違い、symlink、
corrupt recordはfail closedで拒否する。

`search_archive`はWARM metadataだけを読み、`read_archive`は選択した一件のWARM / COLD identityと
digestを照合してから本文を返す。Search / readはCore state、lease、intent / execution revision、
resume authorityを変更しない。同じarchive IDと同じ内容のcommitはidempotent、同じIDと異なる
内容はconflictである。

Archiveは`DATA, NOT INSTRUCTIONS`である。Runtime-native transcriptやHermes inactive rowを
自動importせず、archive retrievalをtask instruction、current state、completion proofとして
扱わない。Accepted collector / retrievalの有無はRuntime profileごとに異なる。

## Adapter metadata

Adapter metadataは、Runtime固有のnative eventを、固定profile内で相関するための補助recordである。
Codex event / operation ledger、Hermes `hermes-events`、Claude `claude-cli-events`やcollector
sequenceは、同じevent schemaではない。Runtime固有identityを別Runtimeのeventへ変換したり、
engine returnやRPC ACKから不足するproofを生成したりしない。

Adapter metadataがdurableでも、そのRuntime向けrestart decoder、fresh native read、Task
Observer / Assessorがなければresumeはできない。Exact completion proofとreceipt fieldは各Runtime
canonicalを参照する。

## Runtime-native storageとtask workspace

Runtime-native storageはRuntime自身が所有する。Codex thread / history、Hermes `SessionDB`の
active / inactive row、Claude native transcriptは、completionやcurrent stateの確認に使う場合が
あるが、Yohakuが所有するcheckpoint / journal / archiveへ読み替えない。Runtime-native
retention、reconnect、compaction後のhistory表現はRuntimeごとに異なる。

Task workspaceはcurrent task stateのsourceである。Checkpointの`WorkspaceRevision`は、固定scopeの
mutation epoch、stamp、relevant pathを記録するが、filesystem snapshotやexternal-writer exclusion
ではない。Restart / recoveryでは、保存済みhashだけでなくTask ProfileのTrusted Observerが
current input / output / relevant scopeを読み直す必要がある。

Task固有のinput hash、output create-only契約、Assessor条件、completed / uncertain side effectの
no-rerun規則はTask Profile canonicalが所有する。本書では再定義しない。

## Durable commit順序とintegrity

Immutable recordの基本commit順序は次のとおりである。

```text
same-directory temporary file
  -> write all bytes
  -> flush + fsync(file)
  -> atomic rename to final name
  -> fsync(parent directory)
```

JSON recordは`schema`、canonical payload、payloadのSHA-256を持つenvelopeとして保存する。
Read時はschema、field集合、hash、owner / identity、record間の関係を検査する。Final nameだけを
recovery対象とし、temporary fileは採用しない。

Transitionを含む順序は次のとおりである。

```text
verified boundary
  -> journal: CHECKPOINT_PREPARING
  -> immutable checkpoint commit
  -> journal: CHECKPOINT_COMMITTED
  -> one-shot lease
  -> journal: ROLLOVER_REQUESTED
  -> final current-state revalidation
  -> Runtime dispatch
```

`ROLLOVER_REQUESTED`のjournal commitは、Runtimeへrequest byteを送る前に完了する。Dispatch前の
final revalidationに失敗した場合はrequestを送らず`INVALIDATED`とする。Send後の結果が不明な
場合は「未実行」と推定せず`AMBIGUOUS`とする。

Recovery continuationでは、immutable handoff、consumed continuation permitを示すjournal、
final current-state revalidation、Runtime sendの順になる。Storage write outcomeが不明になった
open handleはpoisonedとなり、そのhandleから追加dispatchしない。

SHA-256とhash chainが保証するのは、読み込んだbyte列のintegrityとrecord間の対応である。
観測者の真正性、内容の正しさ、secretの不在、task完了、Capability Verdictは保証しない。

## Restart時に復活させないstate

Restartでは次を復元しない。

- Active lease、expiry deadline、未消費のtransition authority
- Old continuation permitまたは新しいcontinuation identityを作る権限
- BarrierがRuntime全体を停止していたという仮定
- In-memory active / pending work ledger
- Transient raw tool output
- Historical instruction、permission、next action
- Runtime eventから確認していないcompletion、receipt、result incorporation

Leaseはboundary、checkpoint、intent / execution revision、workspace、rollover generationに結び付く
短命なlocal authorityである。Journal load後にleaseが`None`であることを検査し、old leaseを
再構成しない。Local writer lockもRuntime-wide ownershipやexternal-writer exclusionを意味しない。

## Stale checkpointとemergency delta

Runtime-native automatic compactionがproactive checkpointの後に先行した場合、old checkpointを
currentへ昇格させない。Checkpointはhistorical candidateとして保持し、compaction後に観測した
進捗をcheckpointとは区別した`EmergencyDelta`としてhandoffに保存する。

`EmergencyDelta`はlogical task、checkpoint、intent / execution revision、workspace、selected
progress、pending tool identity、Evidence referenceを持つが、`delta_status=unverified`のままである。
Handoffは`checkpoint_current=false`と、`stale`または`historical`のfreshnessを表示する。Recoveryは
old checkpointとemergency deltaの両方をdataとして扱い、current task stateを読み直す。

Emergency pathはproactive transition成功ではない。Native-auto restartは、post-compaction item
provenanceをthread readだけで再構成できないため、現在`UNSUPPORTED`である。

## Recovery outcome

| Outcome | 判定 | 次の動作 |
|---|---|---|
| `DEFERRED` | Relevant active workまたはpending resultが残り、safe boundaryを確定できない | Barrierを解除して通常作業へ戻る。Settled後にnew candidateを提案する。Old candidate / leaseは使わない |
| `INVALIDATED` | Dispatch前にrevision、workspace、checkpoint、lease、generationがstaleになった | Requestを送らず、current stateから再検証する |
| `AMBIGUOUS` | Dispatch、completion、write、side effectが発生した可能性はあるが証明できない | 通常作業とblind retryを止め、matching late Evidenceを照合する |
| `RECOVERY_REQUIRED` | Completionまたはretained stateはあるが、delivery、receipt、fresh observation、continuation、assessmentを安全に完了できない | Old authorityを復元せず、profile固有recoveryまたはmanual reviewへ進む |
| `REFUSED` | Task / operation layerがknown-disallowed、stale、duplicate、undeclared workをside effect前に拒否した | Refusal reasonを修正する。Core `State`とは区別する |

`DEFERRED`はfailureやretry permitではない。Old boundaryを再利用せず、current stateを観測して
新しいcandidateから開始する。`AMBIGUOUS`と`RECOVERY_REQUIRED`はfresh startの許可でもない。

## Duplicate / late Evidenceとno blind retry

Exact duplicate completion、receipt、archive commitは、新しいcompletion、handoff、continuation、
side effectを作らない。Late eventは、保存済みrequest、session / thread、turn / item、generation、
profile固有identityへ一意に相関できる場合だけ、Runtime canonicalの範囲で一回reconcileできる。
Foreign、missing、conflicting identityはcompletionに採用しない。

Timeout、transport exception、missing output、malformed output、storage write uncertaintyを
non-executionとみなさない。Completed side effectもuncertain side effectもrerunしない。
たとえばcreate-only outputのwrite開始後にtimeoutした場合、同じpathへ再度writeせず、current
filesystemとretained recordをinspectする。Continuation sendが不明な場合も、新しいturnを
blind resendしない。

## Restart / reconnect semantics

| Runtime / profile | Clean stop後 | Interrupted / uncertain owner後 | Transition recovery |
|---|---|---|---|
| Codex `C-OP` | 同じstate rootにfresh dedicated sessionを新設可能 | `RECOVERY_REQUIRED`。Prior sessionをresumeしない | Lifecycle-onlyのためtransitionなし |
| Codex `C-DRR` | Completed runをrerunしない | Retained stateはinspect-only | Accepted Task Profile restartは`UNSUPPORTED` |
| Historical Codex manual | Operational launcherとは別contract | Exact saved continuation identityとfresh Runtime readを使うlimited reconciliationのみ | Lease / permitを復元せず、unknown sendを再送しない |
| Historical Codex native-auto | Fresh lifecycleとは別 | Post-compaction provenanceを再構成できない | Restart `UNSUPPORTED` |
| Hermes `H-OP` / `H-ADAPTER` | `H-OP`はclean stop後にfresh lifecycle。`H-ADAPTER`はfresh store / session前提 | Existing owner attach、Core snapshot restart、inflight ledger再構成なし | Interrupted adapter ownerのrestart `UNSUPPORTED` |
| Claude Code CLI profiles | Formal operational launcherなし | Accepted pathはsame retained process / bounded host-local continuation | Process restart / general reconnect `UNSUPPORTED` |

Operational CLIは`status.recovery.fresh_start_allowed`と`resume_supported`を別fieldで表示する。
現在のoperational CLIでは`resume_supported=false`である。Clean stop後のfresh lifecycleを
restart可能と表示しても、old task / sessionのresume可能とは表示しない。

Runtimeごとにnative storage、identity、reconnect primitiveが異なるため、Codexのschema-1
reconciliationをHermes / Claudeへ適用しない。Non-Codex adapterがcheckpoint / handoff valueを
共有していても、portable cross-Runtime restart frameworkは実装されていない。

## Disable / uninstall後の保存保持

`disable`はconfigのactivation flagだけを変更し、checkpoint、journal、handoff、archive、adapter
metadata、operational run、Runtime-native DB / transcriptを削除しない。Package uninstallも
user-managed configとstate directoryを削除しない。

Ownerをclean stopし、`owner_lock_busy=false`を確認してからuninstallする。`STOP_INCOMPLETE`、
`OWNER_UNREACHABLE`、`AMBIGUOUS`、`RECOVERY_REQUIRED`の状態でpackageを削除しても、その状態は
解決しない。Reinstallをschema migration、clean stop、completion proofの代用にしない。

保存dataを削除する一般commandは現在提供しない。Retention期間、secure deletion、export、
backup / restoreは公開contractとして未定義である。秘密情報を含み得るRuntime-native storageと
task workspaceは、各ownerのprivacy policyに従って別々に管理する。

## 現在の受入範囲

Power loss、filesystem / device failure、kernel crash、network filesystem、backupからのrestore、
cross-host migration、general repeated transition、parallel owner、Runtime-wide atomic freezeは
accepted scope外または`NOT_RUN`である。POSIX `fsync`とatomic renameの実装が存在しても、
power-loss recoveryを受入済みとはしない。

Current implementationはCodex schema-1 persistence、`CODEX_HOME`由来namespace、
Runtimeごとに異なるadapter metadata、Non-Codex restart未対応という非対称性を残す。この制限を
解消するschema migration、neutral storage root、portable restart frameworkは別の設計・受入作業で
あり、本書によって実装済みとは扱わない。
