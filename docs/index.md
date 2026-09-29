# Documentation Index

Yohakuの公開文書は、知りたい内容から選べるように整理しています。このページがnavigation canonicalです。初めて試す場合はGetting Startedから進んでください。Support claimを確認する場合は、Runtime SupportとEvidence / Support Policyを併せて参照します。

## Canonical document policy

- 日本語文書が現在のpublic canonicalです。
- Current canonicalと、historical / compatibility documentおよびretained Evidenceは分けて扱います。
- Runtime固有のversion、primitive、completion、Evidence scope、制限は各Runtime canonicalが所有します。
- Taskのinput / output、allowed work、Observer、Assessor、quality boundaryはTask Profile canonicalが所有します。
- Evidence、CoverageProfile、Capability Verdict、provenance、非継承規則はEvidence Modelが所有します。
- Profile maturityとrelease channelの条件はSupport Policyが所有します。

## Getting Started

Yohakuをinstallして、現在公開されている範囲を試す場合に読む文書です。

- [Installation](installation.md): review済みwheelのinstall、Python / environmentの前提、configuration、disable、uninstall
- [Quick Start](quick-start.md): no-inference lifecycleと固定real-task profileの最短手順
- [Operations](operations.md): profile確認、preflight、start、status、stop、recovery inspectionと拒否条件
- [Storage and Recovery](storage-and-recovery.md): checkpoint、journal、handoff、archive、no blind retry、restart時の扱い

## Runtime Support

利用可能な範囲はRuntime名だけで判断せず、profileの固定条件とaccepted endpoint、Evidence、Known Limitationsを確認してください。

- [Runtime Support Summary](runtime-support.md): current profileの横断summary、Evidence provenance、Verdict、公開scope
- [Codex Runtime](runtimes/codex.md): historical Reference、lifecycle-only、`document-review-report-v1`の各profile
- [Hermes Runtime](runtimes/hermes.md): H-CLI-01 Probe、connected adapter、lifecycle-only profile
- [Claude Code CLI Runtime](runtimes/claude-code-cli.md): subscription completion、local recovery profile、formal launcher不在の範囲

## Task Profiles

現在packagedされているreal Task Profileは、Codex向けの`document-review-report-v1`だけです。Fixture固有assessorやlifecycle-only profileをTask Profile supportへ読み替えないでください。

- [Task Profile: `document-review-report-v1`](task-profiles/document-review-report-v1.md): 固定input / output、allowed tools、transition、Observer / Assessor、no-rerun、quality boundary

## Architecture / Design

製品の責務境界と、Runtimeごとの差を設計レベルで確認する文書です。

- [Architecture](architecture.md): component、control flow、trust boundary、shared CoreとRuntime固有責務
- [Runtime Mapping](runtime-mapping.md): fixed profileの比較とYohaku roleからRuntime primitiveへの対応
- [Transition Strategies](transition-strategies.md): Manual In-place Compaction、Native Automatic Compaction、Fresh-context Rollover、Session Migrationのtaxonomy

## Evidence / Support Policy

Evidence Modelは「何を、どのprovenanceとscopeで証拠として扱い、Verdictへ対応付けるか」を定義します。Support Policyは、そのEvidenceとCoverageを参照してprofile maturityとrelease channelをどう判断するかを定義します。

- [Evidence Model](evidence-model.md): Evidence taxonomy、CoverageProfile、Capability Verdict、retention、非継承規則
- [Support Policy](../SUPPORT_POLICY.md): experimental / alpha / beta / stableとrelease条件

## Development

新しいadapterやEvidence workflowを実装・reviewする開発者向けです。一般利用者向けの導入手順とは分けています。

- [Runtime Adapter Contract](development/adapter-contract.md): Core / adapter境界、identity、completion、receipt、failure contract
- [Testing and Evidence](development/testing-and-evidence.md): test level、Environment Contract、negative case、Evidence bundle、sanitization、review
- [Runtime文書の構成規則](runtimes/README.md): Runtime canonicalの章順、責務、記述規則

## Historical / Compatibility

次の文書は既存URLとhistorical anchorを維持するcompatibility referenceです。Current support claimの正本ではありません。Retained Evidenceと、そのprovenanceを支える資料もcurrent canonicalへ移動していません。

- [Codex reference path compatibility](reference/codex.md)
- [Hermes reference path compatibility](reference/hermes.md)
- [Claude Code CLI reference compatibility](reference/claude-cli.md)
- [`document-review-report-v1` historical reference](reference/document-review-report-v1.md)
