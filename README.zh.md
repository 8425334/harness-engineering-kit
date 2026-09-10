# Harness Engineering Kit

一套面向 AI 辅助软件变更的仓库内控制系统。它把上下文、决策、审批、验证、同步、生产控制和审计证据变成可执行契约，而不是继续堆进超长根 Prompt。

English documentation: [README.md](README.md)

> 📖 **[Harness AI Coding 实战教程](docs/ai-coding-tutorial.zh.md)**：从"为什么需要工程化"到用真实命令跑通一次非平凡变更的完整导览（含全栈并行进阶；图表以飞书在线版白板呈现）。

> 🎞️ **[Harness Engineering Kit 全局导览 PPT（中文 · 26 页）](presentations/Harness-Engineering-Kit-全局导览.pptx)**：按 Why → What → How → Grow → Use 展开的上手导览，并穿插 xiaohua_vn / aegis / varhub-risk 真实案例；由 `presentations/build_hek_deck.py` 生成，可随时重新生成。

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

`context_cache.py` 会对该精确加载顺序生成稳定指纹，并记录供应商 `hit`、`miss` 或 `bypass`。长程任务参考基准要求实测命中率至少 99.5%；它不会修改宿主 Agent 设置，也不会在没有供应商遥测时冒充命中。

`docs/fitness/**` 是受保护控制面。项目 Agent 只能读取和执行，不能修改；除首次安装和可证明的既有语法修复外，其他变更不论大小，都必须取得与完整变更摘要绑定的外部人工确认。

## 生命周期

```text
Explore → Propose → Apply → Verify → Sync → Archive
```

[统一变更生命周期](i18n/zh/core/change-lifecycle.md) 唯一定义产物、门禁、状态、漂移处理和生产扩展。后端 RAM 与前端 RAD 在 Explore/Propose 完成；Apply 只消费已审批契约。

Design 首先生成可供开发者确认的可实施方案包：架构与关系拓扑、运行流程、职责边界、接口/数据、横切质量、交付/回滚、决策与备选方案、验证追踪、风险和编号确认项。`check_design.py` 强制检查结构，审批前必须得到开发者明确确认。详见[可实施设计评审](i18n/zh/core/design-review.md)。

OpenSpec 的 `tasks.md` 是唯一任务定义和进度来源。Engineering 只为已勾选任务记录 `execution-evidence.json`，包含归属、验证、变更文件、集成顺序及并行/串行选择。详见[任务证据](i18n/zh/core/task-orchestration.md)。

OpenSpec 是生命周期所有者。Engineering 直接调用原生 `openspec-*` Skill 和 CLI，再通过 `governance.json` 附加治理证据；不存在第二套生命周期或调度器。详见 [OpenSpec 集成](i18n/zh/core/openspec-orchestration.md)。

安装后的根入口会把非平凡的功能实现、缺陷修复、重构、API、数据库和 UI 变更自动路由到项目内 `engineering` Skill，用户无需输入 `/engineering`；显式调用仍可作为覆盖方式。该契约会安装到 Claude、Codex、OpenCode、Cursor、Gemini 和 Trae 各自的项目级原生 Skill 目录。

如果 Apply 中断，先执行 `openspec status --change <id> --json`，再继续原生 OpenSpec Apply；Engineering 只校验执行证据与 OpenSpec 已勾选任务一致。

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

支持 `Claude Code`、`Codex`、`OpenCode`、`Cursor` 和 `Gemini CLI`；`WorkBuddy`、`Trae Work` 通过手动 handoff 接入，因为它们没有稳定的公开 CLI 契约。也可以显式指定 Agent 或用于 CI：

```bash
npx --yes --package github:8425334/harness-engineering-kit hek init --agent codex --open --yes
npx --yes --package github:8425334/harness-engineering-kit hek init --agent opencode --open --yes
npx --yes --package github:8425334/harness-engineering-kit hek init --direct --yes
npx --yes --package github:8425334/harness-engineering-kit hek agents                 # 查看支持的 Agent 和安装状态
npx --yes --package github:8425334/harness-engineering-kit hek init --plan --json     # 只读输出机器可读计划
npx --yes --package github:8425334/harness-engineering-kit hek handoff --agent workbuddy
npx --yes --package github:8425334/harness-engineering-kit hek handoff --agent trae-work --json
npx --yes --package github:8425334/harness-engineering-kit hek uninstall --plan --json
npx --yes --package github:8425334/harness-engineering-kit hek uninstall --yes
npx --yes --package github:8425334/harness-engineering-kit hek uninstall --yes --keep-project-facts
```

无 CLI 的桌面 Agent 先执行 `hek init --direct --yes` 导入项目控制面，再执行 `hek handoff --agent workbuddy` 或 `hek handoff --agent trae-work`。然后在对应 Agent 中打开项目，复制命令生成的提示词，让 Agent 读取项目内的 `AGENTS.md`/`CLAUDE.md` 和 `docs/methodology/agent-policy.yaml`。`handoff` 不会猜测或启动未知桌面应用，也不会写入项目文件。

