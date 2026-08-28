# Terminology Glossary / 术语表

Key terms used across the methodology, with Chinese-English equivalents.

## Methodology / 方法论

| English | 中文 | Description |
|---------|------|-------------|
| Spec-Driven Development (SDD) | 规范驱动开发 | Write specs before implementation; all non-trivial changes go through proposal → specs → design → tasks → apply → archive |
| Fitness Framework | 质量门禁框架 | Tiered quality check system; defines AI Agent "completion conditions" |
| Harness Engineering | 工程化系统 | AI Agent engineering system: entry config, path documents, skills, memory |
| Mandatory Skills | 强制性技能 | OpenSpec, Superpowers, Codegraph — 3 skills every Agent must have |
| Path Document | 路径文档 | AI.md + ai.json pairs in directories; provide constraints and context for AI Agents |

## Backend / 后端

| English | 中文 | Description |
|---------|------|-------------|
| RAMER Cycle | RAMER 循环 | READ → ANALYZE → MODEL → EXECUTE → REVIEW — backend development workflow |
| RAMER Agent | RAMER 代理 | Automated agent executing the RAMER cycle, architecture-adaptive |
| Abstraction-First | 抽象优先 | Never write concrete implementation directly; always translate through ACL first |
| ACL (Abstraction-Contract-Logic) | 抽象-契约-逻辑 | Three-layer translation: Abstraction → Contract → Logic |
| Contract-First | 契约优先 | Define interfaces/DTOs first, confirm, then implement |
| Entity Quartet | 实体四件套 | Entity + VO + BO + Mapper + XML — standard domain object artifact set |
| DDD (Domain-Driven Design) | 领域驱动设计 | Strategic (bounded context) and tactical (aggregates, entities, value objects, events) modeling |
| Bounded Context | 限界上下文 | DDD strategic pattern; defines a boundary within which a domain model applies |
| Aggregate Root | 聚合根 | DDD tactical pattern; the entry point to an aggregate, enforces invariants |
| Domain Event | 领域事件 | Spring ApplicationEvent; for cross-service coordination without direct coupling |
| Hexagonal Architecture | 六边形架构 | Ports & Adapters pattern; domain logic isolated from infrastructure |

## Frontend / 前端

| English | 中文 | Description |
|---------|------|-------------|
| RADIR Workflow | RADIR 工作流 | READ → ANALYZE → DECOMPOSE → IMPLEMENT → VERIFY — frontend development workflow |
| 4 Iron Rules | 四条铁律 | Layering, Types-as-contract, Component ≤300 lines, Three-state coverage |
| Three-State Coverage | 三态覆盖 | Every data-fetching scenario must handle Loading, Empty, and Error states |
| Component Decomposition | 组件分解 | Parent (orchestration, ≤150 lines) + children in `modules/` (implementation, ≤300 lines) |
| FE-Engineering | 前端工程化 | The full frontend engineering capability model: iron rules, decomposition, quality gates |
| AIDM (AI-Native Domain Model) | AI原生领域模型 | Frontend domain modeling approach separating data, intent, and interaction |
| FDD (Federated Data Dependency) | 联邦数据依赖 | Component-level data dependency declaration pattern |
| RSC (Reactive State Container) | 响应式状态容器 | State management pattern inspired by React Server Components |

## Quality & Process / 质量与流程

| English | 中文 | Description |
|---------|------|-------------|
| Fitness Gate | 质量门禁 | Executable quality checks run before delivery |
| Hard Gate | 硬门禁 | Quality check whose failure blocks the pipeline (exit code 2) |
| Dry Run | 预演 | Preview mode showing what checks would run without actually executing |
| Tier (fast/normal/deep) | 层级 | Quality check depth: fast (per-change), normal (pre-commit), deep (pre-push/CI) |
| Three-Way Consistency | 三方一致性 | Entity, Mapper XML, and database schema must stay in sync |
| Verification Ledger | 验证账本 | Record of fitness check results over time |

## Agent System / Agent 系统

| English | 中文 | Description |
|---------|------|-------------|
| OpenSpec | OpenSpec | SDD toolchain; manages change lifecycle with `/opsx:*` commands |
| Superpowers | Superpowers | Long-term reference documents stored in `docs/superpowers/` |
| Codegraph | Codegraph | MCP code intelligence tool; provides explore/search/impact capabilities |
| Multi-Agent Parallel | 多Agent并行 | Contract-first → dual background agents (BE + FE) → merge verification |
| Auto-Trigger | 自动触发 | Global CLAUDE.md detects file context and auto-applies RAMER or FE-Engineering |
| Memory System | 记忆系统 | Persistent file-based memory indexed by MEMORY.md |

## Context & Caching / 上下文与缓存

| English | 中文 | Description |
|---------|------|-------------|
| Prompt Caching | 提示词缓存 | Anthropic server-side cache; byte-exact prefix match; cache reads bill ~0.1× base input |
| Context Capability | 上下文能力 | Five-dimension model: window & compression, cross-session memory, injection precision, caching efficiency, reasoning depth per token |
| Compaction | 上下文压缩 | Lossy auto-summarization of the context window; rewriting history invalidates the cache prefix |
| Cache Read | 缓存读取 | Tokens served from a cached prefix instead of reprocessed; billed at a reduced rate |
| Token | 令牌 | Basic unit of LLM context and billing |
| 20-block lookback | 20 块回看窗口 | A cache breakpoint can only walk back ≤20 content blocks to find the longest prefix match; exceeding it causes a silent cache miss |

## Transplant & Init / 移植与初始化

| English | 中文 | Description |
|---------|------|-------------|
| Tier 1/2/3 | 层级 1/2/3 | Progressive methodology deployment: core (5min), quality (15min), full (30min) |
| Transplant | 移植 | Process of deploying the methodology to a new project |
| Init Script | 初始化脚本 | `scripts/init.sh` — one-click methodology setup |
| Placeholder | 占位符 | `{{VARIABLE}}` markers in templates to be filled by the Agent |
| Idempotent | 幂等 | Script can be re-run safely without overwriting existing files |
