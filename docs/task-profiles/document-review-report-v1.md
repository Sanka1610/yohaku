# Task Profile: `document-review-report-v1`

本書は、Task Profile `document-review-report-v1`のcurrent public canonicalである。この
profileは、明示された文書を専用workspaceで読み、固定したMarkdown reportを一つ作成する
real-task profileである。一般的なdocument agent、任意のfilesystem agent、coding agentでは
ない。

このprofileが実証した対象は、固定したinput / output contractのもとで次のsequenceを成立
させることである。

```text
real task
  -> verified boundary
  -> checkpoint
  -> Runtime-specific transition
  -> handoff
  -> receipt
  -> fresh observation
  -> non-duplicate continuation
  -> RESUME_VERIFIED
```

`RESUME_VERIFIED`とmechanical completion `PASS`は、許可したworkだけで未完了処理を一度
継続し、固定出力をdurableに作成したことを示す。文章品質、事実性、完全性、レビュー判断
の妥当性は示さない。これらのcontent qualityは`NOT_ASSESSED`である。

## Runtime supportとTask Profile support

Runtime supportとTask Profile supportは別のclaimである。

```text
Runtime support  = 固定Runtime profileがtransition、handoff、receipt、continuationを
                   観測・制御できる範囲
Task Profile support
                 = 固定Task Profileがinput、output、allowed work、current state、
                   mechanical completionを判断できる範囲
```

Runtimeのlifecycleまたはtransitionが`PASS`でも、Task Assessorがないtaskの完了は判定でき
ない。反対に、Task ProfileのcontractだけではRuntime固有のcompletion proof、handoff delivery、
receiptを補えない。現在acceptedなのは、次のTask ProfileとRuntime Support Profileの組合せ
だけである。

| 項目 | Accepted value |
|---|---|
| Task Profile ID | `document-review-report-v1` |
| Runtime Support Profile | `codex-document-review-report-v1`（Runtime Mapping key: `C-DRR`） |
| Runtime / version | Codex CLI `0.158.0-alpha.2.1` |
| Surface | Dedicated App Server over stdio、profile-owned dynamic tools |
| OS / host runtime | WSL2 Linux / CPython `3.14.4` |
| Owner条件 | 一つのdedicated App Server、一つのfresh thread、`single_owner`、`dedicated_session`、profile workspace lock |
| Transition Strategy | Manual In-place Compactionを一回 |
| Evidence provenance | `DRR-V1-CODEX-0158-LIVE-01`、lab / live-Runtime / nonfixture real task |
| Accepted endpoint | Core `RESUME_VERIFIED`かつmechanical completion `PASS` |
| Capability Verdict | 固定workflowは`PASS`。製品全体のcoverageは`PARTIAL` |
| Maturity / release channel | `experimental` / `undeclared` |
| Content quality | `NOT_ASSESSED` |

Profile workspace lockが排除するのは、同じlockに協調するlauncherの並行実行だけである。
別client、detached process、非協調external writerまで排除するRuntime-wide ownershipではない。
他のCodex version、Codexの別surface、Hermes、Claude Code、他OSへこの結果を継承しない。

## Fixed task identity

一つのlogical taskは、profile、workspace、宣言inputのidentity、固定output、instruction hashを
結び付けて識別する。実装は、このbindingのSHA-256 prefixから
`document-review-<24 hex characters>`形式の`logical_task_id`を作る。同じ文章を扱っていても、
input hash、output path、instructionのいずれかが異なれば、同じlogical taskとして扱わない。

設定はabsolute pathを使うが、Runtimeへ返すinput / output identityとprovenance commentには、
workspaceからのrelative pathを記録する。Input bodyとreport bodyはtask ledgerへ複製しない。

## Input contract

Profileは、開始前に次の条件をすべて検証する。

| 条件 | Contract |
|---|---|
| Workspace | 専用directoryであり、current UIDが所有し、group / other権限を持たない |
| Accepted runのpermission | Workspace `0700`、input file `0600` |
| Input種別 | 明示指定した通常ファイルだけ。symlinkと非regular fileは拒否 |
| Input permission | 各fileをcurrent UIDが所有し、group / other権限を持たない |
| Input数 | 1件以上16件以下 |
| Input size | 各fileは2 MiB以下、全inputの合計も2 MiB以下 |
| Text decoding | `read_review_inputs`でUTF-8として読めること |
| Input identity | Relative path、byte size、SHA-256 |
| Instruction | 空でない文字列、最大16,000 characters |
| Instruction identity | UTF-8 bytesのSHA-256 |
| Output初期状態 | 固定output pathにfileもsymlinkも存在しない |

