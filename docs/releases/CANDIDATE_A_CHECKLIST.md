# Candidate A release checklist

Release review用の未完了checklistです。各項目の根拠を[release record](RELEASE_TEMPLATE.md)に記録してから
checkします。Capability Verdict generatorではなく、全項目のcheckだけでも公開を承認しません。

Scope / Runtime / endpoint / exclusionは[Stage 2 declaration](../release/candidate-a-scope.json)、
Evidenceは[Candidate A index](../release/candidate-a-evidence.json)、accepted sourceとの差分は
[Stage 1 source-drift record](../release/stage1-source-drift.json)を参照します。Release source時点の
commit / hashをrecordへ固定し、これらの一覧をchecklistへ手入力で複製しません。

## Scope and release decisions

- [ ] `SCOPE_MATCH` — Candidate A scopeがdeclarationと一致する。
- [ ] `EXCLUSIONS` — Excluded Hermes / Claude profilesはAlpha support外のままである。
- [ ] `MATURITY_CHANNEL` — Stage 5のELIGIBLEに基づくCandidate A alpha / Product Alphaが一致し、publicationとは分離されている。
- [ ] `SOURCE_FIXED` — Exact source commitを固定し、clean状態とsource associationを確認した。
- [ ] `VERSION_FIXED` — Package version、release identifier、release channelを別々に確定した。
- [ ] `TERMS_RESOLVED` — Apache-2.0 / LICENSEをexact artifactで検証し、recordで`LICENSE_DECISION_REQUIRED`を解消した。
- [ ] `ISSUE_INTAKE` — Public Issue intakeが利用可能。現在のblockerは`REPOSITORY_SETTING_REQUIRED`。

## Exact artifact and verification

- [ ] `WHEEL_BUILT` — Exact sourceからwheelをbuildし、build environment / backend versionを記録した。
- [ ] `DIGEST_FIXED` — Artifact filename / size / SHA-256 / `SHA256SUMS` / 取得先を固定した。
- [ ] `PYTHON_311` — Exact artifactのCPython 3.11検証結果を記録した。
- [ ] `PYTHON_314` — Exact artifactのCPython 3.14検証結果を記録した。
- [ ] `INSTALL_CONTENTS` — pip check、wheel/source member比較、CLI check、public-safe内容reviewを完了した。
- [ ] `C_OP_SMOKE` — C-OP no-inference lifecycle smokeがPASS。結果を当該artifact digestと結び付けた。
- [ ] `C_DRR_DIFF` — C-DRR semantic diffをaccepted source / Stage 1 reviewからrelease sourceまでreviewした。
- [ ] `REACCEPTANCE` — Live再受入のREQUIRED / NOT_REQUIREDと理由を記録し、REQUIREDならbounded受入を完了した。
- [ ] `EVIDENCE_INDEX` — Indexの参照、採用scope、private retained artifact hashのmaintainer照合が成立した。
- [ ] `DRIFT_CHECK` — Stage 2 drift checkerがrelease sourceでPASSした。

## User documentation and final review

- [ ] `RELEASE_NOTES` — Release notesを完成させ、recordのscope / artifactと一致させた。
- [ ] `UPDATE_ROLLBACK` — Upgrade / rollback、exact prior artifact、方向別storage compatibilityを記録した。
- [ ] `SUPPORT_BOUNDARY` — Privacy / security受付方法を確認し、contact linksをdefault branchで到達可能にした。
- [ ] `ZERO_BLOCKERS` — Unresolved blocker = 0をreviewerが確認した。

Repository rootで実行する必須static gate:

```sh
python3.14 scripts/check_candidate_a.py
```

[Checker](../../scripts/check_candidate_a.py)が失敗したらrelease validationを停止します。PASSはlive acceptance、
artifact review、Issue受付の実用性を代替しません。Source変更は
[再acceptance rule](../release/candidate-a.md)で分類し、hash差分だけで一律live rerunしません。

Runtime compatibility、package installability、storage compatibility、Task Profile rerun可否はrelease recordの
別行でreviewします。未実行・未確認事項を成功としてcheckしないでください。
