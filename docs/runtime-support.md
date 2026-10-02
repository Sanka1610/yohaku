# Runtime support

以下は各profileで試した範囲です。CLI registryにあるprofileは`yohaku profiles`でも確認できます。DSH / OpenCodeのadapterはembedding hostから利用し、CLI registryには登録していません。両Runtimeの限定receiptは保存済みacceptanceで確認しています。

| Profile | Status | 試した環境・workflow | 対応機能と制限 |
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

OpenCodeには`2.0.21` / Linux / fresh owned Session限定の[adapter](runtimes/opencode.md)があります。Single owner / known terminal hook graph / later mutatorなし / native deny-all tools / one bounded foreground text task / retry disabledで、unbound receipt、fresh reconciliation、post-receipt claim、actual native inputのlate bind、binding保存後のrelease、bounded continuation一回を確認しました。R4-P-Iではfinal fresh stateとbounded assessmentをRuntime recordへ保存し、既存`ResumeVerification`から`Controller.verify_resume()`へ接続して`RESUME_VERIFIED`までPASSしました。実測はlocal controlled providerによるfresh Session一回で、実model inferenceや一般taskの品質は未評価です。Receiptのtool requestは実行前に拒否します。既存`ResumeProof`とCoreは変更していません。対応範囲とunsupported条件はRuntime pageを参照してください。

DSHには`0.2.0-rc.2` / headless / fresh Session限定の[adapter](runtimes/dsh.md)があります。R3のnative transitionとfresh post-stateを確認しました。R4は公式DeepSeek Messages adapter / plain text / single Agent・owner / additional extension fieldsなし / retry disabledで`HANDOFF_RECEIVED`まで確認しています。R4-P-Iのloopback fixtureではpost-receipt claim、actual native turnのlate binding、一回のtext continuation、独立final readback、固定taskの`FINALIZED`一回を確認しました。DSH固有recordから既存`ResumeVerification`を構成し、Coreの`verify_resume()`で`RESUME_VERIFIED`まで到達しています。これは限定text taskのmechanical acceptanceであり、外部APIや実modelの品質評価は含みません。対応範囲とunsupported条件はRuntime pageを参照してください。新Runtimeの実装は[Adapter Contract](development/adapter-contract.md)を入口とします。