交互式 `init` 会先询问安装范围（未指定 `--tier` 时用方向键选择完整/轻量接入），再启动所选 Agent，由 Agent 完成接入。所选 Agent 只会得到自己的原生根入口（Claude Code 为 `CLAUDE.md`，Gemini CLI 为 `GEMINI.md`，Codex/OpenCode 及兼容 Agent 为 `AGENTS.md`）和对应的项目 Skill，不会同时初始化另一套入口。在 Agent 菜单中选择跳过项即可走兼容性确定性流程，未检测到已安装 Agent 时自动回退。非交互环境不会意外拉起外部程序，使用 `--open` 可显式开启（需配合 `--agent`/`HEK_AGENT`）。`--json` 切换为机器可读输出：从不启动 Agent、也从不交互确认——不带 `--yes` 时打印只读计划并以退出码 2 结束；带 `--yes` 时执行安装、检查并输出单一 JSON 回执（apply 失败回滚时也输出含 `errors` 的回执）。`HEK_AGENT` 可作为 `--agent` 的环境变量替代，`--prompt` 可覆盖传给终端 Agent 的首条提示词（提示词以单行传递，避免 Windows `cmd.exe` 截断）。默认提示词直接按用户语言理解和作答，不做“中文→英文→中文”转译；固定规则放在稳定前缀，项目路径、Tier、Agent 和授权状态集中在末尾，便于上下文缓存复用。

全新项目的占位符必须依据真实仓库事实填写后才能通过接入检查，因此无人值守的 `init --direct --yes` 在全新项目上会先安装脚手架再以退出码 2 结束（fail-closed）；已配置项目的升级则会直接通过。仅需安装脚手架的自动化场景使用 `--no-check`，或在确定性安装后打开 Agent（`--agent <id> --open --yes`）完成"填写-检查"闭环。

`hek init` 采用 Agent 驱动：先选择安装范围与已安装的 Agent，在解析出的项目根目录打开该 Agent 的 CLI，并传入 Kit 路径、接入契约和所选 Agent 目标。由 Agent 读取项目事实、生成只读计划、请求确认、填写项目专属配置、执行 canonical 脚本并运行确定性检查；所选 Agent 只初始化对应的原生上下文入口与项目 Skill。Tier 1（轻量接入）安装核心控制面和生命周期门禁所需的最小 Fitness 执行器及 SDD 同步规则；默认 Tier 2（完整接入）额外安装完整 Fitness 规则和经验记忆。每次接入都会写入 `docs/methodology/onboarding.json`，记录版本、文件摘要、创建/更新/保留的文件和校验结果。只有明确需要无 Agent 的兼容性确定性安装时才使用 `--direct`；它会忽略 `--agent` 和 `HEK_AGENT` 并安装全部兼容入口。

版本化升级会比较项目已安装版本与 Kit 版本：低版本到高版本同步全部规范资源，同版本仍检查漂移，高版本降级直接阻断，并报告该目标版本声明的特殊迁移事项。详见 [版本化管理](docs/versioning.md)。

`hek uninstall` 用于撤销接入。默认只读，必须用 `--yes`（或 `--apply`）确认后才删除；它读取 `docs/methodology/onboarding.json` 回执，只删除 Harness 安装且内容仍与回执摘要一致的资源。安装时保留、属于项目事实、以及安装后被修改的文件都会原地保留并在回执中列出，清空后的目录会被裁剪。每次执行都会写入 `docs/methodology/uninstall.json`。`--keep-project-facts` 额外保留 `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`、`ai.json`、`AI.md`、`agent-policy.yaml`、`profile.yaml` 和 `openspec/config.yaml`；`--json` 输出机器可读计划（不带 `--yes` 时退出码 2）或回执。没有回执时退化为"只删除仍与 Kit 源文件逐字节一致的文件"。

`ai.json` 超限或结构非法、`AI.md` 未索引或超限、策略缺失、占位符未填、引用路径断裂、任务图/执行证据非法、Profile 非法、Skill 资源缺失、安装内容过期或平台适配不支持都会失败。Engineering Skill 会针对 Claude Code、Codex、OpenCode、Cursor、Gemini 和 Trae 安装并校验。旧 `ramer`、`fe-engineering`、`multi-agent` 入口不再兼容。

任务上下文由接入后的项目控制面解析；执行契约见 [CLI 接入指南](templates/engineering/references/onboarding.md)。

## 变更控制

```bash
openspec new change add-capability --schema harness-engineering
python3 docs/methodology/scripts/init_governance.py add-capability \
  --title "新增能力" --mode fullstack --owner team \
  --trigger explicit-selection

python3 docs/methodology/scripts/approve_design.py openspec/changes/add-capability \
  --actor reviewer --source pull-request --approval-id PR-123

openspec status --change add-capability --json
openspec validate add-capability --type change --strict --no-interactive
```

直接检查治理门禁用 `check_phase.py`，检查可实施设计方案包用 `check_design.py`，检查 OpenSpec 任务执行证据用 `check_execution.py`，显式记录降级/人工介入用 `record_skill_event.py`，统计结构化采用效果用 `skill_metrics.py`。

Explore 结束前运行 `preflight_lessons.py`；用 `record_failure.py` 记录 Fitness/测试/差异/生产失败，用 `create_lesson_candidate.py` 提议可复用预防，用 `retrieve_lessons.py` 检索激活经验，并通过 `approve_lesson.py` 在外部审批后激活。

## 权威文档

- [AI Coding 实战教程](docs/ai-coding-tutorial.zh.md)
- [Harness 架构](i18n/zh/core/harness-engineering.md)
- [变更生命周期](i18n/zh/core/change-lifecycle.md)
- [可实施设计评审](i18n/zh/core/design-review.md)
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
