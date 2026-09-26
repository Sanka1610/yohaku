# Yohaku - Semantic Context Lifecycle Manager  
Proactive context compaction, checkpointing, and lazy recovery for long-running AI agent tasks.

現在はPhase 1のProbe基盤です。Python 3.14.xと標準ライブラリで、Codex CLI + WSL2 Ubuntuのローカルmetadataを収集します。

```bash
python3 scripts/probe/run.py collect
```

結果は`probe-results/<run-id>/result.json`に保存されます。実行結果は既定でGit追跡の対象外です。

実行方法、記録形式、検証範囲は[scripts/probe/README.md](scripts/probe/README.md)を参照してください。Gate A/B/CのRuntime実測は後続フェーズで行います。
