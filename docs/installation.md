# Installation

Yohakuを初めて使う場合は、review済みwheelを専用venvへnon-editable installし、
operational CLIのJSON configを作成する。この経路が現在の推奨installation pathである。
PackageをinstallしただけではRuntime integrationは有効にならず、RuntimeやTask Profileも
acceptedにならない。

公開中の全Support Profileはexperimentalであり、release channelは未宣言である。現在利用できるのは、固定した
Runtime versionとprofileに対するbounded supportである。一般的な「installすると任意のRuntime、
task、compactionを自動管理するplugin」ではない。

実際のcommandだけを先に試す場合は、[Quick Start](quick-start.md)へ進む。本書はinstallation
path、前提条件、Runtime選択、storage、uninstall、安全なtroubleshootingを説明する。CLIの
状態遷移と拒否条件は[Operations](operations.md)が正本である。

## 現在利用できる範囲

Package installation、operational lifecycle、transition、Task Profileは別のclaimである。

| 対象 | 現在の範囲 |
|---|---|
| Python package | `yohaku` `0.1.0`。Metadata上はPython `>=3.11`、runtime dependencyなし。Versionはpublished Alphaやrelease channelを意味しない |
| Codex lifecycle | `codex-operational-0.158`。Codex `0.158.0-alpha.2.1`、WSL2 Linux、CPython `3.14.4`でno-inference lifecycleを提供 |
| Hermes lifecycle | `hermes-operational-h-cli-01`。Hermes `0.21.0`、固定source commit、Hermes venvのCPython `3.11.16`でno-inference lifecycleを提供 |
| Packaged real Task Profile | Codex専用の`codex-document-review-report-v1`。固定した`document-review-report-v1`だけを`run`できる |
| Historical Codex Reference | `codex-reference-0.155`。Codex `0.155.0-alpha.16.4`のretained Referenceであり、current operational launcherではない |
| Hermes connected adapter | `hermes-h-cli-01`。H-CLI adapter Evidence用profileであり、current operational launcherではない |
| Claude Code CLI | Runtime canonicalとbounded adapter Evidenceはあるが、Codex / Hermes相当のformal operational launcherはない |

Pure-Python wheelをinstallできても、確認できるのはpackage compatibilityに限られる。
Runtime support、Task Profile support、transition acceptanceは別に確認する。

`profiles`はこの区別をJSONで返す。Runtime family名だけを見てprofileを選ばず、
`runtime_version`、`surface`、`operational_platform`、`operational_python`、
`launch_supported`、`task_profile`、`known_limitations`を確認する。

## Installation pathの区別

### 推奨: review済みwheelのnormal installation

一般利用者は、source commitとSHA-256をreviewしたwheelを、対象profileが要求するPython環境へ
non-editable installする。現在のpackageはpublic releaseを宣言していないため、index上の同名packageを
無条件に取得する手順は示さない。Wheelと期待するdigestは、信頼できる配布元から別々に確認する。

Codex operational profileとTask Profileでは、専用venvへwheelをinstallする。Hermes operational
profileだけは、pinned Hermes sourceに含まれる既存venvがhost interpreterになるため、そのvenvへ
同じwheelをinstallする。

### Repository / development installation

Product checkoutからwheel candidateを作る場合は、source commitを固定してから次を実行する。

```sh
python3.14 -m pip wheel --no-deps --wheel-dir ./dist .
sha256sum ./dist/yohaku-0.1.0-py3-none-any.whl
```

Build frontendは`setuptools>=77`を必要とし、取得時にnetworkを使う可能性がある。生成物は
local candidateであり、build成功だけではreview済みrelease artifactにならない。Source commit、
wheel hash、review結果を対応付けてから、別のclean venvへnormal installする。

`pip install -e .`と`PYTHONPATH=src`は開発・local test用である。利用者向けのoperational
installationとして扱わない。

### Historical source-copy / Probe-only path

Historical Hermes ProbeとStage 4 adapter acceptanceには、Yohaku sourceを固定Hermes環境へcopyして
importしたrunがある。このsource-copyは、そのEvidenceの取得条件を示すhistorical手順であり、current
installation pathではない。Source-copyをnormal wheel installationの代替にせず、過去の結果を
installed wheelの新しいlive acceptanceへ読み替えない。

### Embedded TOML activation

`yohaku.config.load_config()` / `activate()`と次のTOMLは、既存のembedding hostがowner factory、
observer、Hook、storageを自分で構成するためのopt-in helperである。

```toml
[yohaku]
runtime = "codex"
enabled = false
```

