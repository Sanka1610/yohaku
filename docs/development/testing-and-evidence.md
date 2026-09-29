# Testing and Evidence Workflow

本書は、Runtime Adapter、Support Profile、Task Profileを追加・変更したときに、何をどの
順序で検証し、どのEvidenceを保持し、review後にどのclaimを認められるかを定める公開
workflowである。対象読者は、開発者、maintainer、外部tester、Evidence reviewerである。

Evidence level、producer、execution environment、workload、provenance、CoverageProfile、
Capability Verdictの定義は[Evidence Model](../evidence-model.md)を正本とする。本書はその
taxonomyを再定義せず、検証計画、run、bundle作成、reviewへ適用する。Adapterの責務と
failure semanticsは[Runtime Adapter Contract](adapter-contract.md)、maturityとrelease判断は
[Support Policy](../../SUPPORT_POLICY.md)を参照する。

検証workflowを完了しても、既存Evidence、CoverageProfile、Capability Verdictは自動的には
変わらない。新しいclaimには、固定したprofile、named requirement、採用Evidence、reviewer
resultが必要である。

## Workflowの適用単位と役割

検証単位はRuntime family全体ではなく、一つのfixed Support Profileと、該当する場合は一つの
Task Profileである。一つのrunで複数capabilityを観測しても、Verdictはrequirementごとに判断する。
巨大なE2Eが最後まで成功したという理由だけで、途中の全capabilityを`PASS`にしない。

| 役割 | 責務 | 単独では決められないこと |
|---|---|---|
| Developer | Contract、instrumentation、fixture、negative caseを実装し、source associationを示す | 自分の実装説明だけでlive capabilityやmaturityを確定しない |
| Maintainer / operator | Environment Contractを固定し、runを所有し、raw/private observationを保全する | 成功メッセージだけでCapability Verdictを確定しない |
| External tester | 指定profileを自分の環境で実行し、共有可能なsanitized Evidenceを返す | 未観測の内部stateや別profileのsupportを証明しない |
| Reviewer | Scope、provenance、authority、freshness、correlation、negative resultを確認する | 提出されていない値を推測で補わない |

## Workflow上の検証レベル

以下の区分は検証を進める順序を説明するものであり、Evidence Modelへ新しいEvidence levelを
追加するものではない。Recordには、既存taxonomyのEvidence level、producer、execution、
workloadを別々に記録する。

| Workflow上の検証レベル | 確認できること | 確認できないこと | Capability Verdictへ使える範囲 | 次段階へ進む条件 |
|---|---|---|---|---|
| Documentation / theoretical review | 公式contract、公開surface、想定control point、設計上の成立条件 | 対象sourceやbinaryの実装、live event、Yohaku接続 | Documentation factや設計上の制約。Live capabilityの`PASS`には使わない。公式contractが機構の不存在を明示する場合の`UNSUPPORTED`候補はreviewできる | 対象version / surfaceと未確認事項を固定し、sourceまたは実測で確認する項目を列挙する |
| Source verification | 特定commit / file / symbolの実装、event生成条件、failure branch | Build済みbinaryの挙動、OS / provider / Hookを含むlive結果 | Source上のnamed implementation requirement。Live Runtime requirementの`PASS`には使わない | Source revisionとbuild associationを固定し、offlineで構築・検査できる状態にする |
| Static / offline validation | Schema、allowlist、manifest、設定、fixture形式、sanitization rule、offline parser | Runtime enforcement、native lifecycle、provider behavior、実side effect | Static / offline requirementだけを`PASS`候補にできる。Runtime capabilityへ読み替えない | Invalid / missing / unknown fieldなどのoffline negative caseがfail closedになる |
| Unit / local fixture test | Core invariant、Adapter predicate、deduplication、state transition、local failure classification | 実Runtimeのcallback、transport、storage反映、Hook enforcement | Local implementation requirementだけを`PASS`候補にできる。Test数はRuntime coverageにならない | Positiveと対応negative caseがあり、実Runtimeで確認すべき観測点が特定されている |
| Synthetic bounded test | Controlled fixture / Probeでの限定workflow、計測可能なeffect、profile固有correlation | Real taskの妥当性、通常利用全般、Field Evidence、未宣言tool | 実行環境とaccepted endpointに限定したsynthetic requirement。Executionがlocalかliveかも併記する | Environment Contract、workload、tool allowlist、stop条件、保持Evidenceが固定されている |
| Live Runtime acceptance | 対象Runtime / surfaceでのnative lifecycle、completion、receipt、fresh read、到達endpoint | 別version / provider / model、field stability、未実行failure、task quality | 固定profileで実測したnamed requirement。観測していない後続endpointは`NOT_RUN`のまま | Required positive caseと、安全に実行可能なnegative caseをreview可能なEvidenceとして保持する |
| External live synthetic Evidence | 外部環境のfixed live profileで実行したbounded synthetic workflow | Field use、maintainer環境での再現、別subscription、独立review前のVerdict | Review前はtester-reported claim。独立review後に、そのprofileのlab-tested requirementへ採用できる | Sanitized bundle、manifest、failure run、environment不足をreviewし、採用範囲を決める |
| Real-task acceptance | Fixed Task Profileの実input / output contract、allowed work、mechanical assessment | 通常利用条件、一般task、content quality、Field Evidence | Maintainer管理のacceptance条件に限定したreal-task requirement。Controlled runならlab testedになり得る | Task inputの共有範囲、Observer / Assessor、quality boundary、no-rerun条件を固定する |
| Field Evidence | 通常利用条件で外部利用者が実taskを行った成功・失敗、運用上の制限 | 全capability、別環境、未観測failure、一般的な安定性 | Fixed field claimとnamed requirement。Field testedであること自体は`PASS`を意味しない | Provenance、privacy、期間、task、成功・失敗、未観測範囲をreviewし、release判断へ別途入力する |

