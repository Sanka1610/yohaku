# Yohaku — Support maturity and release policy

2026-09-28制定。YohakuのSubtitle・対外的な製品カテゴリは **Proactive Context Compaction Manager**、内部の中核概念は **Verified Context Transition** とする。CompactionはContext Transitionの実装方式の一つであり、RuntimeごとのTransition Strategyは方式別の契約・coverageで評価する。本書はRuntime / Support Profile maturityとrelease policyを所有し、将来の対応予定と現在確認できた対応を区別する。Evidence、CoverageProfile、Capability Verdict、provenanceは[Evidence Model](docs/evidence-model.md)が定義する。

## Runtime priorityと対応範囲

| Priority | Runtime | 実装・検証上の位置づけ |
|---|---|---|
| Reference | Codex | 既存実装と限定受入を比較基準として保持する |
| Target | Claude Code / Hermes | Bounded profileの追加検証とscope拡張を優先する対象。現在の実装状態は各Runtime canonicalで別に示す |
| Next Target | DeepSeek Harness / OpenCode | Targetで境界を確認した後の候補 |
| Future | Gemini CLI / Antigravity | 公開制御点と需要を確認して着手する候補 |
| Research / Auxiliary | Claude Desktop / Cowork | 調査・memory/archive等の補助利用。compact制御対応とは別に評価する |

Priorityは技術的優劣、実装済み機能数、成熟度を表さない。同じPriority内に固定順位は設けず、probe可能な環境・費用・検証課題から着手順を決める。Claude Desktop、Cowork、Claude Codeは同じ対応範囲にまとめない。

対応はRuntime名だけで宣言せず、Runtime version、surface（CLI / SDK / GUI等）、adapter version、OS、provider/model、設定・Hook・権限、backend、tool集合、owner条件を指定したSupport Profileで示す。SDK所有sessionの実測を通常GUIの既存session対応へ読み替えない。未測定OS・subscription・providerへの一般化もしない。

Support Profileには利用可能な経路、無効化した経路、Known Limitations、CoverageProfile参照、Evidence、maturity、最終review日を記載する。調査だけの候補は「未実装」と明示し、対応済み一覧へ混在させない。Runtime全体のmaturityを単一表示する場合も、その根拠となるprofileを必ずリンクする。

## Policyが参照する独立した軸

| 軸 | 答える問い | 値の例 |
|---|---|---|
| Runtime priority | どこから実装・検証するか | Reference / Target / Next Target / Future / Research / Auxiliary |
| Support Profile maturity | Yohakuのそのprofileをどの程度継続利用できるか | experimental / alpha / beta / stable |
| Release channel | その製品版をどの範囲・方針で配布するか | undeclared / Alpha / Beta / Stable |

`undeclared`は、製品版の公開channelをまだ宣言していない状態であり、maturityやVerdictではない。

Priorityからmaturityを決めず、Capability Verdictの集計だけでmaturityや公開可否を決めない。Evidence level、Capability Verdict、CoverageProfileもこれらと独立しており、区別は[Evidence Model](docs/evidence-model.md)を参照する。Stable製品版にexperimental adapterを同梱する場合も、opt-inと個別表示を必須にしてStableの保証対象へ含めない。

## Support Profile maturity

成熟度はYohaku adapter / Support Profileの状態であり、Runtime提供元の製品品質やversion名とは無関係とする。各段階への変更には、対象profile、根拠、未解決事項、review担当者・日付を残す。

| Maturity | 意味 | 次段階への判断材料 |
|---|---|---|
| experimental | 調査中、未実装、または限定prototype。契約・導入手順・対応範囲が変わり得る | scopeを限定した実装と、正常経路・証拠不足時の停止をlabで確認する |
| alpha | 明記した範囲で導入・主要workflowを試せる。破壊的な仕様変更は告知し、データを暗黙変換しない | 利用者向け手順、回帰確認、Issue受付、限定Field Evidenceを整える |
| beta | 対応範囲を固定して外部実利用を募れる。主要workflowのfield記録と問題処理の実績がある | 継続利用、障害・復旧、更新互換性の証拠を蓄積する |
| stable | 宣言したprofileで継続利用・保守・更新を支えられる | 変更影響の検証とField Evidenceの継続reviewで維持する |

