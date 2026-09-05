# Harness Engineering 架构

Harness Engineering 通过显式权威、最小上下文加载、可执行门禁和持久证据，让 AI 编码环境变得可预测。

## 职责边界

| 组件 | 职责 |
|---|---|
| 原生根入口 | 建立范围、权威、安全、必读项，并路由到 `engineering` |
| `agent-policy.yaml` | 唯一保存项目命令、路径、权限和交付引用 |
| 根 `ai.json` | 为初始化提供紧凑项目/模块地图并路由到细节 |
| 路径 `AI.md` | 补充局部职责、边界、导航和验证上下文 |
| `engineering` Skill | 路由用户要求的代码变更，编排生命周期/状态/证据 |
| Profile reference | 特化后端、前端或全栈的 Design 与验证 |
| 确定性脚本 | 解析上下文，并强制策略、审批、任务图、执行证据、状态转换、同步、归档和度量 |

Skill 必须保持短小，不能重复原生指令和策略中的项目规则。OpenSpec、代码导航、测试、浏览器和多 Agent 都是按需支持能力；缺失时不能静默取消门禁。

OpenSpec 明确从属于该生命周期。Harness 创建并拥有 change、状态、审批、执行、Sync 与 Archive；OpenSpec 只能通过 `dispatch_openspec.py` 提供白名单内的写作/校验输入。详见 [Harness 与 OpenSpec 父子调度](openspec-orchestration.md)。

Design 阶段用 `task-plan.json` 把 Tasks 转为受审批绑定的 DAG，明确依赖、不相交写范围、契约引用、验收条件和验证命令。Apply 阶段由协调者按 Agent/隔离能力自适应执行，必要时记录顺序降级，并独占确定性集成证据。详见[任务图与并行执行](task-orchestration.md)。

## 上下文加载

顺序固定为：原生指令 → `resolve_context.py` 输出（`agent-policy.yaml` → 方法论 Profile → 根 `ai.json` → 按父到子排列的已索引 `AI.md`）→ 匹配的 Engineering Profile → 任务代码/契约/测试。路径命中会选择根模块及全部已登记祖先模块；显式 `read_when` 关键词会选择匹配模块及其已登记祖先。每个显式关键词都必须命中，否则链路 fail-closed。索引只路由，Markdown 负责解释；两者都不重复策略或覆盖上层。

## 闭环

生命周期只在 `change-lifecycle.md` 定义。每个非微小变更都有机器可读状态和追加式事件流；审批绑定精确产物；Review 记录精确命令与缺口；Sync 校验内容摘要；生产变更以 `change_id` 关联技术状态与运营状态。

Self-Refine 是门禁前改进工作的辅助内循环，由 Profile 控制并限制次数，可选或要求提供 `self-refine-evidence.json`。它提升发现问题和准备修复的能力，但不会削弱权威层、审批、确定性验证或生产控制。

项目经验记忆把这一循环扩展到多次变更。失败先作为证据采集，经过外部审核后才能发布，并在 Explore 通过 `preflight_lessons.py` 检索；激活经验仍是辅助指导，升级为确定性控制必须另行审批。

## 工作区归属

在已接入仓库中，活跃变更工作区 `openspec/changes/<change-id>/` 归本生命周期所有。存活 change 目录只有在携带规范 `change.json`（schema_version 3，含精确的 Harness 父级/OpenSpec 子级契约，且 `change_id` 与目录名一致）时才有效。只有 OpenSpec 产物而无该契约的目录视为未受管。OpenSpec CLI 只是 `engineering` 名下的子级写作/校验能力；change 级调用必须经过 `dispatch_openspec.py`，独立 `/opsx:*` 通道不得创建、实施、同步或归档 change。`check_change_workspace.py` 在所有阶段门禁及可用的 Claude Code PreToolUse 钩子中强制该不变量。

## 平台边界

Claude 项目发现路径为 `.claude/skills/engineering`，Codex 适配路径为 `.agents/skills/engineering`。`manifest.yaml` 是 Harness 可用性契约；文件检查证明安装完整性，运行时 `skill.triggered` 与 `skill.fallback` 事件反映真实选择行为。
