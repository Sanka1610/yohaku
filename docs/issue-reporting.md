# Troubleshooting and issue reporting

Candidate Aの不具合は、公開可能なmetadataだけで報告してください。Alpha候補の範囲は
[scope declaration](release/candidate-a-scope.json)に固定しています。Hermes / Claude Code CLIの
experimental / measured Evidenceを、この受付文書によってAlpha supportへ変更するものではありません。

## 実行結果が不明な場合

`AMBIGUOUS`、`RECOVERY_REQUIRED`、write uncertainty、unexpected duplicate、owner / state
inconsistencyでは、通常作業とblind retryを止め、既存stateとEvidenceをprivateに保持してください。
Issue作成や追加log採取のために`run`を再実行しないでください。Upgrade、rollback、fresh stateへの
切替も、同じtaskの不確実な副作用を解消する手段にはなりません。

既に記録されているsanitized error code / operational stateを確認します。元のconfigを読める
reviewed packageでの`recover --inspect`は、[Operations](operations.md)に従う検査であり、taskの
resumeや再実行ではありません。出力全文にはprivate情報が含まれ得るため、そのまま投稿しないでください。
不明な値は`UNKNOWN`と記載すれば足ります。

## 投稿してよい情報

Correlationにはpublic-safe release ID、Support Profile ID、sanitized error code、artifact digestを
使います。Bug report / Safety reportともに、次のmetadataだけを手入力してください。

- Yohaku release identifierとpackage version。未公開buildは`UNRELEASED`、不明値は`UNKNOWN`
- Support Profile ID、Runtime exact version / surface、OS、Python version
- Operation名とsanitized error code / operational state
- Side effect / writeが発生した可能性、発生時点でfresh stateかexisting stateか
- Expected / actual behaviorの短い説明。Taskや文書の内容は含めない
- Public release assetのbasenameまたはwheel SHA-256

Credential、token / API key、`auth.json`、config全文、raw transcript、conversation本文、session ID、
receipt nonce、raw tool argument / result、Runtime DB、Yohaku state directory archive、private
repository path、private document本文、report本文、maintainer / user固有absolute pathは投稿禁止です。
Raw exception、raw status、添付archive、画面写真も求めません。安全に要約できない情報は省きます。

Formのcheckboxやrequired fieldは入力の確認を促すものであり、本文からsecretを自動除去する機能では
ありません。投稿前にtitleを含む全内容を確認してください。

## Formの選択と受付状態

- **Bug report**: 通常の不具合を報告するform。
- **Safety / recovery report**: `AMBIGUOUS`、`RECOVERY_REQUIRED`、write uncertainty、unexpected
  duplicate、公開可能なcredential / privacy concern、owner / state inconsistencyを区分して報告するform。

Blank issueはchooserで無効にします。これはGitHub上のすべての投稿経路を遮断するsecurity boundary
ではありません。GitHubはWrite以上の権限を持つmaintainerへblank issueを表示します。
[GitHubの設定仕様](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)を参照してください。

2026-09-30の公開閲覧では、[Issue一覧](https://github.com/Sanka1610/yohaku/issues)に
`Issue creation is restricted in this repository`と表示されました。受付状態は
`REPOSITORY_SETTING_REQUIRED`です。Repository内にformを置いただけではpublicから作成可能に
なりません。Maintainerは受付制限、default branchへの反映、formの表示、contact linkの到達性を確認し、
release recordへ結果を記録してください。受付が有効になるまでは公開Issueを作成できるとは案内しません。

<a id="security-reporting"></a>
## Security reporting boundary

重大security vulnerability、攻撃手順、credential、secretを通常Issueへ投稿しないでください。
Safety / recovery formは公開可能な症状の報告用であり、非公開の脆弱性受付ではありません。

2026-09-30時点では、local repositoryに既存security policyがなく、公開
[Security policy](https://github.com/Sanka1610/yohaku/security/policy)にもpolicy未設定と表示されました。
[Security advisories](https://github.com/Sanka1610/yohaku/security/advisories)の公開画面からも、利用可能な
private reporting窓口を確認できていません。非公開窓口の有効化状態は`NOT_ASSESSED`です。

Repositoryが後にprivate vulnerability reportingを有効化し、GitHub上で非公開の報告先を確認できた
場合は、その窓口を使ってください。確認済みの窓口がない場合は詳細を公開せずprivateに保持してください。
未確認のemailや連絡先へ送信する必要はありません。Maintainerはrelease前に安全な受付方法を決め、
案内とchooserのcontact linkを整合させてください。

## Maintainerのtriage

まずrelease / profile / artifactと症状の区分を確認し、公開可能なmetadataだけで不足情報を整理します。
Uncertain write、duplicate、privacy漏えい、owner / state不整合はrelease blocker候補としてreviewし、
未解決状態を成功へ読み替えません。報告者へraw stateや再実行を一律に要求しないでください。
Public metadataだけでは判断できない場合は`NOT_ASSESSED`を維持し、安全な追加確認方法を別に定めます。

操作上の判断は[Operations](operations.md)、stateとauthorityは[Storage and Recovery](storage-and-recovery.md)、
packageの更新は[Update and Rollback](update-and-rollback.md)を参照してください。
