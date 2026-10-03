# Operations

`doctor`は人が読むためのテキストを出力します。既存の`profiles`、`configure`、`preflight`、`enable`、`start` / `run`、`status`、`stop`、`disable`はJSON出力です。実行例は[Getting Started](getting-started.md)にまとめています。

## Doctor

`yohaku doctor`はinstalled Yohaku、Python、PATH上のRuntime、既存profileの対応条件をlocalで確認します。既存のOperational configを調べる場合は`yohaku doctor --config <absolute-path>`を使います。Configとbindingを読み、設定したRuntime pathを優先します。State path、credential value、config本文は表示しません。

CodexとDSHのversion queryには3秒のtimeoutを設けています。OpenCodeはCLI初期化の副作用を避けるため、実行ファイルに対応する`@opencode/cli`のpackage metadataだけを読みます。Hermesはconfig指定時のsource pinを確認し、OrcaはPATH上の検出に留めます。確認できないversionは`unknown`、確認を実施しない項目は`not checked`、実行ファイル等が見つからない場合は`not detected`です。

Versionやsource pinの一致だけではlive qualificationを認めません。DSHのofficial Messages adapter / single ownerやOpenCodeのterminal hook graph / deny-all toolsなどは実行時の確認が必要です。対応条件外の構成とRuntime全体のsupport statusを区別し、Orcaのproduction integrationは未実装と表示します。Exact条件は[Runtime support](runtime-support.md)を参照してください。

Doctorはconfig、provider files、stateを変更せず、Runtime session、hookの導入、repair、network accessを実行しません。Mismatchや未確認項目を検出しても、診断完了ならexit codeは`0`、doctor自体の失敗は既存CLIと同じ`2`です。

## Configと実行

`configure`はprivate configと新規state rootを作成します。既存pathを採用せず、stateとworkspaceを同一または親子関係にしません。新規configは必ずdedicated session / single owner条件を持ちます。Owner lock、fresh thread、task workspace lockが実行条件を検査しますが、external writerまで排除するものではありません。

```text
configure → preflight → enable → startまたはrun
```

Schema-1の`enabled`は維持しています。`enable` / `disable`は次回実行の可否だけを変え、taskを実行しません。Owner lockの下で変更し、live ownerや未照合の終了状態との競合を拒否します。`disable`はstopの代わりにはなりません。

`preflight`はconfig binding、Runtime compatibility、private paths、前回ownerの状態、task contractを検査します。`PASS`は起動・transitionの実測結果ではありません。

| Command | 動作 |
|---|---|
| `start --config <absolute-path>` | Lifecycle-only profileをforegroundで起動。Task turnとinferenceは拒否 |
| `run --config <absolute-path>` | Codexの固定document-review taskを一回実行。Inferenceを行い、credentialを使う |
| `status --config <absolute-path>` | 保存済み状態と、応答するlifecycle ownerを照合。Retryやresumeは送らない |
| `stop --config <absolute-path>` | Lifecycle ownerへgraceful stopを要求し、clean stopを確認 |

`stop`はtask `run`の制御commandではありません。Taskの中断や結果不明時は状態を保持して確認します。

## Statusの読み方

`task_profile_registered`はtask integrationの登録、`transition_ready`は現在のconfigとpreflight条件による開始可否です。既存の`transition_available`はCodex launcherでは`transition_ready`と同じ値を返します。診断用lifecycle profileではどちらもfalseです。

`owner_lock_busy`がtrueでも、socketから応答が得られなければ`OWNER_UNREACHABLE`です。PIDやsocketの存在だけで生存・正常終了を推定しません。Lockが解放されていても前回recordが`STOPPED`でなければ`RECOVERY_REQUIRED`です。

`recovery.fresh_start_allowed`は新しいsessionの開始可否であり、保存taskのresume許可ではありません。現在のCLIは`resume_supported=false`です。Document-reviewは完了後もfresh startを拒否し、同じtaskをrerunしません。

## 停止・復旧

Stop timeoutでは`STOP_INCOMPLETE`としてowner lock、socket、hostを保持します。Clean stopを証明するまで次のstartやdisableへ進めません。強制killをclean stopとして扱いません。

`AMBIGUOUS`、`RECOVERY_REQUIRED`、write uncertaintyでは`status`で確認し、config、workspace、state、Runtime-native storageを保持します。新しいstateへの切替、output削除、更新・rollbackによって同じtaskをblind rerunしないでください。復旧の契約は[Storage and Recovery](storage-and-recovery.md)を参照します。

主要な停止理由には、何が起きたか、Yohakuが止めた操作、次に確認する内容を補っています。CLIでは既存error / reasonに`guidance`を添え、embedding adapterの送信・完了が不確かな例外には説明を付けます。送信済み・完了済みの可能性がある場合も、自動retryは行わず、消費済みclaimを復元しません。Version / profile mismatchにはdoctorを使えますが、staleなcontinuation evidenceやlive sessionの状態はRuntimeと保存recordで照合してください。

Disableとuninstallはcheckpoint、handoff、journal、archiveを削除しません。Packageを削除する前もowner終了を確認してください。