実装のpermission checkは、owner permission bitsを`0700` / `0600`へ完全一致させる処理では
なく、current UIDによる所有とgroup / other権限の不在を要求する。表の`0700` / `0600`は
accepted runで固定した値である。

Preflight時のworkspaceに存在できる通常ファイルは宣言inputだけである。未宣言fileが一つ
でもあれば`DEDICATED_WORKSPACE_CONTAINS_UNDECLARED_FILES`で拒否する。Path自身または途中の
path componentがsymlinkであれば`SYMLINK_PATH_REJECTED`、走査中にsymlinkを見つけた場合も
拒否する。

Preflightで記録したrelative path、size、SHA-256はinitial input identityとなる。以後の
observation、initial read、fresh read、final assessmentはcurrent identityをinitial identityと
照合する。変更、欠落、型またはpermissionの変化はstale inputとして扱い、通常は
`INPUT_REVISION_CHANGED`で停止する。External writerを防止するcontractではないため、二つの
observationの間だけで発生して元に戻った変更まで検出したとは主張しない。

## Output contract

Outputは設定時に指定したworkspace内の一つのabsolute pathへ固定する。Accepted runのfile名は
`review-report.md`だったが、この名称を全runの共通値とはしない。Task bindingを作った後は
別pathへ変更できない。

Output contractは次のとおりである。

- 開始時にoutput fileまたはoutput symlinkが存在してはならない。
- `publish_review_report`は新規作成だけを行い、既存fileをoverwriteしない。
- Report bodyは空ではなく、trim後の先頭がMarkdown heading marker `#`でなければならない。
- Report bodyのUTF-8 byte size上限は512 KiBである。Hostが先頭に加えるprovenance commentは
  このbodyとは別である。
- 作成するfileのmodeは`0600`である。
- Final pathのsymlink追跡を拒否し、排他的createを行う。
- File contentをflushしてfileを`fsync`し、close後にparent directoryも`fsync`する。
- Durable write後にfileを読み戻し、書き込む予定だったbytesのSHA-256と一致することを確認
  する。
- Report先頭には、profile、logical task ID、instruction hash、input relative path / size /
  SHA-256、`quality_verdict=NOT_ASSESSED`を含むhost-generated provenance commentを付ける。

POSIX実装は`O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW`でfinal pathを開く。`O_EXCL`により
既存fileへの置換を行わず、`O_NOFOLLOW`によりfinal pathがsymlinkである場合の追跡を拒否
する。この処理は、非協調external writerとのすべてのpath raceを排除する保証ではない。

`write_started`を記録した後は、例外、timeout、readback hash mismatchを安全な未実行とは
みなさない。結果が不明なwriteやdurabilityを証明できないwriteを同じpathへblind retry
しない。

## Allowed work plane

Model-visible task work planeは、次の二つのprofile-owned dynamic toolだけである。

| Tool | 許可する処理 |
|---|---|
| `read_review_inputs` | 引数なしで、hostが宣言したinput集合をまとめて読む。Initial stageとpost-transition stageで各一回だけ許可する |
| `publish_review_report` | Fresh read incorporation後、Markdown bodyを受け取り、固定outputを一回だけcreateする |

次の処理はTask Profileのwork planeに含まれない。

- arbitrary shellまたはcommand execution
- general file-edit toolまたは任意pathへのwrite
- MCP
- web / network access
- delegation / subagent
- background work
- Task Profileと無関係なRuntime operation

Codex bindingは、`PreToolUse`で二つのexact tool nameだけを許可し、それ以外をdenyする。
App Server observerは`commandExecution`、`fileChange`、`mcpToolCall`も別に監視し、観測したrunを
受入れない。Model instructionsもshell、file、MCP、web、delegation、他toolを禁止する。
これは、Runtime内部のApp Server lifecycle、Hook、Core state maintenance、checkpoint write、
manual compactまでmodel-visible task workと数えるという意味ではない。内部control planeと
Task Profileのwork planeを分ける。

## Work lifecycle

Profile-owned tool callは、次のlifecycleで扱う。

