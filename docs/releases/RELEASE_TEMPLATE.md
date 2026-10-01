# Release record — TEMPLATE

**未記入template。Release承認・公開・artifact作成の記録ではありません。**
このfileを同directory内のrelease別fileへコピーし、`TBD`をreview済み値に置き換えます。
Public-safe ID / digest / sanitized summaryだけを記載し、private pathやraw Evidenceを含めません。

Local RC validationではscope declarationの`release_candidate_id`を使用します。
現在のlocal RC identifierは`yohaku-0.1.0a1-rc3`です。公開release名の決定ではありません。
検証record / notesはworkspaceに保持し、RC source commit固定後はsourceを編集しません。

## Release identity

| Field | Value |
|---|---|
| Yohaku release identifier | TBD |
| Package version | TBD — release identifier / channelと別field |
| Release channel | Alpha — current channel。Publication BLOCKED_EXTERNAL |
| Source commit | TBD — full commit、clean source |
| Tag | TBD — 対象commitとの対応を確認 |
| Review date | TBD |
| Reviewer | TBD — 公開用識別子 |
| Review decision | PENDING |
| License / distribution terms | Apache-2.0 / [LICENSE](../../LICENSE) — exact artifact metadata / LICENSE memberの検証: PENDING |

`LICENSE_DECISION_REQUIRED`は、exact artifactの`License-Expression: Apache-2.0`、
`License-File: LICENSE`、LICENSE memberと標準本文の一致を検証したRC recordで解消します。
License方針の確定だけではartifact integrationの検証完了を意味しません。

Package `0.1.0a1`はPublished Alphaを意味しません。Version、profile maturity、channelをそれぞれreviewします。

## Alpha scope

[Candidate A declaration](../release/candidate-a-scope.json)をこのreleaseのscope sourceとして採用します。
以下の値は指定fieldを読み取ってreviewし、別一覧として手入力で複製しません。

| Record field | Declaration field / review |
|---|---|
| Scope source commit / SHA-256 | TBD / TBD — release sourceで固定 |
| Included Support Profiles | `alpha_scope_profile_ids` |
| Excluded Support Profiles | `excluded_profile_ids`、`excluded_runtime_families` |
| Included Task Profiles | `profiles[].task_profile_id`のnull以外 |
| Runtime exact version / surface | `profiles[].runtime_exact_version` / `surface` |
| Accepted endpoint | `profiles[].accepted_endpoint` |
| Profile maturity | `profiles[].maturity`、変更review: PENDING |
| Scope一致とHermes / Claude除外のreview | PENDING |

## Evidence

| Reference / decision | Commit / SHA-256 / public-safe result |
|---|---|
| [Stage 2 scope declaration](../release/candidate-a-scope.json) | 上記scope sourceと同一 |
| [Candidate A Evidence index](../release/candidate-a-evidence.json) | TBD / TBD |
| [Stage 1 source-drift review](../release/stage1-source-drift.json) | TBD / TBD |
| Stage 1 review以降からrelease sourceまでの差分review | TBD — public-safe record reference |
| CoverageProfile references | TBD — profileごとのpublic-safe ID / manifest hash / summary。Privateならnot public |
| Accepted Evidence | Index内の採用Record IDsと限定claim: TBD |
| Excluded Evidence | 対象外Record ID / profileと除外理由: TBD |
| Retained Evidence hash review | NOT_RUN — maintainerの確認結果とreview日 |
| Unresolved unknowns | TBD — 不明範囲を列挙。解決済みならnoneと根拠 |

Capability VerdictやCoverageProfileをこのrecordで再生成しません。Stage 2 indexのPASSはartifact適合や
公開承認ではありません。[Source-drift rule](../release/candidate-a.md)に基づき差分をreviewします。

## Artifact

| Field | Value |
|---|---|
| Wheel filename | TBD — basename |
| Size in bytes | TBD |
| SHA-256 | TBD |
| Source association | TBD — exact commit、wheel/source比較の記録 |
| Python build environment | TBD — Python / OS / build tool versions、private pathなし |
| Build backend / exact version | TBD |
| Artifact download location | TBD — 公開取得先。Local pathや認証付きURLは禁止 |
| SHA256SUMS | TBD — 公開checksum fileへの参照、上記digestとの一致 |

