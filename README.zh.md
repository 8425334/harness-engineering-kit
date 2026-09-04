# Harness Engineering Kit

一套面向 AI 辅助软件变更的仓库内控制系统。它把上下文、决策、审批、验证、同步、生产控制和审计证据变成可执行契约，而不是继续堆进超长根 Prompt。

English documentation: [README.md](README.md)

## 架构

| 层 | 负责 | 不负责 |
|---|---|---|
| `AGENTS.md` / `CLAUDE.md` | 原生权威适配、安全、必读入口、Skill 路由 | 命令、模块图、完整方法论 |
| `agent-policy.yaml` | 唯一项目事实、命令、权限、引用路径 | 任务级设计 |
| 根 `ai.json` | 轻量机器可读项目地图，以及详细上下文路由 | 命令、策略、不变量或详细规则 |
| 路径 `AI.md` | 局部职责、边界、导航、局部验证 | 覆盖原生指令或项目策略 |
| `engineering` Skill | 任务路由、生命周期编排、证据与降级 | 重复项目约定 |
| 后端/前端/全栈 Profile | Design 与验证特化 | 独立生命周期或命令 |

权威顺序固定为：system/developer/user → 原生指令层级 → `agent-policy.yaml` → 根 `ai.json` → 按需选中的路径 `AI.md` → Profile 默认值。

修改代码前，`resolve_context.py` 会把目标路径和显式 `read_when` 关键词解析为唯一、fail-closed 的加载顺序。根上下文强制存在，已登记的祖先 `AI.md` 先于子级详情加载。

`docs/fitness/**` 是受保护控制面。项目 Agent 只能读取和执行，不能修改；除首次安装和可证明的既有语法修复外，其他变更不论大小，都必须取得与完整变更摘要绑定的外部人工确认。

## 生命周期

```text
Explore → Propose（Spec → Design → Approval）→ Apply → Sync → Archive
```

[统一变更生命周期](i18n/zh/core/change-lifecycle.md) 唯一定义产物、门禁、状态、漂移处理和生产扩展。后端 RAM 与前端 RAD 在 Explore/Propose 完成；Apply 只消费已审批契约。

生产交付是 Engineering 生命周期的扩展。生产范围变更只有在关联生产记录以观测、分阶段灰度、停止条件、回滚与审计证据达到 `CLOSED` 后，才能 Archive。

Self-Refine 是草稿和实现质量的可选或按 Profile 要求启用的内层循环：`生成 → 自我批判 → 优化 → 再检查`。它产生可审计证据，但不替代审批、确定性门禁或生产控制。详见 [Self-Refine 反馈闭环](i18n/zh/core/self-refine.md)。

项目经验记忆把这一循环扩展到多次变更：将失败转化为经过审核、可检索的预防指导，必要时再升级为确定性控制。详见 [项目经验记忆](i18n/zh/core/lesson-memory.md)。

## 对话式接入

不再要求项目成员手动执行 `init.sh`。在目标仓库的 Agent 对话中发送：

```text
请把当前项目接入 Harness Engineering Kit。先只读检查并识别是全新、部分接入、老架构还是当前版本；给出将创建、更新、保留的文件清单。不要删除旧的 ramer/fe-engineering/multi-agent 或 Cursor 配置，等我确认后再执行完整接入并校验。
```

已接入项目会通过 `engineering` Skill 自动路由到接入流程。Agent 会先运行只读计划：

```bash
python3 <kit>/scripts/onboard.py --project-root . --source-root <kit> --plan --json
```

得到用户确认后才运行 `--apply`，随后运行 `--check`。Tier 1 安装核心控制面；完整接入默认使用 Tier 2（包含 Fitness、生产控制和经验记忆）。每次接入都会写入 `docs/methodology/onboarding.json`，记录版本、文件摘要、保留的旧文件和校验结果。`scripts/init.sh` 仅作为旧自动化的兼容转发，不是接入入口。

`ai.json` 超限或结构非法、`AI.md` 未索引或超限、策略缺失、占位符未填、引用路径断裂、Profile 非法、Skill 资源缺失、安装内容过期或平台适配不支持都会失败。Cursor 以及旧 `ramer`、`fe-engineering`、`multi-agent` 入口不再兼容。

可用 `python3 docs/methodology/scripts/resolve_context.py <目标路径> [<目标路径> ...]` 直接解析任务上下文；显式语义路由通过重复的 `--keyword <read_when>` 参数传入。

完整接入、升级和旧架构迁移规则见 [对话式接入指南](docs/onboarding-conversation.zh.md)；Skill 执行细节见 [Onboarding Playbook](templates/engineering/references/onboarding.md)。

## 变更控制

```bash
python3 docs/methodology/scripts/init_change.py add-capability \
  --title "新增能力" --mode fullstack --owner team \
  --trigger explicit-selection \
  --profile-path docs/methodology/profile.yaml

python3 docs/methodology/scripts/approve_design.py openspec/changes/add-capability \
  --actor reviewer --source pull-request --approval-id PR-123

python3 docs/methodology/scripts/methodology_state.py \
  openspec/changes/add-capability EXPLORED --actor agent
```

直接检查门禁用 `check_phase.py`，显式记录降级/人工介入用 `record_skill_event.py`，统计结构化采用效果用 `skill_metrics.py`。

Explore 结束前运行 `preflight_lessons.py`；用 `record_failure.py` 记录 Fitness/测试/差异/生产失败，用 `create_lesson_candidate.py` 提议可复用预防，用 `retrieve_lessons.py` 检索激活经验，并通过 `approve_lesson.py` 在外部审批后激活。

## 权威文档

- [Harness 架构](i18n/zh/core/harness-engineering.md)
- [变更生命周期](i18n/zh/core/change-lifecycle.md)
- [SDD 工作流](i18n/zh/core/sdd-workflow.md)
- [治理基线](i18n/zh/core/methodology-governance.md)
- [Self-Refine 反馈闭环](i18n/zh/core/self-refine.md)
- [项目经验记忆](i18n/zh/core/lesson-memory.md)
- [后端 Profile](i18n/zh/core/backend-profile.md)
- [前端 Profile](i18n/zh/core/frontend-profile.md)
- [全栈 Profile](i18n/zh/core/fullstack-profile.md)
- [移植指南](TRANSPLANT.md)

`manifest.yaml` 是 Harness 自己的可用性契约，不是假装所有平台都支持相同原生 manifest。平台是否自动选中 Skill 必须通过运行时事件观测；安装和资源完整性由 `verify_skill.py` 与 `smoke_test_skills.py` 确定性验证。
