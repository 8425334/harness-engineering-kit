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

---

## 组件 5：Token 压缩保持（Compaction Preservation）

自动压缩是有损的——上下文窗口被压缩时，进行中任务的契约与状态可能被静默丢弃，Agent 会在任务中途丢失线索。压缩保持模式让本轮工作**在压缩前存盘、压缩后重新注入**，从而扛过压缩事件。

> 关于字节稳定的提示词缓存前缀不变式与完整五维上下文能力模型，见 `context-capability.md`。

### 模式

```
round-contract.md（≤50 行，始终保持最新）
        │   每轮开始前更新
        ▼
  PreCompact hook（matcher: auto | user）
        │   把 round-contract.md + 压缩触发 JSON 归档
        │   到 .claude/compaction-state/（保留最近 20 份）
        ▼
        ── 上下文被压缩 ──
        ▼
  SessionStart hook（matcher: compact）
        │   cat round-contract.md 重新注入上下文
        ▼
   Agent 带着契约继续
```

### 本轮契约文件（`.claude/round-contract.md`）

一份紧凑文件（≤50 行），只放**压缩后必须还记得**的事实：

| 段落 | 内容 |
|------|------|
| 当前任务 | 任务名、一句话目标、所在模块 |
| 关键契约字段 | API 端点、请求 BO 字段、返回 VO 字段、枚举 |
| 相关文件清单 | 后端（adapter/application/domain/infra）+ 前端（api/页面/组件） |
| 当前待办 | 本轮的下一步 |

规则：保持 ≤50 行；只放压缩后 Agent 仍需知道的事实；不要散文。`SessionStart(matcher=compact)` hook 会把本文件重新注入，保证本轮不丢失。

### Hook 接线（`settings.json`）

```json
{
  "hooks": {
    "PreCompact": [
      { "matcher": "auto", "hooks": [{ "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/save-state.sh" }] },
      { "matcher": "user", "hooks": [{ "type": "command", "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/save-state.sh" }] }
    ],
    "SessionStart": [
      { "matcher": "compact", "hooks": [{ "type": "command", "command": "cat ${CLAUDE_PROJECT_DIR}/.claude/round-contract.md 2>/dev/null || true" }] }
    ]
  }
}
```

### 存盘 Hook（`.claude/hooks/save-state.sh`）

- 归档 `round-contract.md` → `.claude/compaction-state/round-contract-<时间戳>.md`
- 捕获压缩触发 JSON → `.claude/compaction-state/compact-<时间戳>.json`
- 裁剪到最近 20 份归档（有界增长）
- 永不阻断压缩（始终 `exit 0`）

可部署模板：`templates/compaction/`（round-contract、save-state hook、settings 片段）。

Codex 当前没有 Claude `PreCompact` / `SessionStart` 的项目级等价 hook。使用同目录提供的显式降级方案：持续更新 `.codex/round-contract.md`，长轮次或预计压缩前运行 `bash .codex/hooks/save-state.sh`，恢复后重新读取契约和 `.codex-state/round-contract-*.md` 最新存档。不要在 `.codex/config.toml` 中写入尚未支持的 hook 配置键。

### 与记忆的关系

记忆（组件 4）跨会话持久化*事实*；压缩保持是在**会话内**把*进行中的本轮*扛过压缩事件。二者互补：记忆回答「我知道什么」，本轮契约回答「我现在在做什么」。
