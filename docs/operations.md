# Operations

CLIの出力は常にJSONです。`profiles`、`configure`、`preflight`、`enable`、`start` / `run`、`status`、`stop`、`disable`を提供します。実行例は[Getting Started](getting-started.md)にまとめています。

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

Disableとuninstallはcheckpoint、handoff、journal、archiveを削除しません。Packageを削除する前もowner終了を確認してください。
