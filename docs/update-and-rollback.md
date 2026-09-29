# Candidate A update and rollback policy

本書は[Candidate A scope declaration](release/candidate-a-scope.json)が指定するprofileに限った
更新方針です。各releaseの適用元・適用先・artifact・互換性判断は[release record](releases/RELEASE_TEMPLATE.md)
で固定します。現在のpackage version `0.1.0`はPublished Alphaを意味せず、profile maturityは
experimental、release channelはundeclaredです。

## 更新前の判断

Package upgradeとstate migrationは別の操作です。Installに成功しても、old checkpoint / handoffが
current authorityになることや、旧taskを再開できることは証明されません。旧recordはhistorical dataとして
保持し、古いlease、continuation permit、instructionを新versionの実行権限へ変換しません。

Running ownerを残したままpackageを差し替えないでください。Clean stopとowner終了を確認できない場合、
またはtaskがinterrupted / ambiguous / recovery-requiredの場合は、更新を復旧手段にせず、元の
environmentとstateを保持して[Operations](operations.md)の検査・reviewへ進みます。

Completed C-DRRを新versionでrerunしないでください。Reportを消す、output名を変える、fresh stateへ
切り替えるといった操作も、同じtaskを再実行してよい根拠にはなりません。

## Upgrade

1. 対象release recordでexact source / wheel、digest、Runtime条件、利用条件、Known Limitationsを確認します。
2. 現在のownerがclean stop済みで、不確実な副作用が残っていないことを確認します。確認できなければ停止します。
3. 旧packageのexact artifactとdigest、既存config / state / outputをprivateに保持します。削除や上書きは不要です。
4. 対象wheelのSHA-256をreleaseの`SHA256SUMS`と照合し、reviewされた専用environmentへinstallします。
5. Existing-state compatibilityが未検証なら、新規作業用にfresh config / stateを使用します。旧stateをコピーして
   新規stateに見せかけたり、旧taskの不確実な結果を新規実行で置き換えたりしません。
6. `COMPATIBLE`と記録されている場合も、そのsource → target、schema / record、operationの範囲だけに適用します。
   C-DRRのno-rerun / no-restart制約を解除する判断とは分けます。

Install / stop / inspectionの具体的な操作は[Installation](installation.md)と[Operations](operations.md)、
Taskの再実行制約は[Task Profile](task-profiles/document-review-report-v1.md)が正本です。

## Rollback

Packageを旧versionへ戻してもstate compatibilityは自動保証されません。Newer schema / recordをolder
codeで暗黙に採用しないでください。Schema番号が同じであることやdecode成功だけでも十分ではありません。

Rollbackにはexact prior artifactが必要です。Release asset名、wheel SHA-256、当時のrelease record /
`SHA256SUMS`を照合します。Version名だけが同じ別buildや、digest不明のartifactへ戻さないでください。
Old environmentを残す場合も、同じstateを新旧ownerから並行して開きません。

`AMBIGUOUS`、`RECOVERY_REQUIRED`、write uncertaintyでrollback → rerunを行わないでください。
Downgrade方向のstorage compatibilityが`INCOMPATIBLE`または`NOT_ASSESSED`なら、そのstateをold codeへ
渡しません。旧stateとnewer recordを保持し、必要なreviewが終わるまで当該taskの通常作業を停止します。
Fresh environment / stateの利用は別の新規作業向けであり、既存taskの副作用照合を省略する方法ではありません。

## 初回Alphaとexisting experimental state

初回Alphaでは、pre-release experimental stateをautomatic upgrade targetに含めません。
新規Alpha作業にはfresh config / stateを推奨します。Retained Evidence、checkpoint、handoff、Runtime-native
data、task input / outputは原位置で保持し、更新のために勝手に削除・改名・再採番しません。

このbounded policyは現行実装と整合しています。Operational configureはexisting config / state rootを
拒否し、loadはschemaとconfig bindingを検査します。C-DRRは既存runがある場合のfresh startとresumeを
拒否し、create-only outputを要求します。保存契約はold leaseを再構成せず、schema / hash / identityの
不一致を拒否します。これらは安全な拒否条件であり、release間のstorage compatibility実測ではありません。

初回Alphaへのexisting experimental state compatibilityは、release固有の検証がない限り
`NOT_ASSESSED`と記録します。Historicalなsaved-format互換性Evidenceを、将来のreleaseへ自動継承しません。
契約の根拠は[Storage and Recovery](storage-and-recovery.md)と
[Operations](operations.md)を参照してください。

## Compatibility classification

次の分類はrelease record上のstate compatibility判断であり、Capability Verdictではありません。

| Classification | 意味 |
|---|---|
| `COMPATIBLE` | 記録したsource → target、schema / record、operationの範囲で検証済み。根拠の参照が必要 |
| `INCOMPATIBLE` | 記録した組合せで利用を認めない。理由と安全な取扱いを記載する |
| `NOT_ASSESSED` | 必要な検証・reviewが未成立。既存stateの採用を許可しない |

Release recordでは、Runtime compatibility、package installability、storage compatibility、Task Profile
rerun / restart policyを別行で評価します。Storageはupgrade方向とrollback方向も分けます。
InstallやRuntime lifecycleのPASSをstorage互換性やtask再実行許可へ読み替えません。