| State | このprofileでの意味 |
|---|---|
| `admitted` | Call identityが新規で、namespaceがなく、tool名がallowlist内にあり、現在phaseでその操作を受理できる |
| `active` | Handlerがcallを登録し、input observation、readまたはcreate-only writeを実行中 |
| `pending` | Handlerがsuccess resultを作成したが、対応するsuccessful Runtime itemをまだ確認していない |
| `incorporated` | Runtimeの`dynamicToolCall` itemが正しいtool、terminal `completed`、`success=true`として対応し、task phaseへ反映済み |

したがって、tool handlerがsuccess responseを返したこととresult incorporationは同じではない。
さらに、result incorporationは、modelが文書の意味を正しく理解したことも示さない。
`read_review_inputs`のincorporationが示すのは、固定inputを返したtask itemがRuntime stateへ
取り込まれたことである。内容理解はObserverにもTask Assessorにも観測できない。

## Trusted Observer

Trusted Observerはhost側でcurrent workspaceとtask ledgerを読み、次のstateを取得する。

- logical task ID
- instruction SHA-256
- input relative path、byte size、SHA-256
- output existenceと、存在する場合のSHA-256
- read completionとread count
- write started
- durable write completed
- Runtime result incorporation
- active workとpending work
- workspace mutation epoch
- workspace stamp
- relevant scope（宣言input relative pathと固定output relative path）

Workspace stampは、current instruction hash、input identities、output existence / hashを
canonical JSONにしたbytesのSHA-256である。Mutation epochは、この実装ではreport write開始時
に一回進む。Observerは未宣言fileとsymlinkも再走査する。

これらはhostがfileとRuntime itemから作るobservationであり、assistant message、modelの
「読み終えた」「書き終えた」という発言、report本文内の自己申告をObserver Evidenceとして
使わない。

## Verified Boundary

このprofileのVerified Boundaryは、単なる「レビューが終わった」というmodel self-reportでは
確定しない。Initial turnの終了後に、次の条件をまとめて確認する。

1. `read_review_inputs`を一回だけ実行し、そのsuccessful resultがincorporatedである。
2. Current input identitiesがinitial identitiesと一致する。
3. Instruction hashがtask bindingと一致する。
4. Outputはまだ存在しない。
5. Active workとpending workがともに空である。
6. Profile phaseが`INITIAL_READ_DONE`である。
7. Relevant workが残っていないというquiescence observationを取得する。
8. Current workspace revisionをcaptureし、boundary verificationを`passed`として記録できる。
9. Current checkpointをdurable commitし、一回限りのtransition authorityを発行できる。
10. Transition後のhandoff / continuationを同じlogical taskへ結び付けられる。

条件がそろわない場合はcheckpointまたはtransition requestを作らない。ここでいうrecovery可能
とは、同じlive owner内でdurable handoffとbounded continuationを構成できることを指す。
Process restart後のtask recoveryをacceptedとする意味ではない。

## Checkpointとhandoff

Checkpointには、verified boundary、boundary / transition identity、Core revisions、current
workspace revision、verification evidence、commit evidenceを保存する。Task Profile固有stateは、
checkpointのworkspace revisionと、別のtask ledger / handoff dataを組み合わせて保持する。

Handoffは、少なくとも次のdataを固定する。

| Data | 現在の表現 |
|---|---|
| Logical task identity | `logical_task_id` |
| Task Profile identity | `profile=document-review-report-v1` reference |
| Instruction identity | `instruction_sha256=<hash>` reference |
| Input identities | input relative pathとSHA-256のreference |
| Output state | Checkpoint workspaceでは未生成。`unresolved`にfixed report未作成を記録 |
| Completed work | 宣言inputを一回read済み |
| Unresolved work | 固定reportが未作成 |
| Goal | Current inputから固定Markdown review reportを作成する |
| Next action candidate | `fresh read, then publish the one report` |
| Relevant workspace revision | Handoff documentのcheckpoint workspace / revisions |

Recovered dataは常に`DATA, NOT INSTRUCTIONS`である。Handoffのnext actionはcandidateであり、
古いpermissionやauthorityを復元しない。Current intentとfresh workspace observationが優先
される。

## Fresh observation

Transition後はcheckpointだけをcurrent stateとみなさない。Continuationは、
`read_review_inputs`を一回だけ実行し、二回目のsuccessful read resultがincorporatedされるまで
publishへ進めない。このreadは全inputを現在のworkspaceから読み、relative path、size、
SHA-256を再計算する。