`runtime`には`codex`または`hermes-h-cli-01`を指定できる。`enabled = true`にしてもYohakuがRuntimeを
自動launchするわけではなく、embedding applicationが`activate(..., create=...)`へ渡したfactoryを
呼ぶだけである。このTOMLはcurrent operational CLIのconfigではない。新規利用者は、次項のJSON / CLI
configurationを使う。

### Operational JSON / CLI configuration

`yohaku configure`は、profile、Runtime path、workspace、private state rootをbindingしたJSON configを
新規作成する。`preflight`、`enable`、`start`または`run`、`status`、`stop`、`disable`、
`recover --inspect`はこのconfigを使う。Config fileとstate rootは既存物を採用せず、別Runtime、
別profile、別workspaceへ切り替えるときは新しい組を作る。

## Python、platform、storageの前提

`requires-python = ">=3.11"`はpackage metadataのinstallation floorである。Operational
profileのaccepted host条件は、これより狭い。

| Profile | Host Python | Platform / storage | Runtime requirement |
|---|---|---|---|
| `codex-operational-0.158` | CPython `3.14.4` | WSL2 Linux。POSIX ownership、mode、`flock`、Unix socket、`fsync`を利用 | `codex-cli 0.158.0-alpha.2.1`と完全一致するbinary |
| `codex-document-review-report-v1` | CPython `3.14.4` | WSL2 Linux。private dedicated workspaceと別のprivate state root | 同じCodex binary、既存のCodex `auth.json`、profile実行に利用できるaccount / provider access |
| `hermes-operational-h-cli-01` | Hermes venvのCPython `3.11.16` | WSL2 Linux。POSIX storage、native Hermes DB、Yohaku store | Hermes `0.21.0`、source `c5594ec4b34097cafbe24deb6dfd9ac4b21d411d`、clean source tree、`<source>/venv` |

Wheelのclean installと`pip check`はCPython `3.11.16`と`3.14.4`で確認されている。これは
CPython `3.12` / `3.13`、Windows native、他OS、他interpreter、他patch versionのoperational
acceptanceではない。Current `preflight`はprofileに固定したPython versionとWSL2 Linuxを検査し、
未測定条件を拒否する。

Windowsから利用する場合も、command、Runtime、config、state、control socketはWSL2 Linux内で動かす。
Windows-native persistenceは未対応である。Storageは、accepted local POSIX semanticsを満たすprivate
filesystemへ置く。Network filesystem、backup restore、cross-host migration、power-loss recoveryは
accepted scope外である。

`--config`、`--runtime-path`、`--workspace`、`--state-dir`、Task Profileのinput / output /
credential homeにはabsolute pathが必要で、`..`やsymlink componentは拒否される。Config directory、
config file、state root、Task Profile workspace / inputはcurrent UIDが所有し、group / otherから
accessできない必要がある。

## Runtimeの選択

### Codex

初回のoperational確認には`codex-operational-0.158`を選ぶ。このprofileは専用App Server、fresh
thread、status、graceful stopを確認するが、credentialを読み込まず、inference、task turn、compact、
handoff、resumeを無効にする。Lifecycle `PASS`はtransition `PASS`ではない。

実taskを実行できるcurrent bindingは`codex-document-review-report-v1`だけである。Codex
`0.158.0-alpha.2.1`上で、宣言したUTF-8 Markdown / text inputを読み、一回のmanual compact後に
create-only Markdown reportを一つ作る。Mechanical completionはaccepted scopeに含まれるが、文章品質と
事実性は`NOT_ASSESSED`である。

`codex-reference-0.155`はHistorical Referenceである。Codex `0.155.0-alpha.16.4`のmanual / native
transition Evidenceを保持するが、current `0.158` operational profileまたはTask Profileへ継承しない。
`launch_supported=false`なので、一般利用者が`start`するprofileではない。

### Hermes

`hermes-operational-h-cli-01`は、pinned native Hermes source、native DB、Yohaku storeを一つの
foreground processで開くlifecycle-only profileである。Hermesの既存venvへwheelをinstallし、
`--runtime-path`にはshell launcherではなくpinned source rootを指定する。Inference agent、chat、
compression、task tools、provider requestは有効にならない。

`hermes-h-cli-01`は別profileである。H-CLI adapter Evidenceはmanual compression、Runtime固有の
completion proof、adapter-defined receipt、fixed synthetic assessorを含むが、formal operational
launcherとして公開されていない。H-CLI adapter workflowのbounded `PASS`を、lifecycle launcher、
general Task Profile、Hermes family supportへ読み替えない。

