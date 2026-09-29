# Yohaku — Proactive Context Compaction Manager

Yohakuは、長時間続くAI agent taskでcontext transitionを安全に管理するPython packageです。
単にcontextを圧縮するのではなく、transition前後の安全確認、durable state、taskを再開できる
状態かどうかの検証を扱います。この考え方を **Verified Context Transition** と呼びます。

## What Yohaku does

Yohakuは、次の流れを一つのtransitionとして扱います。

1. Safe transition boundaryと現在の作業状態を確認し、durable checkpointを保存する。
2. 固定したRuntime profileに応じてcompactionまたはtransitionを実行し、その完了を確認する。
3. Handoffを作成してreceiptを照合し、freshな現在状態を観測する。
4. 未完了の作業だけをcontinuationへ渡し、同じtaskが再開されたことを検証する。

証拠が不足する経路は成功として扱いません。完了したか判断できない場合は`AMBIGUOUS`として停止し、副作用を照合するまで再実行を抑止します。

## Current status

- 公開中の全Support Profileのmaturityは`experimental`です。
- Release channelは`undeclared`です。
- 公開scopeは、Runtime、version、surface、environment、taskを固定したbounded profileに限られます。
- Strong Transition Assuranceは成立していません。
- Field Evidenceはありません。

Production ready、general purpose、全Runtime対応のいずれも宣言していません。

## Support snapshot

| Profile / Runtime | 現在の公開scope |
|---|---|
| Codex lifecycle-only | Inferenceとtask transitionを無効にしたoperational lifecycle |
| Codex `document-review-report-v1` | 固定input、manual transition 1回、create-only report 1点に限定したreal-task profile |
| Hermes lifecycle-only | Inferenceとtask transitionを無効にしたoperational lifecycle |
| Hermes adapter | `H-ADAPTER`（product registry `hermes-h-cli-01`）のbounded connected workflowに対するaccepted Evidence。overall coverageは`PARTIAL` |
| Claude Code CLI | Subscription completionとlocal recoveryを分けたbounded adapter Evidence。Subscription recoveryは`NOT_RUN`で、formal operational launcherはない |

Profileごとの固定条件、Evidence provenance、Capability Verdictは、Documentation IndexからRuntime Supportへ進んで確認してください。

## Quick Start

用途に応じて、次のどちらかから始めます。

- **No-inference lifecycle:** packageとRuntimeのowned lifecycleだけを確認する手順は[Quick Start](docs/quick-start.md)を参照してください。この経路はtaskを実行せず、transitionも有効にしません。
- **Fixed real-task:** Codexで固定文書をreviewする手順は[`document-review-report-v1` Quick Start](docs/quick-start.md#document-review-report-v1-quick-start)を参照してください。一般の文書taskやcoding taskには使えません。

## Important safety behavior

- Preflightの`PASS`は、transitionの`PASS`ではありません。
- Runtime supportは、Task Profile supportを意味しません。
- `AMBIGUOUS`または副作用が不明な状態では、blind retryしません。
- Runtime-native historyは、Yohaku checkpointまたはYohaku archiveではありません。
- Mechanical completionの成功は、文章、事実、その他のcontent qualityを保証しません。

## Major limitations

- 実装とEvidenceはexperimentalで、固定したRuntime、version、surface、environmentだけを対象とします。
- Runtime-wide atomic freezeとexternal writer exclusionは成立していません。
- Parallel、background、detached、subagentのcoverageは限定されています。
- 受け入れ済みの汎用的なrestart recoveryとpower-loss recoveryはありません。
- Packaged real Task ProfileはCodex `document-review-report-v1`の1つだけです。
- Content qualityは`NOT_ASSESSED`です。
- Field Evidenceはありません。
- Claude Code CLIにはformal operational launcherがありません。
- Strong Transition Assuranceとgeneral exactly-onceは成立していません。

## Installation

推奨経路は、review済みwheelを、対象operational profile専用の固定environmentへnon-editable installする方法です。Package floorはPython `>=3.11`です。Editable installやsource-copy executionはdevelopment / Probe用途であり、公開installation pathではありません。

Wheelの確認からuninstallまでの手順は[Installation](docs/installation.md)を参照してください。Installしただけではintegrationは有効になりません。

<!-- Retain historical README anchors while routing readers through docs/index.md. -->
<a id="direction-and-support-status"></a>
<a id="controller-core"></a>
<a id="production-architecture-and-persistence"></a>
<a id="manualcompactbackend-and-owner-api"></a>
<a id="production-recovery-and-continuation"></a>
<a id="bounded-work-plane-integration"></a>
<a id="archive-and-lazy-rehydration"></a>
<a id="reference-runtime-archive-adapter"></a>
<a id="bounded-native-automatic-compaction-recovery"></a>
<a id="focused-verification"></a>

## Documentation

詳細は[Documentation Index](docs/index.md)から目的に応じて選んでください。Architecture、Runtime support、Task Profiles、Operations、Evidence、development documentationへの入口をまとめています。日本語文書が現在のpublic canonicalです。