下位段階の`PASS`は上位段階のEvidenceにならない。たとえば、source verificationは
implementationの存在を、unit testはlocal predicateを、live acceptanceは固定Runtimeでの実挙動を
それぞれ支える。三つの結果は併用できるが、相互に代用しない。

## 基本検証順序

新しいRuntime、Support Profile、Task Profileは、原則として次の順に検証する。Fixed profileの
accepted endpointが途中にある場合は、そこまでを評価し、後続段階を`NOT_RUN`またはprofile scope外と
記録する。存在しない後続機能を、E2Eを完了させるために別Runtimeのprimitiveで補わない。

1. **Environment / version固定**
   Environment Contractを記録し、取得できない値を`UNKNOWN`にする。既存profileの値を推測で移さない。
2. **Static contract確認**
   Named requirement、positive / negative case、accepted endpoint、stop条件、Evidence sourceを固定する。
3. **Offline negative cases**
   Invalid schema、missing identity、stale revision、unknown field、manifest mismatchなどをRuntime I/Oなしで
   拒否できることを確認する。
4. **Lifecycle observation**
   Native eventの発生源、順序、terminal条件、欠落検出、host-local captureを確認する。
5. **Work admission / deny**
   Allowlist内のworkをadmitし、明示deny時に対象side effectが0であることを別観測で確認する。
6. **Active / pending / incorporated**
   Profile固有の状態遷移、result identity、observation lossを確認する。Semantic understandingを推定しない。
7. **Verified boundary**
   Relevant workのsettle、revision、workspace、Trusted ObserverのEvidenceが揃うまでboundaryをverifyしない。
8. **Transition request**
   Durable checkpoint、one-shot authority、final freshness check、actual dispatchを分離して記録する。
9. **Completion proof**
   Request acceptanceではなく、profile固有predicateとnative / storage readbackでcompletionを判断する。
10. **Handoff delivery**
    Durable handoffとtarget identityを対応付け、transportへのdeliveryをreceiptから分ける。
11. **Explicit receipt**
    Profile固有identityまたはhost-mediated protocolでreceiptを確認し、後続work成功で代用しない。
12. **Fresh observation**
    Receipt後のcurrent Runtime / task / workspaceを読み、old checkpointやold instructionを除外する。
13. **Continuation**
    One-shot permitを対象dispatchへ対応付け、未完了workだけを一回実行する。
14. **Task assessment**
    Task ProfileのTrusted Observer / Task Assessorでsame-task、nonduplication、mechanical effectを判断する。
15. **`RESUME_VERIFIED`**
    Receipt、freshness、continuation、assessmentを相関した`ResumeProof`をCoreが受理したことを確認する。
16. **Failure / uncertainty cases**
    Timeout、missing / malformed result、late / duplicate Evidence、unknown write / sendを、side effectの可能性に
    応じて分類する。
17. **Restart等の追加scope**
    Restart、reconnect、power loss、repeated transition、parallel workは別claimとして個別に追加する。
