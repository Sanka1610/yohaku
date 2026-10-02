# Yohaku development

- Tested configurationとhard requirementを区別し、起動を拒否する条件には実装上の理由を示す。
- Unsupportedまたはno-opでしかないcommandを公開CLIへ追加しない。
- 新RuntimeのProbeは調査する質問に必要な最小コードで作り、historical Probe frameworkを自動継承しない。
- Release専用のEvidence分類・review制度をCoreやadapterの契約へ持ち込まない。
