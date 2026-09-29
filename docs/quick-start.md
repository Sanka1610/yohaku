# Quick Start

本書は、review済みwheelをinstall済みの利用者が、current operational CLIを最小構成で実行するための
手順である。Installation、Python / platform要件、Runtime差、uninstallは
[Installation](installation.md)を先に確認する。

二つの例は別profileである。

- Lifecycle-only: Codexをno-inferenceでstart / status / stopする。Taskもtransitionも実行しない
- Real-task: Codex専用`document-review-report-v1`を一回だけ`run`する

Lifecycle-only成功をVerified Context Transition成功として扱わず、Real-task成功をgeneral document
supportや文章品質の証明として扱わない。

<a id="lifecycle-only-quick-start"></a>
## Lifecycle-only Quick Start

対象は`codex-operational-0.158`である。次を満たす環境で実行する。

- WSL2 Linux
- CPython `3.14.4`
- Review済み`yohaku` `0.1.0` wheelをinstallした専用venv
- `codex-cli 0.158.0-alpha.2.1`と表示するCodex binary

このprofileはcredentialを読み込まず、provider request、inference、task turn、compact、handoff、resumeを
実行しない。

### Terminal 1: configure、preflight、enable、start

Wheelをcurrent directoryへ置いた状態から始める。既にclean install済みなら、installation部分を飛ばし、
`YOH_VENV`をそのvenvのabsolute pathへ設定する。

```sh
umask 077
YOH_WHEEL="$(realpath ./yohaku-0.1.0-py3-none-any.whl)"
YOH_VENV="$(pwd -P)/.venv-yohaku"
test -f "$YOH_WHEEL"

python3.14 --version
test ! -e "$YOH_VENV"
python3.14 -m venv "$YOH_VENV"
"$YOH_VENV/bin/python" -m pip install --no-index --no-deps "$YOH_WHEEL"
"$YOH_VENV/bin/python" -m pip check
"$YOH_VENV/bin/python" -m yohaku --version
"$YOH_VENV/bin/yohaku" profiles

YOH_ROOT="$(pwd -P)/yohaku-lifecycle-example"
YOH_CONFIG_DIR="$YOH_ROOT/config"
YOH_WORKSPACE="$YOH_ROOT/workspace"
YOH_CONFIG="$YOH_CONFIG_DIR/codex.json"
YOH_STATE="$YOH_ROOT/codex-state"
command -v codex >/dev/null
YOH_CODEX="$(readlink -f "$(command -v codex)")"

test ! -e "$YOH_ROOT"
mkdir -p "$YOH_CONFIG_DIR" "$YOH_WORKSPACE"
chmod 700 "$YOH_ROOT" "$YOH_CONFIG_DIR" "$YOH_WORKSPACE"
test ! -e "$YOH_CONFIG"
test ! -e "$YOH_STATE"
"$YOH_CODEX" --version

"$YOH_VENV/bin/yohaku" configure \
  --config "$YOH_CONFIG" \
  --profile codex-operational-0.158 \
  --runtime-path "$YOH_CODEX" \
  --workspace "$YOH_WORKSPACE" \
  --state-dir "$YOH_STATE" \
  --single-owner \
  --dedicated-session

"$YOH_VENV/bin/yohaku" preflight --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" enable --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" start --config "$YOH_CONFIG"
```

`preflight`は`verdict: PASS`を返す一方、`transition_available: false`と
`TASK_PROFILE_REQUIRED`も返す。Lifecycle-only profileではこれが正常である。`start`はstartup JSONを
表示した後、foreground ownerとして待機する。このterminalを閉じずにTerminal 2へ進む。

`preflight PASS`はnative startup、transition acceptance、Task Profile completion、Codex family supportを
意味しない。`start`後もNo inference / No transitionである。

### Terminal 2: status、stop、disable、inspect

Terminal 1と同じdirectoryで、変数を再設定する。

```sh
YOH_VENV="$(pwd -P)/.venv-yohaku"
YOH_ROOT="$(pwd -P)/yohaku-lifecycle-example"
YOH_CONFIG="$YOH_ROOT/config/codex.json"

"$YOH_VENV/bin/yohaku" status --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" stop --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" status --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" disable --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" recover --inspect --config "$YOH_CONFIG"
```

Stop後の`status`で、少なくとも`owner_lock_busy: false`、`operational.state: STOPPED`、
`recovery.resume_supported: false`を確認する。`fresh_start_allowed: true`は、同じstate root内にfresh
dedicated sessionを新設できるという意味であり、停止前sessionやtaskをresumeできるという意味ではない。

Terminal 1はclean stop後に終了する。`disable`は次回startを禁止するだけで、保存dataを削除しない。
`recover --inspect`はread-onlyであり、Runtimeへ接続せず、continuationやretryを送らない。

<a id="document-review-report-v1-quick-start"></a>
## `document-review-report-v1` Quick Start

対象は`codex-document-review-report-v1`であり、current accepted bindingは次に限定される。

- Codex CLI `0.158.0-alpha.2.1`
- WSL2 Linux / CPython `3.14.4`
- Fresh dedicated Codex App Server session
- Dedicated private workspace
- 宣言したUTF-8 Markdown / text input
- 存在しないcreate-only Markdown output
- 一回のmanual compactと一回のreport write

この例では既存のinput fileをdedicated workspaceへcopyする。`YOH_SOURCE_DOCUMENT`と
`YOH_CODEX_CREDENTIAL_HOME`の二つを、実在するabsolute pathへ置き換える。Credential homeには、Codexが
管理する既存`auth.json`が必要である。Yohaku configへcredential valueを記録しない。