18. **Evidence review**
    RunごとのEvidenceをrequirementへ対応付け、CoverageProfile、Known Limitations、accepted endpointをreviewする。

各段階には、段階固有のEvidence referenceと結果を持たせる。最終stateだけを記録したE2Eは、どの
identity、gate、readbackが成立したかを独立reviewできないため、全段階のEvidenceにはならない。

## Environment Contract

Runを開始する前に、次の値を固定する。固定とは、設定した値だけでなく、実際に利用するbinary、source、
owner、workspace、storageとの対応を記録することを指す。

| 分類 | 最低限記録する値 |
|---|---|
| Yohaku artifact | Yohaku commit、package version、wheel / artifact SHA-256、build source association |
| Adapter tooling | Adapter、collector、harness、plugin、fixtureのrevisionまたはhash |
| Runtime | Runtime family、exact version、source revisionまたはbinary hash、surface |
| Host | OS / distribution / architecture、Pythonまたはhost runtime version |
| Provider | Provider、backend、model、reasoning設定、endpoint種別 |
| Local model | Model digest、quantization、template、backend version。該当しない場合はnot applicableとする |
| Context | Context limit、compaction / compression設定、threshold、prompt / system configurationの識別子 |
| Integration | Hook、plugin、permission、allowlist、output format、collector設定 |
| Ownership | Single owner、dedicated / fresh session、既存session非採用、parallel / external client条件 |
| Paths | Task workspace、Yohaku storage root、Runtime-native storage root。公開bundleでは必要に応じて匿名化する |
| Contract | Support Profile ID、Transition Strategy、Task Profile ID、tool allowlist、accepted endpoint |
| Limits | Timeout、request budget、token budget、cost boundary、最大transition数 |
| Retry | Retry禁止条件、許可するreconciliation、rerun時のnew run ID規則 |

値を取得できない項目は推測で埋めず、`UNKNOWN`として記録する。`UNKNOWN`を既存profileの既知値で
補完せず、Verdictへの影響をreviewする。環境差がclaimへ影響しないと判断する場合も、その理由と
source associationをreview recordへ残す。

Run中にEnvironment Contractが変化した場合は、同一runの成功条件を維持できるか判断する。Runtime、
model、surface、Strategy、Task Profile、owner、tool集合などprofileを固定する値が変わった場合は、原則として
runを停止し、別run IDと新しいprofile claimで再開する。

## Positive / negative caseの対応

各capabilityには、正常系と、その正常系が誤って成立しないことを確認するnegative caseを対応付ける。
Positive caseの成功だけでは、missing / stale / duplicate / uncertain outcome時のfail-closedを証明しない。

### Work admission

| Case | 必要な観測 |
|---|---|
| 正常allow | Exact tool / operation、owner、turn、argumentsのallowlist一致と、admitted operationのresult |
| Explicit deny | Deny reason、対象identity、handler非実行、後続event |
| Deny時のside effect 0 | Trusted fixture counter、workspace diff、provider request countなど、対象effectを観測できる別source |
| Gate外operation | Coverage外として記録し、Runtime-wide denyやatomic barrierを主張しない |

Hookがdenyを返したことだけではside effect 0を証明しない。Runtimeがhandlerを実行しなかったことを、
対象effectを観測できるauthorityから確認する。

### Completion

| Case | 期待する扱い |
|---|---|
| 正常completion | Exact request / session / generationとprofile固有signal / readbackが揃った一件だけを受理する |
| Missing signal | Completionを成立させず、dispatch済みの可能性があれば`AMBIGUOUS` |
| Stale signal | Current generationへ採用せず、stale Evidenceとして保持する |
| Wrong request / session / generation | Foreign evidenceとして拒否し、別identityで補正しない |
| Exact duplicate | No-op。二つ目のhandoff、permit、continuationを作らない |
| Late Evidence | Matching correlationとprofile固有reconciliationがある場合だけ照合する |
| Unchanged Runtime state | Engine returnやACKで補わず、completion不足として扱う |
| Storage mismatch | Host projectionとnative readbackを一致扱いにせず、通常作業へ進めない |

### Receipt