制定時はCodex Referenceをexperimentalとし、他Runtimeを未実装・live capability受入
`NOT_RUN`の調査候補として分類した。これは制定時点の記録であり、現在の実装状態ではない。
その後に追加したHermes / Claude Code CLIのbounded profileもexperimentalのままであり、
各profileのEvidenceとVerdictはRuntime canonical pageで個別に示す。限定PASSをRuntime family
全体や公開Alphaの承認へ読み替えない。

その後、Hermes H-CLI-01はbounded connected adapter workflow PASS / profile PARTIALとなり、completion predicateをCoreから分離した。General Hermes adapter、Strong Transition Assurance、公開channelは未成立。更新後の実装・実測範囲は[Hermes Runtime](docs/runtimes/hermes.md)と[Runtime support](docs/runtime-support.md#target-runtime-status)を参照する。

Claude Code + Ollama localは、固定version / backend / modelの
[maintainer testing profile](docs/runtimes/claude-code-cli.md#model-comparisonの扱い)として別登録した。
2026-09-29時点で同一構成のbounded recoveryは成功1回・追加試行の失敗1回。歴史的workflow
PASSと再現確認FAILを併記し、overall PARTIAL / experimentalを維持する。手動reviewを伴う
回帰診断には条件付きで使用できるが、安定した必須自動gateには採用しない。Anthropic
subscription profileのEvidence・Verdictは変更しない。

Historical Codex Referenceの既存受入はCLI `0.155.0-alpha.16.4` / WSL2 Ubuntu / Python `3.14.4`の限定profileである。Phase 14のlive信号を使った合成taskはlab tested / live-runtime、局所・合成テストはlab tested / local-syntheticとして読む。Field Evidenceの取得や現在版での再実行を示すものではない。native auto compactは1 attachmentにつき1回の範囲、native recovery途中のrestartはUNSUPPORTED、反復compactや一般の並列・外部work等は未受入である。

Codex `0.158.0-alpha.2.1`の`document-review-report-v1`は、2026-09-29に別Support Profileとして追加した。専有workspace、明示入力2点、manual compact 1回、create-only Markdown report 1点に限定した非fixture実taskで`RESUME_VERIFIED`へ到達した。固定workflowのCapability VerdictはPASSだが、文章品質はNOT_ASSESSED、profile maturityはexperimental、製品全体のcoverageはPARTIAL、release channelはundeclaredとする。この結果を一般文書task、coding task、別Runtime、Field Evidenceへ適用しない。

重大な回帰やRuntime仕様変更が判明した場合は、該当version/profileの推奨を停止し、必要ならmaturityを下げる。旧versionの証拠を消さず、新versionは影響確認が済むまで未確認として扱う。

## Evidence / Coverage / Verdictとの関係

Maturityとrelease判断ではreview済みEvidenceとCoverageProfileを参照するが、Evidence
level、Capability Verdict、外部tester recordの取扱いを本書で再定義しない。定義、
privacy、sanitization、runの追記原則は[Evidence Model](docs/evidence-model.md)に従う。

既存のPhase全体の集約Verdictも履歴として保持する。Phase 14のoverall PARTIAL、Scenario
ごとの限定PASS、Hook FAIL_OPEN、native recovery restart UNSUPPORTED等は変更しない。
`FAIL_OPEN`は障害時の挙動を表す分類であり、maturityやCapability Verdictではない。
重大なfailure Evidenceやcoverage不足はmaturity / release判断の入力になるが、個別Verdictを
書き換えて一つのrelease判定へ統合しない。

## 公開に共通する最低条件

公開可否はreleaseごとに宣言したscopeで判断する。全Runtime・全OS・全provider・全capabilityのPASSは要求しない。Subscription不足、provider token cost、入手不能なOS/Runtime等により自前実測できない条件は、理由・Evidence level・Verdict・既知の制限を示して公開できる。

ただし有効化する自動transitionには、指定scopeでのboundary/freshness検証、durable checkpoint、期限とrevisionに結びつくauthority、Runtime固有completion proof、handoff receipt、current-state/resume確認の正常経路と、証拠不足・stale・重複への拒否経路のlab証拠を必要とする。不足する経路は無効化またはcheckpoint/archive等の補助モードに限定し、verified transitionとは表示しない。

このproactive要求の条件と、Runtime自身が先行して起こしたnative compactの復旧は別profileとする。後者では未取得のboundary検証やleaseを後付けで成立させず、stale checkpointとunverified emergency deltaを区別したまま、実完了・現在state・安全な残作業を照合する。native復旧の成功をproactive要求の全条件PASSへ転用しない。

Yohaku ownerが不明状態で進めないことと、Runtime全体を強制停止できることは別の保証とする。Hook FAIL_OPENが残る限定profileの公開は許容するが、専有owner等の前提、観測できないwork、failure時にRuntimeが継続し得る制限を導入前に示す。Strong Transition Assuranceの成立やRuntime全体のatomic freezeを主張しない。

全channelで、対象範囲内のデータ破損、秘密情報露出、既知の無断・重複実行、曖昧な完了を成功とする不具合はrelease blockerとする。修正するか、その機能を確実に無効化してscopeから外すまで公開しない。既知の保証不足を制限として開示することと、対象内の既知の危険な不具合を放置することを区別する。

## Alpha / Beta / Stable release criteria

| Channel | 必須条件 | 許容する未達・制限 |
|---|---|---|
| Alpha | 少なくとも一つのalpha以上のprofile。導入・停止・復旧手順、主要workflowと上記安全条件のlab証拠、Known Limitations、Issue受付方法、変更可能性を公開 | fieldは未取得でもよい。他Runtime未実装、任意機能PARTIAL / UNSUPPORTED / NOT_RUN、未測定OS/providerを明示できる |
| Beta | 主対象profileがbeta以上。Alpha条件に加え、開発者以外のtesterによる少なくとも一つの実taskのreview済みField Evidence、主要workflowの回帰・停止/復旧確認、bug triage、更新互換性方針、対象profileを固定 | fieldで全capabilityを再実証する必要はない。費用・OS等で不足するmatrixを制限付き公開できる |
| Stable | 主対象profileがstable。Beta条件に加え、宣言scopeで複数session・複数日にわたる継続Field Evidence、実際の更新または更新候補からの互換/復旧確認、未解決blockerなし、サポートversion範囲・保守担当・非推奨化方針を公開 | 対象外runtime/OS、任意機能の未達、開示済みの保証限界を残せる。全capability PASSや世界中の構成の実測は不要 |

Beta/StableのField Evidenceは、開発者、友人、外部testerの記録を条件付きで組み合わせられる。人数・利用日数だけで成熟度を決めず、採用するtask/workflow、観測期間、成功・失敗、未確認の範囲をrelease recordへ記す。Stableの宣言を別Runtimeや別surfaceへ波及させない。

Release recordには、channel/version/commit、主対象profileとmaturity、必須workflowと採用Evidence、除外機能・既知の制限、残debt、費用等による未測定理由、Issue対応状況、導入/更新/復旧手順、判定者・日付を記載する。自動判定の総合PASS一つに置き換えない。本方針の制定は公開承認・公開実行ではない。

## Candidate A release review fields

次の表はCandidate Aに限定したrelease review用の検証対象である。Alpha候補の範囲を示し、
現在のmaturity / channelや個別EvidenceのVerdictを昇格させない。Fieldの意味、除外コード、
検証手順は[Candidate A review](docs/release/candidate-a.md)を参照する。

<!-- candidate-a:start -->
| field | Candidate A |
|---|---|
| release_candidate_id | yohaku-0.1.0a1-rc2 |
| alpha_scope_profile_ids | codex-operational-0.158, codex-document-review-report-v1 |
| excluded_profile_ids | codex-reference-0.155, hermes-operational-h-cli-01, hermes-h-cli-01, claude-c-cli, claude-c-cli-local-nonce |
| excluded_runtime_families | hermes, claude |
| maturity | experimental |
| release_channel | undeclared |
| known_exclusions | no-runtime-family-support, no-field-evidence, no-other-runtime-os-provider, no-general-parallel-background-external-work, no-strong-transition-assurance |
<!-- candidate-a:end -->
