# Evidence Model

Yohakuでいう **Evidence** は、固定したclaimを第三者がreviewできるように、観測の
対象、条件、出所、結果、制限を保持した記録である。単独のlog、成功メッセージ、
Runtime event、testerの自己申告は、それだけではCapability Verdictを確定しない。
Evidence Recordがclaimとprofileへ対応付けられ、必要なauthority、freshness、correlationを
満たすかreviewした後に、そのclaimへVerdictを付ける。

本書は、Evidence、provenance、authority、freshness、correlation、CoverageProfile、
Capability Verdictの公開上の正本である。本書の制定は、既存Evidence、CoverageProfile、
Verdictを変更せず、過去のrunを現在のversionで再実行したことにもならない。既存recordに
本書の項目がない場合は、原資料から確認できる値だけを記録し、確認できない値を推定で
補わない。

## 文書の責務

公開文書は、次の責務を分ける。

| 文書 | 所有する内容 |
|---|---|
| [Architecture](architecture.md) | component、control flow、trust boundary |
| [Runtime Mapping](runtime-mapping.md) | fixed Runtime / Support Profile固有の事実とRuntime primitiveへの対応 |
| [Transition Strategies](transition-strategies.md) | Context TransitionのtaxonomyとStrategy共通semantics |
| 本書 | Evidence、Coverage、Verdict、provenanceと非継承規則 |
| [Support Policy](../SUPPORT_POLICY.md) | Runtime / Support Profile maturityとrelease policy |

Runtime固有pageはnative event、version、configuration、timeout、Known Limitationsを保持
する。本書は個別runの一覧を保持せず、各recordをどの条件でEvidenceとして採用し、
CoverageProfileとVerdictへ反映するかを定義する。

## Evidence Recordとclaimの単位

Evidence Recordは、少なくとも次の単位へ結び付ける。

```text
one Evidence Record
  → one fixed run or one fixed static review
  → one fixed Support Profile
  → one Transition Strategy and, when applicable, one Task Profile
  → one or more named capability requirements
  → one retained result, including failure or incomplete observation
```

claimのscopeには、該当する範囲で次を含める。

- Yohaku source commit、adapter / plugin / collector version
- Runtime family、Runtime version、surface、OS、owner model
- provider、backend、model、context設定、Hook / permission設定
- Transition Strategy、Task Profile、tool集合、workspace scope
- capability requirement、accepted endpoint、期待した観測
- 実行日時、run ID、観測者またはtesterのrole

このscopeを固定しないrecordは、調査資料やtester-reported claimとして保持できるが、
不足する条件を推定してCapability PASSに使わない。複数のcapabilityを一つのrunで観測
した場合も、Verdictはrequirementごとに判断する。

## Provenance、authority、freshness、correlation

四つの性質は互いを代替しない。

| 性質 | 答える問い | 必要な記録 |
|---|---|---|
| Evidence provenance | 誰が、どこで、何を、どの手順で取得・変換したか | producer、環境、取得方法、source/run ID、変換・sanitization履歴、reviewまでの関係 |
| Evidence authority | その観測主体またはsourceは、どの事実を証明できるか | 公式仕様、特定source、trusted host、Runtime-native storage、tester、reviewerごとの権限と限界 |
| Evidence freshness | 観測は、claim対象のversion、revision、task state、時点を表すか | version / commit、観測日時、revision、current-state read、stale条件 |
| Evidence correlation | 複数の観測が、同じrequest、session、generation、task、runに属するか | native identity、host-local identity、request / session / generation / attachmentの対応、順序 |

Authorityはsourceごとに限定する。公式文書は公開contractを、source reviewは特定commitの
処理を、trusted hostは宣言した観測面の状態を、Runtime-native storage readbackはその
storageに反映された状態を証明できる。いずれも、単独ではtask全体のcorrectnessや別の
観測面を証明しない。testerは体験と提供した原資料の出所を報告できるが、未観測の内部
stateまで証明するわけではない。reviewerは提出物からVerdictを判断できるが、提出されて
いない事実を補完できない。

Freshnessは単なる新しさではない。過去のrecordはhistorical Evidenceとして有効なまま
保持できるが、異なるRuntime version、source commit、configuration、task stateの現在の
claimには自動適用しない。現在stateを要求するcapabilityでは、old checkpoint、以前の
screen capture、過去runのhashだけではfreshnessを満たさない。

Correlationは名前が似ていることでは成立しない。Runtime-native IDとhost-local IDを
区別し、profileが定めたbindingとevent順序で対応付ける。RPC acknowledgement、engine
return、tool success、単一のHook、後続actionの成功だけからtransition completionや
resume correctnessを推定しない。

