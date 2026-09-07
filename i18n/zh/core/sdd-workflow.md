# 规格驱动开发

OpenSpec schema 是 proposal、spec、design 和 tasks 的唯一来源。仓库的 `harness-engineering` schema 只补充可实施 Design、开发者确认和精确任务验证，不改变生命周期归属。

- Propose 生成 `proposal.md`、delta specs、`design.md` 和 `tasks.md`。
- Engineering 在 Apply 前检查上下文影响并绑定外部审批。
- Apply 执行 OpenSpec 任务并记录治理证据。
- Verify 先运行 `openspec validate --strict` 校验产物结构，再由 `openspec-verify-change` 校验实现一致性，并通过 Engineering 门禁后才能 Sync/Archive。
