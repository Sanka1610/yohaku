# Getting Started

この手順は未公開のBeta candidateに対応します。公開済みAlpha wheelを使う場合は[対応tagの文書](https://github.com/Sanka1610/yohaku/tree/v0.1.0a1)を参照してください。Alpha wheelと未公開sourceを混ぜず、配布物を更新するときは新しいversionを使います。

## Wheelを導入する

[GitHub Releases](https://github.com/Sanka1610/yohaku/releases)から対象版の`yohaku-<version>-py3-none-any.whl`を取得します。Python `>=3.11`が必要です。Operational CLIはLinux上のlocal POSIX filesystem、owner permissions、`flock`、Unix socket、file / directory `fsync`を使います。

```sh
umask 077
YOH_WHEEL="$(realpath /absolute/path/to/yohaku-<version>-py3-none-any.whl)"
YOH_VENV="$(pwd -P)/.venv-yohaku"
test -f "$YOH_WHEEL"
test ! -e "$YOH_VENV"
python3 -m venv "$YOH_VENV"
"$YOH_VENV/bin/python" -m pip install --no-index --no-deps "$YOH_WHEEL"
"$YOH_VENV/bin/python" -m pip check
"$YOH_VENV/bin/yohaku" --version
"$YOH_VENV/bin/yohaku" profiles
"$YOH_VENV/bin/yohaku" doctor
```

Non-editable wheelを使います。Editable installや`PYTHONPATH=src`は開発用です。Hermesの場合は専用sourceの既存`venv`へ導入し、native dependenciesを変更しません。Runtime version / source pinとtested configurationの違いは[Runtime support](runtime-support.md#hard-requirementとtested-configuration)を参照してください。

起動前にdoctorの検出結果と[Beta support表](runtime-support.md#beta-support-status)を照合し、使うprofileのexact条件を確認してください。`unknown` / `not detected` / `not checked`は確認済みの互換性を意味しません。以下のCLI例はCodexのlaunch-supported profile用です。DSH / OpenCodeとOrcaは各Runtimeページのembedding host契約を使います。

Config、state、workspaceにはabsolute pathを使い、symlinkや`..`を含めません。Configとstateはcurrent UIDが所有しgroup / otherからアクセスできない必要があります。State rootとworkspaceは別directoryとし、親子関係にも置きません。`configure`がstate rootを新規作成するため、先に作らないでください。

## Inferenceなしで起動・停止を確認する

`codex-operational-0.158`とCodex CLI `0.158.0-alpha.2.1`を使います。このprofileはtask、compact、handoff、resumeを実行しません。

Terminal 1で次を実行します。

```sh
umask 077
YOH_ROOT="$(pwd -P)/yohaku-lifecycle-example"
YOH_CONFIG="$YOH_ROOT/config/codex.json"
YOH_CODEX="$(readlink -f "$(command -v codex)")"
test ! -e "$YOH_ROOT"
mkdir -p "$YOH_ROOT/config" "$YOH_ROOT/workspace"
"$YOH_CODEX" --version
"$YOH_VENV/bin/yohaku" configure \
  --config "$YOH_CONFIG" --profile codex-operational-0.158 \
  --runtime-path "$YOH_CODEX" --workspace "$YOH_ROOT/workspace" \
  --state-dir "$YOH_ROOT/state"
"$YOH_VENV/bin/yohaku" preflight --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" enable --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" start --config "$YOH_CONFIG"
```

`preflight`の`PASS`と`task_profile_registered: false` / `transition_ready: false`は両立します。起動後はforeground ownerとして待機します。

Terminal 2では`YOH_VENV`と`YOH_CONFIG`を同じabsolute pathへ設定し、次を実行します。

```sh
"$YOH_VENV/bin/yohaku" status --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" stop --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" status --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" disable --config "$YOH_CONFIG"
```

`STOPPED`と`owner_lock_busy: false`を確認します。`fresh_start_allowed: true`は新sessionの開始可否です。旧taskをresumeする許可ではありません。Stop timeoutやstale ownerでは[Operations](operations.md#停止復旧)に従います。

## 固定document-review taskを一回実行する

`codex-document-review-report-v1`は宣言したUTF-8文書を読み、manual compact一回の後、Markdown reportを一つ新規作成します。Inferenceと既存credentialを使うため、実行対象文書とaccount / provider accessを確認してから`run`してください。

次のsourceとcredential homeを、実在するabsolute pathに置き換えます。Credential homeと`auth.json`はcurrent UID所有でgroup / other権限がなく、symlinkでない必要があります。Credential valueをconfigへ書きません。

```sh
umask 077
YOH_TASK_ROOT="$(pwd -P)/yohaku-review-example"
YOH_CONFIG="$YOH_TASK_ROOT/config/review.json"
YOH_WORKSPACE="$YOH_TASK_ROOT/workspace"
YOH_SOURCE_DOCUMENT="/absolute/path/to/source.md"
YOH_CODEX_CREDENTIAL_HOME="/absolute/path/to/existing-private-codex-home"
YOH_CODEX="$(readlink -f "$(command -v codex)")"
test ! -e "$YOH_TASK_ROOT"
mkdir -p "$YOH_TASK_ROOT/config" "$YOH_WORKSPACE"
install -m 600 "$YOH_SOURCE_DOCUMENT" "$YOH_WORKSPACE/source.md"
"$YOH_VENV/bin/yohaku" configure \
  --config "$YOH_CONFIG" --profile codex-document-review-report-v1 \
  --runtime-path "$YOH_CODEX" --workspace "$YOH_WORKSPACE" \
  --state-dir "$YOH_TASK_ROOT/state" \
  --input "$YOH_WORKSPACE/source.md" --output "$YOH_WORKSPACE/review-report.md" \
  --instruction '宣言文書の根拠不足と矛盾を指摘し、根拠箇所を添えてMarkdownで報告する。' \
  --credential-home "$YOH_CODEX_CREDENTIAL_HOME"
"$YOH_VENV/bin/yohaku" preflight --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" enable --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" run --config "$YOH_CONFIG"
"$YOH_VENV/bin/yohaku" status --config "$YOH_CONFIG"
```

Workspaceには宣言inputだけを置き、outputを先に作りません。Inputは1〜16 files、各fileと合計は2 MiB以下、instructionは16,000 characters以下です。詳細な拒否条件は[Task Profile](task-profiles/document-review-report-v1.md)を参照します。

成功時は`core_state: RESUME_VERIFIED`、`mechanical_task_completion: PASS`とoutputを確認します。文章品質・事実性は`NOT_ASSESSED`です。Same config / state / outputでrunを繰り返しません。Completedまたはuncertainなtaskは、outputを消したりfresh stateへ切り替えたりしてrerunせず、状態を保持します。

## 更新・uninstall

Ownerのclean stopを確認してからpackageを更新・削除します。Schema-1の既存config / stateは暗黙migrationせず保持します。更新はtask recoveryやold authority復活を意味しません。[Support Policy](../SUPPORT_POLICY.md#更新と互換性)を参照してください。

```sh
"$YOH_VENV/bin/python" -m pip uninstall yohaku
```

Uninstallはworkspace、checkpoint、handoff、archive、Runtime-native DBを削除しません。問題を報告する場合は[Issue reporting](issue-reporting.md)のprivacy境界を確認します。