## Evidence taxonomy

Evidenceは一つの強弱尺度へまとめず、少なくともEvidence level、producer、execution
environment、workloadの四軸で記録する。

### Evidence level

| Evidence level | 根拠 | そのEvidenceだけでは示せないこと |
|---|---|---|
| documentation / theoretical | 公式文書、公開仕様、設計上の推論。sourceの記載とYohaku側の推論を分ける | 実装の存在、対象binaryの動作、Yohakuとの接続 |
| source verified | 特定commit / file / symbolで処理またはcontractを確認 | 稼働binaryの挙動、provider、Hook、OSを含むlive成功 |
| lab tested | profileと手順を固定し、controlled taskまたはProbeを実行して原資料を保持 | 日常利用全般の安定性、試験外の構成、Field Evidence |
| field tested | 実際の利用条件とreal taskで観測し、成功・失敗と条件を保持 | 全capabilityの適合、別環境での再現、未観測経路の安全性 |

失敗したrunも、取得条件が該当すればlab testedまたはfield testedである。Evidence levelは
成功度を表さず、Verdictの別名でもない。source verifiedがlab testedより低いVerdictを
意味するわけでもなく、field testedが自動的にPASSを意味するわけでもない。
後から得た別levelのrecordで過去のrecordを置換せず、異なる条件と結果を持つEvidenceと
して併存させる。Field Evidenceでは、通常利用中に自然に生じたfailureと、意図的に
注入したfailureを区別する。

### Producer、execution、workload

| 軸 | 値の例 | 意味 |
|---|---|---|
| Producer | `maintainer` / `external` | Yohaku maintainerが取得したか、外部tester / community contributorが取得したか |
| Execution | `local` / `local-live` / `live-runtime` | static・local fixtureか、maintainer管理のlocal backendを含む実Runtimeか、対象外部surfaceを含む実Runtimeか |
| Workload | `theoretical` / `synthetic` / `real-task` | 実行なしの推論か、Probe / fixture / controlled taskか、通常利用を目的とした実taskか |

現行recordで使う複合表記は、次のように読む。

| 表記 | 読み方 | Evidence level上の扱い |
|---|---|---|
| `documentation / theoretical` | 文書または設計根拠であり、runはない | documentation / theoretical |
| `source verified` | 特定sourceを静的に確認した | source verified |
| `external / live-runtime / synthetic` | 外部testerが対象live surfaceでbounded Probeまたは合成taskを実行した | review可能ならlab tested。real taskでないためField Evidenceではない |
| `maintainer / local-live / synthetic` | maintainerがlocal backend / modelを使う実Runtimeで合成taskを実行した | lab tested。外部subscriptionやField Evidenceではない |
| `field tested / real-task` | 通常利用の条件でreal taskを実行した | field tested。個別Capability Verdictは別途reviewする |

`live-runtime`はworkloadを表さない。providerへ接続したsynthetic Probeはliveであっても
Field Evidenceではない。反対に、real taskであっても観測条件が不足すれば、特定の
capabilityをPASSにできない。Nonfixtureのreal-task workloadも、controlled acceptanceと
して実行した場合はlab testedになり得る。

## Evidenceの保持と公開

Evidenceの取得から公開までは、次の層を分ける。

```text
raw/private observation
    → sanitized Evidence
    → manifest / hash
    → reviewer result
    → public summary
```

### Raw/private observation

Raw/private observationは、Runtimeが生成した原log、database readback、transcript、
screen capture、run directory、operator noteなど、取得時の原資料である。原資料は
最も多くの情報を含む一方、secret、private conversation、account情報、機微なpathを
含み得るため、既定では公開物にしない。

原資料を保持できない場合は、保持しなかった理由と、review不能になったfieldを記録
する。原資料へのprivate referenceはEvidence chainに残せるが、そのreference自体が
公開閲覧可能であるとは限らない。

### Sanitized Evidence

Sanitized Evidenceは、claimのreviewに必要なfieldを残し、公開不要な情報を削除または
不可逆に置換したderived recordである。少なくとも次を公開recordへ含めない。

- secret、API key、token、credential、cookie、認証用nonceの原値
- account ID、個人を特定できるtester ID、private repositoryの識別子
- private conversation、prompt / response全文、task本文のうちclaimに不要な内容
- user名、home directory、temporary directoryなど、claimに不要なabsolute path
- tool argument / resultや環境変数のうち、correlationや判定に不要な値

必要なidentityは、scopeを限定したrecord ID、redacted label、hash等へ置換する。ただし、
sanitizationでcorrelation、freshness、結果をreviewできなくなった場合は、その欠落を
明記し、残った資料だけでVerdictを昇格させない。Sanitized Evidenceはraw observationの
完全な代替とは限らない。

