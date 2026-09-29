# Hermes reference path compatibility

Hermes Runtime integrationのcurrent public canonicalは
[Hermes Runtime](../runtimes/hermes.md)へ移った。このpathは、既存public linkとhistorical
headingを維持するために残す互換案内である。

Stage 2 / Stage 4のretained Evidence、CoverageProfile、RESULT、manifest、hash、source
associationは移動していない。H-PROBE、H-ADAPTER、H-OPを統合せず、最新のprofile、primitive、
Known Limitationsはcanonical pageを参照する。

<a id="host-integration"></a>
## Host integration

Native `HermesCLI` host、`PluginContext`、tool ledger、manual `/compress`、
`HermesManualCompletionPolicy`の対応は
[Hermes Runtime](../runtimes/hermes.md#lifecycle-observation)を参照する。

<a id="receipt-and-current-task-state"></a>
## Receipt and current task state

Adapter-defined receipt、fresh read、controller-driven continuation、`ResumeProof`は
[Hermes Runtime](../runtimes/hermes.md#explicit-receipt)を参照する。

<a id="storage-and-limits"></a>
## Storage and limits

Yohaku checkpoint / handoff / archive、adapter metadata、Hermes `SessionDB`、native historyの
区別とKnown Limitationsは
[Hermes Runtime](../runtimes/hermes.md#checkpoint--yohaku-storage)を参照する。
