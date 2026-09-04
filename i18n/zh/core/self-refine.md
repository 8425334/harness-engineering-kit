# Self-Refine 反馈闭环

Self-Refine 是 Harness Engineering 的内层质量循环。它通过有界的自反馈改进产物或实现，但不创建第二套生命周期，也不能替代外部审批、确定性门禁、人工 Review 或生产证据。

```text
生成 → 自我批判 → 优化 → 再检查
```

## 所处位置

规范生命周期保持不变：

```text
Explore → Propose（Spec → Design → Approval）→ Apply → Sync → Archive
```

内循环可以发生在 Explore、Spec、Design、Apply 和 Verify 内，并必须在申请对应阶段门禁前结束。后端 RAM 和前端 RAD 发现遗漏或矛盾时，也可以使用同一循环。

## Profile 策略

通过 `docs/methodology/profile.yaml` 配置 Self-Refine，让团队按风险选择流程强度：

| 策略 | 含义 |
|---|---|
| `disabled` | 不要求反思记录；客观门禁仍然有效。 |
| `recommended` | 有价值时使用；使用后记录证据。 |
| `required` | 每个非微小变更在 Review 时必须提交 `self-refine-evidence.json`。 |
| `required-independent` | 除上述要求外，还必须记录独立的人或 Agent 检查。 |

`max_iterations` 限制在 1 到 10 次。若在上限内无法解决问题，必须记录未解决风险并交给负责人或正常门禁处理，不能通过宣称成功来隐藏问题。

## 批判契约

每轮都要依据已批准需求、适用 Profile 和风险标准检查产物，并记录：

- 被检查的产物或修改区域；
- 具体发现，而不是笼统的质量结论；
- 修改结果，或保留问题的原因；
- 未覆盖风险及后续负责人或门禁；
- 策略要求时的独立检查。

标准证据文件是 `self-refine-evidence.json`。它属于过程证据，不属于审批契约，因此不能默默授权契约变更。Spec、Design 或 Tasks 发生变化时，审批仍然失效并进入 `CONTRACT_CHANGED`。

## 信任边界

自反馈不是独立证明：同一个模型可能重复同一个错误。高风险结论要使用确定性检查、测试、外部 Review 或独立评估器。反思结果不能直接写入 `agent-policy.yaml`、`ai.json`、`AI.md` 或 Fitness 规则，必须遵守正常变更和审批控制。Skill 降级和人工介入仍记录在追加式事件流中。

## 完成定义

当迭代次数未超过配置上限，每个选定问题都有解决结果或明确的未覆盖风险，且阶段正常门禁通过时，Self-Refine 才算完成。反思记录通过不能把失败测试、缺失审批、摘要不一致或生产停止条件变成通过。

## 理论依据

本实践参考 Madaan 等人的 *Self-Refine: Iterative Refinement with Self-Feedback*（NeurIPS 2023）。Shinn 等人 2023 年提出的 Reflexion 是相关的跨任务经验保留模式；这类记忆在通过正常方法论变更控制审核前，只能作为辅助建议。