Hermesのhistorical live profilesは既存`openai-codex` credential、`gpt-5.6-luna`、reasoning lowを
使った。Lifecycle-only profileはprovider requestを発行しないため、provider / account compatibilityを
確認する用途には使えない。

### Claude Code CLI

Claude Code CLIにはRuntime canonicalとbounded completion / recovery adapter Evidenceがある。ただし、
`claude-c-cli`と`claude-c-cli-local-nonce`は`launch_supported=false`であり、Codex / Hermes相当の
formal operational launcherではない。`configure`で選択しても`preflight`は
`OPERATIONAL_PROFILE_UNSUPPORTED`を返す。Installation guideから一般operational supportを推定しない。

## Clean wheel installation

次の例はCodex operational profile向けであり、wheelをcurrent directoryへ置いた状態から始める。
`python3.14 --version`が`Python 3.14.4`であることを先に確認する。変数は例を実行するshell内だけで使う。

```sh
python3.14 --version
YOH_WHEEL="$(realpath ./yohaku-0.1.0-py3-none-any.whl)"
YOH_VENV="$(pwd -P)/.venv-yohaku"
test -f "$YOH_WHEEL"
test ! -e "$YOH_VENV"

sha256sum "$YOH_WHEEL"
python3.14 -m venv "$YOH_VENV"
"$YOH_VENV/bin/python" -m pip install --no-index --no-deps "$YOH_WHEEL"
"$YOH_VENV/bin/python" -m pip check
"$YOH_VENV/bin/python" -m yohaku --version
"$YOH_VENV/bin/yohaku" profiles
"$YOH_VENV/bin/python" -I -c 'import yohaku; from importlib.metadata import metadata; print(yohaku.__file__); print(metadata("yohaku")["Requires-Python"])'
```

出力では、versionが`0.1.0`、`Requires-Python`が`>=3.11`、package pathが作成したvenvの
`site-packages`配下であることを確認する。WheelのSHA-256は、配布元から得た期待値と照合する。
`profiles`の表示はcurrent registryの確認であり、各profileのlive acceptanceを再実行するcommandではない。

Hermesでは新しいvenvを作らず、pinned sourceの既存venvを使う。

```sh
YOH_WHEEL="$(realpath ./yohaku-0.1.0-py3-none-any.whl)"
HERMES_SOURCE="$(realpath /absolute/path/to/pinned-hermes-source)"
"$HERMES_SOURCE/venv/bin/python" --version
"$HERMES_SOURCE/venv/bin/python" -m pip install --no-index --no-deps "$YOH_WHEEL"
"$HERMES_SOURCE/venv/bin/python" -m pip check
"$HERMES_SOURCE/venv/bin/python" -m yohaku --version
```

このinstallによってHermes dependenciesをupgradeしない。Install前後のpackage一覧を保存し、Yohaku以外が
変わっていないことを確認する。Pinned source revisionとclean treeは`preflight`も検査する。

## Config / storage作成前の確認

`configure`はconfig fileとstate rootを新規作成し、既存pathがあれば拒否する。まずprivate config
directoryとworkspaceだけを作り、state pathは存在しない状態にする。

```sh
umask 077
YOH_LOCAL_ROOT="$(pwd -P)/yohaku-local"
YOH_CONFIG_DIR="$YOH_LOCAL_ROOT/config"
YOH_WORKSPACE="$YOH_LOCAL_ROOT/workspace"
YOH_CONFIG="$YOH_CONFIG_DIR/codex-lifecycle.json"
YOH_STATE="$YOH_LOCAL_ROOT/codex-lifecycle-state"

test ! -e "$YOH_LOCAL_ROOT"
mkdir -p "$YOH_CONFIG_DIR" "$YOH_WORKSPACE"
chmod 700 "$YOH_LOCAL_ROOT" "$YOH_CONFIG_DIR" "$YOH_WORKSPACE"
test ! -e "$YOH_CONFIG"
test ! -e "$YOH_STATE"
```

State rootとworkspaceは、同一pathにも親子関係にもできない。Ambient environmentにあるRuntime homeを
`--state-dir`として採用しない。別profileを試すときもconfigのfieldを直接編集せず、新しいconfig fileと
state rootを使う。

## Configureからrecovery inspectionまで

