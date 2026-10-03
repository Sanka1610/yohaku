# Runtime support

このページをcurrent checkoutのBeta support statusの正本とします。Supportedは明記した検証経路に限ります。DSH / OpenCodeの`Supported — qualified profile`は、実測・acceptedされた条件内でVerified Context Transitionを提供するという意味です。Supportの定義とprofile maturityの違いは[Support Policy](../SUPPORT_POLICY.md#beta-supportの表記)に記載します。

## Beta support status

| Target | Beta status | Qualification |
|---|---|---|
| [Codex](runtimes/codex.md) | Supported | 既存のcurrent lifecycle-only / fixed document-review経路。下記CLI profileの範囲に限定 |
| [Hermes](runtimes/hermes.md) | Supported | 既存のlifecycle-only / single fixture tool経路。下記CLI profileの範囲に限定 |
| [DSH](runtimes/dsh.md#tested-profile) | Supported — qualified profile | `0.2.0-rc.2` / headless / official DeepSeek Messages / plain text。Exact条件はRuntime pageに記載 |
| [OpenCode](runtimes/opencode.md#tested-profile) | Supported — qualified profile | `2.0.21` / Linux / known terminal `http.request` hook graph / native deny-all tools。Exact条件はRuntime pageに記載 |
| Orca structured Codex | Production adapter prototype — transition-only | 限定profileでSupervisorから一回のcompactと`ROLLOVER_OBSERVED`を確認。Recoveryはunsupported。下記と[Orca](runtimes/orca.md)に限定 |
| [Context Assist Stage 1](storage-and-recovery.md#context-assist-stage-1) | Supported | Current baselineへ統合済み。Deterministic / model-freeのhandoff表示補助 |
| Context Assist Stage 2 | Deferred | Beta非搭載 |
| Context Assist Stage 3 | Deferred | Post-Beta |
| [Claude Code CLI](runtimes/claude-code-cli.md) | Experimental | Subscription completionとlocal fixture recoveryを分けて扱う。下記profileの範囲に限定 |

DSH / OpenCodeのadapterはembedding hostから利用し、CLI registryには登録していません。両Runtimeのqualified profileはnative transition、receipt、fresh reconciliation、late-bound continuation、Runtime固有の最終検証と既存`ResumeVerification`を経て`RESUME_VERIFIED`まで確認しています。Receipt成功だけではresume成功としません。

## CLI profiles

CLI registryにあるprofileは`yohaku profiles`でも確認できます。表のRegistry statusは既存のprofile maturityであり、上記Beta support statusや配布版のrelease段階とは別です。

| Profile | Registry status | 試した環境・workflow | 対応機能と制限 |
|---|---|---|---|
| `codex-operational-0.158` | alpha | Codex `0.158.0-alpha.2.1`、WSL2 Linux / CPython `3.14.4`。Start / status / stop / fresh lifecycle | Lifecycle supported。Inference、task、transitionはunsupported |
| `codex-document-review-report-v1` | alpha | 同じCodex / OS / Python。公開文書2点、manual compact一回、create-only report一つ。`RESUME_VERIFIED` | 固定task supported。文章品質untested。Restart、反復transition、一般文書・coding taskはunsupported |
| `codex-reference-0.155` | experimental | Codex `0.155.0-alpha.16.4`、WSL2 Ubuntu / CPython `3.14.4`。Historical manual scenariosとnative-auto一回 | Historicalな限定結果。Current launcherはunsupported。Native-auto restartもunsupported |
| `hermes-operational-h-cli-01` | experimental | Hermes `0.21.0`、WSL2 / Python `3.11.16`。Native CLI / DB / store起動・停止 | Lifecycle supported。Inference、task、compressionはunsupported |
| `hermes-h-cli-01` | experimental | 同じHermes。Single fixture tool、manual compression一回、receipt、fresh continuationで`RESUME_VERIFIED` | 限定adapter workflowを検証。General task、restartはunsupported。Installed wheelでの新しいlive検証はuntested |
| `claude-c-cli` | experimental | Claude CLI `2.1.280`、Linux、print / stream-json / command Hooks。Subscription manual completionは`ROLLOVER_OBSERVED`まで確認 | Completionを検証。Subscription recoveryはuntested。Formal operational launcherはunsupported |
| `claude-c-cli-local-nonce` | experimental | 同じClaude CLI、Ollama `0.34.1` / `qwen3.5:9b`。Nonce receiptとfixture recovery一回で`RESUME_VERIFIED` | Local限定結果。Repeatabilityはuntested。Subscription supportへ適用しない |

Hermesのsource pinとRuntime固有completion条件は[Hermes](runtimes/hermes.md)、Claudeのfull-identity recoveryでの成功・失敗は[Claude Code CLI](runtimes/claude-code-cli.md)に記載します。現在packaged real Task ProfileがあるのはCodexの[document-review-report-v1](task-profiles/document-review-report-v1.md)だけです。

## Hard requirementとtested configuration

PackageはPython `>=3.11`、Operational CLIはLinuxの`/proc`、POSIX ownership / permissions、`flock`、Unix socket、atomic filesystem publish、file / directory `fsync`を必要とします。WSL2とPython patch versionはtested configurationであり、一致しないだけではpreflightを拒否しません。他LinuxやPython versionでのlive workflowはuntestedです。

Codexのexact versionとHermesのsource pin / clean tree / host venvは、内部APIと観測条件のbindingを保つため現時点ではhard requirementです。理由と制限は各Runtime文書に示します。

## 共通のKnown Limitations

Runtime-wide atomic freeze、外部writerの排除、general exactly-onceは成立していません。Local owner lockは協調するlauncherだけを排他します。Parallel、background、detached、subagent、反復transition、power-loss recoveryは一般的な対応範囲に含みません。

Runtime-native historyはYohaku checkpointやarchiveとは別です。Receipt、fresh current-state reconciliation、task assessmentのどれかが欠ければresume成功にはなりません。Mechanical completionは文章・コード・事実品質を保証しません。

## Qualified profiles

Exact条件、対応範囲外の構成、安全停止の詳細は各Runtimeページに集約しています。

- [DSH](runtimes/dsh.md#tested-profile)は公式Messages / plain textの固定`FINALIZE` / `FINALIZED` taskです。保存済みacceptanceはloopback protocol fixtureとstock HTTP transportによるmechanical verificationです。[制限](runtimes/dsh.md#limitations)と[安全停止](runtimes/dsh.md#safety-behavior)を参照してください。
- [OpenCode](runtimes/opencode.md#tested-profile)はknown terminal hook graph / native deny-all toolsのbounded foreground text taskです。保存済みacceptanceは実OpenCodeとlocal controlled providerによるfresh Session一回です。[制限](runtimes/opencode.md#limitations)と[安全停止](runtimes/opencode.md#safety-behavior)を参照してください。

両経路とも外部APIや実modelの品質評価を含みません。

別versionや未実測環境はNot qualified / Not testedとして扱います。外部API、実modelの品質、installed-wheel live acceptanceなどの`NOT_RUN`を、非互換性やUnsupportedの実証へ読み替えません。

両Runtimeのtrusted adapterはRuntime固有のcompletion evidence、final fresh state、bounded task assessmentを照合・保存し、既存`ResumeVerification`を`Controller.verify_resume()`へ渡します。Coreのlate-binding対応以外にadapter固有のCore変更はありません。新Runtimeの実装は[Adapter Contract](development/adapter-contract.md)を入口とします。

## Orca production adapter prototype

Phase 5でtransitionを確認し、Phase 5-RではこのprofileのrecoveryをUNSUPPORTEDと判定しました。Package同梱のadapterは`orca/structured/codex/local`、Orca `1.4.218`、Windows-native、local、Windows-local workspace、`wslDistro=null`、Codex `0.159.0-alpha.12.1`に限ります。Orcaを唯一のtrigger、Codexをprovider-native evidence observerとしてSupervisorへ登録します。Fresh sessionで一回のstructured compact、native completion、fresh stateと既存Coreの`ROLLOVER_OBSERVED`を確認しました。

Recovery on Orca structured Codex: unsupported/unqualifiedです。Structured sendは保存後に自動dispatchされ、actual native turnを取得した後にHandoff deliveryやprovider effectを待たせる外部gateがありません。既存early-bound / late-boundの安全条件を維持するproduction seamは成立しません。Adapterはrecovery inputを送る前に停止します。`HANDOFF_RECEIVED`はNOT_REACHED、production continuationと`RESUME_VERIFIED`はNOT_RUNです。O3のbounded continuation PASSは、このproduction recoveryの実測結果として扱いません。Embedding hostのI/O契約と制限は[Orca](runtimes/orca.md)を参照してください。