| Case | 期待する扱い |
|---|---|
| Correct receipt | Handoff、target、owner、continuation、native tool lifecycleをprofile規則で相関する |
| Wrong identity / nonce | Receiptを拒否し、値を補正・再発行しない |
| Duplicate | No-opまたは明示拒否。二つ目のcontinuation authorizationを作らない |
| Stale | Old handoff / generationへ対応するreceiptをcurrent recoveryへ採用しない |
| Wrong owner | Foreign receiptとして停止し、ownerを暗黙に移さない |
| Post欠落 | Handler returnだけでreceiptを成立させない |
| Result mismatch | Native resultとadapter resultを一致扱いにせず、fresh observationへ進まない |

### Fresh observation

| Case | 期待する扱い |
|---|---|
| Current state | Receipt後に取得したRuntime / task / workspace revisionが安定し、handoffと同じlogical taskを示す |
| Stale checkpoint | Historical dataとして保持し、current stateへ昇格させない |
| Changed input / workspace | Old continuation authorizationをinvalidateし、再検証する |
| Old instruction | Historical instructionをcurrent permission / next actionとして実行しない |

### Continuation

| Case | 期待する扱い |
|---|---|
| Unfinished work | Fresh observationとTask Assessorが未完了と判断したworkだけを一回実行する |
| Completed work | 再実行せず、nonduplication Evidenceを残す |
| Undeclared work | Task / operation layerで`REFUSED`とし、scopeを拡張しない |
| Send uncertainty | Permitを復元せず`AMBIGUOUS`とし、blind retryしない |

Runtimeへ安全にfault injectionできないcaseは、offline fixtureまたはlocal synthetic testで確認できる。
その結果はlocal failure-classification requirementを支えるが、live Runtimeのfailure enforcementを
`PASS`にしない。Live caseが危険、費用超過、または観測不能なら`NOT_RUN`と理由を記録する。

## `AMBIGUOUS`とno blind retry

Side effectの有無を否定できないunknown outcomeは`AMBIGUOUS`である。Timeoutやmissing outputを
「実行されなかった」と推定すると、二重transition、二重write、二重continuationを起こし得る。

| Uncertain case | 確認する挙動 |
|---|---|
| Dispatch後timeout | Consumed authorityを戻さず、同じrequestを再送しない |
| Completion不明 | Handoff / continuationへ進まず、matching completion Evidenceだけを照合する |
| Write uncertainty | Open handleまたはownerをpoisoned / stoppedとして扱い、同じwriteを繰り返さない |
| Continuation send uncertainty | Permitを再発行せず、新しいcontinuation turnをblindに作らない |
| Late Evidence | Retained request、session、generation、ownerへ一意に相関できる場合だけprofile規則でreconcileする |

各caseでは、次をEvidenceとして確認する。

- Blind retryを行っていない
- Duplicate request、handoff、receipt、continuationを作っていない
- 成功・失敗・timeoutまでのretained Evidenceを保持している
- 許可された操作がcurrent-state inspectionとmatching late Evidenceの照合に限定されている
- Reconciliationできない場合は通常作業を再開していない

`AMBIGUOUS`はCapability Verdictではない。Requirementが「unknown outcomeでfail closedに止まること」を
求める場合、その挙動をEvidence Modelに従って評価する。一方、requested transition自体のcompletionを
証明できなければ、そのcompletion requirementを`PASS`にしない。

## Evidence bundle contract

Evidence bundleは、raw/private observationをそのまま公開するcontainerではない。外部testerまたは
maintainerが共有するbundleは、allowlistで選んだsanitized Evidence、manifest / hash、run metadata、
reviewに必要な制限をまとめる。論理的に次の情報を含めるが、共通file schemaが実装済みであるとは
仮定しない。

| Bundle項目 | 最低限の内容 |
|---|---|
| Identity | Support Profile ID、run ID、Evidence Record IDが割り当て済みならその値 |
| Runtime environment | Runtime family / version / source revision、surface、OS、Python / host runtime |
| Yohaku environment | Yohaku commit / wheel hash、Adapter / collector / harness revision |
| Provider configuration | Provider / backend / model、取得できる場合はmodel digest / quantization / context設定 |
| Contract binding | Transition Strategy、Task Profile、tool allowlist、accepted endpoint |
| Environment Contract | Run前に固定した値、`UNKNOWN`、run中の差分 |
| Event projection | Allowlisted lifecycle、ordering、terminal、storage readbackのsanitized projection |
| Correlation | Request / session / generation / attachment / continuationのrun-scoped匿名化対応 |
| Capability observations | Requirementごとのpositive / negative observation、未観測項目 |
| Result | 実際に到達したendpoint、failure stage、issues、uncertain state |
| Usage | 取得可能なrequest、token、time、cost等。取得不能なら`UNKNOWN` |
| Verdict candidate | Testerまたはproducerが提案するrequirementごとの候補。Reviewer resultではない |
| Review state | `tester-reported`、`pending review`、review済みresultへの参照 |
| Integrity | Source / artifact / bundle fileのhash、manifest、sanitization version |
| Relationships | Prior runへの`relates-to` / `supersedes`、同一profile内のrerun関係 |

