# Harness Engineering

Harness Engineering 是 AI Agent 的工程化系统 — 它不是某一个工具，而是让代码仓库成为 Agent 可读、可验证、可纠偏的运行环境的一组模式。

## 通用原则

Harness Engineering 的核心模型：

```
        反馈回路
             ▲
             │
系统可读性 ─── 防御机制 ─── 自动化反馈
```

1. **系统可读性**：让仓库结构能被 AI 理解 — CLAUDE.md、路径文档、模块图
2. **防御机制**：收敛 AI 的行动空间 — Fitness 规则、架构边界检查、权限控制
3. **反馈回路**：让 AI 能持续修正 — 编译错误、测试结果、fitness 报告

---

## 组件一：CLAUDE.md — AI 入口配置

`CLAUDE.md`（或 `AGENTS.md`）是仓库的 AI 入口点。它是 AI Agent 进入项目时读到的第一份文档。

### 六个强制节

| 节 | 内容 | 为什么必须 |
|----|------|-----------|
| **Mandatory Workflow** | 项目开发周期定义（如 RAMER 循环） | Agent 需要知道"先做什么" |
| **Architecture Overview** | 模块依赖图（哪个模块可以依赖哪个） | Agent 需要知道边界 |
| **Build & Run Commands** | 编译、测试、打包的精确命令 | Agent 需要快速反馈循环 |
| **Key Conventions** | 领域特定模式（如 Entity Quartet） | Agent 需要知道项目特有约定 |
| **SDD Reference** | 指向 SDD 流程文档的引用 | Agent 需要知道变更流程 |
| **Fitness Gate** | 质量门禁说明和调用方式 | Agent 需要知道完成条件 |

### 编写原则

- 入口比说明更重要 — 把 Agent 带到正确的位置，而不是让它理解整个工程
- 精确命令优于描述性说明 — "运行 `mvn -pl my-service -am compile -q`" 优于"编译项目"
- 模块依赖图用 ASCII art — 一目了然，Agent 和人都能读

---

## 组件二：路径文档系统（AI.md + ai.json）

路径文档是放在目录级别的上下文指南。当 AI Agent 要修改某个目录的文件时，先读该目录的路径文档。

### 双文件模式

| 文件 | 格式 | 用途 |
|------|------|------|
| `AI.md` | Markdown | 人类阅读的叙事指南 |
| `ai.json` | JSON | 机器读取的结构化约束 |

两者语义一致，格式不同。Fitness 规则检查它们的同步性。

### AI.md 八个标准节

1. **适用范围** — 本文档管理哪些目录
2. **目录职责** — 该目录负责什么
3. **可修改范围** — 允许修改什么
4. **禁止事项** — 绝对不能做什么
5. **依赖约束** — 依赖什么、被什么依赖、允许/禁止的依赖方向
6. **性能要求** — 查询、IO、缓存、并发约束
7. **测试要求** — 什么变更需要测试、测试类型
8. **交付说明** — 变更时需要同步更新什么（SQL 脚本、配置、文档）

### ai.json 结构

```json
{
  "$version": "1.0",
  "scope": "当前目录及其子目录，除非下层目录另有 AI.md",
  "responsibilities": ["该目录的职责列表"],
  "allowed": ["允许的操作列表"],
  "forbidden": ["禁止的操作列表"],
  "dependencies": {
    "allow": [],
    "deny": [],
    "rules": ["依赖规则列表"]
  },
  "performance": ["性能约束"],
  "testing": ["测试要求"],
  "delivery": ["交付检查项"],
  "ext": {}
}
```

### 优先级链

当多个路径文档覆盖同一目录时：

```
最近的 ai.json > 最近的 AI.md > 父级 AI.md > 根 AI.md > AGENTS.md
```

**子目录文档可以细化父级规则，但不能违反父级规则。** 当本地规则与全局规则冲突时，优先保证架构一致性和边界稳定性。

### 哪些目录应该有路径文档

- 仓库根目录
- 顶层模块目录
- 复杂业务模块目录
- 有特殊边界、规则或性能敏感性的目录

### 新增目录规则

新增非 trivial 目录时，先创建 `AI.md`，再添加代码。

---

## 组件三：Skill 工作流自动化

Skills 是通过 slash command 触发的可复用工作流脚本。常见操作：

| Skill | 作用 |
|-------|------|
| `propose` | 创建变更提案 + 生成全套产物 |
| `apply` | 按任务清单逐步实现 |
| `sync` | 同步 delta specs 到主规格库 |
| `archive` | 归档完成的变更 |
| `explore` | 探索性思考，澄清需求 |

Skills 让工作流不依赖团队记忆 — 每次执行都是一致的、可重复的。

### 强制性 Skill

所有项目必须配置 3 个基础 Skill，详见 `docs/methodology/core/mandatory-skills.md`：

| Skill | 类别 | 职责 |
|-------|------|------|
| OpenSpec | SDD 工作流 | 变更生命周期管理（/opsx:*） |
| Superpowers | 参考系统 | 长期设计决策与规格参考 |
| Codegraph | 代码智能 | 符号搜索、调用链追踪、影响分析 |

缺失任何一个 Skill 都会导致 Agent 能力降级。init/移植时必须在 Tier 1 阶段验证。

---

## 组件四：持久化记忆系统

AI Agent 需要在跨会话间记住用户偏好、项目上下文和反馈。

### 四种记忆类型

| 类型 | 存储内容 | 示例 |
|------|---------|------|
| **user** | 用户角色、偏好、知识背景 | "用户是资深后端，React 经验较少" |
| **feedback** | 纠正和确认 | "不要 mock 数据库 — 上次导致生产事故" |
| **project** | 进行中的工作、目标、决策 | "下周四合并冻结，非关键 PR 暂停" |
| **reference** | 外部系统指针 | "Bug 跟踪用 Linear 项目 INGEST" |

### 记忆文件格式

```markdown
---
name: <名称>
description: <一句话描述>
type: user | feedback | project | reference
---

<内容>
```

### 什么不该存为记忆

- 代码模式、架构约定（应该在代码中或 CLAUDE.md 中）
- Git 历史（`git log` 才是权威源）
- 调试方案（修复在代码中，commit message 有上下文）
- 临时任务状态（用 task tracking，不是 memory）
