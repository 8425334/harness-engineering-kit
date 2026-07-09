# Agent 强制性 Skill 配置

Mandatory Agent Skills

定义 AI Coding Agent 在项目中**必须具备**的 3 个基础 Skill。这些 Skill 是 Agent 执行任何非 trivial 任务的前提条件，缺失任何一个都会导致能力大幅下降。

> 新项目通过 `init` 初始化或 Tier 1 移植时，必须确保这 3 个 Skill 已配置。检查方法见各 Skill 的"验证"章节。

## 1. OpenSpec — SDD 变更流程

### 职责

管理软件变更的完整生命周期：从需求探索、方案设计、规格定义到任务分解和归档。

### 核心能力

| 命令 | 阶段 | 说明 |
|------|------|------|
| `/opsx:explore` | 探索 | 需求分析、架构思考、方案对比 |
| `/opsx:propose` | 提案 | 生成 proposal + design + specs + tasks |
| `/opsx:apply` | 实现 | 按 tasks 逐步实现 |
| `/opsx:sync` | 同步 | Delta specs → 主 specs |
| `/opsx:archive` | 归档 | 完成变更，归档到主规格库 |

### 适用场景

- 新功能开发
- 跨模块重构
- 新增领域对象
- 任何非 trivial 变更

### 配置方式

项目根目录需存在 `openspec/config.yaml`，定义 schema、context 和 rules。模板见 `docs/methodology/templates/openspec-config.yaml.template`。

### 验证

```bash
ls openspec/config.yaml 2>/dev/null && echo "OK" || echo "MISSING: run openspec init"
openspec list --json 2>/dev/null && echo "OK" || echo "MISSING: openspec CLI not available"
```

### 降级

OpenSpec 不可用时，回退到手动 SDD 流程（手写 proposal/design/tasks 文件），但失去自动化状态追踪。

---

## 2. Superpowers — 长期计划与规格参考

### 职责

维护项目的**长期**参考文档：设计决策记录（ADR）、持久化规格、架构参考。与 OpenSpec 的**临时**变更生命周期互补。

### 核心能力

| 目录 | 用途 | 生命周期 |
|------|------|----------|
| `docs/superpowers/plans/` | 设计决策记录、架构方案 | 长期（项目存续期间） |
| `docs/superpowers/specs/` | 持久化规格参考 | 长期（随功能演进更新） |

### 与 OpenSpec 的分工

```
OpenSpec (临时)                    Superpowers (长期)
───────────────                    ──────────────────
管理"这个变更怎么做"              记录"为什么这么做"
proposal.md → 合入后归档          plans/*.md → 持续维护
specs delta → sync 到主 specs     specs/*.md → 功能演进时更新
变更完成 → archive                archive 后的关键决策 → 记录到 plans/
```

### 适用场景

- 记录重大架构决策（如"为什么选择 A 方案而非 B 方案"）
- 维护需要跨变更生命周期的规格（如领域模型、API 契约）
- 存储 AI Agent 可参考的长期上下文

### 配置方式

```bash
mkdir -p docs/superpowers/plans docs/superpowers/specs
```

### 验证

```bash
test -d docs/superpowers/plans && test -d docs/superpowers/specs && echo "OK" || echo "MISSING: mkdir -p docs/superpowers/plans docs/superpowers/specs"
```

### 降级

Superpowers 目录不存在时，长期决策记录分散在 git commit message 或 PR 描述中，难以检索。

---

## 3. Codegraph — 代码知识图谱

### 职责

提供毫秒级代码智能：符号搜索、调用链追踪、影响分析。替代低效的 `grep + read` 循环，是 AI Agent 理解代码的核心工具。

### 核心能力

| 工具 | 用途 | 示例 |
|------|------|------|
| `codegraph_explore` | **首选探索工具**——理解区域/流程/架构 | "how does driver dispatch work" → 直接返回相关源码 |
| `codegraph_search` | 符号名快速查找 | `codegraph_search("AuthService")` → 所有匹配位置 |
| `codegraph_node` | 单个符号完整定义（含调用者/被调用者） | 查看函数签名 + body |
| `codegraph_callers` | 谁调用了这个符号 | 定位上游依赖 |
| `codegraph_callees` | 这个符号调用了谁 | 追踪下游依赖 |
| `codegraph_impact` | 修改影响分析 | 重构前评估影响范围 |
| `codegraph_files` | 项目文件树 | 了解目录结构 |

### 使用原则

1. **先 explore，再 search，最后才 grep**：`codegraph_explore` 一次调用通常能回答 80% 的代码理解问题
2. **不重复读取**：codegraph 已返回完整源码时，不要再用 Read 工具重读同一文件
3. **影响分析先于重构**：修改任何被多处引用的符号前，先跑 `codegraph_impact`

### 配置方式

Codegraph 作为 MCP Server 配置在 `settings.json` 中：

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "npx",
      "args": ["@anthropic/codegraph-mcp-server"]
    }
  }
}
```

### 验证

```bash
# 检查 MCP 配置中是否有 codegraph
grep -r "codegraph" ~/.claude/settings.json ~/.claude/settings.local.json 2>/dev/null && echo "OK" || echo "WARN: codegraph MCP not found in settings"
```

### 降级

Codegraph 不可用时，回退到 `grep` + `Read` 循环。效率降低但功能不受阻。首次使用需 `codegraph init` 建立索引。

---

## Skill 依赖矩阵

| 场景 | OpenSpec | Superpowers | Codegraph |
|------|:--------:|:-----------:|:---------:|
| Bug 修复 | ○ | - | ● |
| 新功能 (单模块) | ● | ○ | ● |
| 新功能 (跨模块) | ● | ● | ● |
| 重构 | ● | ● | ● |
| 代码审查 | - | - | ● |
| 架构决策 | - | ● | ● |
| 新项目 init | ● | ● | ● |

> ● = 必须 &nbsp;&nbsp; ○ = 推荐 &nbsp;&nbsp; - = 不需要

---

## 新项目集成

在 `init` 或 Tier 1 移植时，按顺序检查：

```bash
# 1. OpenSpec
test -f openspec/config.yaml || echo "TODO: openspec init"

# 2. Superpowers
test -d docs/superpowers/plans || echo "TODO: mkdir -p docs/superpowers/plans docs/superpowers/specs"

# 3. Codegraph
grep -r "codegraph" ~/.claude/settings.* 2>/dev/null || echo "TODO: add codegraph MCP to settings.json"
```

参见 `docs/methodology/TRANSPLANT.md` 完整的 Tier 1/2/3 移植步骤。
