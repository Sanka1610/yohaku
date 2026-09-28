# Yohaku — Support, maturity, evidence and release policy

2026-09-28制定。YohakuのSubtitle・対外的な製品カテゴリは **Proactive Context Compaction Manager**、内部の中核概念は **Verified Context Transition** とする。CompactionはContext Transitionの実装方式の一つであり、RuntimeごとのTransition Strategyは方式別の契約・coverageで評価する。本書は公開利用者向けの方針であり、将来の対応予定と現在確認できた対応を区別する。

## Runtime priorityと対応範囲

| Priority | Runtime | 実装・検証上の位置づけ |
|---|---|---|
| Reference | Codex | 既存実装と限定受入を比較基準として保持する |
| Target | Claude Code / Hermes | 次のCapability Probeと実装の優先対象 |
| Next Target | DeepSeek Harness / OpenCode | Targetで境界を確認した後の候補 |
| Future | Gemini CLI / Antigravity | 公開制御点と需要を確認して着手する候補 |
| Research / Auxiliary | Claude Desktop / Cowork | 調査・memory/archive等の補助利用。compact制御対応とは別に評価する |

Priorityは技術的優劣、実装済み機能数、成熟度を表さない。同じPriority内に固定順位は設けず、probe可能な環境・費用・検証課題から着手順を決める。Claude Desktop、Cowork、Claude Codeは同じ対応範囲にまとめない。

対応はRuntime名だけで宣言せず、Runtime version、surface（CLI / SDK / GUI等）、adapter version、OS、provider/model、設定・Hook・権限、backend、tool集合、owner条件を指定したSupport Profileで示す。SDK所有sessionの実測を通常GUIの既存session対応へ読み替えない。未測定OS・subscription・providerへの一般化もしない。

Support Profileには利用可能な経路、無効化した経路、Known Limitations、CoverageProfile参照、Evidence、maturity、最終review日を記載する。調査だけの候補は「未実装」と明示し、対応済み一覧へ混在させない。Runtime全体のmaturityを単一表示する場合も、その根拠となるprofileを必ずリンクする。

## 五つの独立した軸

| 軸 | 答える問い | 値の例 |
|---|---|---|
| Runtime priority | どこから実装・検証するか | Reference / Target / Next Target / Future / Research / Auxiliary |
| Runtime maturity | Yohakuのそのprofileをどの程度継続利用できるか | experimental / alpha / beta / stable |
| Evidence level | 主張をどの方法で確認したか | documentation / theoretical、source verified、lab tested、field tested |
| Evidence Verdict | 個別capabilityが記録条件で要求を満たしたか | PASS / PARTIAL / FAIL / UNSUPPORTED / NOT_RUN |
| Release channel | その製品版をどの範囲・方針で配布するか | Alpha / Beta / Stable |

Priorityからmaturityを決めず、Evidence levelからVerdictを決めず、Verdictの集計だけで公開を決めない。Stable製品版にexperimental adapterを同梱する場合も、opt-inと個別表示を必須にしてStableの保証対象へ含めない。

## Runtime maturity

成熟度はYohaku adapter / Support Profileの状態であり、Runtime提供元の製品品質やversion名とは無関係とする。各段階への変更には、対象profile、根拠、未解決事項、review担当者・日付を残す。

| Maturity | 意味 | 次段階への判断材料 |
|---|---|---|
| experimental | 調査中、未実装、または限定prototype。契約・導入手順・対応範囲が変わり得る | scopeを限定した実装と、正常経路・証拠不足時の停止をlabで確認する |
| alpha | 明記した範囲で導入・主要workflowを試せる。破壊的な仕様変更は告知し、データを暗黙変換しない | 利用者向け手順、回帰確認、Issue受付、限定Field Evidenceを整える |
| beta | 対応範囲を固定して外部実利用を募れる。主要workflowのfield記録と問題処理の実績がある | 継続利用、障害・復旧、更新互換性の証拠を蓄積する |
| stable | 宣言したprofileで継続利用・保守・更新を支えられる | 変更影響の検証とField Evidenceの継続reviewで維持する |

制定時はCodex Referenceをexperimentalとする。これは新しい分類の初期値であり、既存の限定PASSを取り消すものでも、公開Alphaを承認するものでもない。他Runtimeはexperimentalの調査候補で、adapterは未実装・live capability受入はNOT_RUN。未実装という状態もmaturityと併記する。

