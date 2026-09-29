# Operations

本書は、Yohakuをinstallした利用者・運用者が、どのcommandをどの順序で実行し、
どの条件で拒否されるかを定める公開正本である。保存対象とrecovery判定は
[Storage and Recovery](storage-and-recovery.md)、Runtime固有のprimitiveとcompletion
proof / receiptは[Codex](runtimes/codex.md)、[Hermes](runtimes/hermes.md)、
[Claude Code CLI](runtimes/claude-code-cli.md)を参照する。Task固有のinput / output、
Trusted Observer、Task Assessorは[Task Profile](task-profiles/document-review-report-v1.md)、
EvidenceとVerdictは[Evidence Model](evidence-model.md)が正本である。

Operational support、transition support、Task Profile supportは別のclaimである。
`start`が成功してもtransitionを利用できるとは限らず、transitionがacceptedでも任意taskの
完了を判定できるとは限らない。`profiles`と`status`はこの差を別fieldで表示する。

## Install後の基本flow

Reviewed wheelを[Installation](installation.md)に従ってinstallした後は、次の順で進める。
例ではCodexのlifecycle-only profileを使う。`yohaku`は、installしたvenv内のabsolute pathへ
置き換える。

```sh
/absolute/path/yohaku-venv/bin/yohaku profiles

/absolute/path/yohaku-venv/bin/yohaku configure \
  --config /absolute/path/yohaku-config/codex.json \
  --profile codex-operational-0.158 \
  --runtime-path /absolute/path/to/codex \
  --workspace /absolute/path/project \
  --state-dir /absolute/path/yohaku-codex-state \
  --single-owner --dedicated-session

/absolute/path/yohaku-venv/bin/yohaku preflight \
  --config /absolute/path/yohaku-config/codex.json
/absolute/path/yohaku-venv/bin/yohaku enable \
  --config /absolute/path/yohaku-config/codex.json
/absolute/path/yohaku-venv/bin/yohaku start \
  --config /absolute/path/yohaku-config/codex.json
```

`start`はforeground ownerである。起動後もそのterminalを占有するため、別terminalから
`status`と`stop`を実行する。

```sh
/absolute/path/yohaku-venv/bin/yohaku status \
  --config /absolute/path/yohaku-config/codex.json
/absolute/path/yohaku-venv/bin/yohaku stop \
  --config /absolute/path/yohaku-config/codex.json
/absolute/path/yohaku-venv/bin/yohaku disable \
  --config /absolute/path/yohaku-config/codex.json
/absolute/path/yohaku-venv/bin/yohaku recover --inspect \
  --config /absolute/path/yohaku-config/codex.json
```

Task Profile `document-review-report-v1`は`start`ではなく`run`を使う。Task input、固定output、
credential home、allowed work、repeat拒否はTask Profile canonicalに従う。Lifecycle-only
profileへtask設定を渡すと拒否され、Task Profileを`start`すると`USE_RUN_FOR_TASK_PROFILE`で
拒否される。

## `profiles`

`yohaku profiles`は、固定したprofileごとにRuntime / version / surface、maturity、
Evidence level、Verdict、accepted scope、Known Limitations、launcherの有無をJSONで返す。
Profile選択時はRuntime名だけでなく、version、surface、OS、owner条件、Task Profileまで確認する。

| Profile | Operational launcher | 利用できる範囲 |
|---|---|---|
| `codex-operational-0.158` | あり | Codex `0.158.0-alpha.2.1`のno-inference lifecycle。Fresh dedicated App Serverのstart / status / stop |
| `hermes-operational-h-cli-01` | あり | Hermes `0.21.0`のno-inference lifecycle。Pinned source、native DB、Yohaku storeのstart / status / stop |
| `codex-document-review-report-v1` | `run`のみ | 固定したCodex Task Profile。One manual compactとcreate-only reportのbounded workflow |
| `codex-reference-0.155` | なし | Historical Reference。Operational startには使えない |
| `hermes-h-cli-01` | なし | Fixed connected adapter profile。Operational startには使えない |
| `claude-c-cli` / `claude-c-cli-local-nonce` | なし | Bounded adapter / Evidence profile。正式なoperational launcherではない |

