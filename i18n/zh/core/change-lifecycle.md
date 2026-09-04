# 统一变更生命周期

这是 Harness Engineering 唯一拥有的生命周期。后端、前端和全栈 Profile 只细化 Design 与验证，不再各自定义独立工作流。

```text
Explore → Propose（Spec → Design → Approval）→ Apply → Sync → Archive
```

## 阶段契约

| 阶段 | 必需产物 | 门禁 | 目标状态 |
|---|---|---|---|
| Explore | `change.json`、`context-pack.md`、`impact-analysis.md`、`context-impact.json`、`evidence/lesson-preflight.json` | `EXPLORE` | `EXPLORED` |
| Propose / Spec | `proposal.md`、`specs/<capability>/spec.md` | `SPEC` | `CONTRACT_READY` |
| Propose / Design | `design.md`、`tasks.md` | `DESIGN` | `DESIGN_READY` |
| Approval | 外部身份及全部契约产物摘要 | `EXECUTE` | `APPROVED` |
| Apply | 已审批契约、完成的 Tasks、改动文件摘要、精确验证命令 | `EXECUTE`，再 `REVIEW` | `IMPLEMENTING → VERIFYING → VERIFIED` |
| Sync | 已验证行为同步到规范/文档且摘要一致 | `SYNC` | `SYNCED` |
| Archive | 归档证据；学习结论；生产变更还需生产闭环 | `ARCHIVE` | `ARCHIVED` |

只能使用 `methodology_state.py` 推进状态。门禁失败自动记录 `phase.blocked`；审批后契约漂移进入 `CONTRACT_CHANGED`，仓库漂移进入 `DRIFT_DETECTED`，验证失败进入 `REMEDIATING`。

Self-Refine 是阶段内部的有界循环，不是新增状态机：

```text
生成 → 自我批判 → 优化 → 再检查 → 阶段门禁
```

其策略由项目 Profile 选择。策略要求时，Review 必须包含 `self-refine-evidence.json`；该记录描述发现和处理结果，但不能批准契约变更，也不能替代客观验证。详见 [Self-Refine 反馈闭环](self-refine.md)。

## 契约边界

审批契约由上下文、影响分析、上下文更新决策、提案、全部行为 Spec、Design 和 Tasks 的精确内容组成。`context-impact.json` 枚举全部计划交付文件，并声明根 `ai.json` 或已索引 `AI.md` 是否必须更新。`approve_design.py` 保存外部审批来源、稳定审批 ID 及 SHA-256 摘要。脚本证明内容完整性，不证明审批人身份真实性；身份与授权必须由 CI 或审批系统验证。

Explore 还要在 `evidence/lesson-preflight.json` 记录与任务匹配的项目经验。如果记录过失败，Archive 前必须形成经验候选或明确的不可泛化决策；该学习结论不会改变审批契约。

后端 RAM（Read → Analyze → Model）和前端 RAD（Read → Analyze → Decompose）都发生在 Explore 与 Propose。Apply 只能做局部漂移检查，不能静默重做已审批设计。

## 生产扩展

技术完成和生产完成是由同一 `change_id` 关联的两套状态机：

```text
RELEASE_READY → DEPLOYED（阶段 1..n）→ OBSERVING → CLOSED
                  ↘ ROLLED_BACK ───────────────────↗
```

生产范围的 Engineering 变更，只有关联生产记录达到 `CLOSED` 后才能 Archive。每个声明的灰度阶段必须按顺序携带证据推进；命中停止条件后可进入有证据的回滚和关闭。生产记录必须包含观测、回滚责任人、回滚演练，且审计日志只能位于项目生产审计目录。

## 微小变更

只有局部、可逆、不改变公共契约/Schema/信任边界且不影响生产控制的变更，Profile 才可允许不创建工作区。最终输出仍必须报告修改文件、精确验证及未覆盖项。