### Manifest / hash

Manifestは、bundle内のfile、Evidence ID、source association、size、hash algorithm、
digest、sanitization版を列挙する。Hashは、reviewしたbyte列と後から参照するbyte列の
同一性を確認するために使う。

Hashが証明するのはbyte-level integrityであり、取得者の身元、観測の真正性、Runtime
capability、記載内容の正しさではない。Manifest validationのPASSをCapability PASSへ
読み替えない。

### Reviewer result

Reviewer resultは、tester-reported claimとEvidenceを照合し、採用した資料、欠落、
scope、requirementごとのVerdict、判定理由、reviewer、review日を記録する。Review前の
submissionは`pending review`または`tester-reported`として保持する。これらは新しい
Capability Verdictではない。

独立reviewとは、run実行者の結論を転記することではなく、固定profile、manifest / hash、
必須event、correlation、freshness、negative result、sanitizationによる欠落を別の担当者
または独立したreview工程で確認することを指す。同じsubscriptionでmaintainerが再実行
することは必須ではない。

### Public summary

Public summaryは、review済み結果から公開可能なscope、Evidence provenance、Verdict、
Known Limitations、非継承範囲を抜き出した説明である。Raw/private observationやsanitized
bundleの代わりではなく、summaryだけから原資料以上のclaimを作らない。個別run一覧は
Runtime固有のrecord / indexへ置き、本書には追加しない。

## External tester / community Evidence

外部testerまたはcommunityからEvidenceを受け取る場合は、次の規則を適用する。

1. 取得前またはreview時に、Runtime、version、surface、OS、provider、backend、model、
   configuration、Transition Strategy、Task Profileを固定する。不明な値は`unknown`として
   残し、既知のprofileへ推定で対応付けない。
2. 成功runと失敗runを同じ基準で保持する。採用した成功だけを残さず、既知のtimeout、
   malformed output、recovery failure、再現失敗をCoverage判断へ含める。
3. Rerunは新しいrun IDとEvidence Recordを作る。過去runの結果、timestamp、manifest、
   Verdictを書き換えず、後続recordからsupersedes / relates-to関係を付ける。
4. `tester-reported claim`と`independently reviewed Evidence`を分ける。未reviewの報告は
   observationとして有用でも、review済みVerdictとは表示しない。
5. Testerが明示的に共有した範囲だけを扱い、自動telemetryや会話全文の提出を要求しない。
   公開転載には公開範囲の同意を確認する。
6. Secret、credential、account ID、private conversation、不要なabsolute pathを公開recordへ
   含めない。Sanitizationで失った判定材料も記録する。

外部testerが一つのfixed profileで十分なEvidenceを提供した場合、そのEvidenceだけを
独立reviewしてCapability Verdictを付けられる。ただし、そのVerdictを別profile、Runtime
family全体、maturity、release channelへ自動反映しない。

## CoverageProfile

CoverageProfileは、宣言したSupport Profileについて、どのcapability requirementをどの
Evidenceで評価し、何が未確認かを集約するreview recordである。run log、機能一覧、
test count、単一の総合点ではない。

CoverageProfileには、少なくとも次を関連付ける。

- CoverageProfile ID / revisionと対象Support Profile
- Runtime / version / surface、adapter version、OS、provider / backend / model、設定
- Transition Strategy、Task Profile、tool / workspace / owner assumptions
- 宣言したcapability requirementとaccepted endpoint
- requirementごとのEvidence ID、Evidence level、producer / execution / workload
- requirementごとのCapability Verdictと判定理由
- 成功、失敗、degraded path、negative case、未実行、coverage外の項目
- Known Limitations、sanitizationによる欠落、reviewerとreview日

Overall Verdictは、requirement rowの多数決、最高値、最良runだけで決めない。Required
capabilityの欠落、failure safety、repeatability、accepted endpoint、除外範囲を明示し、
集約理由を記録する。一つのbounded runがPASSでも、Runtime profile全体のCoverageProfileは
PARTIAL、FAIL、または他の適切な値になり得る。

CoverageProfileのscope自体を狭く定義し、その宣言requirementを十分なEvidenceで満たした
場合は、そのbounded profileへPASSを付けられる。ただし、そのPASSはscope外のRuntime、
Strategy、Task Profile、qualityを含まない。

## Capability Verdict

Capability Verdictは、固定したprofile内のnamed requirementが、採用したEvidenceで要求を
満たしたかを表す。