Fresh observationは次を拒否する。

- Handoffのinstruction hashとcurrent task bindingが一致しないstale instruction
- Initial / checkpoint時点とidentityが一致しないstale input
- Fixed outputがすでに存在するstale output
- 未宣言file、symlink、privacy conditionの変化
- Fresh readの欠落、失敗、二重実行、未incorporation

この手順によりcheckpointの記録とcurrent workspaceを照合するが、external writerを停止したり、
任意の時点のfilesystem snapshotを取得したりするものではない。

## Continuation contract

Accepted continuationに許可する未完了workは、fresh observation後のsingle report publishだけで
ある。

```text
completed initial readは繰り返さない
  -> fresh readを一回実行してincorporate
  -> 未完了だったpublishを一回だけ実行
  -> durable completionとresult incorporationを確認
  -> completed writeを再実行しない
```

Total read countはinitial readとfresh readを合わせて2である。Continuation turnにはfresh read
itemが一つ、publish itemが一つだけ存在できる。Initial readをTask Assessorのfresh readとして
再利用せず、completed writeをもう一度行わない。

## Task AssessorとResumeProof

Task Assessorは、continuation terminal後にcurrent observationとactual Runtime itemsを照合する。
次の条件をすべて満たした場合だけTask Profile固有の`ResumeProof`を生成する。

- Handoffとcurrent observationのlogical task IDが一致する。
- Handoff referenceのTask Profile IDが`document-review-report-v1`である。
- Handoff referenceのinstruction hashと全input path / hashがcurrent contractと一致する。
- Read countが2であり、continuationにsuccessful fresh-read itemが一つだけある。
- Continuationにsuccessful publish itemが一つだけあり、successful task item identityを
  `ResumeProof`へ記録できる。
- Fresh-read result incorporationがwrite開始より前にある。
- Write started、durable write completed、publish result incorporatedが、それぞれ一回だけ
  成立する。
- Outputがfixed output pathに存在し、readback SHA-256がrecorded write hashと一致する。
- Final input identitiesがinitial identitiesから変わっていない。
- Active workとpending workがともに0である。
- Continuation itemsにunrelated workがない。
- Duplicate writeがなく、profile phaseが`COMPLETE`である。
- Handoffのunresolved workとnext actionをcurrent stateに対して再評価している。
- Completed workを繰り返さず、historical dataをinstructionsとして再実行せず、同じtaskの
  unfinished workだけを継続している。

Core recoveryは、Task Assessorが返したfresh `ResumeProof`、successful continuation turn、
correlated receipt、assessment前後で不変のcurrent observationを再確認してから
`RESUME_VERIFIED`へ遷移する。Assessorはreport本文のqualityを判定しない。

## Failure / refusal semantics

Outcomeは、既知の拒否、side effect uncertainty、transition後のrecovery不足を区別する。

| 条件 | 主なreason / outcome | 動作 |
|---|---|---|
| Undeclared input file | `DEDICATED_WORKSPACE_CONTAINS_UNDECLARED_FILES`または`UNDECLARED_WORKSPACE_FILE` / `REFUSED` | Taskを開始せず、またはcurrent observationを拒否する |
| Symlink / wrong object | `SYMLINK_PATH_REJECTED`、`TASK_INPUT_MUST_BE_REGULAR`、`WORKSPACE_SYMLINK_DETECTED`、`INVALID_OUTPUT_OBJECT` / `REFUSED` | Followせず停止する |
| Stale instruction | Handoff referenceとcurrent task bindingの不一致 / `REFUSED`または`RECOVERY_REQUIRED` | Historical instructionを実行せず、`ResumeProof`を発行しない |
| Stale input | `INPUT_REVISION_CHANGED` | Transition前は`REFUSED`。Transition dispatch後ならrun全体は`AMBIGUOUS`になり得る |
| Pre-existing output | `STALE_OUTPUT_PRESENT` / `REFUSED` | Createもoverwriteもしない |
| Stale output during continuation | `STALE_OUTPUT_PRESENT`または`COMPLETED_OR_STALE_WRITE_REFUSED` | Publishを開始しない |
| Replayed / duplicate tool call | `INVALID_OR_REPLAYED_TOOL_CALL`、`READ_ALREADY_COMPLETED`、`WRITE_NOT_PENDING` / `REFUSED` | 二回目のworkを実行しない |
| Write outcome unknown | `WRITE_RESULT_UNKNOWN_NO_RETRY` / `AMBIGUOUS` | 同じoutputへretryしない。Stateとartifactを保持する |
| Readback hash mismatch | `WRITE_READBACK_MISMATCH_NO_RETRY` / `AMBIGUOUS` | 完了扱いせず、overwrite / retryしない |
| Active / pending workあり | `TRANSITION_BOUNDARY_NOT_READY`またはboundary failure | Boundary、checkpoint、transitionを進めない |
| Unrelated work | `UNRELATED_TOOL_REFUSED`、`BUILTIN_TOOL_ATTEMPT_REFUSED`、`UNRELATED_RUNTIME_OPERATION` | Task acceptanceを拒否する |
| Runtime result未incorporation | `TOOL_RESULT_NOT_INCORPORATED`または`TASK_ASSESSMENT_FAILED` | Handler successをcompletionへ昇格しない |
| Completion proof不足 / dispatch不明 | `AMBIGUOUS` | Correlated Evidenceなしにcompactやcontinuationをblind retryしない |
| Completion後のdelivery、receipt、fresh observation、assessment不足 | `RECOVERY_REQUIRED` | Old authorityを復元せず、retained stateをinspection対象とする |
| Missing Task Evidence | `TASK_ASSESSMENT_FAILED`またはresume verification failure | `ResumeProof`を発行せず、Coreを`RESUME_VERIFIED`にしない |

