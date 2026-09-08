# Harness Engineering 架构

Harness Engineering 通过显式权威、最小上下文加载、可执行治理门禁和持久证据，让 AI 编码环境变得可预测。

## 职责边界

| 组件 | 职责 |
|---|---|
| 原生根入口 | 权威、安全、必读项和 Skill 路由 |
| `agent-policy.yaml` | 项目命令、路径、权限和交付引用 |
| `ai.json` / `AI.md` | 项目地图和局部上下文 |
| `engineering` Skill | OpenSpec 与仓库控制的治理外壳 |
| 确定性脚本 | 上下文、审批、执行/评审、Fitness、经验和生产门禁 |

OpenSpec 是生命周期所有者。它的原生 Skills 与 CLI 创建 change、推进产物、验证、同步规格和归档。Engineering 不再维护第二套状态机、调度器、任务计划或复选框投影。

## 治理闭环

执行 `openspec new change <id>` 后，用 `init_governance.py` 附加 `governance.json`。Engineering 随后负责上下文、需求反思、Design 评审、审批绑定、执行证据、Review、Fitness、经验和生产闭环；`.openspec.yaml`、schema、产物图和 `tasks.md` 始终由 OpenSpec 作为权威。

## 平台边界

Claude 使用 `.claude/skills/engineering`，Codex 使用 `.agents/skills/engineering`，OpenCode 使用 `.opencode/skills/engineering`，Cursor 使用 `.cursor/skills/engineering`，Gemini 使用 `.gemini/skills/engineering`，Trae 使用 `.trae/skills/engineering`。Skill frontmatter 与原生根入口同时要求对非平凡代码变更进行隐式选择，用户无需输入 `/engineering`。OpenSpec 1.12.0 会在相同的 Agent 目录生成七个原生工作流 Skill（包含 Verify）。
