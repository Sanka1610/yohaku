# 問題の報告

[Bug / Problem form](https://github.com/Sanka1610/yohaku/issues/new?template=bug_report.yml)から、Yohaku version、Runtime / version、OS、観測した症状、expected behavior、公開可能なerror codeやstateを報告してください。安全に共有できる場合だけ再現手順を添えてください。

`AMBIGUOUS`、`RECOVERY_REQUIRED`、write uncertaintyでは、報告のためにtaskを再実行しません。Workspace、state、Runtime-native storageを保持し、[Operations](operations.md)の`status`と[Storage and Recovery](storage-and-recovery.md)で照合します。更新・rollback・fresh stateへの切替もrerunの許可にはなりません。

## 公開しない情報

Credential、token、API key、`auth.json`、private transcript、入力文書・reportの本文、config全文、Runtime DB、state directory archiveを公開Issueへ貼らないでください。Raw JSONやlogにはsession ID、nonce、tool引数、個人のpathが含まれ得るため、必要なerror codeとstateだけをsanitizeして共有します。

<a id="security-reporting"></a>
## Security reporting

重大な脆弱性、secret、攻撃に使える詳細は通常の公開Issueへ投稿しません。確認済みのprivate reporting窓口がある場合にだけ非公開で共有し、窓口が未確認なら詳細を公開せず保持してください。