### Workspaceとconfigの準備

Task workspaceには、宣言input以外のfileを置かない。Output fileは作成しない。

```sh
umask 077
YOH_VENV="$(pwd -P)/.venv-yohaku"
YOH_TASK_ROOT="$(pwd -P)/yohaku-document-review-example"
YOH_CONFIG_DIR="$YOH_TASK_ROOT/config"
YOH_TASK_WORKSPACE="$YOH_TASK_ROOT/workspace"
YOH_CONFIG="$YOH_CONFIG_DIR/document-review.json"
YOH_STATE="$YOH_TASK_ROOT/document-review-state"
YOH_INPUT="$YOH_TASK_WORKSPACE/source.md"
YOH_OUTPUT="$YOH_TASK_WORKSPACE/review-report.md"
command -v codex >/dev/null
YOH_CODEX="$(readlink -f "$(command -v codex)")"

YOH_SOURCE_DOCUMENT="$(realpath /absolute/path/to/source.md)"
YOH_CODEX_CREDENTIAL_HOME="$(realpath /absolute/path/to/existing-codex-home)"

test -f "$YOH_SOURCE_DOCUMENT"
test -f "$YOH_CODEX_CREDENTIAL_HOME/auth.json"
test ! -e "$YOH_TASK_ROOT"
mkdir -p "$YOH_CONFIG_DIR" "$YOH_TASK_WORKSPACE"
chmod 700 "$YOH_TASK_ROOT" "$YOH_CONFIG_DIR" "$YOH_TASK_WORKSPACE"
install -m 600 "$YOH_SOURCE_DOCUMENT" "$YOH_INPUT"
test ! -e "$YOH_OUTPUT"
test ! -e "$YOH_CONFIG"
test ! -e "$YOH_STATE"
```

Inputは1〜16 files、各fileと合計はいずれも最大2 MiBである。Symlink、directory、workspace外path、
undeclared file、既存outputは拒否される。複数inputを使う場合は、各fileをworkspaceへcopyし、
`configure`へ`--input`を繰り返す。Report bodyはMarkdown heading marker `#`で始め、UTF-8で
512 KiB以下にする必要がある。

### Configure、preflight、run

Instructionはそのrunに固定され、最大16,000 charactersである。次の例は、宣言文書の根拠不足と矛盾を
指摘し、Markdown reportへまとめるよう依頼する。

```sh
YOH_INSTRUCTION='宣言文書をレビューし、根拠が不足する記述と文書内の矛盾を指摘し、各指摘に根拠箇所を添えてMarkdownで報告する。'

"$YOH_VENV/bin/yohaku" configure \
  --config "$YOH_CONFIG" \
  --profile codex-document-review-report-v1 \
  --runtime-path "$YOH_CODEX" \
  --workspace "$YOH_TASK_WORKSPACE" \
  --state-dir "$YOH_STATE" \
  --input "$YOH_INPUT" \
  --output "$YOH_OUTPUT" \
  --instruction "$YOH_INSTRUCTION" \
  --credential-home "$YOH_CODEX_CREDENTIAL_HOME" \
  --single-owner \
  --dedicated-session

"$YOH_VENV/bin/yohaku" preflight --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" enable --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" run --config "$YOH_CONFIG"
```

Task Profileは`start`ではなく`run`を使う。`run`はforegroundで完了まで待機する。成功時のJSONには
`verdict: PASS`、`mechanical_task_completion: PASS`、`core_state: RESUME_VERIFIED`、`output`が含まれる。
Reportは指定した`YOH_OUTPUT`に一回だけcreateされる。

### Completed outputとno rerun

Run終了後は状態とoutputの存在を確認し、将来のrunをdisableする。

```sh
"$YOH_VENV/bin/yohaku" status --config "$YOH_CONFIG"
test -f "$YOH_OUTPUT"
"$YOH_VENV/bin/yohaku" disable --config "$YOH_CONFIG"
```

`mechanical_task_completion: PASS`は、declared input、fixed instruction、one compact、one create-only
output、fresh observation、non-duplicate continuationがTask Profile contractを満たしたことを示す。
Reportの文章品質、事実性、指摘の妥当性は`NOT_ASSESSED`である。

同じconfig、state root、outputを使って`run`を繰り返さない。Completed runでは
`TASK_COMPLETE_NO_RERUN`、interrupted / uncertain runでは`TASK_RESTART_UNSUPPORTED`または
`RECOVERY_REQUIRED`となる。Outputを削除したり別pathへ変えたりしてrerunすると、同じlogical taskの
side effectを重複させる可能性がある。

Runが成功以外で終了した場合は、次だけを実行する。

```sh
"$YOH_VENV/bin/yohaku" status --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" recover --inspect --config "$YOH_CONFIG"
```

`stop`はlifecycle-onlyのforeground ownerを停止するcommandであり、Task Profile `run`を制御しない。
`AMBIGUOUS`、`RECOVERY_REQUIRED`、stale owner、uncertain outputではblind retryしない。Workspace、state root、
Runtime-native storageを保持し、[Storage and Recovery](storage-and-recovery.md)と
[Task Profile canonical](task-profiles/document-review-report-v1.md)に従ってmanual reviewする。

## 次に読む文書

[Documentation Index](index.md)から、Operations、Runtime Support、Task Profile、Storage and Recovery、
またはdevelopment documentationへ進んでください。
