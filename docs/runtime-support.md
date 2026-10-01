# Runtime support summary

本書は、Codex、Hermes、Claude Code CLIについて、公開済みのfixed profile、Evidence、
accepted endpoint、Verdict、maturity、Known Limitationsを一覧できるsummaryである。最終横断
review日は2026-10-01。Candidate Aの2 Support Profileは`alpha`、Product release channelは
`Alpha`である。Publicationは`BLOCKED_EXTERNAL`。Hermes / Claude / Historical Referenceは
Alpha scope外で、maturityは`experimental`を維持する。

Runtime固有contractは[Codex](runtimes/codex.md)、[Hermes](runtimes/hermes.md)、
[Claude Code CLI](runtimes/claude-code-cli.md)を正本とする。Profile比較は
[Runtime Mapping](runtime-mapping.md)、EvidenceとVerdictの定義は
[Evidence Model](evidence-model.md)、maturityとrelease条件は
[Support Policy](../SUPPORT_POLICY.md)が所有する。本書はそれらを再定義せず、個別runのraw
recordやCoverageProfileを置き換えない。

## 識別子の読み方

Mapping key、Support Profile ID、Evidence Record IDは別の識別子である。Runtime version /
surface / OS、provider / backend / modelはprofile dimensionであり、どのIDの別名でもない。
一つのSupport Profileへ複数の成功・失敗Evidenceを関連付けられる。別IDが未割当の場合は
推定で新設しない。

## Current profile summary

| Mapping key | Support Profile ID | Evidence Record ID / provenance | Accepted endpointとVerdict | Maturity / 主な制限 |
|---|---|---|---|---|
| `C-REF-M` | `codex-reference-0.155` | `PHASE14`配下のmanual records | Scenarioごとのoriginal Verdict。Accepted recoveryは`RESUME_VERIFIED`、Phase 14 overall `PARTIAL` | experimental。Historical Codex `0.155`だけ |
| `C-REF-A` | `codex-reference-0.155` | `PHASE14` Scenario G | Same-turn `RESUME_VERIFIED`、Scenario G `PASS`。Phase 14 overall `PARTIAL` | experimental。Native-auto一回のemergency recoveryだけ |
| `C-OP` | `codex-operational-0.158` | `S5-OP-CODEX-0158` | Native lifecycle `PASS`。Task / transition `NOT_RUN` | alpha。No inference / lifecycle-only |
| `C-DRR` | `codex-document-review-report-v1` | `DRR-V1-CODEX-0158-LIVE-01` | Fixed workflow `PASS`、`RESUME_VERIFIED`。Overall product coverage `PARTIAL` | alpha。Task Profile `document-review-report-v1`だけ。Quality `NOT_ASSESSED` |
| `H-PROBE` | `H-CLI-01` internal Probe | Separate public Evidence Record ID未割当。Stage 2 retained record | Bounded Probe workflow `PASS`、explicit receipt `PARTIAL`、overall `PARTIAL` | experimental。Product adapterやlauncherではない |
| `H-ADAPTER` | Product registry `hermes-h-cli-01`。Historical retained label `H-CLI-01` | `H-CLI-01-STAGE4` | Fixed connected workflow `PASS`、Core `RESUME_VERIFIED`、overall `PARTIAL` | experimental。One fixture tool / one compression / one owner |
| `H-OP` | `hermes-operational-h-cli-01` | `S5-OP-HERMES` | Native lifecycle `PASS`。Task / tool / transition `NOT_RUN` | experimental。No inference / lifecycle-only |
| `CL-SUB-C` | Product registry `claude-c-cli`。Retained label `C-CLI/2.1.280/Linux/print-stream-json/command-hooks` | `C-CLI-COMPLETION`、external / live-runtime / synthetic | Manual completionから`ROLLOVER_OBSERVED`まで`PASS`、overall `PARTIAL` | experimental。Subscription recoveryは含まない |
| `CL-SUB-R` | Separate ID未割当。`claude-c-cli` recovery capability row | External qualifying recordなし | Recovery implementationあり、external subscription acceptance `NOT_RUN` | experimental。Local Ollama Evidenceを継承しない |
| `CL-LOCAL-FULL` | `C-CLI-OLLAMA-LOCAL/2.1.280/0.34.1/spark-x2.5-4b-uncensored/e1646156c204` | `C-CLI-OLLAMA-LOCAL-REPEAT-2026-09-29` | `RESUME_VERIFIED`成功一回、matching repeat `FAIL`、overall `PARTIAL` | experimental。Repeatability `FAIL` |
| `CL-LOCAL-NONCE` | `claude-c-cli-local-nonce` | `C-CLI-NONCE-QWEN35-9B` | `host-nonce-v1` bounded workflow `PASS`、overall `PARTIAL` | experimental。Single owner / single pending handoff。Repeatability `NOT_ASSESSED` |

