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

Stage 3時点のrelease blockerは`LICENSE_DECISION_REQUIRED`と`REPOSITORY_SETTING_REQUIRED`です。
Local checkoutには明確なLICENSE / COPYING /利用条件がなく、pyprojectにもlicense宣言がありません。
Templateは配布許諾を新設しません。Maintainerが利用条件を決定し、package metadata、配布物、release record、
READMEの説明が一致することをrelease前に確認してください。Public Issue受付の設定・確認も別途必要です。
