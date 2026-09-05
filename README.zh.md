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

Design 还会生成受审批绑定的 `task-plan.json` DAG。Apply 阶段只有在 Agent 运行时和工作树/不相交范围隔离都支持时，协调者才并发执行依赖已满足的任务；否则按同一任务图顺序执行并记录原因。`execution-evidence.json` 证明任务归属、真实并发、集成顺序和协调者级验证。详见[任务图与并行执行](i18n/zh/core/task-orchestration.md)。

Harness Engineering 是父级生命周期，OpenSpec 是子级写作/校验能力。所有 change 级 OpenSpec 操作都必须经过 Harness 白名单调度器；每个 DAG 任务成功后，Harness 会记录 run 并自动勾选对应的 OpenSpec `tasks.md` 项。详见 [Harness 与 OpenSpec 父子调度](i18n/zh/core/openspec-orchestration.md)。

如果 Apply 中断，保持 change 处于 `IMPLEMENTING`，执行 `record_task_completion.py resume <change-dir> --actor <agent> --json`；该命令从经过校验的证据修复任务投影，并返回下一就绪任务波次。

生产交付是 Engineering 生命周期的扩展。生产范围变更只有在关联生产记录以观测、分阶段灰度、停止条件、回滚与审计证据达到 `CLOSED` 后，才能 Archive。

Self-Refine 是草稿和实现质量的可选或按 Profile 要求启用的内层循环：`生成 → 自我批判 → 优化 → 再检查`。它产生可审计证据，但不替代审批、确定性门禁或生产控制。详见 [Self-Refine 反馈闭环](i18n/zh/core/self-refine.md)。

需求反思是回答级质量门：Agent 在发送任务回答或产生副作用前，检查需求是否明确、是否与仓库事实一致、是否已获授权。存在会影响结果的歧义或冲突时，暂停有后果的操作，向用户聚焦确认，并给出最佳推荐方案。详见[需求反思与澄清](i18n/zh/core/requirement-reflection.md)。

项目经验记忆把这一循环扩展到多次变更：将失败转化为经过审核、可检索的预防指导，必要时再升级为确定性控制。详见 [项目经验记忆](i18n/zh/core/lesson-memory.md)。

## CLI 接入

### 独立 CLI（`hek`）

本仓库也提供一个不依赖第三方 Node 包的独立入口。不需要发布到 npm，可直接通过 `npx` 从 GitHub 或本地目录运行：

```bash
cd your-project
npx --yes --package github:8425334/harness-engineering-kit hek init
# 或使用本地 checkout
npx --yes --package /path/to/harness-engineering-kit hek init
```

执行后先用方向键选择安装范围（完整接入/轻量接入）与已安装的 AI Agent，确认计划，程序会自动打开对应的 Agent 面板并带上初始化提示词。`npx hek init` 仅适用于已发布 npm 包或项目已安装该依赖，本项目不依赖这种方式。

如果希望在任意 target 项目目录直接输入 `hek init`，先从 GitHub 安装一次全局命令（不会访问 npm 包仓库，也不需要发布 npm 包）：

```bash
npm install --global git+https://github.com/8425334/harness-engineering-kit.git
cd target-project
hek init
```

`npx` 方式不会持久安装命令；若不想全局安装，每次使用完整的 `npx --package ... hek init` 命令即可。

支持 `Claude Code`、`Codex`、`Cursor` 和 `Gemini CLI`；`WorkBuddy`、`Trae Work` 通过手动 handoff 接入，因为它们没有稳定的公开 CLI 契约。也可以显式指定 Agent 或用于 CI：

```bash
npx --yes --package github:8425334/harness-engineering-kit hek init --agent codex --open --yes
npx --yes --package github:8425334/harness-engineering-kit hek init --direct --yes
npx --yes --package github:8425334/harness-engineering-kit hek agents                 # 查看支持的 Agent 和安装状态
npx --yes --package github:8425334/harness-engineering-kit hek init --plan --json     # 只读输出机器可读计划
npx --yes --package github:8425334/harness-engineering-kit hek handoff --agent workbuddy
npx --yes --package github:8425334/harness-engineering-kit hek handoff --agent trae-work --json
```

无 CLI 的桌面 Agent 先执行 `hek init --direct --yes` 导入项目控制面，再执行 `hek handoff --agent workbuddy` 或 `hek handoff --agent trae-work`。然后在对应 Agent 中打开项目，复制命令生成的提示词，让 Agent 读取项目内的 `AGENTS.md`/`CLAUDE.md` 和 `docs/methodology/agent-policy.yaml`。`handoff` 不会猜测或启动未知桌面应用，也不会写入项目文件。