`launch_supported=false`のprofileは、過去のEvidenceやadapterが存在しても
`OPERATIONAL_PROFILE_UNSUPPORTED`で拒否される。Lifecycle `PASS`をtransition `PASS`、
Task Profile `PASS`、Runtime family全体のsupportへ読み替えない。

## `configure`

`configure`はdisabled状態のJSON configと、新しいprivate state rootを作る。既存のconfig、
state root、Runtime homeは採用しない。次の条件を満たす必要がある。

- `--config`、`--runtime-path`、`--workspace`、`--state-dir`はabsolute pathであり、
  `..`とsymlink componentを含まない。
- Config directory、config file、state rootはcurrent UIDが所有し、group / otherから
  accessできない。
- Task workspaceとstate rootは同一pathでも親子関係でもない。
- `--stop-timeout`は0.1秒以上60秒以下である。
- `--single-owner`と`--dedicated-session`を明示する。
- 別Runtime、別profile、別workspaceへ切り替える場合は、新しいconfigとstate rootを作る。
  Config fileのbinding fieldを直接編集したり、configを別pathへcopyしたりしない。

`configure`はRuntimeを起動せず、transitionも許可しない。Unknown field、schema不一致、
configとstate rootのbinding不一致はfail closedで拒否される。

## `single-owner`と`dedicated-session`

`--single-owner`と`--dedicated-session`は、運用者がprofileの前提を受け入れたことを記録する
flagであり、環境全体を自動検査する機能ではない。Yohakuのowner lockが防ぐのは、同じ
state rootを使う協調launcherの二重ownerだけである。別Runtime client、detached process、
background work、非協調external writer、別state rootのownerは排除しない。

したがって、同じRuntime sessionやtask workspaceを別clientから操作しない。専用sessionは
freshに作り、既存sessionへのattachや、別ownerが作ったsessionのadoptを行わない。

## `preflight`

`preflight`はprocessを起動せず、設定と固定profileの前提を検査する。主な検査対象は次の
とおりである。

- WSL2 Linuxと、profileに固定したCPython version
- Runtime version。Hermesではpinned source commit、clean source tree、Hermes venvも確認
- Operational launcherの有無
- `single_owner` / `dedicated_session`のacknowledgement
- Workspaceとconfig / state binding
- 既存ownerとrestart可否
- Task Profileの場合はtask contract、credential、Trusted Observer / Assessorを構成できるか

Codexのversion出力が一致しない場合は`RUNTIME_VERSION_MISMATCH`、Hermes source commitが
一致しない場合は`SOURCE_VERSION_MISMATCH`、未測定platform / Pythonはそれぞれ
`OPERATIONAL_PLATFORM_NOT_MEASURED` / `OPERATIONAL_PYTHON_NOT_MEASURED`となる。
いずれも`start`前に拒否される。Preflight `PASS`はnative startup、task execution、
transition acceptanceを示さない。

Lifecycle-only profileにはTrusted ObserverとTask Assessorがない。この場合、preflight自体は
通り得るが、`transition_available=false`と`TASK_PROFILE_REQUIRED`を返す。`transition`、
task turn、compact、resumeを送る経路は拒否される。

## `enable`

`enable`は、次回の`start`または`run`を許可する。Runtime processを開始せず、既存ownerへ
接続せず、transition authorityを発行しない。Live owner、clean stopが確認できない
stale owner、restart不可能なprior runがある場合は、`RECOVERY_REQUIRED_BEFORE_ENABLE_OR_DISABLE`
または`OWNER_BUSY`で拒否される。

## `start`とforeground owner

`start`はlifecycle-only profile専用である。Configがenabledで、preflightが`PASS`し、
fresh startが許可される場合だけ、foreground ownerが新しいrun directoryとfresh dedicated
sessionを作る。Startup recordをJSONで出力した後も、owner lock、control socket、Runtime
connectionを保持して待機する。

Codex ownerはisolated `CODEX_HOME`でdedicated App Serverとfresh threadを作り、inference
credential、task turn、compactを使わない。Hermes ownerはpinned sourceとnative venv内で
`HermesCLI`とnative DBを構築するが、lazy inference agent、chat、compress、task toolを
有効にしない。

`Ctrl-C`または`SIGTERM`はgraceful stop要求として扱う。Foreground processを強制終了すると、
clean stopが記録されず、次回startはrecovery判定で拒否される可能性がある。

## `status`

