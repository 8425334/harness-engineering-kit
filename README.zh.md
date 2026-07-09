# AI 辅助开发方法论

将 AI Coding Agent 引入软件开发流程的完整工程方法论。适用于任何技术栈、任何项目规模。

> **语言**: 中文 | [English](README.md)

---

## 快速部署

在新项目中部署本方法论，只需两步：

### 步骤 1：运行初始化脚本

在项目目录下，打开 **Claude Code** / **Codex** / **Cursor** 的命令行，执行：

```bash
bash docs/methodology/scripts/init.sh --tier 1
```

脚本会完成文件复制和目录创建（幂等，可重复运行）。

### 步骤 2：让 Agent 完成配置

在同一个会话中，告诉 Agent：

```
根据项目实际情况，填充 CLAUDE.md 和 openspec/config.yaml 中的 {{占位符}}，
画出模块依赖图，补充构建命令和约定。
```

Agent 会：
1. 读取项目结构（`package.json`、`pom.xml`、目录树等）自动推断技术栈和构建命令
2. 替换 `CLAUDE.md` 和 `openspec/config.yaml` 中所有 `{{PLACEHOLDER}}`
3. 绘制模块依赖图（ASCII art）
4. 验证强制性 Skill 可用性
5. 运行 `--check` 确认配置完整

### 常用命令

```bash
bash docs/methodology/scripts/init.sh --tier 1     # 最小可用（推荐起点）
bash docs/methodology/scripts/init.sh --tier 2     # 追加 Fitness 质量门禁
bash docs/methodology/scripts/init.sh --tier 3     # 追加 RAMER Agent + CI 集成
bash docs/methodology/scripts/init.sh --check      # 仅检查当前配置状态
bash docs/methodology/scripts/init.sh --dry-run    # 预览操作，不实际修改
```

| Tier | 时间 | 脚本创建 | Agent 补全 |
|------|------|----------|------------|
| 1 | 5 分钟 | CLAUDE.md + OpenSpec + Superpowers + mandatory-skills + fe-engineering | 填充占位符、模块图、构建命令、技术栈 |
| 2 | +10 分钟 | Fitness scripts + rules + SDD docs + 根路径文档 | 替换 fitness 参数、补充约定 |
| 3 | +15 分钟 | RAMER Agent + CI 提示 | 配置 CI 流水线、E2E 测试 |

> 脚本是**幂等**的 — 重复运行不会覆盖已有文件。详细手动步骤见 [TRANSPLANT.md](TRANSPLANT.md)。

---

## 这是什么

本目录包含一套经过真实项目验证的 AI 辅助开发方法论。核心由四个组件构成：

| 组件 | 文档 | 说明 |
|------|------|------|
| **SDD** (Spec-Driven Development) | `core/sdd-workflow.md` | 规范驱动的开发流程，所有非 trivial 变更先写规格再实现 |
| **Fitness** (质量门禁) | `core/fitness-framework.md` | 分层质量检查体系，定义 AI Agent 的"完成条件" |
| **Harness Engineering** | `core/harness-engineering.md` | AI Agent 的工程化系统：入口配置、路径文档、技能、记忆 |
| **Mandatory Skills** | `core/mandatory-skills.md` | Agent 必须具备的 3 个 Skill：OpenSpec、Superpowers、Codegraph |

四个组件之上是统一的开发方法论：
- **后端**：**RAMER 循环** (`core/ramer-cycle.md` + `core/ramer-agent.md`) — 抽象优先、契约先于实现、fitness 门禁
- **前端**：**FE-Engineering RADIR 工作流** (`core/frontend-engineering.md`) — 4 铁律、组件分解、多 Agent 并行
- **通用**：**抽象优先建模** (`core/abstraction-first.md`)、**DDD 建模** (`core/ddd-modeling.md`)、**调试日志纪律** (`core/debug-log-discipline.md`)

## 谁需要用

