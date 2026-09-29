# Runtime support summary

本書は、Codex、Hermes、Claude Code CLIについて、公開済みのfixed profile、Evidence、
accepted endpoint、Verdict、maturity、Known Limitationsを一覧できるsummaryである。最終横断
review日は2026-09-29。実装はexperimentalで、public release channelは宣言していない。

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
| `C-OP` | `codex-operational-0.158` | `S5-OP-CODEX-0158` | Native lifecycle `PASS`。Task / transition `NOT_RUN` | experimental。No inference / lifecycle-only |
| `C-DRR` | `codex-document-review-report-v1` | `DRR-V1-CODEX-0158-LIVE-01` | Fixed workflow `PASS`、`RESUME_VERIFIED`。Overall product coverage `PARTIAL` | experimental。Task Profile `document-review-report-v1`だけ。Quality `NOT_ASSESSED` |
| `H-PROBE` | `H-CLI-01` internal Probe | Separate public Evidence Record ID未割当。Stage 2 retained record | Bounded Probe workflow `PASS`、explicit receipt `PARTIAL`、overall `PARTIAL` | experimental。Product adapterやlauncherではない |
| `H-ADAPTER` | Product registry `hermes-h-cli-01`。Retained profile `H-CLI-01` | `H-CLI-01-STAGE4` | Fixed connected workflow `PASS`、Core `RESUME_VERIFIED`、overall `PARTIAL` | experimental。One fixture tool / one compression / one owner |
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

- Codex manual completionは、同じrequest / compact turnに対するcompaction item、
  `PostCompact`、compact turn completionの三要素を要求する。Native-autoは別contractで、
  compaction itemと`PostCompact`をcompletionに使い、active turn completionは後段で使う。
- Hermes completionは、host history mutationとindependent `SessionDB` readback、projection /
  hash / count一致、inactive old rowを要求する。Engine returnやcountだけでは成立しない。
- Claude completionは、`PreCompact(manual)`、`PostCompact(manual)`、
  `SessionStart(compact)`、closed / drained collectorを要求する。最後の二eventの相互順序は
  固定しない。CLI success envelope単独はproofにならない。
- Receiptは、Codexの`YOH_ACK`、Hermesのadapter-defined full-field tool receipt、Claudeの
  full-identity receiptまたは別profileの`host-nonce-v1`を分ける。Delivery、receipt、fresh
  observation、continuation、ResumeProofは別段階である。
- Accepted Yohaku archive collector / retrievalがあるのはhistorical Codex Referenceだけで
  ある。Hermes `SessionDB`、Claude native history / transcript、Ollama stateはYohaku archive
  ではない。`C-DRR`もarchive coverageを持たない。

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

## Claude Code Ollama local maintainer testing profile

次のrecordはすべてmaintainer / local-live / synthetic、maturity experimentalである。成功run
だけをsummaryへ残さず、失敗・`AMBIGUOUS`・後段`NOT_RUN`も保持する。

| Evidence Record | Fixed backend / model | 観測結果 | Verdict / 非継承 |
|---|---|---|---|
| `C-CLI-OLLAMA-LOCAL-REPEAT-2026-09-29` | Ollama `0.34.1`、Spark-X2.5-4B digest `e1646156c204…`、context 131072 | `recovery-04`は7 requests / 294.11秒で`RESUME_VERIFIED`。Matching `recovery-05`は最初のcommand引数欠落でadapter前に停止 | Historical bounded run `PASS`、repeatability check `FAIL`、overall `PARTIAL` |
| `C-CLI-OLLAMA-MIMO-COMPARE-2026-09-29` | MiMo-V2.6-Distill-Qwen-9B-Ablitrated digest `616953773b51…` | 二attemptとも最初のcommand引数欠落で`FAIL`。一attemptは別にupstream `TimeoutError`も記録。Compact以降`NOT_RUN` | SparkやsubscriptionのVerdictを変更しない |
| `C-CLI-OLLAMA-QWEN-COMPARE-2026-09-29` | Qwen3.5-4B-abliterated digest `4ce045509cfb…` | 二attemptともbackend template HTTP 500。Tool callなし、recovery stages `NOT_RUN` | Backend / template compatibility `FAIL`。Model tool semanticsは未評価 |
| `C-CLI-OLLAMA-QWEN35-4B-2026-09-29` | `qwen3.5:4b` digest `2a654d98e6fb…`、context 32768 | 二attemptともcompletion / handoff submission後、full-identity receiptの一文字不一致で停止 | 二workflow `FAIL`。Fresh observation以降`NOT_RUN` |
| `C-CLI-OLLAMA-QWEN35-9B-2026-09-29` | `qwen3.5:9b` digest `6488c96fa5fa…`、context 32768 | 一attemptはreceipt `session_id`不一致で`FAIL`、一attemptは7 requests / 128.37秒で`RESUME_VERIFIED` | Bounded success一回。Repeatability未成立、subscriptionへ非継承 |
| `C-CLI-NONCE-QWEN35-9B` | 同じQwen 9B、`host-nonce-v1` | Accepted runは7 requests / 100.01秒で`RESUME_VERIFIED`。Earlier context 4096 attemptは`PreCompact`だけで`AMBIGUOUS` | Fixed workflow `PASS`、overall `PARTIAL`。Earlier failureも保持 |

Full-identity receiptと`host-nonce-v1`は別protocolである。Nonce profileの成功をfull-identity
receipt、Anthropic subscription、Claude Code family全体へ適用しない。Elapsed timeの差から
speed improvementを推定せず、一成功からreliabilityを推定しない。詳細contractは
[Claude Code CLI Runtime](runtimes/claude-code-cli.md#explicit-receipt)を参照する。

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

## Operational Alpha Foundation

Codex `0.158.0-alpha.2.1`とpinned Hermes `0.21.0`には、no-inference lifecycle profileが
ある。Native start / status / stop / clean stop後のfresh lifecycleはlab-testedである。
Codex `0.155` Reference Evidenceを`C-OP`へ、H-CLI-01 adapter Evidenceを`H-OP`へ適用しない。
Claude Code CLIには同等のformal operational launcherがない。

Codex `document-review-report-v1`は、public document二点、manual compact一回、create-only
Markdown report一点のfixed workflowで`RESUME_VERIFIED`へ到達した。Final accepted runの前に、
task dynamic toolをHookが拒否してtransition前に`REFUSED`となったrunを保持する。修正後の
accepted runと、existing outputを`STALE_OUTPUT_PRESENT`で拒否したrepeat checkも別結果として
保持する。Mechanical completionは`PASS`だが、writing / factual qualityは`NOT_ASSESSED`である。

## Known Limitations

- 全profileのmaturityはexperimental、release channelはundeclared
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