## Verification

Resultは実施内容に応じて`PASS` / `FAIL` / `PARTIAL` / `NOT_RUN`を記録し、tested artifact SHA-256を
上記artifactと結び付けます。Test成功を他profileのCapability Verdictへ転用しません。

| Check | Result | Artifact / source reference、範囲、reviewer |
|---|---|---|
| CPython 3.11 | NOT_RUN | TBD |
| CPython 3.14 | NOT_RUN | TBD |
| pip check | NOT_RUN | TBD |
| Wheel/source member comparison | NOT_RUN | TBD |
| CLI check | NOT_RUN | TBD |
| C-OP no-inference lifecycle smoke | NOT_RUN | TBD — start / status / stop / clean-stop後fresh lifecycle |
| C-DRR semantic diff review | NOT_RUN | TBD |
| C-DRR live re-acceptance requirement | PENDING | REQUIRED / NOT_REQUIRED、理由、reviewer。必要ならrun record参照 |
| Candidate A Evidence index / drift check | NOT_RUN | 下記commandの結果、source commit |
| Public-safe artifact / record review | NOT_RUN | TBD |

Repository rootで[Stage 2 checker](../../scripts/check_candidate_a.py)を実行します。

```sh
python3.14 scripts/check_candidate_a.py
```

失敗時はrelease validationを停止します。`NOT_REQUIRED`はC-DRR再受入が不要とのreview decisionであり、
新しいlive PASSではありません。Semantic changeがあれば必要なbounded再acceptanceを別recordへ残します。

## Known Limitations

| Topic | Release-specific disclosure |
|---|---|
| Candidate A scope | Declarationの`known_exclusions`とprofile別除外を参照して記載: TBD |
| Restart | TBD — C-DRR restart未対応を明示 |
| Power loss | TBD — 未受入範囲を明示 |
| External writer | TBD — 非協調writerを排除しない |
| Parallel / background | TBD — 一般coverageなし |
| Content quality | TBD — mechanical completionとquality NOT_ASSESSEDを分離 |
| Field Evidence | TBD — 未成立の範囲を明示 |
| Excluded Hermes / Claude profiles | Declarationの除外を維持しexperimental / measured Evidenceと区別: TBD |

## Support and compatibility

| Field | Value / reference |
|---|---|
| Issue intake | REPOSITORY_SETTING_REQUIRED — public受付可否の確認日・方法・URL: TBD |
| Privacy / security reporting boundary | [Issue reporting](../issue-reporting.md)、release時点の確認済みprivate窓口または未成立の明示: TBD |
| Upgrade / rollback | [公開policy](../update-and-rollback.md)、当該release固有の補足: TBD |
| Exact prior artifact / digest | TBD — rollback先を固定 |

互換性は以下の独立した行で記録します。Storageの`COMPATIBLE` / `INCOMPATIBLE` / `NOT_ASSESSED`は
Capability Verdictではありません。Source → target、schema / record、operation、根拠を指定します。

| Dimension | Scope | Result / policy | Evidence / reason |
|---|---|---|---|
| Runtime compatibility | exact version / surface / environment: TBD | NOT_ASSESSED | TBD |
| Package installability | wheel / Python / OS: TBD | NOT_RUN | TBD |
| Storage compatibility — upgrade | source → target / record / operation: TBD | NOT_ASSESSED | TBD |
| Storage compatibility — rollback | target → prior / record / operation: TBD | NOT_ASSESSED | TBD |
| Existing experimental state | source → initial Alpha: TBD | NOT_ASSESSED、automatic upgrade対象外 | Fresh config / state for new work |
| Task Profile rerun / restart | C-DRR | Completed / uncertain taskのrerun不可、restart未対応 | [Task canonical](../task-profiles/document-review-report-v1.md) |

## Final review

- [Candidate A checklist](CANDIDATE_A_CHECKLIST.md)の各項目と根拠: TBD
- Unresolved blocker count / IDs: TBD — 0を確認できるまで承認しない
- Release notes: TBD — 完成したnotesへの参照
- Final decision / reviewer / date: PENDING / TBD / TBD

このtemplateの存在やcheckboxの数から公開承認を自動生成しません。
