# OpenSpec 集成

OpenSpec 直接拥有完整生命周期。Engineering 通过 OpenSpec 1.12.0 生成的原生 Skill 调用 `explore`、`propose`、`apply`、`verify`、`sync`、`archive` 和 `update`，不存在父子生命周期、dispatcher 或 Harness 状态机。

```bash
openspec new change <id> --schema harness-engineering
python3 docs/methodology/scripts/init_governance.py <id> \
  --title "..." --mode backend --owner <actor> --trigger native-selection
```

`check_change_workspace.py` 要求活跃 change 的 `.openspec.yaml` 选择 `harness-engineering` schema，并同时存在 `governance.json`，但不会阻止原生 OpenSpec 命令。`openspec validate --strict` 校验产物结构，`openspec-verify-change` 校验实现相对产物的完整性、正确性和一致性。自定义 schema 保留 OpenSpec `tasks.md` 格式，并要求 Engineering 记录 `execution-evidence.json`。