交互式 `init` 会先询问安装范围（未指定 `--tier` 时用方向键选择完整/轻量接入），再启动所选 Agent，由 Agent 完成接入；在 Agent 菜单中选择跳过项即可走确定性流程，未检测到已安装 Agent 时自动回退。非交互环境不会意外拉起外部程序，使用 `--open` 可显式开启（需配合 `--agent`/`HEK_AGENT`）。`--json` 切换为机器可读输出：从不启动 Agent、也从不出交互确认——不带 `--yes` 时打印只读计划并以退出码 2 结束；带 `--yes` 时执行安装、检查并输出单一 JSON 回执（apply 失败回滚时也输出含 `errors` 的回执）。`HEK_AGENT` 可作为 `--agent` 的环境变量替代，`--prompt` 可覆盖传给终端 Agent 的首条提示词（提示词以单行传递，避免 Windows `cmd.exe` 截断）。

全新项目的占位符必须依据真实仓库事实填写后才能通过接入检查，因此无人值守的 `init --direct --yes` 在全新项目上会先安装脚手架再以退出码 2 结束（fail-closed）；已配置项目的升级则会直接通过。仅需安装脚手架的自动化场景使用 `--no-check`，或在确定性安装后打开 Agent（`--agent <id> --open --yes`）完成"填写-检查"闭环。

`hek init` 采用 Agent 驱动：先选择安装范围与已安装的 Agent，在解析出的项目根目录打开该 Agent 的 CLI，并传入 Kit 路径和接入契约。由 Agent 读取项目事实、生成只读计划、请求确认、填写项目专属配置、执行 canonical 脚本并运行确定性检查。Tier 1（轻量接入）安装核心控制面（含 `agent-policy.yaml` 引用的生产策略脚手架）；默认 Tier 2（完整接入）额外安装 Fitness 门禁脚本、Fitness 规则和经验记忆。每次接入都会写入 `docs/methodology/onboarding.json`，记录版本、文件摘要、创建/更新/保留的文件和校验结果。只有明确需要无 Agent 的确定性安装时才使用 `--direct`；它会忽略 `--agent` 和 `HEK_AGENT`。

版本化升级会比较项目已安装版本与 Kit 版本：低版本到高版本同步全部规范资源，同版本仍检查漂移，高版本降级直接阻断，并报告该目标版本声明的特殊迁移事项。详见 [版本化管理](docs/versioning.md)。

`ai.json` 超限或结构非法、`AI.md` 未索引或超限、策略缺失、占位符未填、引用路径断裂、任务图/执行证据非法、Profile 非法、Skill 资源缺失、安装内容过期或平台适配不支持都会失败。Cursor 以及旧 `ramer`、`fe-engineering`、`multi-agent` 入口不再兼容。

任务上下文由接入后的项目控制面解析；执行契约见 [CLI 接入指南](templates/engineering/references/onboarding.md)。

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

直接检查门禁用 `check_phase.py`，检查确定性任务波次和执行证据用 `check_task_plan.py`，显式记录降级/人工介入用 `record_skill_event.py`，统计结构化采用效果用 `skill_metrics.py`。

Explore 结束前运行 `preflight_lessons.py`；用 `record_failure.py` 记录 Fitness/测试/差异/生产失败，用 `create_lesson_candidate.py` 提议可复用预防，用 `retrieve_lessons.py` 检索激活经验，并通过 `approve_lesson.py` 在外部审批后激活。

## 权威文档

- [Harness 架构](i18n/zh/core/harness-engineering.md)
- [变更生命周期](i18n/zh/core/change-lifecycle.md)
- [SDD 工作流](i18n/zh/core/sdd-workflow.md)
- [治理基线](i18n/zh/core/methodology-governance.md)
- [Self-Refine 反馈闭环](i18n/zh/core/self-refine.md)
- [需求反思与澄清](i18n/zh/core/requirement-reflection.md)
- [任务图与并行执行](i18n/zh/core/task-orchestration.md)
- [项目经验记忆](i18n/zh/core/lesson-memory.md)
- [后端 Profile](i18n/zh/core/backend-profile.md)
- [前端 Profile](i18n/zh/core/frontend-profile.md)
- [全栈 Profile](i18n/zh/core/fullstack-profile.md)
- [移植指南](TRANSPLANT.md)

`manifest.yaml` 是 Harness 自己的可用性契约，不是假装所有平台都支持相同原生 manifest。平台是否自动选中 Skill 必须通过运行时事件观测；安装和资源完整性由 `verify_skill.py` 与 `smoke_test_skills.py` 确定性验证。