Codex lifecycle-only profileのcopy-paste可能な全手順は
[Lifecycle-only Quick Start](quick-start.md#lifecycle-only-quick-start)に示す。Commandの順序は次である。

```text
profiles
  → configure
  → preflight
  → enable
  → start
  → status
  → stop
  → disable
  → recover --inspect
```

`start`はforeground ownerとしてterminalを占有する。`status`と`stop`は別terminalから実行する。
`disable`は将来のstartを止めるconfig変更であり、実行中ownerを停止しない。先に`stop`が`STOPPED`を
記録し、owner lockが解放されたことを`status`で確認する。

`preflight PASS`が示すのは、固定profileの設定、version、platform、ownership、fresh-start条件が
実行前検査を通ったことだけである。Native startup、transition acceptance、Task Profile completion、
Runtime family supportは示さない。Lifecycle-only profileでは`transition_available=false`と
`TASK_PROFILE_REQUIRED`が正常な結果である。

## Lifecycle-only Quick Start

公開例には`codex-operational-0.158`を使う。Hermes lifecycleと異なり、既存Runtime venvへwheelを
installする必要がなく、credential、provider request、inferenceを使用しないためである。

このprofileは次だけを確認する。

- Dedicated Codex App Serverをowned processとしてstartできる
- Fresh thread、private run storage、status、graceful stopを扱える
- Confirmed clean stop後にfresh dedicated sessionを開始できる

Task input、inference、manual / native transition、handoff、receipt、resumeは実行しない。成功しても
Verified Context Transition成功ではない。実行手順は
[Lifecycle-only Quick Start](quick-start.md#lifecycle-only-quick-start)を参照する。

## `document-review-report-v1` Quick Start

Packaged real Task Profileは`document-review-report-v1`だけであり、current accepted bindingはCodex
`0.158.0-alpha.2.1`に限定される。`start`ではなく`run`を使う。

Task workspaceには宣言したinput fileだけを置き、outputは存在しないpathを指定する。Config、state、
credential homeはworkspace外に置く。`configure`では次をすべて固定する。

- `--profile codex-document-review-report-v1`
- 一回以上の`--input`
- 一つのcreate-only `--output`
- 固定`--instruction`
- 既存Codex `auth.json`を持つ`--credential-home`
- `--single-owner --dedicated-session`

実行順は`configure → preflight → enable → run → status → disable`である。Runnerは宣言inputの
read、verified boundary、checkpoint、一回のmanual compact、handoff、explicit receipt、fresh observation、
一回のreport write、mechanical assessmentをboundedに実行する。成功時は`mechanical_task_completion=PASS`、
`core_state=RESUME_VERIFIED`、固定output pathを返す。

同じstate rootまたは同じoutputでrerunしない。Completed runは`TASK_COMPLETE_NO_RERUN`、interruptedまたは
uncertain runは`TASK_RESTART_UNSUPPORTED` / `RECOVERY_REQUIRED`として扱う。文章品質、事実性、レビュー内容の
妥当性は`NOT_ASSESSED`であり、mechanical `PASS`から推定しない。正確な例は
[`document-review-report-v1` Quick Start](quick-start.md#document-review-report-v1-quick-start)、完全な
contractは[Task Profile canonical](task-profiles/document-review-report-v1.md)を参照する。

## `CODEX_HOME`とcredential home

`CODEX_HOME`には文脈ごとに別の役割がある。

- Historical Reference / embedded integrationでは、Codex config / authのrootであると同時に、既存
  persistence互換性のためYohaku schema-1 storage namespaceの選択にも使われる。
- `codex-operational-0.158`はrunごとにisolated `CODEX_HOME`を作り、credentialを置かず、inferenceを
  無効化する。利用者がambient `CODEX_HOME`を設定しても、operational JSON configや`--state-dir`にはならない。
- `codex-document-review-report-v1`の`--credential-home`は、既存`auth.json`の所在を指定する。Runnerは
  per-run isolated Codex homeを作り、その`auth.json`だけをsymlinkする。Credential valueをYohaku configや
  Evidenceへcopyするためのoptionではない。

Runtime authentication、account、subscriptionはRuntime側で管理する。Yohakuの`preflight`はTask Profileで
`auth.json`の存在を確認するが、account、provider、quota、billing、model accessの成立までは証明しない。

## Status、stop、recoveryの安全な使い方

通常時は`status`の`owner_live`、`owner_lock_busy`、`operational.state`、
`recovery.fresh_start_allowed`、`recovery.resume_supported`を一緒に読む。PIDやsocketの有無だけでclean stopを
推定しない。

| 表示 | 次の安全な動作 |
|---|---|
| `RUNTIME_VERSION_MISMATCH` / `SOURCE_VERSION_MISMATCH` | Profileを変更して通過させず、固定version、binary / source path、source commitを照合する |
| `OWNER_UNREACHABLE` / stale owner | 第二ownerを起動せず、lock、retained run record、Runtime processをinspectする |
| `STOP_INCOMPLETE` / `STOP_TIMEOUT` | Kill、lock削除、uninstall、fresh startを行わず、同じownerへ`status` / `stop`を行ってnative shutdownを確認する |
| `AMBIGUOUS` | Side effectまたはtransitionが完了した可能性を保持し、通常作業とblind retryを止め、correlated late Evidenceを照合する |
| `RECOVERY_REQUIRED` | Old authorityを復元せず、state rootとRuntime-native storageを保持してprofile canonicalに沿ってmanual reviewする |

Read-only inspectionは次で実行する。

```sh
yohaku recover --inspect --config /absolute/path/to/config.json
```

このcommandはRuntimeへ接続せず、continuationやretryを送らず、authorityを復元しない。
`recover`を`--inspect`なしで実行すると`UNSUPPORTED_RECOVERY`で拒否される。詳細は
[Storage and Recovery](storage-and-recovery.md)を参照する。

## Disable、uninstall、data deletion

次のoperationは別々であり、一つを実行しても他は実行されない。

| Operation | 変更するもの | 保持するもの |
|---|---|---|
| `disable` | Configのactivation flag | Config binding、run metadata、Yohaku storage、Runtime-native storage |
| Package uninstall | 選択したinterpreterのpackage files | User-managed config、state root、workspace、Runtime-native storage |
| Config deletion | User-managed JSON config | State rootとRuntime-native storage。Bindingとの対応を失うため、recovery前に行わない |
| Yohaku storage deletion | Checkpoint、journal、handoff、archive、adapter / operational metadata | Runtime-native DB / transcriptとtask workspace。Completionやclean stopの代用にならない |
| Runtime-native storage deletion | Codex thread / transcript / home、Hermes SessionDBなど | Yohaku stateとtask workspace。Runtime側のretention / auth policyに従う |

Uninstall前にownerをclean stopし、`status`で`owner_lock_busy=false`と`STOPPED`を確認する。その後、
installに使った同じinterpreterからpackageだけを削除する。

```sh
/absolute/path/to/yohaku-venv/bin/python -m pip uninstall yohaku
```

`STOP_INCOMPLETE`、`OWNER_UNREACHABLE`、`AMBIGUOUS`、`RECOVERY_REQUIRED`の状態でuninstallしても、
recovery問題は解決しない。現在、保存dataを一括削除する一般commandはない。Retention期間、secure deletion、
export、backup / restore policyも未定義である。したがって、installation guideは再帰的なcleanup commandを
提示しない。削除が必要な場合は、config、Yohaku state、task workspace、Runtime-native storageを個別に
inventoryし、各ownerのretention / privacy policyとrecovery要否を確認してから扱う。

## Security / privacy

- Credential、token、cookie、account情報をYohaku Evidenceへ含めない
- Runtime authはRuntime側で管理し、Yohaku configやtask inputへcopyしない
- Config directory、state root、task workspace、Runtime-native storageをprivateに保つ
- Evidenceを共有するときはallowlist方式でsanitizationし、不要なabsolute pathとtool argument / resultを除く
- Private transcript、Codex thread / home、Hermes `SessionDB`、Runtime state DBをそのまま公開しない
- Secretの単純hashも公開correlation IDとして使わない

Evidenceのauthorityと公開境界は[Evidence Model](evidence-model.md)、bundle作成とsanitization手順は
[Testing and Evidence](development/testing-and-evidence.md)を参照する。

## Known Limitations

- 全profileのmaturityはexperimental、release channelはundeclared
- Package publishingとinstallerは提供していない。一般利用者はreview済みwheelを別途必要とする
- Operational hostはWSL2 Linuxとprofile固定Python / Runtime versionに限定される
- Windows native、他OS、network filesystem、power loss、backup restore、cross-host migrationは未受入
- Lifecycle-only profileにはTask Observer / Assessorがなく、inferenceとtransitionを実行しない
- Packaged Task ProfileはCodexの`document-review-report-v1`だけで、general document / coding taskではない
- Task Profileのrestart、rerun、repeated transition、existing output採用は未対応
- Hook fault時のRuntime-wide fail-closed、Runtime-wide atomic freeze、external writer排除は未成立
- Parallel、background、detached、subagent、general MCP / shell / filesystem toolはaccepted coverage外
- Strong Transition Assurance、general exactly-once、Field Evidence、文章 / 事実品質の評価は未成立
- Claude Code CLIのformal operational launcherはない
- General retention、secure deletion、backup / restore policyは未定義

## Documentation navigation

[Documentation Index](index.md)から、Quick Start、Operations、Runtime Support、Task Profile、
Storage and Recovery、またはdevelopment documentationへ進んでください。
