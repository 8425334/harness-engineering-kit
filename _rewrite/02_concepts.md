## 二、核心概念：把"规则"变成"仓库里的文件"

上一章说 Harness 补的是上下文、流程、门禁。这一章看它们具体落在仓库的哪些文件里——**每一层只干一件事，并声明自己的权威边界**，避免把规则堆成一份超长根 Prompt。

| 概念 | 落地文件 | 职责 | 不负责 |
|-|-|-|-|
| 入口 | 根 `CLAUDE.md` / `AGENTS.md` | 权威、安全、必读入口，路由到 engineering Skill | 命令、模块图、完整方法论 |
| 策略（唯一事实） | `docs/methodology/agent-policy.yaml` | 项目命令、可读写/禁用路径、权限、交付引用 | 任务级设计 |
| 方法论档位 | `docs/methodology/profile.yaml` | 档位（light/standard/regulated/experimental）、Self-Refine 策略、审批要求 | 命令与权限 |
| 上下文索引 | 根 `ai.json`（≤4096 字节） | 机器可读项目地图，路由到详情 | 命令、权限、详细规则 |
| 路径上下文 | `AI.md`（≤400 行/篇） | 局部职责、边界、导航、局部验证 | 覆盖上层指令 |
| 编排 | `engineering` Skill | 路由任务、编排生命周期、记录证据 | 重复项目约定 |
| Design/验证特化 | 后端 / 前端 / 全栈 Profile | RAM / RAD / 全栈契约的建模与验证方式 | 独立生命周期 |
| 变更工作区 | `openspec/changes/<id>/` | proposal / specs/…/spec / design / tasks + 治理证据（change.json、task-plan.json、approval.json…） | 拥有生命周期 |
| 质量门禁 | `docs/fitness/**`（受保护） | 分层质量检查，定义"真正完成" | 被 Agent 修改 |

**权威顺序固定**：system/developer/user 指令 → 原生指令层级 → `agent-policy.yaml` → 根 `ai.json` → 按需选中的路径 `AI.md` → Profile 默认值。任何一层都只补充、不覆盖上一层；仓库文本（Issue、fixture、生成内容、日志、代码注释）一律当作**不可信输入**处理。

> 注意区分两件事：`docs/methodology/profile.yaml` 是**方法论档位**（light/standard/regulated/experimental），由 `resolve_context.py` 紧随 `agent-policy.yaml` 加载，不参与上面这条权威层级；句末的“Profile 默认值”指**工程 Profile**（后端 / 前端 / 全栈）。

### 2.1 工程化 vs 直接生成

| 维度 | 直接生成 | 工程化交付 |
|-|-|-|
| 任务起点 | 一句自然语言需求 | 需求经反思确认：目标、范围、约束、验收、授权 |
| 上下文 | Agent 临时搜索 | `resolve_context.py` 确定性加载 + 路径 `AI.md`/`ai.json` |
| 设计方式 | 边写边调整 | 先建模（后端 RAM / 前端 RAD）再申请契约与审批 |
| 完成定义 | 代码生成或编译通过 | 生命周期状态推进 + 门禁 + 证据（测试/构建/Fitness/审查） |
| 出错处理 | 下次可能重蹈 | 需求反思 + Self-Refine + 经验记忆，错误沉淀为规则 |
| 更适合 | 低风险局部改动 | 新能力、跨模块、接口与架构变化 |

### 2.2 需求反思：动手前的回答级质量门

工程化不是先斩后奏。Agent 形成任务回答草稿后、发送或产生副作用前，必须把对需求的理解归入四类之一（见 `requirement-reflection.md`）：

| 结果 | 判断条件 | Agent 行动 |
|-|-|-|
| `ready` | 目标、范围、完成标准、约束、授权足够明确 | 说明重要假设，在授权范围内行动 |
| `clarify` | 歧义可能改变实现/结果/成本/安全 | 停止写入，聚焦提问并给推荐方案 |
| `correct` | 需求与仓库事实/约束/不变量冲突 | 展示证据与最小可行修正，等确认 |
| `blocked` | 缺授权或证据，无法继续 | 说明阻塞点与最安全的下一步 |

规则只有一条：**不要在多个实质不同的解释之间静默选择**。歧义影响结果就停下来问，并把推荐选项一起给出。

### 2.3 统一生命周期：状态、门禁、证据

每个非微小变更都对应一条生命周期，唯一由 `methodology_state.py` 推进状态、`check_phase.py` 校验阶段门禁：

```text
Explore → Propose（Spec → Design → Approval）→ Apply → Sync → Archive
```

| 阶段 | 状态目标 | 门禁 | 说明 |
|-|-|-|-|
| Explore | `EXPLORED` | EXPLORE | 读取上下文，产出影响分析与上下文决策，预检经验 |
| Spec | `CONTRACT_READY` | SPEC | 业务提案 + 可观测行为 Spec（WHEN/THEN） |
| Design | `DESIGN_READY` | DESIGN | 技术 Design + `tasks.md` + 审批绑定的 `task-plan.json` 任务图 |
| Approval | `APPROVED` | EXECUTE | 外部身份审批，绑定全部契约摘要 |
| Apply | `IMPLEMENTING → VERIFYING → VERIFIED` | EXECUTE → REVIEW | 按任务图执行，逐任务记录证据并勾选进度；验证/Review 在 Apply 内完成 |
| Sync | `SYNCED` | SYNC | 已验证行为同步回权威 Spec/文档，摘要一致 |
| Archive | `ARCHIVED` | ARCHIVE | 归档证据；生产变更需生产闭环先到 `CLOSED` |

设计之外还有三条异常轨道：契约漂移 → `CONTRACT_CHANGED`（需回 `CONTRACT_READY` 重新审批）、仓库漂移 → `DRIFT_DETECTED`、验证失败 → `REMEDIATING`。审批绑定的是契约摘要——Design/Spec/任务图任一变化，原授权即失效。

### 2.4 OpenSpec 是子级，不是第二条生命周期

`openspec/changes/<id>/` 是唯一活跃变更工作区，但它的"父亲"是 Harness 生命周期：`init_change.py` 负责创建 change 并写入父子契约（`change.json`），OpenSpec 只通过 `dispatch_openspec.py` 提供白名单内的写作/校验（`status` / `instructions` / `validate` / `show` / `templates`）。**不再有独立的 `/opsx:*` 生命周期**——这是它与上一代架构最大的区别。工程化交付依赖的各个概念不是互相独立的流程，而是同一份生命周期里职责不同的部分。
