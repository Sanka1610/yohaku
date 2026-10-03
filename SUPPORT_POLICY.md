# Yohaku Support Policy

SupportはRuntime名だけでなく、profileごとに示します。各profileには`status`、試した環境とworkflow、`supported` / `unsupported` / `untested`な機能、Known Limitationsを記載します。現在の一覧は[Runtime support](docs/runtime-support.md)を参照してください。

`untested`は非互換という意味ではありません。動作に必要なhard requirementと、試したtested configurationを区別します。Runtime APIへの依存からversionやsourceを固定する場合は、Runtime文書に理由を記載します。別環境への結果の適用は、変更がcompletion、identity、storage、task observationへ与える影響で判断します。

## Beta supportの表記

現在のBeta対応範囲の正本は[Runtime support](docs/runtime-support.md)です。`Supported`は明記した既存検証経路、`Supported — qualified profile`はexact version、構成、owner条件、task範囲を固定した経路でVerified Context Transitionを提供することを意味します。DSHとOpenCodeのqualified profileは、保存済みbounded acceptanceで`RESUME_VERIFIED`まで確認しています。実modelの品質、一般task、別構成への対応を含みません。

`Unsupported`は対応範囲外、`Not qualified`は昇格条件を満たしていない構成、`Not tested` / `NOT_RUN`は未実測です。未実測だけを理由に`Unsupported`へ変換しません。`Probe validated`は調査でprimitiveを確認した段階で、production supportを意味しません。`Deferred`は今回のBetaに搭載しない予定の機能です。

このsupport表記と、下記のprofile maturity、CLI registryの`status`、配布版のrelease段階は別です。既存Codex / Hermes profileのregistryにある`alpha` / `experimental`は保持し、Betaの対応範囲はRuntime supportで示します。Qualified profileの昇格だけでpackage全体のBeta配布条件を満たしたとは扱いません。

## Profile status

| Status | 意味 |
|---|---|
| experimental | 限定実装または調査段階。Interfaceや手順が変わり得る |
| alpha | 明記した範囲で導入と主要workflowを試せる。破壊的変更は告知する |
| beta | 主対象と制限が固定され、maintainerの実taskと必要な回帰確認がある |
| stable | 宣言したprofileで継続利用、障害対応、更新互換性を支えられる |

一回の成功でprofile全体を昇格させません。重大な回帰やRuntime APIの変更が判明した場合は、対象profileの推奨を停止し、必要ならstatusを下げます。成功だけで既知の失敗を隠さず、未検証範囲を公開します。

## Betaへの条件

主対象profileを固定し、以下を確認します。

- Maintainerによるreal taskと正常なtransition path。
- 主要なstale、duplicate、ambiguous outcomeの拒否とno blind retry。
- 変更範囲に必要な回帰確認。
- Update / compatibility方針と公開されたKnown Limitations。
- 宣言範囲に既知のrelease blockerがないこと。

外部testerやcommunityの記録は任意の追加資料です。Betaのmaturity gateにはしません。全Runtime・全OSの検証や絶対的な動作保証は要求しません。秘密露出、データ破損、無断・重複実行、曖昧な完了の成功扱いはrelease blockerです。

## 更新と互換性

AlphaからBetaではCLIや公開interfaceのbreaking cleanupを行えます。変更した操作と対応versionをrelease notesで知らせます。永続schemaや既存stateは暗黙に変換せず、形式変更が必要になった時点で影響と移行方法をreviewします。

更新前にownerのclean stopを確認します。中断・曖昧なtaskでは旧environment、workspace、stateを保持し、更新やrollbackを再実行の許可として扱いません。Packageを戻してもold leaseやcontinuation authorityは復活しません。[Storage and Recovery](docs/storage-and-recovery.md)に従って照合します。

## 配布

Published state、tag target、timestamp、asset一覧とdigest、source archive metadata、pre-release / stable表示の正本は[GitHub Releases](https://github.com/Sanka1610/yohaku/releases)です。Profile statusは、配布版のpre-release表示とは別に扱います。

Prereleaseのprimary artifactは`yohaku-<version>-py3-none-any.whl`です。Source zip / tar.gzはGitHub生成archiveを使います。Custom SHA256SUMS、release manifest、per-file source hash inventory、sdist uploadは、具体的な用途が生じるまで追加しません。PyPIやsource installが必要になった場合はsdistを検討します。

既に公開した同名wheelは差し替えず、変更した配布物には新しいversionを使います。