Event projectionは、reviewに必要なidentity、sequence、result class、hash、count、freshnessを残す。
Raw prompt、response、tool payloadを含めなければcorrelationを確認できない設計は見直し、trusted hostが
必要metadataをcaptureする。Sanitization後に独立reviewできないfieldは、欠落理由と影響するclaimを
bundleへ記録する。

Manifest validationが確認するのはbundle byteの整合性である。Bundleがschemaとallowlistを満たしても、
Runtime eventの真正性、capability、accepted endpoint、Verdictは確定しない。

## Privacy / sanitization

Shared bundleとpublic summaryには、次を含めない。

- Credential、token、API key、cookie、authentication secret
- Account ID、個人を特定できるtester ID
- Private conversation、private task本文、private repository identifier
- Secret、非公開source、公開不要なenvironment variable
- Claimに不要なabsolute path、user名、home / temporary directory
- Raw prompt / response全文
- Correlationや判定に不要なtool argument / output
- Runtime state DB、private transcript、session storeそのもの
- Receipt nonceや再利用可能なnative session credentialの原値

Sanitizationはallowlist方式を基本とし、共有可能fieldだけを選ぶ。Secretを直接hashした値も、入力候補が
狭ければ推測に使われ得るため、公開用correlation IDとして流用しない。必要なidentityにはrun-scopedな
opaque labelまたはsalted transformationを使い、変換規則と保持者をprivate recordへ記録する。

匿名化によってrequest / session / generation correlation、freshness、storage一致を独立reviewできなく
なった場合は、そのclaimを`PASS`へ昇格させない。Bundleには、削除したfield、削除理由、review不能に
なったrequirementを記録する。

Raw/private observationの保持にもprivacy policyを適用する。Secret-bearing raw dataを安全上削除・隔離する
必要がある場合は、Evidence Record自体を消さず、削除対象、理由、時点、失われたreview可能性を記録する。

## External tester workflow

外部testerには、実行前にSupport Profile、Environment Contract、budget、stop条件、共有範囲を提示する。
Testerは次の条件でrunを行う。

- 自身のsubscription、API access、またはlocal backendを使用する
- Credential、token、cookie、account accessをmaintainerへ渡さない
- 明示したrequest、token、cost、time budget内だけで実行する
- Existing sessionを再利用せず、指定されたfresh profile / owner / storageを使う
- Success runだけでなく、timeout、failure、mismatch、incomplete runも返す
- Rerunは新しいrun IDとbundleとして保存し、以前のbundleを書き換えない
- Raw/private dataではなく、allowlistに基づくsanitized Evidenceだけを共有する
- Real taskの場合は、task本文、artifact、path、公開転載の範囲を実行前に合意する
- Stop条件に達した後は、completion確認のためのblind retryや追加provider requestを行わない

受領時には、bundleをまず`tester-reported`または`pending review`として保持する。Environmentの不足、
manifest、correlation、accepted endpoint、negative result、sanitization limitationを独立reviewした後にだけ、
該当requirementのEvidenceとして採用する。

External runを受け取っただけでCapability `PASS`、Field Evidence、maturity、release channelへ自動昇格
させない。外部testerがlive Runtimeでsynthetic Probeを実行したrecordは、review可能なら
external / live-runtime / syntheticのlab Evidenceになり得るが、real-taskのfield tested recordではない。

## Synthetic、real-task acceptance、Field Evidence

| Workload / use | 条件 | 支えられるclaim | 支えられないclaim |
|---|---|---|---|
| Synthetic | Controlled fixture、Probe、bounded workflow。Effectとidentityを意図的に限定する | Fixed synthetic requirement、Adapter wiring、failure classification | 任意task、通常利用の安定性、Field Evidence |
| Real-task acceptance | 実際のTask Profile contractを使うが、maintainer管理のworkspace、input、owner、acceptance条件で実行する | Fixed Task Profileのmechanical workflow、accepted endpoint | 一般task、未評価quality、通常利用条件、Field Evidence |
| Field Evidence | 外部利用者が通常利用条件で実taskを行い、成功・失敗、期間、環境を保持する | Fixed field claimと運用上の制限 | 全capability、別profile、未観測failure、Stable readinessの自動判定 |

