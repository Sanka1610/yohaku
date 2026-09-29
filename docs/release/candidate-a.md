# Candidate A release review

Candidate AのAlpha候補は`codex-operational-0.158`（C-OP）と
`codex-document-review-report-v1`（C-DRR）だけである。現在は両profileとも
`experimental`、release channelは`undeclared`であり、公開承認は成立していない。
Hermes / Claude Code CLIはexperimental / measured Evidenceとして保持し、Alpha候補の
support scopeへ含めない。

## Release claimの参照順

1. [Release-scope declaration](candidate-a-scope.json)が候補ID、profile、Runtime、endpoint、
   Evidence参照、除外、required artifact checksを固定する。
2. [Minimal Evidence index](candidate-a-evidence.json)がC-OP / C-DRRの既存Record IDを
   source commit、manifest hash、retained artifact hash、review結果に結び付ける。
3. MaintainerはRecord IDをprivate locatorで解決し、原位置のretained Evidenceを照合する。
   公開indexの`private_source_ref`はopaqueなRecord IDであり、pathではない。
4. [Stage 1 source-drift record](stage1-source-drift.json)でaccepted sourceと
   `84b34f8eff42d5b2a46b9ce1b38913a35bd8f25b`の差分とreview decisionを確認する。
5. Static checkがreview済みsourceとcurrent implementation、およびcanonical文書の検証表を照合する。

Declarationの`alpha_scope_profile_ids`は将来のAlpha候補範囲を意味する。
`release_candidate_id`はreview用識別子であり、package versionではない。後続release reviewでは
declaration、canonical検証表、registry、checkerのallowlistを同じ変更内でreviewする。
既存indexやsource-drift recordは新しいacceptanceの結果で上書きせず、新recordを追加する。

## Static check

Repository rootで実行する。Python標準ライブラリとlocal sourceだけを使う。
BaselineのGit objectも必要なため、source archiveや該当履歴のないshallow checkoutでは成功しない。

```sh
python3.14 scripts/check_candidate_a.py
PYTHONPATH=src python3.14 -m unittest discover -s tests -p test_candidate_a_release.py -q
```

Mismatch、missing record、unknown field、重複JSON key、未reviewのsource変更はexit code `1`。
Release validationはこのcheckの成功を必須とし、失敗時はrelease reviewを停止する。
成功が示すのはCandidate Aのstatic consistencyと公開recordのallowlist適合だけである。
Provider acceptance、Evidenceのauthenticity、release artifactの適合、公開可否は別のreviewを要する。

照合するfieldはMapping key、Support Profile ID、Runtime family / exact version、surface、
Task Profile ID、operational launcher support、task runner support、maturity、release channel、
accepted endpoint、Evidence Record ID、Known exclusionsである。RegistryのKnown Limitationsは
review時の配列hashとも照合する。Candidate A以外のregistry profileとHermes / Claudeの除外も検査する。

検証表は[Runtime support](../runtime-support.md)、[Runtime mapping](../runtime-mapping.md)、
[Codex canonical](../runtimes/codex.md)、[Task canonical](../task-profiles/document-review-report-v1.md)、
[Support Policy](../../SUPPORT_POLICY.md)の`candidate-a:start` / `candidate-a:end`内に置く。
この表がCandidate A release fieldの検証対象である。本文の説明や段落順は自動照合せず、
検証表と本文の意味が一致することは文書reviewで確認する。

`operational_launcher_support=true`はregistryの`launch_supported`を表す。
C-DRRのtaskを起動するentry pointは`run`であり、lifecycle-onlyの`start`によるtask実行を意味しない。

## Minimal Evidence indexの責務

Indexはrelease claimから既存Evidenceへ辿る参照情報である。Evidence本体、Capability Verdict
自動判定器、CoverageProfile generator、public telemetry、raw transcript storeではない。
`reviewer_result=retained-bounded-PASS`は既存review結果の参照であり、今回の再採点ではない。
`producer=maintainer`は既存runの実施主体を表し、新たな独立第三者reviewを意味しない。

各recordにprofileとTask Profile、private sourceのRecord ID、sanitized sourceの公開状態、
source manifest SHA-256、retained wheel / result / acceptanceのSHA-256、source commit、
producer、execution、workload、accepted endpoint、review結果、public summary、exclusions、
`relates_to` / `supersedes`を持たせた。`supersedes=[]`は既存Evidenceを置換しないことを示す。
`relates_to`の`STAGE1-SOURCE-DRIFT-84B34F8`は新しいsource review recordである。

Sanitized raw bundleは両recordとも`not public`である。公開summaryとraw bundleのsanitizationを
混同しない。Artifactのhashは既存retained artifactを指し、これから配布するrelease artifactの
hashではない。Manifest / hashの一致は内容の同一性を示すが、runの真正性を単独では証明しない。