`status`は常にJSONを返す。`--json`も受理するが、出力形式は変わらない。主な表示は次の
とおりである。

| Field | 意味 |
|---|---|
| `enabled` | Configが次回start / runを許可しているか |
| `owner_live` | Owner lockだけでなく、private control socketから現在のowner応答を確認できたか |
| `owner_lock_busy` | 同じstate rootをownerが保持しているか |
| `profile` / `package` | 固定profile、installed package version、Python、installed RECORD hash |
| `observed_runtime` / profile内のexpected identity | 起動時に照合したRuntime versionまたはsource commit |
| `operational.state` | `NEVER_STARTED`、`STARTING`、`RUNNING`、`STOPPING`、`STOP_INCOMPLETE`、`STOPPED`、`FAILED`、`AMBIGUOUS`、`OWNER_UNREACHABLE`、`RECOVERY_REQUIRED`のいずれか |
| `recovery.fresh_start_allowed` | Prior runをresumeせず、新しいdedicated sessionを開始できるか |
| `recovery.resume_supported` | Prior runのtask / sessionを再開できるか。現在のoperational CLIでは常に`false` |
| `recovery.reason` | Fresh start可能、不可能、またはmanual inspectionが必要な理由 |
| `recovery.saved_data_retained` | Recovery判断によって保存dataを削除していないこと |
| `transition_available` / `transition_reason` | Task integrationの有無。Lifecycle statusやcompletion proofではない |

`fresh_start_allowed=true`と`resume_supported=true`は同じ意味ではない。Confirmed clean stop後の
lifecycle-only profileは、新しいsessionを開始できるだけで、停止前sessionをresumeしない。
Task Profile runは、正常終了後も`TASK_COMPLETE_NO_RERUN`となり、同じstate rootで再実行しない。

Owner lockがbusyなのにsocketへ到達できない場合、`OWNER_UNREACHABLE`と表示する。Lockが空いて
いてもprior stateが`STOPPED`以外なら`RECOVERY_REQUIRED`である。PID不在やsocket欠落だけを
clean stopの証拠にしない。

## `stop`

`stop`はprivate Unix socketを通じて、同じ`run_id`を持つforeground ownerへgraceful shutdownを
一回要求する。Codexではstdin EOF後のApp Server正常終了、Hermesではnative DBとYohaku storeの
closeを確認してから`STOPPED`と記録し、owner lockを解放する。Lifecycle `stop`はforeground
`run`で実行するTask Profileを制御しない。

Stop timeoutではSIGKILLへescalateしない。OwnerはlockとRuntime観測を保持し、
`STOP_INCOMPLETE`を記録する。`stop` commandは`STOP_TIMEOUT; owner retained; inspect runtime`
を返す。ここで二回目のownerを起動したり、lock fileを削除したり、`STOPPED`へ書き換えたり、
uninstallしたりしない。既存ownerへ`status` / `stop`を行い、native shutdownの完了を待つ。

## `disable`

`disable`は将来の`start` / `run`を止めるconfig変更であり、実行中ownerのemergency stopではない。
Ownerを開始済みなら先に`stop`を完了し、`owner_lock_busy=false`と
`operational.state=STOPPED`を確認する。一度も開始していないconfigは直接disableできる。
Live owner、stale owner、`STOP_INCOMPLETE`、uncertain task runがある場合は拒否される。

Disableはconfig binding、run metadata、checkpoint、journal、handoff、archive、adapter metadata、
Runtime-native DB / transcriptを削除しない。保存dataの扱いは
[Storage and Recovery](storage-and-recovery.md)を参照する。

## `recover --inspect`

Operational CLIが公開するrecovery commandはread-only inspectionだけである。

```sh
yohaku recover --inspect --config /absolute/path/config.json
```

このcommandは`status`とrecovery decisionを返すが、Runtimeへ接続せず、continuationを送らず、
leaseやauthorityを復元しない。保存済みcheckpoint / handoff / archiveの全内容を検証する
commandでもない。`recover`を`--inspect`なしで実行すると
`UNSUPPORTED_RECOVERY`で拒否される。

