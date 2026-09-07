# OpenSpec 变更生命周期

OpenSpec 是生命周期所有者：

```text
Explore → Propose → Apply → Verify → Sync → Archive
```

原生 OpenSpec Skill/CLI 负责创建 change、产物顺序、任务复选框、校验、规格同步和归档。Engineering 只附加治理外壳：上下文、需求反思、Design 评审、审批、执行/Review/Fitness/生产证据。

OpenSpec 创建 `openspec/changes/<id>/.openspec.yaml` 后，用 `init_governance.py` 创建 `governance.json`。`tasks.md` 是唯一任务定义和进度来源；`check_execution.py` 只验证已勾选任务是否有完整执行证据，不维护第二套任务图或状态机。

```bash
openspec status --change <id> --json
openspec validate <id> --type change --strict --no-interactive
python3 docs/methodology/scripts/check_phase.py <change-dir> DESIGN
```