| Verdict | 定義 |
|---|---|
| `PASS` | 明示したrequirementを、記録した条件・範囲のEvidenceで実証した |
| `PARTIAL` | requirementまたは集約coverageの一部だけが成立した。成立範囲、未成立部分、理由を列挙する |
| `FAIL` | 評価を実行し、対象requirementを満たさない挙動を確認した |
| `UNSUPPORTED` | 指定version / surface / profileに、requirementを支える機構またはcontractがないと確認した |
| `NOT_RUN` | 当該requirementの必要な評価を実行していない |

`PASS`は「そのrunで観測したbounded claimが成立した」を意味する。実装が存在すること、
RPCが成功したこと、別requirementがPASSしたことは、対象claimのPASS条件ではない。

`PARTIAL`は「だいたい動く」という印象評価ではない。次のような具体的理由のいずれかを
持ち、recordに理由を記載する。

- **bounded scope**: 一部のtool、event order、owner、endpointだけをacceptedとし、より
  広い集約claimには未成立部分がある
- **limited coverage**: 宣言したrequirement群のうち、十分なEvidenceがあるのは一部だけ
- **evidence insufficiency**: 動作の一部は観測したが、必要なauthority、freshness、
  correlation、readback、negative caseが不足する
- **degraded path**: 通常経路は成立せず、明示したfallbackまたは制限付き経路だけが成立する
- **mixed results**: 成功runと失敗runが併存し、repeatabilityまたは適用条件を確定できない

個別requirementで失敗を確認した場合、そのrowを`PARTIAL`に弱めず`FAIL`とする。集約profile
が、別のPASS rowとFAIL rowを含むため`PARTIAL`になる場合は、内訳と集約規則を示す。
単なる情報不足から`UNSUPPORTED`を推定せず、必要なlive評価をしていなければ`NOT_RUN`を
維持する。

### `NOT_ASSESSED`との違い

`NOT_ASSESSED`はCapability Verdictではない。機械的完了とは別のquality dimensionや、
profileが評価対象に含めていない属性について、評価基準またはassessorを適用していない
ことを表すassessment statusである。

たとえば、`document-review-report-v1`が入力のfresh read、create-only output、重複なし、
`RESUME_VERIFIED`までのmechanical completionを満たせば、そのbounded workflowはPASSに
できる。一方、文章品質、コード品質、事実性、完全性は`NOT_ASSESSED`のままになり得る。
Mechanical completionのPASSをcontent qualityのPASSへ読み替えない。

Capability requirementとして評価すると宣言した項目を実行しなかった場合は
`NOT_ASSESSED`ではなく`NOT_RUN`を使う。提出済みだがreview前のrecordには`pending review`
を使い、Verdict vocabularyへ追加しない。`AMBIGUOUS`、`FAIL_OPEN`、`DEFERRED`、
`RECOVERY_REQUIRED`等はRuntime / Core behaviorまたはfailure classificationであり、
Capability Verdictではない。

## Evidence、Verdict、maturity、releaseの違い

これらは別の問いに答える。

| 概念 | 対象 | 答える問い | 値の例 |
|---|---|---|---|
| Evidence | 一つのstatic reviewまたはrun | 何を、誰が、どの条件と根拠で観測したか | source verified、external / live-runtime / synthetic |
| Capability Verdict | fixed profileのnamed requirement | 採用Evidenceで要求を満たしたか | PASS / PARTIAL / FAIL / UNSUPPORTED / NOT_RUN |
| CoverageProfile | Support Profileのrequirement集合 | 何を評価し、何が未確認か | row別Verdict、overall PARTIAL、Known Limitations |
| Runtime / Profile maturity | YohakuのSupport Profile | そのprofileをどの程度継続利用・保守できるか | experimental / alpha / beta / stable |
| Release channel | 配布する製品versionと宣言scope | どの利用者と保証範囲に向けて公開するか | Alpha / Beta / Stable / undeclared |

Maturityは個別runやRuntime提供元の品質ではなく、Yohakuのfixed Support Profileに付ける。
`experimental`、`alpha`、`beta`、`stable`の昇格・降格条件は[Support Policy](../SUPPORT_POLICY.md)
が定義する。Release channelも同文書が定義し、maturityと同名の段階であっても同じ値では
ない。Stable channelの製品にexperimental profileをopt-inで含めても、そのprofileが
stableへ昇格したことにはならない。反対に、一つのCapability PASSだけでAlpha releaseを
宣言しない。

## EvidenceとVerdictの非継承規則

Evidenceを採用できる範囲は、記録したprofile tupleとclaimに限定する。Runtime version、
surface、OS、provider、backend、model、configuration、Transition Strategy、Task Profile、
tool集合、owner、Yohaku / adapter revisionのいずれかを越える場合は、新しいclaimとして
影響をreviewする。差分に影響されないstatic factを再利用できる場合も、その理由とsource
associationを新しいrecordに示す。

