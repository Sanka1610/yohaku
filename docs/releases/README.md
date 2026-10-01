# Release records and notes

このdirectoryにはrelease準備用templateとCandidate A checklistを置きます。現時点で完成したrelease
recordやPublished Alphaを示すものではありません。Package version、release identifier、release channelは
別のfieldであり、現在の`0.1.0a1`だけからAlpha公開を推定しません。

- [Release record template](RELEASE_TEMPLATE.md): releaseごとのcanonicalなscope / artifact / verification / support判断
- [Release notes template](RELEASE_NOTES_TEMPLATE.md): 利用者向けの短い案内
- [Candidate A checklist](CANDIDATE_A_CHECKLIST.md): release reviewの確認順と未解決条件
- [Update and Rollback](../update-and-rollback.md): existing-stateと更新・切り戻しの公開方針
- [Issue reporting](../issue-reporting.md): 公開可能なmetadata、no-rerun、security reporting boundary

後続releaseではtemplateを同directory内の別fileへコピーし、releaseごとのrecordを作成します。
`TBD`、空欄、未解決blockerを残したまま承認しません。必要な確認の`NOT_RUN` / `NOT_ASSESSED`は成功として
数えず、`NOT_REQUIRED`には理由とreviewerを記録します。対象外の確認は適用しない理由を残します。

Scopeの正本は[Stage 2 declaration](../release/candidate-a-scope.json)です。Recordには参照元のcommitと
file hashを固定し、その内容を採用します。Profile / Runtime / endpoint一覧をnotesやchecklistへ別々に
手入力して維持しません。後続reviewでscopeまたはmaturity / channelを変更する場合は、declaration、
registry、canonical検証表、checkerの整合も同じ変更でreviewします。

Distribution licenseは[Apache License 2.0](../../LICENSE)（SPDX: `Apache-2.0`）です。
Package metadataはPEP 639の`project.license`と`project.license-files`で宣言しています。
Stage 3由来の`LICENSE_DECISION_REQUIRED`は、exact RC artifactのSPDX metadataとLICENSE fileの
一致を検証したrelease recordで解消します。`REPOSITORY_SETTING_REQUIRED`とpublic Issue受付の
実用性確認と公開工程は未完了です。Stage 5に基づくCandidate A alpha / Product Alphaへの昇格は
current declarationに記録し、公開済みとは表示しません。
