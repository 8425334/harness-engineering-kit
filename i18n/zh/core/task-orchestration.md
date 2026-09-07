# 任务证据

OpenSpec 在 `tasks.md` 中定义任务和复选框进度，Engineering 不创建 `task-plan.json` 或其他任务投影。

```markdown
- [ ] 1.1 实现边界行为；使用 `pytest tests/test_api.py` 验证。
```

Apply 完成后，在 `execution-evidence.json` 记录任务 ID、执行者、工作区、时间、变更文件、命令和集成顺序。`check_execution.py` 会阻断缺少证据、未知任务、非零命令、路径越界或与 Review 文件摘要不一致的情况。