`REFUSED`は、known-disallowed conditionをuncertain side effect前に拒否したtask / operation
layer outcomeであり、Core `State`ではない。`AMBIGUOUS`は実行された可能性を否定できない状態、
`RECOVERY_REQUIRED`はcompletionが既知またはretainedでもsafe resumeの残条件が不足する状態で
ある。完了済みまたはuncertainなwriteをblind retryしない。

## Duplicate run / rerun

このprofileはsingle-use task stateとcreate-only outputを使う。同じtaskを再要求した場合、
観測する層によって次のreasonが現れる。

| Check | Result |
|---|---|
| 同じworkspaceでoutputが残っているpreflight | `STALE_OUTPUT_PRESENT`。Accepted duplicate checkはoutput hash、size、mtime、inodeが不変であることを確認した |
| Completed runのlifecycle inspection | `TASK_COMPLETE_NO_RERUN; TASK_RESTART_UNSUPPORTED; completed or uncertain writes are never retried` |
| Outputを手作業で除去しても既存task stateを再利用 | Fresh startを許可せず`RECOVERY_REQUIRED`。保存stateを消してrerunする手順はcontractにない |
| Interrupted / uncertain run | `RECOVERY_REQUIRED`または`AMBIGUOUS`。Inspection対象であり、自動再送しない |

Output fileの存在だけで一般的なtask完了を証明しているのではない。`STALE_OUTPUT_PRESENT`は、
「開始時にoutputが存在せず、一回だけcreateする」というこのprofile固有contractに基づく
fail-closed refusalである。Mechanical completion `PASS`には、outputだけでなくidentity、fresh
read、write lifecycle、result incorporation、active / pending 0、unrelated workなし、
`ResumeProof`が必要である。

## Quality boundary

### Mechanical completion

YohakuとTask Assessorは、fixed contract、current state、actual task items、durable outputを照合し、
mechanical completionを判定する。Accepted runはmechanical completion `PASS`である。

### Content quality

次の評価は現在のYohaku / Task Assessorの責務に含まれず、すべて`NOT_ASSESSED`である。

- 文章品質
- 事実性
- 網羅性
- レビュー判断の妥当性
- 構成やスタイルの良し悪し

将来quality assessorを追加する場合も、mechanical completionとは別capability、別Evidence、別
Verdictとして扱う。Mechanical completion `PASS`をquality `PASS`へ昇格させない。

## Codex-specific binding

ここまでのinput / output safety、fresh observation、unfinished-work-only continuation、Task
Assessorの条件はTask Profile contractである。現在acceptedのRuntime bindingはCodex固有で
あり、Task Profileの共通仕様ではない。

