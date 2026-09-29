# Runtime文書の構成規則

`docs/runtimes/`は、Yohakuが接続する各Runtimeの公開canonical pageを置く。各pageは、
Runtime family全体ではなく、固定したSupport Profileごとの実装、観測、Evidence、制限を
説明する。

[Architecture](../architecture.md)はcomponentとtrust boundary、
[Runtime Mapping](../runtime-mapping.md)はprofile固有事実の比較表、
[Transition Strategies](../transition-strategies.md)はStrategy taxonomy、
[Evidence Model](../evidence-model.md)はEvidence / Coverage / Verdict、
[Support Policy](../../SUPPORT_POLICY.md)はmaturity / release policyを所有する。Runtime pageは
これらを再定義せず、一つのRuntimeでどのprimitiveが各roleを実現するかを確定する。

現在のcanonical Runtime pageは[Codex](codex.md)、[Hermes](hermes.md)、
[Claude Code CLI](claude-code-cli.md)である。

## Profileを先に分ける

同じRuntime familyやversionを使っていても、Probe、historical Reference、product adapter、
operational lifecycle、Task Profileを一つのprofileへ統合しない。各profileには、少なくとも
次を記載する。

- 一意なSupport Profile IDまたは既存mapping key
- Runtime / version / surface / OS
- provider / backend / modelの扱い
- 実装状態と起動可能範囲
- Transition Strategyとaccepted endpoint
- Evidence provenance、Capability Verdict、maturity
- Known LimitationsとEvidenceを継承しない範囲

Mapping keyがSupport Profile IDではない場合は、その違いを明記する。古いversionの
Evidenceを新しいversionへ移さず、Probe PASSをproduct adapter acceptanceへ読み替えない。

## 共通の章順

Runtime pageは、次の章を同じ順序で置く。Profile固有の比較は各章内の表または小見出しで
示す。

1. `Runtimeの位置付け`
2. `Supported / measured profiles`
3. `Runtime / version / surface / OS`
4. `Provider / backend / model`
5. `Transition Strategy`
6. `Lifecycle observation`
7. `Work observation / admission / gate`
8. `Active / pending / incorporated`
9. `Native identity / host-local identity`
10. `Trigger`
11. `Completion proof`
12. `Checkpoint / Yohaku storage`
13. `Runtime-native storage`
14. `Handoff creation / delivery / injection`
15. `Explicit receipt`
16. `Fresh current-state observation`
17. `Continuation`
18. `Task Observer / Task Assessor`
19. `Resume verification`
20. `Archive / native history`
21. `Failure / timeout / late / duplicate`
22. `Restart / reconnect`
23. `Evidence provenance`
24. `Verdict / maturity`
25. `Known Limitations`
26. `Unsupported / NOT_RUN scope`

Canonicality、旧path、詳細Task Profileへの案内は、この章順の後に追加できる。個別runの
大量な一覧、installation手順、内部acceptance手順はRuntime pageへ含めない。

## 不在の概念を共通APIへ変換しない

共通なのは章順とYohaku roleであり、Runtime primitiveではない。各Runtimeに存在しない
event、identity、storage、receipt、restart機構を、別Runtimeの名前で補わない。

| 表記 | Runtime pageでの使い方 |
|---|---|
| `UNIMPLEMENTED` | Roleまたはpathを実現する製品実装が存在しない |
| `UNSUPPORTED` | Fixed profileが明示的に除外または拒否する |
| `NOT_RUN` | 仕様や実装は存在し得るが、必要な評価を実行していない |
| `UNKNOWN` | Retained recordまたは公開可能な資料から確定できない |

これらをCapability Verdictへ新しく追加しない。`UNIMPLEMENTED`と`UNKNOWN`は状態説明で
あり、Capability Verdictの定義は[Evidence Model](../evidence-model.md)に従う。

## Identityとstorageの記述規則

Identityは、Runtime-native identityとYohaku / host-local identityを分ける。文字列が一致
してもauthorityが同じとは扱わず、両者の対応を固定profileのcorrelation ruleとして示す。
Native generationが存在しない場合は、その欠落をhost-local generationで隠さない。

Storageは、少なくとも次を分ける。

- Yohaku checkpoint
- append-only journal
- durable handoff
- Yohaku archive
- adapter / operational metadata
- Runtime-native session、thread、turn、history、database、transcript

Runtime-native readbackがcompletion Evidenceになっても、Yohaku checkpointやarchiveには
ならない。逆に、Yohaku journalのstateだけでRuntime-native completionを証明しない。

## Evidence要約の規則

Runtime pageは、profile、Evidence provenance、accepted endpoint、Capability Verdict、
overall limitationを一つの要約表で示す。Evidence levelやVerdict vocabularyを再定義せず、
retained Evidence / CoverageProfileを指す安定したreferenceを置く。

成功runだけを選ばず、既知のfailure、mixed result、未測定範囲をKnown Limitationsまたは
Evidence referenceへ対応付ける。Maturityとrelease channelはEvidenceから自動決定せず、
[Support Policy](../../SUPPORT_POLICY.md)の値を参照する。

## Task Profileとの境界

Runtime pageは、Task Profileが存在すること、必要なRuntime primitive、live acceptanceの
有無、Task Observer / Task Assessorの必要性までを説明する。Input / output schema、task
固有tool semantics、assessment ruleの詳細は`docs/task-profiles/`のcanonical pageへ委ねる。

Runtime supportからTask Profile supportを推定せず、Task Profileのaccepted resultから
Runtime family全体のsupportを推定しない。
