# 规格驱动开发

OpenSpec schema 是 proposal、spec、design 和 tasks 的唯一来源。仓库的 `harness-engineering` schema 只补充可实施 Design、开发者确认和精确任务验证，不改变生命周期归属。

- Propose 生成 `proposal.md`、delta specs、`design.md` 和 `tasks.md`。
- Engineering 在 Apply 前检查上下文影响并绑定外部审批。
- Apply 执行 OpenSpec 任务并记录治理证据。
- Verify 先运行 `openspec validate --strict` 与 `openspec-verify-change`，再执行 `fitness.py --stage review --change <id>` 并生成摘要绑定的 JSON 回执，通过 Engineering REVIEW 门禁后才能 Sync。
- Sync 先快照每个主规格（新 capability 原先不存在时使用空快照），再运行 `openspec-sync-specs`、`openspec validate --specs` 和 `fitness.py --stage sync --change <id>`，最后通过 Engineering SYNC 门禁。