`RECOVERY_REQUIRED`、`AMBIGUOUS`、stale owner、interrupted Task Profile runから、利用者が
blind retryしてはならない。Runtime side effectまたはtransitionが完了した可能性を否定できず、
同じoperationを再送すると重複し得るためである。State root、Runtime-native storage、log / Evidenceを
保持し、matching Runtime canonicalに従ってmaintainer reviewする。対応するrecovery contractが
ないprofileでは、新しいownerや新しいoutputで結果を推定せず、unsupportedのまま扱う。

## 拒否と対応

| 条件 | 表示またはreason | 運用者の対応 |
|---|---|---|
| Runtime / source version不一致 | `RUNTIME_VERSION_MISMATCH` / `SOURCE_VERSION_MISMATCH` | Profileを変更せず、fixed versionと実体を照合する |
| Operational launcherがないprofile | `OPERATIONAL_PROFILE_UNSUPPORTED` | Adapterやhistorical Evidenceをlauncherとして使わない |
| Observer / Assessor不足 | `TASK_PROFILE_REQUIRED` | 対応するTask Profileを選ぶ。Lifecycle profileからtask supportを推定しない |
| 二重owner | `OWNER_BUSY` | 既存ownerを`status`で確認し、第二ownerを起動しない |
| Stale owner / unclean exit | `OWNER_UNREACHABLE`または`RECOVERY_REQUIRED` | PIDだけで死亡判定せず、保存dataとRuntimeをinspectする |
| Stop timeout | `STOP_INCOMPLETE` / `STOP_TIMEOUT` | Lockを保持したownerの観測を継続し、killやfresh startを行わない |
| Clean stop済みlifecycle profile | `fresh_start_allowed=true`、`resume_supported=false` | 同じroot内にfresh dedicated sessionを新設できる |
| Task Profile完了または中断 | `TASK_COMPLETE_NO_RERUN`または`TASK_RESTART_UNSUPPORTED` | Completed / uncertain side effectを再実行せず、Task Profile contractに従う |
| Dispatch / completion不明 | `AMBIGUOUS` | Correlated late Evidenceを照合するまで通常作業とretryを止める |

## Runtime間の運用差

### Codex

`codex-operational-0.158`はformal operational launcherを持つ。Isolated home、dedicated App
Server、fresh thread、no-inferenceでlifecycleだけを実行する。Historical Codex `0.155`の
transition / restart Evidenceは、このprofileへ継承しない。

`codex-document-review-report-v1`は別の`run` entry pointを持つが、acceptedなのは固定Task
Profileだけである。Input / output、Assessor、no-rerun条件はTask Profile canonicalを参照する。

### Hermes

`hermes-operational-h-cli-01`はformal operational launcherを持つ。Hermes native venv内で
同じwheelを使い、`--runtime-path`にはshell launcherではなくpinned source rootを指定する。
Native DBとYohaku storeを一つのforeground processで開くが、inference agentとH-CLI-01
transition adapterは有効にしない。Interrupted ownerへのattach / restartは未対応である。

### Claude Code CLI

Claude Code CLIには、Codex / Hermesと同等のformal operational launcherがない。
`claude-c-cli`と`claude-c-cli-local-nonce`はbounded adapter / Evidence profileであり、
`configure`後に`start`できるoperational supportではない。Maintainer runnerやaccepted
completion / recovery Evidenceをformal lifecycle supportへ昇格させない。

Runtime固有のcompletion proof、receipt、late / duplicate event、restart / reconnectの条件は
各Runtime canonicalが所有する。本書では共通化しない。

## Disable / uninstallと保存data

Uninstall前にownerをclean stopし、lockが解放されたことを確認する。同じinterpreterから
packageを削除する。

```sh
/absolute/path/to/venv/bin/python -m pip uninstall yohaku
```

Uninstallはuser-managed config、state root、各run directory、Yohaku checkpoint / journal /
handoff / archive、Runtime-native DB / transcriptを削除しない。再接続する場合は、同じ保存契約を
読めるreviewed wheelをinstallしてからinspectする。Uninstallやreinstallをrecovery、schema
migration、clean stopの代用にしない。

## 現在の公開範囲

全profileのmaturityは`experimental`、release channelは`undeclared`である。現在の文書は、
Runtime family全体、Strong Transition Assurance、general exactly-once、field acceptance、
power-loss recoveryを宣言しない。個別profileのaccepted scopeとKnown Limitationsは
[Runtime support summary](runtime-support.md)で確認する。
