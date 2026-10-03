# Yohaku — Proactive Context Compaction Manager

Yohakuは、長時間続くAI agent taskでcontext transitionを管理するPython packageです。切替前の安全確認とcheckpoint保存、Runtime固有の完了確認、切替後の状態照合と再開検証を扱います。この仕組みを **Verified Context Transition** と呼びます。

実行されたか判断できない場合は`AMBIGUOUS`として停止し、副作用を照合するまで再実行を抑止します。RuntimeのACKやagentの成功宣言だけでは、transition完了やtask再開を認めません。

## 利用できる範囲

BetaのSupported対象はCodexとHermesの既存検証経路、およびDSHとOpenCodeのqualified profileです。Supportedは明記した条件とworkflowに限ります。Orca structured CodexはProduction adapter prototype — partialで、限定profileのtransitionを確認し、recovery入口で停止します。Exact version、profile、対応機能と未検証範囲は[Runtime support](docs/runtime-support.md)を参照してください。

公開CLIの固定taskは`codex-document-review-report-v1`で、manual compact一回とcreate-only report一つを扱います。文章品質・事実性は評価しません。DSHとOpenCodeはembedding hostから利用します。Claude Code CLIはexperimentalです。

Context Assist Stage 1はdeterministic / model-freeでSupportedです。Stage 2 / 3はDeferredです。[表示内容と制限](docs/storage-and-recovery.md#context-assist-stage-1)を参照してください。

現在のcheckoutはBeta準備中の未公開変更を含みます。公開wheelを使う場合は、そのtagの文書を参照してください。配布版、release notes、assetsは[GitHub Releases](https://github.com/Sanka1610/yohaku/releases)で確認できます。

## 導入と文書

Python `>=3.11`が必要です。Operational CLIはLinuxのlocal POSIX filesystem、privateなconfigとstate directoryを使います。[Getting Started](docs/getting-started.md)にwheel導入と二つの実行例をまとめています。

[Documentation Index](docs/index.md)から、操作、保存と復旧、設計、adapter開発の文書へ進めます。Supportの段階と更新・配布方針は[Support Policy](SUPPORT_POLICY.md)を参照してください。

`yohaku doctor`でlocal Runtimeの検出とprofileの対応条件を確認できます。読み取り専用の診断で、live sessionのqualificationは実行時に確認します。[Operations](docs/operations.md#doctor)を参照してください。

Runtime全体のatomic freeze、外部writerの排除、一般的なexactly-once、任意taskのrestart recoveryは保証しません。`AMBIGUOUS`や`RECOVERY_REQUIRED`では状態を保持して確認してください。[問題の報告方法](docs/issue-reporting.md)も参照できます。

Licenseは[Apache License 2.0](LICENSE)（SPDX: `Apache-2.0`）です。
