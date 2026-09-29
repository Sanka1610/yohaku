# Codex reference path compatibility

Codex Runtime integrationのcurrent public canonicalは
[Codex Runtime](../runtimes/codex.md)へ移った。このpathは、既存のpublic linkとhistorical
anchorを維持するために残す互換案内である。

Historical Evidence、CoverageProfile、private record、source associationは移動していない。
旧Reference Evidenceをcurrent Codex versionへ継承せず、最新のprofile、primitive、
Known Limitationsはcanonical pageを参照する。

<a id="controller-core"></a>
## Controller Core

Shared Coreの責務は[Architecture](../architecture.md)、Codexへの対応は
[Codex Runtime](../runtimes/codex.md#controller-core)を参照する。

<a id="production-architecture-and-persistence"></a>
## Production architecture and persistence

Checkpoint、journal、handoff、archive、Runtime-native storageの区別は
[Codex Runtime](../runtimes/codex.md#production-architecture-and-persistence)を参照する。
Historical section名の`production`は
release readinessを意味しない。

<a id="manualcompactbackend-and-owner-api"></a>
## ManualCompactBackend and owner API

Manual triggerとCodex固有のcompletion proofは
[Codex Runtime](../runtimes/codex.md#manualcompactbackend-and-owner-api)を参照する。

<a id="production-recovery-and-continuation"></a>
## Production recovery and continuation

Handoff、`SessionStart(compact)`、`YOH_ACK`、Controller continuation、`ResumeProof`は
[Codex Runtime](../runtimes/codex.md#production-recovery-and-continuation)を参照する。

<a id="bounded-work-plane-integration"></a>
## Bounded work-plane integration

`PreToolUse` / `PostToolUse`、active / pending / incorporated、Hook `FAIL_OPEN`は
[Codex Runtime](../runtimes/codex.md#bounded-work-plane-integration)を参照する。

<a id="archive-and-lazy-rehydration"></a>
## Archive and lazy rehydration

Historical Reference archiveのscopeは
[Codex Runtime](../runtimes/codex.md#archive-and-lazy-rehydration)を参照する。

<a id="reference-runtime-archive-adapter"></a>
## Reference Runtime archive adapter

App Server dynamic archive toolsとCodex native historyの区別は
[Codex Runtime](../runtimes/codex.md#reference-runtime-archive-adapter)を参照する。

<a id="bounded-native-automatic-compaction-recovery"></a>
## Bounded native automatic-compaction recovery

Scenario Gのhistorical scope、stale checkpoint、unverified `EmergencyDelta`、restart
`UNSUPPORTED`は
[Codex Runtime](../runtimes/codex.md#bounded-native-automatic-compaction-recovery)を参照する。

<a id="focused-verification"></a>
## Focused verification

Retained EvidenceとCoverageProfileの公開summaryは
[Runtime support](../runtime-support.md)を参照する。Documentation Stage 3B-1では新しい
Probe、Evidence再採点、test suite変更を行っていない。