`PASS`は表に記載したbounded requirementだけに適用する。Lifecycle PASS、completion PASS、
recovery PASS、Task Profile PASS、overall CoverageProfile、maturity、release channelは別のclaim
である。

## Operational / adapter / task support

| 種類 | Codex | Hermes | Claude Code CLI |
|---|---|---|---|
| Lifecycle-only operational support | `C-OP`あり。App Server startup / status / stop / fresh lifecycle | `H-OP`あり。Native CLI / DB / store startup / status / stop / fresh lifecycle | Formal launcherなし。Adapterやmaintainer runnerをoperational supportへ読み替えない |
| Transition adapter implementation | Historical Reference、`C-DRR` | `H-ADAPTER` | Completion adapterとopt-in recovery adapter |
| Live accepted transition | Historical fixed scenarios、`C-DRR` | Fixed Stage 4 synthetic adapter workflow | Subscriptionはcompletionまで。Local recoveryはfixed Ollama profileだけ |
| Packaged real Task Profile | `document-review-report-v1`だけ | なし。H-CLI-01 assessorはfixture固有 | なし。Local assessorはfixture固有 |
| Runtime family全体 | Support claimなし | Support claimなし | Support claimなし |

## Completion、receipt、archive

Exact completion predicate、receipt、storage / archiveの横断比較は
[Runtime Mapping](runtime-mapping.md#completion-proofとrecovery段階)を参照し、Runtime固有factは
各Runtime canonicalを正本とする。Accepted Yohaku archive collector / retrievalがあるのは
historical Codex Referenceだけであり、Runtime-native historyをYohaku archiveへ読み替えない。

## Historical provenance

Codex Phase 1–14 freezeのintegrated baselineは
`7c4a2dda3ca2aed363ca8401ccad9ab5a489c16f`である。Phase 14 A–F/H/Iは
`c490f9172dcb7928810d8c2ff5e3ac217f7f7de0`とのsource associationを保持し、Scenario Gは
freeze baselineへ結び付く。Recorded 98 testsはlocal / synthetic regression Evidenceであり、
98 live scenariosではない。新しいdocumentation commitはhistorical scenarioのrerunではない。

Hermes Stage 2はHermes `0.21.0`、source
`c5594ec4b34097cafbe24deb6dfd9ac4b21d411d`、Ubuntu-Hermes / Python `3.11.16`、
`openai-codex` / `gpt-5.6-luna` / reasoning lowに固定した。八provider requestsとmanual
compression一回を測定した。Stage 4は同じpinで九requests（`4 / 1 / 4`）とmanual
compression一回を実行し、別EvidenceでCore `RESUME_VERIFIED`へ到達した。Stage 2のProbe
VerdictをStage 4へコピーしたものではない。

## Target runtime status

Hermes / Claude Code CLIのexact profile、identity、storage、completion、receipt、failure
contractは各Runtime canonical pageを参照する。DeepSeek HarnessとOpenCodeはNext Target、
Gemini CLIとAntigravityはFuture、Claude Desktop / CoworkはResearch / Auxiliaryである。
これらのpriorityは実装、maturity、Verdictを意味しない。

Claude subscription completionのreturned external recordは、original bundle source hashと
unchanged completion policyに対してreview済みである。Manual requestから
`ROLLOVER_OBSERVED`まで`PASS`、overall `PARTIAL`。Older Probeの`TIME_LIMIT`は別recordとして
保持する。Sanitized submissionはcorrelation reviewを支えるが、tester private checkpoint /
leaseの独立readbackやexternal runのauthenticityを証明しない。Subscription recoveryは
`NOT_RUN`のままである。

Hermes Stage 2はProbe、Stage 4はconnected adapter、`H-OP`はlifecycle-only launcherである。
三つを一つのHermes supportへ統合しない。Stage 4 receiptはHermes built-in acknowledgement
ではなくadapter-defined protocolである。General tool、Hook-fault enforcement、race、restart、
late completion、repeated compression、visible-turn archiveはacceptedではない。

Claude Code CLIの個別model / backend比較は
[Claude Code CLI Runtime](runtimes/claude-code-cli.md#model-comparisonの扱い)を正本とする。

## Installation compatibility

Package minimumはPython `>=3.11`で、同じnormal wheelをCPython `3.11.16`と`3.14.4`へ
non-editable installできる。これはtransition acceptanceとは別のinstallation Evidenceである。

| Check | Evidence |
|---|---|
| Clean wheel install | CPython `3.11.16` / `3.14.4`で`PASS`、`pip check` `PASS` |
| Python floor regression | CPython `3.11.16`で124 local tests `PASS` |
| Existing interpreter regression | CPython `3.14.4`でselected 40 tests `PASS` |
| Saved-format compatibility | 16 snapshots / 17 durable filesがretained baselineとbyte-equal |
| Hermes actual venv | Same wheel install、existing dependency versions unchanged、`pip check` `PASS` |
| Installed Hermes rehearsal | Native offline preflightとsynthetic-response H-CLI-01 rehearsal `PASS`、provider request 0 |
| Installed wheelの新しいlive acceptance | `NOT_RUN`。Historical Stage 4 scopeを維持 |

## Operational lifecycle foundation

以下のlifecycle Evidenceとmaturity / release判断は別である。2026-10-01のStage 5 reviewに基づき、
Candidate Aだけを`alpha`、Product release channelを`Alpha`へ昇格した。公開は未完了である。

Codex `0.158.0-alpha.2.1`とpinned Hermes `0.21.0`には、no-inference lifecycle profileが
ある。Native start / status / stop / clean stop後のfresh lifecycleはlab-testedである。
Codex `0.155` Reference Evidenceを`C-OP`へ、H-CLI-01 adapter Evidenceを`H-OP`へ適用しない。
Claude Code CLIには同等のformal operational launcherがない。

Codex `document-review-report-v1`は、public document二点、manual compact一回、create-only
Markdown report一点のfixed workflowで`RESUME_VERIFIED`へ到達した。Final accepted runの前に、
task dynamic toolをHookが拒否してtransition前に`REFUSED`となったrunを保持する。修正後の
accepted runと、existing outputを`STALE_OUTPUT_PRESENT`で拒否したrepeat checkも別結果として
保持する。Mechanical completionは`PASS`だが、writing / factual qualityは`NOT_ASSESSED`である。

このEvidenceはlifecycle-only Codex profile、historical Codex `0.155`、別Runtime、別Task
Profileへ適用しない。External-writer exclusion、restart、repeated transition、arbitrary
document task、coding taskも対象外である。Input / output、Observer、Assessor、no-retryの
詳細は[fixed Task Profile contract](task-profiles/document-review-report-v1.md)を正本とする。

## Known Limitations

- Candidate Aだけalpha / Product channel Alpha。PublicationはBLOCKED_EXTERNAL、他profileはexperimental
- Runtime family全体のsupportとStrong Transition Assuranceは未成立
- Hook fault時のRuntime-wide fail-closedとatomic work freezeは未受入
- Parallel、background、detached、subagent、external writerの一般coverageはない
- Hermes / Claude transition restartは`UNSUPPORTED`。Power lossは`NOT_RUN`
- General repeated transition、manual / native race、late-event recoveryは未受入
- Packaged real Task ProfileはCodex `document-review-report-v1`だけ
- Hermes / Claude fixture assessorからgeneral Task Profile supportを推定しない
- Field Evidenceは成立していない
- Runtime version、surface、OS、provider、backend、model、receipt protocol、Task Profileを
  越えてEvidenceとVerdictを継承しない

Raw records、CoverageProfile、RESULT、manifest、hash、source associationはprivate development
workspaceに保持し、このsummary作成によって移動・改名・再採点していない。

## Candidate A release review fields

次の表はCandidate Aに限定したrelease review用の検証対象である。Alpha候補の範囲を示し、
現在のmaturity / channelや個別EvidenceのVerdictを昇格させない。Fieldの意味、除外コード、
検証手順は[Candidate A review](release/candidate-a.md)を参照する。

<!-- candidate-a:start -->
| field | C-OP | C-DRR |
|---|---|---|
| mapping_key | C-OP | C-DRR |
| support_profile_id | codex-operational-0.158 | codex-document-review-report-v1 |
| runtime_family | codex | codex |
| runtime_exact_version | 0.158.0-alpha.2.1 | 0.158.0-alpha.2.1 |
| surface | dedicated App Server / stdio | dedicated App Server / dynamic task tools / manual compact |
| task_profile_id | none | document-review-report-v1 |
| operational_launcher_support | true | true |
| task_runner_support | false | true |
| maturity | alpha | alpha |
| release_channel | Alpha | Alpha |
| accepted_endpoint | native-start-status-stop-fresh-lifecycle | RESUME_VERIFIED |
| evidence_record_id | S5-OP-CODEX-0158 | DRR-V1-CODEX-0158-LIVE-01 |
| known_exclusions | no-runtime-family-support, no-field-evidence, no-other-runtime-os-provider, no-general-parallel-background-external-work, no-strong-transition-assurance, no-inference-or-task-transition, no-reference-evidence-inheritance | no-runtime-family-support, no-field-evidence, no-other-runtime-os-provider, no-general-parallel-background-external-work, no-strong-transition-assurance, one-fresh-session-one-manual-compact-one-report, no-restart-or-repeated-transition, quality-not-assessed, no-general-document-coding-shell-mcp, external-writers-not-prevented |
<!-- candidate-a:end -->