- **技术负责人** — 将 AI Coding 从"个人技巧"提升为"团队工程能力"
- **开发者** — 在新项目中快速建立 AI 辅助开发的工作流
- **团队** — 需要可复制、可验证、可在多项目间移植的方法论

## 目录结构

```
docs/methodology/
├── README.md                           # 本文件（含一键迁移指南）
├── TRANSPLANT.md                       # 详细移植指南（Tier 1/2/3 手动步骤）
├── scripts/
│   └── init.sh                         # 一键迁移脚本
├── core/                               # 通用原则（技术栈无关）
│   ├── ramer-cycle.md                  # RAMER 循环
│   ├── ramer-agent.md                  # RAMER Agent 自动化
│   ├── abstraction-first.md            # 抽象优先建模
│   ├── ddd-modeling.md                 # 领域驱动设计建模
│   ├── debug-log-discipline.md         # 调试日志纪律
│   ├── frontend-architecture.md        # AI 原生前端架构（AIDM + FDD + RSC）
│   ├── frontend-engineering.md         # 前端工程能力模型（4铁律 + 多Agent并行）
│   ├── mandatory-skills.md             # 强制性 Skill 配置
│   ├── sdd-workflow.md                 # SDD 流程
│   ├── fitness-framework.md            # Fitness 质量门禁
│   └── harness-engineering.md          # Harness 工程化
└── templates/                          # 复制即用的模板
    ├── CLAUDE.md.template              # AI 入口配置
    ├── openspec-config.yaml.template   # SDD 配置
    ├── sdd-readme.md.template          # SDD 流程文档
    ├── path-document.md.template       # 路径文档 (AI.md + ai.json)
    ├── fitness/                        # Fitness 框架模板
    │   ├── README.md                   # 占位符参考 + 迁移步骤
    │   ├── fitness.py.template         # Fitness runner
    │   ├── check_*.py.template         # 10 个可移植检查脚本
    │   └── rules/*.md.template         # 11 个维度规则模板
    ├── ramer/                          # RAMER Agent 模板
    │   ├── README.md                   # 迁移步骤
    │   ├── SKILL.md.template           # /ramer skill 定义
    │   ├── ramer-design.js.template    # 设计工作流
    │   └── ramer-implement.js.template # 实现工作流
    ├── fe-engineering/                 # 前端工程集成模板
    │   ├── README.md                   # 迁移步骤
    │   ├── SKILL.md                    # /fe skill 定义
    │   ├── claude-md/                  # CLAUDE.md 追加片段
    │   └── ai-config/                  # AI.md + ai.json 片段
    └── mandatory-skills/               # 强制性 Skill 声明模板
        └── SKILLS.md.template          # 3 Skill 配置模板
```

## 核心原则

1. **文档先行，设计后行，实现最后** — 不读路径文档不动代码
2. **契约优先** — 先定义接口/DTO，确认设计，再写实现
3. **领域建模以 DDD 为骨架** — 战略（限界上下文）定边界，战术（聚合/实体/事件）定结构
4. **组合优于继承** — 继承深度 ≤ 1，优先 DI + 组合
5. **多态优于分支** — 嵌套 if/else ≥ 2 或 switch ≥ 3 → Strategy/Factory/Handler
6. **调试日志三阶段** — 编码后打日志、跑测试自检预期、通过后清理临时日志
7. **完成条件必须可执行** — 规则在仓库中，可被人阅读，也可被脚本执行
8. **前后端联动并行执行** — 契约定义后，前后端双 Agent 并行开发，合并验证
9. **完备的 Agent Skill 配置** — Agent 必须具备 OpenSpec、Superpowers、Codegraph 三项基础能力，缺失即降级

## 与 VibeCoding 的关系

本方法论关注 **工程过程层**（SDD + Fitness + Harness），与 VibeCoding（代码生成纪律层）互补：

- VibeCoding 定义 **如何写好代码**（PACE 路由、RIPER-7 阶段、状态持久化）
- 本方法论定义 **如何组织工程**（变更流程、质量门禁、Agent 系统配置）

两者可按需独立采用，也可组合使用。