<a id="c-op"></a>
## C-OP

`C-OP` → `codex-operational-0.158` → `S5-OP-CODEX-0158`を結ぶ。
Source associationは`92a82de662672240ca3b57bc8e498eeaf250a5f2`。Retained manifest内の
source hashをこのcommitと照合した。Executionはnative lifecycle / no inference、workloadは
lifecycle-onlyである。

Accepted endpointの`native-start-status-stop-fresh-lifecycle`は、dedicated App Serverの
startup、fresh thread、status、stop、clean stop後のfresh lifecycleを表す。既存reviewは
この範囲でPASS。Task transitionはNOT_RUNであり、C-DRRやhistorical Referenceのtransition
Evidenceを継承しない。Source-drift recordはcurrent codeへの参照であり、C-OPを再測定した記録ではない。

<a id="c-drr"></a>
## C-DRR

`C-DRR` → `codex-document-review-report-v1` → Task Profile `document-review-report-v1`
→ `DRR-V1-CODEX-0158-LIVE-01`を結ぶ。Source associationは
`76c086cc4381af9488fb511a191b899d7279f0af`。Accepted manifestの14 tracked fileすべてが
このcommitと一致する。Executionはlive Runtime、workloadはmaintainer管理のnonfixture real taskである。

Accepted endpointは`RESUME_VERIFIED`かつmechanical completion PASS。二つの宣言入力、
fresh session一つ、manual compact一回、create-only report一つの固定workflowだけに適用する。
Writing / factual qualityはNOT_ASSESSED、overall product coverageはPARTIAL。
最終accepted runに加え、先行するtransition前REFUSED、hardening前の成功、existing outputの
拒否結果も原位置に保持している。Indexが参照するacceptanceは最終accepted sourceに対応する。

<a id="stage1-source-review"></a>
## Stage 1 source review

Accepted manifestを保存したまま、別record `STAGE1-SOURCE-DRIFT-84B34F8`を追加した。
JSONの`files`に14 tracked fileすべてのold / current SHA-256、MATCH / CHANGED、変更分類を
記録した。3 filesがMATCH、11 filesがCHANGEDである。比較終点はStage 1の`84b34f8`であり、
本ページやStage 2の検証表追加による文書変更をそのsnapshotへ混ぜない。

| 対象 | Reviewした変更 |
|---|---|
| `document_review_runtime.py` | credential admissionとoperator status。Credential再検査をRuntime起動・initial turn前に追加し、statusを保守的に投影する |
| `operational.py` | credential admission、preflight / status projection、runnerへ渡すcredential identity。Accepted transition authorityのidentityとは別の検査である |
| `cli.py` | CLI wordingとerror status projection |
| `profiles.py` | registry wording。Candidate Aの登録能力と実行準備状態を分ける |
| `test_document_review_runtime.py` | tests only |
| README、Policy、architecture、operations、runtime support、旧task reference | docs only。Canonical移行を含む |

`document_review.py`、`recovery.py`、`test_document_review.py`はaccepted manifestと同一。
元manifestにない16個の関連sourceもaccepted source commitとStage 1 commitで同一であり、
`supporting_source`にhashを追加した。この追加reviewをoriginal accepted manifestの内容とは扱わない。

| Accepted semantic area | Review根拠とdecision |
|---|---|
| transition authority / dispatch | Initial turn開始以降のrunner処理が同一。Boundary、checkpoint、lease、`request_compact`の順序・引数はUNCHANGED。`controller` / `manual` / `runtime`も同一 |
| completion predicate | `completion.py` / `codex.py`とrunnerのcompletion待機条件はUNCHANGED |
| handoff | `recovery.py`とrunnerの`RecoveredData` / `continue_task`呼出しはUNCHANGED |
| receipt | `recovery.py`、Hook bridge、Runtime eventの相関処理はUNCHANGED |
| fresh observation | `document_review.py`のobservation / readとrunnerの`current_context`利用はUNCHANGED |
| write path | `document_review.py`のcreate-only write、fsync、readbackはUNCHANGED |
| Task Assessor | `document_review.py`の`assessor`とrecovery verificationはUNCHANGED |
| continuation | Handoff後のowned continuation、one-attempt制限はUNCHANGED |

Decisionは`NO_ACCEPTED_SEMANTIC_CHANGE` / `NO_NEW_PROVIDER_ACCEPTANCE_REQUIRED`。
Credential admissionは開始前の拒否を強化する変更であり、runtime invocation orderingの変更箇所を
reviewしたうえで、accepted transition sequenceは変わらないと判断した。新しいprovider acceptanceは
`NOT_RUN`。これはcurrent sourceを用いたlive成功の主張ではない。

