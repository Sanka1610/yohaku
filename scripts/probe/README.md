# Phase 1 metadata runner

Python 3.14.x、標準ライブラリのみを使用する。検証環境はCodex CLI + WSL2 Ubuntu。収集するのはローカルの実行条件であり、Gate A/B/Cの能力実証ではない。

## 実行

リポジトリのrootで実行する。

```bash
python3 scripts/probe/run.py collect
python3 scripts/probe/run.py validate probe-results/<run-id>/result.json
```

`<run-id>`は`collect`が出力した値に置き換える。`validate`の成功は形式検証の成功を示し、記録内容の真実性やRuntime能力を証明しない。

`collect --codex /absolute/path/to/codex`で実行ファイル、`--output /absolute/path/to/results`で出力先を選べる。`--codex`には信頼できるCLI実行ファイルを指定する。任意の追加CLI引数、profile、設定上書きの転送は行わない。`CODEX_HOME`は親processから継承し、実際の値または既定値を記録する。

Codexへの呼出しは`--version`と`features list`。model session、Hook、MCP、compactは起動しない。各コマンドのtimeoutは10秒。不正な出力や失敗時のstderrは保存せず、理由codeを残す。

終了code:

| code | 意味 |
|---|---|
| 0 | 結果保存・再読込に成功し、必須observationに取得不能がない。または`validate`に成功 |
| 1 | 入力・形式・保存処理の失敗 |
| 2 | 結果は保存したが取得不能のobservationがある。またはCLI引数・Python versionが不適合。`SAVED`の有無で区別する |

設定の収集範囲は常に`PARTIAL`。終了code 0を、実効設定全体やGateのPASSとして扱わない。

形式検証でも、configの完全取得を主張する記録を拒否する。sourceを`OBSERVED`とするにはGit HEADとdirty判定の両方を必要とし、取得できない場合は`PARTIAL`または`UNAVAILABLE`として記録する。Git HEADは40桁または64桁のhexに限る。

## 保存とfixture

```text
probe-results/<run-id>/
├── result.json
└── fixture/
    └── marker.txt
```

run IDはUUIDから生成する。既存run IDの再利用は拒否する。JSONを一時名で書き、形式検証と再読込の一致を確認してから`result.json`へrenameする。途中失敗したrunは調査用に残り、`result.pending.json`を完成した結果として扱わない。

runディレクトリはPOSIX mode `0700`、結果ファイルは`0600`で作成する。これはPhase 1の結果保存であり、電源断耐性やPhase 8のcheckpoint commit保証は含まない。

`fixture/marker.txt`は合成の作業対象。Gate固有の設定やHookは含まない。通常利用のworkspace/sessionを実測対象にせず、後続フェーズで必要なfixtureを追加する。

既定の`probe-results/`配下はGit追跡から除外する。別の出力先を選ぶ場合は、その場所の追跡・共有範囲を確認する。結果にはローカルパスやplugin識別子が含まれる。

## 記録形式

schema version 1の実行可能な定義は[result.py](result.py)の`validate()`。未知のversion、余分なフィールド、不正な型、重複JSON key、非有限数、2 MiBを超える入力を拒否する。

| フィールド | 内容 |
|---|---|
| `schema_version` | `1` |
| `run_id` / `created_at` | UUIDの32桁hex、UTC時刻 |
| `kind` | 通常は`metadata-only`。検証用データは`synthetic` |
| `runtime` | 計測対象の名前`codex-cli-wsl`。実際のOS/WSL情報はenvironmentに記録 |
| `invocation` | runnerの実行引数。Codexの既存sessionの起動引数ではない |
| `observations` | environment、codex_version、features、config、source |
| `cases` | A01〜A08、B01〜B06、C01〜C06。すべて`NOT_RUN` |
| `limitations` | 収集範囲と保証の限界 |

observationは`status`、`value`、`reason`、`evidence`を持つ。statusは`OBSERVED / PARTIAL / UNAVAILABLE`。これは取得状態であり、Gateの判定語彙とは別に扱う。Evidenceには`claim / source / authority / scope / freshness / coverage`を保存する。`freshness`はその観測の時刻であり、実行revisionの鮮度保証ではない。

caseにはID、Gate、status、理由、証拠配列、`hook_failure_behavior`を持たせる。Phase 1では証拠配列は空、障害時挙動は`null`。`PASS / PARTIAL / FAIL / UNSUPPORTED`をcaseへ設定した入力は拒否する。後続実測の記録は、証拠と判定条件を定めたschemaへの明示的な更新が必要。

## metadataの取得範囲

- environment: Python、OS、kernel、CPU architecture、distribution、WSL判定、`SHELL`、cwd、`CODEX_HOME`。hostnameや全環境変数は保存しない。
- codex_version: 選択した実行ファイルのパスと`--version`の規定形式に一致する値。
- features: `features list`で報告されたflag、stage、enabled。現在のアプリsessionへの適用は未確認。
- config: system/user/作業rootと祖先の候補configファイルから、sandbox/approvalの既知の値、booleanのfeature、pluginのenabled宣言のみ。取得元ごとに保存し、実効値へmergeしない。
- source: Git HEAD、dirty状態、Probeコード・README・Python要件・ignore設定のSHA-256。

認証ファイル、Hook command、MCP接続情報、設定ファイル全文は収集しない。configは1 MiBまで。ファイル不在、不正形式、読込不能を区別して残す。profile、managed policy、pluginロード状態は未確認として扱う。複数の取得はatomic snapshotではない。

Codex設定には複数の適用層とproject trust条件があるため、ファイルの宣言だけで実効値を確定しない。[公式Config basics](https://learn.chatgpt.com/docs/config-file/config-basic)

## 後続ProbeのケースID

| Gate | ケース |
|---|---|
| A | A01 対照実行、A02 explicit deny、A03 開始登録race、A04 active workからDEFER、A05 timeout、A06 crash、A07 malformed output、A08 missing output |
| B | B01 有効lease、B02 expired、B03 stale boundary、B04 generation mismatch、B05 intent revision mismatch、B06 execution revision mismatch |
| C | C01 受付と完了、C02 復元先identity、C03 配送時点、C04 ACK correlation、C05 作業継続、C06 timeout/late completion |

実測前にRuntime/version、対象tool/Backend、隔離設定、合成入力、観測点、timeout、後片付け、provider呼出しの要否を固定する。自己申告や無エラーだけを完了証拠にしない。