特に、次の推論は行わない。

- **1 runのPASS ≠ Runtime全体のPASS**。一つの成功は、そのrunとbounded claimだけを支える。
- **implementation exists ≠ live capability verified**。sourceの存在はsource verifiedに
  なり得るが、live-runtime PASSにはならない。
- **Probe PASS ≠ product adapter acceptance**。Probeはcapability seamの存在を示し得るが、
  製品adapterのsource association、failure handling、persistence、receipt、resume、運用
  手順まで実証しない。
- **synthetic Evidence ≠ Field Evidence**。Synthetic taskはlive Runtimeで成功しても、
  real-taskのfield tested recordにはならない。
- Runtime version、surface、provider、backend、model、Transition Strategy、Task Profileを
  越えてEvidenceまたはVerdictを自動継承しない。
- Claude Codeのlocal Ollama EvidenceをAnthropic subscription Evidenceへ転用しない。
- Hermes H-CLI-01のbounded resultをHermes全体、別tool、別session形態、別versionへ拡張
  しない。
- **Runtime support ≠ Task Profile support**。Lifecycle / transition capabilityからtaskの
  semantic boundaryやtask completionを推定せず、Task Profileの成功からRuntime一般の
  supportを推定しない。
- **mechanical completion ≠ 文章・コード・事実品質**。Artifact作成、freshness、重複排除、
  resumeの成功から内容の正しさや品質を推定しない。

Profile間で共有できるのは、明示したsource associationを持つstatic factと、Architecture
が定義するsafety semanticsである。Lifecycle event、identity strength、completion proof、
storage authority、Verdict、maturity、release statusは、matching Evidenceなしに共有しない。

## 現行recordへの適用

本書は既存recordのschema migrationを要求しない。現行のCoverageProfile、private raw
Evidence、sanitized external bundle、public Runtime summaryは、それぞれの元のscopeとhashを
保ったまま維持する。現行公開文書と記録方式には次の不一致が残るため、後続reviewでは
不足を新しい値で上書きせず明示する。

- producer / execution / workloadが一つの自由記述へ結合され、各軸を機械的に検索できない
- profile declaration、Evidence index、public support tableの対応を手動で維持している
- 公開summaryの一部だけでは、review status、sanitization version、accepted endpoint、
  supersedes関係を確認できない
- Raw/private observation、sanitized Evidence、manifest、reviewer result、public summaryの
  関係を、一つの共通indexで参照できない
- Field Evidenceが未取得のprofileと、quality / repeatabilityを`NOT_ASSESSED`とするprofileが
  ある

これらはEvidenceを無効化する理由ではない。欠落fieldを`unknown`または未記録として扱い、
元のVerdictを保持する。新しいrunから本書の項目を適用し、過去runを再実行したかのような
backfillは行わない。

## Runtime固有docsに必要なEvidence項目

RuntimeまたはTask Profileの個別pageでは、個別runの羅列を避けつつ、採用Evidenceについて
次を確認できるようにする。章順とprofile記述規則は
[Runtime文書の構成規則](runtimes/README.md)に従う。

1. Support Profile ID、CoverageProfile ID、Evidence ID、対象capability requirement
2. Yohaku commit、adapter / collector version、Runtime version / binary / surface、OS
3. Provider、backend、model、context、Hook、permission、owner条件
4. Transition Strategy、Task Profile、tool集合、workspace scope、accepted endpoint
5. Evidence level、producer、execution environment、workload、run日時
6. Trigger、期待するcompletion predicate、合法なevent order、timeout closure
7. Native identityとhost-local identityの対応、request / session / generation correlation
8. Authorityを持つevent、storage readback、current-state observationとfreshness条件
9. 成功・失敗run、negative case、duplicate / late / malformed / missing evidenceの扱い
10. Raw/private reference、sanitized record、manifest / hash、sanitizationによる欠落
11. Reviewer result、reviewer / review日、tester-reported claimとの区別
12. RequirementごとのVerdict、overall CoverageProfileの集約理由、Known Limitations
13. 前後のrecordとの`relates-to` / `supersedes`関係と、Evidenceを継承しない範囲
14. Maturityとrelease channelへの参照。ただし、Evidence recordから自動決定しない

個別pageにこれらの項目がない場合も、別のretained Evidence indexへ安定した参照を置けば
よい。公開summaryにはprivate pathやsecretを載せず、reviewに必要なscope、結果、欠落、
非継承範囲を残す。