## Source変更後の再acceptance rule

Hash差分はreview開始の手掛かりとする。Codeのhashがreview済みsnapshotと異なる場合、checkerは
`SOURCE_REVIEW_REQUIRED`に相当する不一致でrelease validationを停止する。自動live rerunは行わない。
Reviewerは変更を次の区分に分類し、public-safeな別review recordと必要なlocal testを追加する。

| 区分 | 対象 | 必要な判断 |
|---|---|---|
| No new provider acceptance required | docs only、CLI wording、status projection、pre-transition fail-closed admission、test-only、public metadata | Accepted semantic areaを変えず、拒否や表示だけの変更であることを差分と必要なlocal testで確認する |
| Review required | Runtime invocation ordering、identity correlation、storage write / readback、owner lifecycle | 適用するprofile、失敗時の副作用、相関・保存順序への影響をreviewする。意味不明またはaccepted pathへの影響が残れば次の区分へ進む |
| Bounded live re-acceptance required | transition authority、compact trigger、completion predicate、handoff、receipt、fresh observation、continuation、task write、Task Assessor | 変更したbounded pathと対応する拒否条件に限定して再受入する。新runを既存recordへ追記・関連付け、旧runは保持する |

Storage write / readbackがtask outputやfreshness / completion proofを直接変える場合は最後の区分を
優先する。C-OPのowner lifecycleだけが変わる場合は、影響範囲に応じてno-inference lifecycleを
確認する。変更したfile名だけでprovider acceptanceの要否を決めない。未分類の変更はreviewを完了するまで
release blockerとする。後続のlive確認は別途scopeと実行条件を定める。

## Public / private guard

Public JSONは固定keyと値のallowlistを再帰的に検査する。自由入力欄は設けず、可変の文字列は
SHA-256欄だけに限定し、public summaryも既知の文書参照だけを許可する。JSONの余分なfield、
入れ子のprivate field、既知fieldへの本文混入、重複keyは拒否する。エラー出力へ入力値や例外本文を
返さない。Secret pattern grepだけに依存しない。

Record ID、profile、commit、manifest / artifact hash、review result、endpoint、exclusion、
sanitized summaryを公開側で扱う。Raw prompt / response、credential、account、session ID、
nonce、transcript、private path、raw DB、task本文、tool payloadはprivate側に保持する。
公開indexからprivate pathを推定生成せず、maintainerがRecord IDをprivate locatorで解決する。

Privacy regressionはsynthetic canaryでcredential値、`auth.json`内容、input / report本文、
raw exception、tool argument / result、native session ID、receipt nonce、maintainer absolute path、
private workspace pathの混入を検査する。実際の秘密情報をtest fixtureへ取り込まない。
このguardの対象はStage 2の公開JSONとcheck出力であり、将来のrelease bundle全体には別途artifact reviewが必要である。

## Known exclusions

| Code | 除外範囲 |
|---|---|
| `no-runtime-family-support` | Runtime family全体へのsupport一般化 |
| `no-field-evidence` | Field Evidence / field stabilityのclaim |
| `no-other-runtime-os-provider` | 未測定Runtime、version、surface、OS、provider / backend / modelへの継承 |
| `no-general-parallel-background-external-work` | parallel、background、detached、subagent、external workの一般保証 |
| `no-strong-transition-assurance` | Runtime-wide atomic freeze / Strong Transition Assurance |
| `no-inference-or-task-transition` | C-OPのinference / task transition |
| `no-reference-evidence-inheritance` | C-OPへのhistorical Reference Evidenceの適用 |
| `one-fresh-session-one-manual-compact-one-report` | C-DRRのfixed input contract、fresh session一つ、manual compact一回、report一つを超えるworkflow |
| `no-restart-or-repeated-transition` | C-DRR restart / repeated transition / power-loss保証 |
| `quality-not-assessed` | Reportの文章品質・事実品質のPASS claim |
| `no-general-document-coding-shell-mcp` | 任意文書、coding、shell、MCP task |
| `external-writers-not-prevented` | 非協調external writerの排除保証 |

## Required artifact checksの扱い

`candidate-a-drift`、`public-safe-allowlist`、`retained-evidence-hashes`、
`reviewed-source-association`はreviewの前提である。Private locatorのhash照合はmaintainerが別に
実施し、公開checkoutだけのstatic PASSと区別する。

`release-artifact-source-association`、`release-artifact-content-review`、
`release-artifact-installation`は後続reviewへの要求であり、このStageの成功結果ではない。
Declarationの`release_artifact_status=NOT_CREATED`を維持し、後続release recordで結果とartifactを結び付ける。