`document-review-report-v1`のaccepted runは、nonfixture real taskを使ったmaintainer管理の
real-task acceptanceである。Dedicated workspace、入力、manual transition、output、assessmentを固定した
lab Evidenceであり、それだけでField Evidenceにはならない。Mechanical completionの`PASS`から文章品質や
事実性も推定しない。

## Test resultとEvidence resultの分離

次の結果は別々に記録する。

| Result | 示すこと | 示さないこと |
|---|---|---|
| Unit tests `PASS` | 実行したlocal testとassertionが成功した | Live Runtime、provider、Hook、Field coverage |
| Harness validation `PASS` | Harness自身のschema、control flow、fixture検査が成功した | Harnessが外部Runtimeを正しく観測したこと |
| Manifest validation `PASS` | 列挙fileのsize / hash / associationがmanifestと一致した | 取得者、内容、Runtime capabilityの真正性 |
| Runtime workflow `PASS` | Fixed environmentで、宣言したworkflowがaccepted endpointへ到達した | 別requirement、別profile、maturity、release readiness |
| Capability Verdict `PASS` | Reviewerがnamed requirementを採用Evidenceで実証済みと判断した | Runtime family全体、未観測scope、quality |

したがって、次の等式は成立しない。

```text
SCHEMA_AND_ALLOWLIST_OK
    != Runtime capability PASS
```

Test countは、実行したassertion数を表すだけである。Requirement、Runtime surface、negative case、
accepted endpointとの対応がなければCoverageの代わりにならない。多数のunit testより、一件のlive
Evidenceが常に強いわけでもない。両者は異なるclaimを支える。

## CoverageProfile review

Run終了後は、次の順でCoverageProfileへの対応をreviewする。既存CoverageProfileを直接上書きせず、
対象profileのreview規則に従ってrevisionまたは新recordを作る。

1. **Scopeを再確認する**
   Support Profile、Task Profile、Strategy、tool集合、accepted endpoint、Environment Contractをrun実値と照合する。
2. **Evidence Recordを列挙する**
   Success、failure、`AMBIGUOUS`、timeout、incomplete、offline negative、external submissionを別recordとして扱う。
3. **Integrityとprovenanceを確認する**
   Source association、artifact hash、manifest、producer、execution、workload、sanitization履歴を確認する。
4. **Named requirementへ対応付ける**
   各recordが何を測り、何を測っていないかをrequirement rowへ記録する。
5. **Authority、freshness、correlationを確認する**
   Self-report、ACK、engine return、stale observationを、より強いEvidenceの代わりにしない。
6. **Positive / negative resultを併記する**
   最良runだけを採用せず、known failure、mixed result、unresolved unknown、repeatabilityを残す。
7. **RequirementごとのVerdictを判断する**
   `PASS` / `PARTIAL` / `FAIL` / `UNSUPPORTED` / `NOT_RUN`はEvidence Modelの定義をそのまま使う。
8. **Overall resultの理由を記録する**
   Required capability、failure safety、repeatability、endpoint、coverage外を一つずつ示す。
9. **Known Limitationsを更新候補にする**
   Missing field、sanitization limitation、unmeasured scope、unsupported restart等をpublic summaryへ対応付ける。
10. **Public canonicalとの整合を確認する**
    Runtime page、Task Profile page、runtime-support table、Support Policyのclaimがreview結果を越えていないか確認する。

Overall `PARTIAL`には、成立した範囲と不足理由を記載する。理由にはEvidence Modelが定めるbounded scope、
limited coverage、evidence insufficiency、degraded path、mixed resultsのどれが該当するかを示す。個別
requirementの確認済みfailureを`PARTIAL`へ弱めず、そのrowは`FAIL`として保持する。

Review前のCapability Verdict候補はVerdictではない。Reviewer resultには、採用したEvidence ID、除外した
recordと理由、requirementごとの判断、overall集約理由、reviewer、review日を残す。

## Evidence retention、rerun、supersede

Evidence Recordは追記を基本とする。