その後、Hermes H-CLI-01はbounded workflow PASS / profile PARTIALとなり、completion predicateをCoreから分離した。完成adapterと公開channelは未成立。更新後の実装・実測範囲は[Runtime support](docs/runtime-support.md#target-runtime-status)を参照する。

Claude Code + Ollama localは、固定version/modelの[maintainer testing profile](docs/runtime-support.md#claude-code-ollama-local-maintainer-testing-profile)として別登録した。2026-09-29時点で同一構成のbounded recoveryは成功1回・追加試行の失敗1回。歴史的workflow PASSと今回の再現確認FAILを併記し、overall PARTIAL / experimentalを維持する。手動reviewを伴う回帰診断には条件付きで使用できるが、安定した必須自動gateには採用しない。Anthropic subscription profileのEvidence・Verdictは変更しない。

Codexの既存受入はCLI `0.155.0-alpha.16.4` / WSL2 Ubuntu / Python `3.14.4`の限定profileである。Phase 14のlive信号を使った合成taskはlab tested / live-runtime、局所・合成テストはlab tested / local-syntheticとして読む。Field Evidenceの取得や現在版での再実行を示すものではない。native auto compactは1 attachmentにつき1回の範囲、native recovery途中のrestartはUNSUPPORTED、反復compactや一般の並列・外部work等は未受入である。

重大な回帰やRuntime仕様変更が判明した場合は、該当version/profileの推奨を停止し、必要ならmaturityを下げる。旧versionの証拠を消さず、新versionは影響確認が済むまで未確認として扱う。

## Evidence levelと記録単位

| Evidence level | 根拠 | その証拠だけでは示せないこと |
|---|---|---|
| documentation / theoretical | 公式文書、公開仕様、設計上の成立見込み。文書の記載と推論を分ける | 実装の存在、対象配布版での動作、Yohakuとの接続 |
| source verified | 特定commit / file / symbolで処理を確認 | 稼働binaryの挙動、provider・Hook・OS込みの成功 |
| lab tested | 条件を固定して試験し、結果・原資料を保存 | 日常利用全般の安定性、試験外の構成や作業 |
| field tested | 実際の利用者・実taskで観測し、条件と結果を記録 | 全capabilityの適合、別環境での再現、強制停止の完全保証 |

四段階は証拠の種類を示す。単一の最高levelで過去の証拠を置換せず、複数のEvidence Recordを併存させる。失敗したfield runもfield testedであり、成功を意味しない。

lab testedでは少なくとも`local/synthetic`と`live-runtime`を区別し、liveでもsynthetic task、制御した通知欠落・遅延・replayを併記する。providerを利用しただけではfield testedにならない。Field Evidenceも自然な障害観測と人工的な障害注入を分ける。

Evidence Recordには次を残す。これは文書上の契約であり、既存journalやCoverageProfileのschema変更を要求しない。

- 一意なEvidence ID、対象capability・要求、Support Profile / CoverageProfile参照。
- Yohaku commit、Runtime/SDK/plugin version、OS、surface、provider/model、関係する設定と観測日。秘密値は保存しない。
- Evidence levelと試験種別、実taskかfixtureか、確認者、観測手順、期待結果、実際の結果。
- 原資料の参照・hash、完了相関、現在state照合等の確認範囲、欠落・再現条件・Known Limitations。
- 個別Verdict、判定理由、review担当者と日付、旧記録との関係。未判定reportは`pending review`とし、Verdictへ新しい値を追加しない。

旧Evidenceのsource・versionとの差分がある場合は、影響するcapabilityだけを再評価する。古い結果を現在のsourceで実行済みとは表示しない。秘匿化により確認不能になった箇所も明記する。

## Evidence Verdict

| Verdict | 定義 |
|---|---|
| PASS | 明示した要求を、記録した条件・範囲の証拠で実証した |
| PARTIAL | 要求の一部または限定・degraded経路を確認した。未成立部分を列挙する |
| FAIL | 評価対象の要求を満たさない挙動を確認した |
| UNSUPPORTED | 指定version/surface/profileでは要求を支える機構・契約がないと確認した |
| NOT_RUN | 当該要求の評価を実施していない。文書調査だけでlive試験済みにしない |

ソースの存在はruntime capabilityのPASSにならない。静的根拠でUNSUPPORTEDを付ける場合は、公開契約上の非対応と実測結果を分ける。単なる情報不足は非対応の証明にならず、live評価はNOT_RUNのままにする。

既存のPhase全体の集約Verdictも履歴として保持する。Phase 14のoverall PARTIAL、Scenarioごとの限定PASS、Hook FAIL_OPEN、native recovery restart UNSUPPORTED等は変更しない。FAIL_OPENは障害時の挙動を表す分類であり、maturityや六つ目のVerdictではない。

## Issue・bug report・tester feedback

友人や外部testerの通常作業もField Evidenceとして利用できる。受付時にEvidence IDを付け、成功報告・失敗報告の両方について、利用version、構成、task概要、期待/実際の挙動、再現手順、共有可能な証拠、欠落情報を記録する。利用者が送信した範囲だけを扱い、会話全文・認証情報の提出や自動telemetryは要求しない。公開転載には共有範囲の同意を確認する。

処理順は、受付 → profile/capabilityへの対応づけ → 原資料・不足条件のreview → 必要な再現または追加確認 → Verdictの個別判断 → maturity/release判断への参照とする。「動いた」という報告だけなら利用観測として保存し、compact完了やresume検証まで成立したと推定しない。条件不明のreportは未判定のまま保持できる。

Field EvidenceからCapability PASSへの自動昇格は行わない。要求に十分な相関・現在state・実行結果等の証拠があれば、外部testerの記録だけを根拠にreviewして判定することはできる。開発者が同じsubscriptionを契約して再実行することは必須ではない。不足時はPARTIAL / NOT_RUN等を維持し、reportの有用性と適合判定を分ける。

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