| Codex binding | Current accepted behavior |
|---|---|
| Runtime lifecycle | Dedicated App Server over stdio、fresh ephemeral thread |
| Task tool surface | App Server `dynamicTools` |
| Transition request | `thread/compact/start`を一回送るManual In-place Compaction |
| Completion proof | Correlated `contextCompaction` item completion、successful `PostCompact`、successful compact turn completionの三要素 |
| Handoff delivery | Trusted `SessionStart` Hook |
| Receipt | Continuationのassistant itemにあるexact `YOH_ACK` marker |
| Continuation | 一つのowned `turn/start`、`max_attempts=1` |

`thread/compact/start`のRPC ACKだけではcompletionにならない。`YOH_ACK`もhandoff receiptで
あり、Task Profileのmechanical completionではない。HermesやClaude CodeにCodex event名、
三要素predicate、`SessionStart`、`YOH_ACK`を要求しない。別Runtimeは、同等のsafety propertyを
そのRuntime固有のnative identityとEvidenceで実証する必要がある。

Current implementationは`gpt-5.6-luna`、reasoning `low`を選択するが、public Evidenceの
provider / backend / model値から再利用可能な互換性claimを作らない。

## Evidence summary

Accepted Evidenceは`DRR-V1-CODEX-0158-LIVE-01`である。Provenanceは、最終sourceと
documentationからclean buildしたwheel、source manifest、task ledger、Runtime event projection、
output readbackで構成する。Wheel SHA-256は
`26f56dad8b3a832481aeb88ca7e51307312c6b7d1655b8ae5d8778673667b024`である。

Live real-task acceptanceは、dedicated workspaceに置いた公開文書2点を読み、一回のmanual
compact、receipted handoff、fresh read、一回のcreate-only report publishを経て、Core
`RESUME_VERIFIED`とmechanical completion `PASS`へ到達した。Final active / pendingは0、read
countは2、write started / completed / incorporatedは各1、unrelated Runtime operationは0だった。

初回run `a5c99afd16bd4e55a1763a7fb3402658`は、deny-all Hookがprofile-owned dynamic toolも
拒否したため、transition前に`BUILTIN_TOOL_ATTEMPT_REFUSED` / `REFUSED`となった。Coreは
`WORKING`、outputなし、write開始0であり、このfailure Evidenceも保持している。Exact
allowlistへ修正した後、最終run `befe25e2f8f249309a72753d94c4f570`をaccepted runとした。

Duplicate checkでは同じrunを再要求し、`STALE_OUTPUT_PRESENT`で`REFUSED`となった。Output
hashとstatは変化していない。Accepted endpointは`RESUME_VERIFIED`であるが、Verdict `PASS`は
この一つのfixed workflowだけに適用する。製品全体のcoverageは`PARTIAL`、maturityは
`experimental`、Field Evidenceはない。

Retained Evidenceは`DRR-V1-CODEX-0158-LIVE-01`で索引し、private maintainer workspaceに
保持している。公開側のEvidence規則とRuntime scopeは[Evidence Model](../evidence-model.md)、
[Codex Runtime](../runtimes/codex.md)、[Runtime Support](../runtime-support.md)を参照する。

## Known Limitations

- 一般的なdocument taskまたはgeneral document agentではない。
- Accepted RuntimeはCodex CLI `0.158.0-alpha.2.1`の固定surfaceだけである。Hermes、Claude
  Code、他Codex versionはこのTask Profileについて`NOT_RUN`である。
- Outputは一つのfixed Markdown fileだけである。複数出力や既存file更新を扱わない。
- Arbitrary file editingを許可しない。
- Network、web、MCP、shellをwork planeに含めない。
- Delegation、subagent、background workをwork planeに含めない。
- Directory lockは協調launcherだけを排他する。External writerの完全な排除、race coverage、
  atomic filesystem snapshotはない。
- 一つのmanual transitionだけを受入れた。Repeated transitionは未受入である。
- Task restart、owner crash recovery、process restart、power lossは未受入である。
- General Task Profile registry、Observer registry、Assessor registryはない。
- Reportのwriting qualityとcontent qualityは`NOT_ASSESSED`である。
- Field Evidence、release acceptance、一般ユーザー環境での運用Evidenceはない。

## Canonicalとretained資料

Current public canonicalは本書
`docs/task-profiles/document-review-report-v1.md`である。旧public path
`docs/reference/document-review-report-v1.md`は既存linkの互換性とhistorical summaryを保持する
ため、移動・改名・削除しない。Internal contract、accepted result、source manifest、run
Evidenceも元のpathで保持し、Evidence provenanceを変更しない。
