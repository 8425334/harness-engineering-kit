# Harness 与 OpenSpec 父子调度

Harness Engineering 是父级生命周期；OpenSpec 是规格写作指引与校验的子能力，
不是与 Harness 并列的工作流。

## 归属契约

每个存活的 `change.json` 都必须携带精确、机器可校验的关系：

- 父级：`harness-engineering`；
- 子级：`openspec`；
- 唯一子能力入口：`docs/methodology/scripts/dispatch_openspec.py`；
- 子级动作：`status`、`instructions`、`validate`、`show`、`templates`；
- 仅父级拥有：创建 change、生命周期状态、审批、实施、Sync、Archive。

`init_change.py` 创建该关系。`check_change_workspace.py` 和所有阶段门禁会拒绝
关系缺失或被修改的 change。在已接入仓库中，直接调用 change 级 OpenSpec
命令以及独立 `/opsx:*` 生命周期都不是合法入口。

## 调度协议

Engineering 协调者只能调用固定且返回 JSON 的操作：

```text
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> status
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> instructions --artifact proposal|specs|design|tasks|apply|archive
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> validate
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> show
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> templates
```

调度器先校验规范工作区、父子契约和当前 Harness 状态，再构造固定 OpenSpec
参数；它不提供任意参数透传，并把输出摘要和退出码记录为 Harness 事件。
OpenSpec 输出只是协调者的子级输入，不能推进状态或授权修改源码。

proposal/specs 指引仅限早期契约状态，design/tasks 指引仅限
`CONTRACT_READY` 或契约返工，Apply 指引仅限已审批实施状态，Archive 指引
仅限已验证/已同步状态。Apply 与 Archive 的指引调度仍是只读的，实际操作
始终由父级执行。

## Task 进度投影

`task-plan.json` 是受审批绑定的父级 DAG；OpenSpec `tasks.md` 是人类可读的
子级投影，并承载运行态勾选。协调者不得直接编辑复选框。Worker 完成任务且
所有聚焦验证通过后，必须执行：

```text
python3 docs/methodology/scripts/record_task_completion.py complete <change-dir> T1 --run <task-run.json>
```

该操作会校验依赖、范围、时间、隔离与计划验证，随后把 run 写入
`execution-evidence.json`、产生 `task.completed` 事件，并把 T1 同步为
`- [x]`。并行完成会被串行化。若写入中断，可运行
`record_task_completion.py sync <change-dir>` 从证据修复投影。Review 会强制
检查已勾选任务与成功 task run 完全一致。

如果 Apply 中断，保持 change 处于 `IMPLEMENTING`，由父级协调者执行恢复：

```text
python3 docs/methodology/scripts/record_task_completion.py resume <change-dir> --actor <agent> --json
```

恢复命令会校验已有 run、修复复选框投影、记录 `execution.resumed` 事件，并返回
已完成、待完成和下一就绪任务波次。工作区中即使已经出现源码改动，只要没有经过
校验的 run，该任务仍保持待完成；应重新执行聚焦验证，使用 `complete` 提交新的
`task-run.json` 后再执行依赖任务。恢复不会修改已审批的 DAG，也不会推进生命周期状态。
