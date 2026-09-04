# 规格驱动交付

SDD 是统一 Engineering 生命周期中负责产出契约的部分，不是第二套生命周期。

`openspec/changes/<change-id>/` 是唯一的活跃变更工作区。OpenSpec 的 proposal/spec/design/tasks 与 Harness 的上下文、状态、审批和证据产物共置于此。

- Explore 产出上下文、影响证据，以及覆盖全部计划文件并受审批绑定的 `context-impact.json` 决策。
- Propose 产出业务提案、可观测行为 Spec、技术 Design、依赖有序 Tasks 和外部审批。
- Apply 实现已审批契约并记录结构化 Review 证据。
- Sync 把已验证行为同步到权威 Spec/文档并证明摘要相同。
- Archive 在关联生产记录关闭后结束技术记录。

行为 Spec 使用 `#### Scenario`、`WHEN`、`THEN`，保持实现中立，并按需覆盖校验、错误、权限、精度/时间、兼容和失败行为。Design 记录实现这些行为所需的选择。审批同时绑定两者，因此任一变化都会使执行授权失效。

Review 必须精确摘要 `context-impact.json` 声明的全部文件。项目摘要、模块拓扑、上下文路由或入口变化必须更新 `ai.json`；职责、边界、不变量、依赖、契约或局部验证变化必须更新受影响且已索引的 `AI.md`。

申请阶段门禁前，作者可以针对需求、场景、设计决策、任务或实现运行有界 Self-Refine 循环（`生成 → 自我批判 → 优化 → 再检查`）。Profile 要求时，在 Review 阶段记录 `self-refine-evidence.json`。自反馈可以发现缺口并准备修复，但测试、摘要、审批和外部 Review 仍是权威依据。
