# Release notes — TEMPLATE

未記入template。Release別fileへコピーし、短い利用者向け案内にしてください。
公開前に`TBD`を置き換えます。Metadata・対応範囲・artifactは完成したrelease recordから参照し、
独立した別一覧として維持しません。Private情報や内部Evidence taxonomyの詳細は含めません。

Release identifier: TBD / Package version: TBD / Release channel: TBD

Canonical release record: TBD — 公開済みrecordへのlink

## What is included

TBD — Release recordが採用したCandidate Aの対象と、利用できる操作を短く説明。

## What is explicitly not included

TBD — Hermes / ClaudeのAlpha support、一般task / 全Runtime対応など、誤解されやすい除外を明示。

## Installation

TBD — Review済みartifactの取得先、対象environment、[Installation](../installation.md)への案内。
利用条件はrelease recordの確定したtermsを参照。

## Upgrade

TBD — Source → targetの条件とfresh stateの要否。[Update policy](../update-and-rollback.md)を参照。
Package更新をstate migrationや未完了taskの復旧として案内しない。

## Rollback

TBD — Exact prior artifact / digestとstorage互換性の条件。[Rollback policy](../update-and-rollback.md)を参照。
Ambiguous taskのrollback → rerunを案内しない。

## Known Limitations

TBD — Restart、power loss、external writer、parallel / background、content quality、Field Evidenceの制限。

## Breaking changes

TBD — 変更内容と利用者の対応。ない場合も確認根拠に基づき「なし」と記載。

## Artifact verification

TBD — Release recordのwheel filename / SHA-256 / `SHA256SUMS`へのlinkと照合方法。
Digest確認は信頼できる取得元の確認と併用。

## Reporting issues

TBD — 実際に利用可能と確認したIssue受付先。[Privacy / security案内](../issue-reporting.md)を参照。
Secret、本文、raw log / stateは投稿しない。`AMBIGUOUS` / `RECOVERY_REQUIRED` / write uncertaintyでは
報告のためにrunを再実行しない。