- Failure runを削除しない
- `AMBIGUOUS` runを削除しない
- Success runで過去のfailure、timeout、incomplete resultを上書きしない
- Rerunは新しいrun ID、Evidence Record、timestamp、manifestを持つ
- `supersedes`は、旧recordの削除ではなく新旧relationとして記録する
- Diagnostic runはrelease gateに採用しなくてもretained Evidenceとして保持する
- Historical Evidenceのhash、source association、relative referenceを維持する
- Runtime version、surface、OS、provider、backend、model、Strategy、Task Profile、receipt方式、revisionを越えて自動継承しない

Rerun成功は、旧failureが発生しなかったことにはならない。修正後のrunは、変更commitと新しいenvironmentへ
結び付け、旧failureとの`relates-to`または`supersedes`関係を示す。Repeatabilityを主張する場合は、成功runを
複数持つだけでなく、同一profile条件、試行回数、失敗の有無、許容差をreviewする。

Privacy上raw materialを保持できない場合も、run ID、result、削除理由、残存hash / metadata、review可能性の
低下をEvidence Recordへ残す。Secretを保持するためにretention原則を優先しない。

## Release判断と最小回帰

Alpha、Beta、Stableはrelease channelであり、個別testやCapability Verdictの別名ではない。Release条件は
Support Policyを正本とし、本workflowでは採用Evidenceと変更影響を整理する。

- Alphaで全capabilityの`PASS`は要求しない。Scope外、`PARTIAL`、`UNSUPPORTED`、`NOT_RUN`を明示できる。
- Maintainer local synthetic profileを、必ず自動release gateにするとは限らない。
- Unstable modelや再現性が低いbackendのrunも、failure modeとcompatibilityを示すdiagnostic Evidenceとして保持する。
- Capability `PASS`一件からprofile maturityやrelease channelを自動決定しない。
- 対象scope内の既知のdata corruption、secret exposure、unauthorized / duplicate execution、ambiguous completion成功扱いはrelease blockerとして扱う。

回帰は変更によって影響したpathを基準に選ぶ。慣例的に全profileのfull acceptanceを再実行せず、影響を
説明できる最小集合を実行する。ただし、安全性やserializationのように複数profileへ影響する変更を、
局所変更とみなして狭めない。

| 変更 | 最小回帰候補 | 再acceptanceが必要になる条件 |
|---|---|---|
| Documentationのみ | Link、用語、claim scope、canonical整合のstatic review | Capability claim、profile tuple、accepted endpointを変更した場合 |
| Core state / authority / ambiguity | 関係するunit negative caseと、影響する全profileのbounded workflow | Lease、deduplication、resume gate、failure semanticsが変わる場合 |
| Runtime Adapter / completion | 対象profileのlifecycle、completion positive / negative、late / duplicate | Native event、binding、transport、readback、versionが変わる場合 |
| Storage / restart codec | Integrity、corrupt / partial write、reopen、unsupported拒否 | Schema、namespace、codec、durable orderingが変わる場合 |
| Task Profile | Input / output、allowed work、Observer / Assessor、no-rerun、real-task acceptance | Task contract、tool、quality boundary、Runtime bindingが変わる場合 |
| Collector / sanitizer / manifest | Offline schema / allowlist、redaction、hash、reviewability | Captured event、correlation、freshness、privacy boundaryが変わる場合 |
| Runtime / provider / model / OS | 影響requirementのnew profile run | Profile tupleのdimensionが変わり、旧Evidenceを継承できない場合 |

Runtime patch versionだけが変わった場合も、変更差分がcompletion、Hook、storage、tool lifecycleへ影響するかを
確認する。影響しないstatic factを再利用する場合は理由を新recordへ記載し、旧Verdictを無条件にcopyしない。

## Adapter Contractとのconformance matrix

次のmatrixは、Adapter Contract requirementと検証方法を計画するための最小対応表である。自動conformance
runnerや統一harnessが存在することを意味しない。

