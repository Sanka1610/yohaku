# Yohaku — Proactive Context Compaction Manager

Yohakuは、長時間続くAI agent taskでcontext transitionを管理するPython packageです。切替前の安全確認とcheckpoint保存、Runtime固有の完了確認、切替後の状態照合と再開検証を扱います。この仕組みを **Verified Context Transition** と呼びます。

実行されたか判断できない場合は`AMBIGUOUS`として停止し、副作用を照合するまで再実行を抑止します。RuntimeのACKやagentの成功宣言だけでは、transition完了やtask再開を認めません。

## 利用できる範囲

現在の主対象はCodexの二つのalpha profileです。`codex-operational-0.158`はinferenceを行わない起動・停止の診断用、`codex-document-review-report-v1`は宣言した文書を読み、manual compactを一回行い、Markdown reportを一つ新規作成する限定taskです。Reportの文章品質・事実性は評価しません。

HermesとClaude Code CLIにはexperimentalなadapterがあります。Profileごとの対応機能と未検証範囲は[Runtime support](docs/runtime-support.md)にまとめています。

現在のcheckoutはBeta準備中の未公開変更を含みます。公開wheelを使う場合は、そのtagの文書を参照してください。配布版、release notes、assetsは[GitHub Releases](https://github.com/Sanka1610/yohaku/releases)で確認できます。

## 導入と文書

Python `>=3.11`が必要です。Operational CLIはLinuxのlocal POSIX filesystem、privateなconfigとstate directoryを使います。[Getting Started](docs/getting-started.md)にwheel導入と二つの実行例をまとめています。

[Documentation Index](docs/index.md)から、操作、保存と復旧、設計、adapter開発の文書へ進めます。Supportの段階と更新・配布方針は[Support Policy](SUPPORT_POLICY.md)を参照してください。

Runtime全体のatomic freeze、外部writerの排除、一般的なexactly-once、任意taskのrestart recoveryは保証しません。`AMBIGUOUS`や`RECOVERY_REQUIRED`では状態を保持して確認してください。[問題の報告方法](docs/issue-reporting.md)も参照できます。

Licenseは[Apache License 2.0](LICENSE)（SPDX: `Apache-2.0`）です。