| Adapter Contract requirement | Verification type | Required Evidence | Accepted Verdict |
|---|---|---|---|
| Identity separation / correlation | Source verification、offline negative、live observation | Native / Core / host-local inventory、wrong identity拒否、run-scoped mapping | Fixed requirementを全条件で実証した場合だけ`PASS` |
| Work admission / gate | Unit / fixture、bounded live | Allow / deny、side effect 0、gate coverage外 | Declared work planeだけに限定した`PASS`または不足を示す`PARTIAL` |
| Active / pending / incorporated | Fixture、bounded live | State transition、result identity、observation loss、semantic limitation | Profile固有機械条件への`PASS`。Semantic qualityは別assessment |
| Verified boundary | Unit、synthetic / real-task acceptance | Quiescence、revision、workspace、Trusted Observer、stale拒否 | Declared observer scopeに限定したVerdict |
| Completion Policy | Unit negative、live Runtime | Positive predicate、missing / stale / wrong / duplicate / late、native readback | Accepted endpointとprofileに限定したVerdict |
| Handoff delivery / receipt | Offline identity negative、live recovery | Durable handoff、delivery、correct / wrong / duplicate receipt、Post / result相関 | Deliveryとreceiptを別requirementとして判断 |
| Fresh observation | Fixture、live recovery / task acceptance | Receipt後read、stale checkpoint、changed workspace、old instruction拒否 | 観測scopeとfreshness条件に限定したVerdict |
| Continuation / `ResumeProof` | Unit、bounded live / real-task | One-shot permit、unfinished-only、no duplicate、assessment、`RESUME_VERIFIED` | Mechanical resume requirementだけのVerdict |
| Failure / no blind retry | Offline fault、可能なlive failure | Timeout、unknown send / write、retained Evidence、no duplicate dispatch | Offlineとlive enforcementを分けたVerdict |
| Storage / restart | Unit corruption、bounded restart acceptance | Commit / readback、codec、fresh native reconciliation、unsupported拒否 | Restartを実行していなければ`NOT_RUN`を維持 |
| Evidence / privacy | Offline bundle review | Environment、projection、manifest、sanitization、review status、Known Limitations | Bundle requirementのVerdictでありRuntime capabilityではない |

Matrixのrowを埋めただけではconformanceにならない。各rowはEvidence Recordとreviewer resultを参照し、
未実行、coverage外、sanitization欠落を残す。

## Alpha公開前の最小testing documentation

Alpha公開前には、少なくとも次の文書またはtemplate相当のrecordが必要である。共通schemaやtemplate
generatorは現在未実装であり、fixed profileごとに既存形式で保持してよい。

1. Support Profile declaration: Environment dimension、Strategy、Task Profile、tool、owner、accepted endpoint
2. Run plan / Environment Contract: Budget、timeout、retry、stop条件、positive / negative case
3. Capability case matrix: Requirement、verification level、必要Evidence、期待result
4. Evidence bundle checklist: Sanitized metadata、event projection、correlation、issues、manifest / hash
5. Reviewer worksheet: 採用 / 除外Evidence、Verdict候補との差、CoverageProfile対応、Known Limitations
6. External tester runbook: Credential boundary、fresh profile、budget、共有範囲、failure返却、rerun規則
7. Regression impact record: 変更path、影響profile、実行 / 非実行理由、再acceptance範囲

これらの文書が存在してもAlpha公開条件を自動的には満たさない。Support Policyが要求するprofile maturity、
主要workflowのlab Evidence、導入・停止・復旧手順、Known Limitations、Issue受付を別途reviewする。

## 現在の実装との差

現在のYohakuには、profile固有のProbe、acceptance record、CoverageProfile、manifest、sanitized external
bundleがある。一方、次の共通機能は完成していない。

- Probe / acceptance harnessはprofileごとに異なり、共通の実行interfaceはない
- Environment、producer / execution / workload、issues等に自由記述fieldが残る
- Raw/private observation、sanitized Evidence、manifest、reviewer result、public summaryを横断する共通Evidence indexは未完成
- Public runtime-support table、Runtime canonical、CoverageProfileの整合は一部manual reviewで維持している
- Field Evidenceは取得していない
- 全Runtime共通のconformance runner、negative-case runner、bundle generatorは存在しない
- Evidence bundle schema、sanitization profile、review worksheetは全profileで統一されていない
- Test resultからCoverageProfileを自動生成・更新する仕組みはない

したがって、本書は完成済みの統一testing frameworkの操作説明ではない。開発者とreviewerが、既存の
profile固有harnessとretained recordを同じ安全semanticsで評価するためのworkflow contractである。

## 本workflowの非責務

本書は次を実装または実行しない。

- Test harness実装
- Evidence schema migration
- Telemetryの追加・有効化
- CI構築
- 新しいCapability Probe
- Runtime実行またはprovider request
- 製品コード / test codeのrefactor
- 既存Evidence、CoverageProfile、Capability Verdictの再採点
