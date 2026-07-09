# 方法论移植指南

将这套 AI 辅助开发方法论部署到新项目，按 3 个 Tier 递进。每个 Tier 独立交付价值 — 可以在任意 Tier 停下。

---

## Tier 1：最小可用（~10 分钟）

**目标：让 AI Agent 理解项目结构和基本规则。**

### 检查清单

- [ ] 1.1 复制 `templates/CLAUDE.md.template` → 项目根目录 `CLAUDE.md`
- [ ] 1.2 填入 `{{PROJECT_NAME}}`：项目名称和一句话描述
- [ ] 1.3 填入 `{{WORKFLOW_NAME}}`：工作流名称（推荐 "RAMER" 或自定义）
- [ ] 1.4 填入 `{{BUILD_COMMAND}}`：单模块编译命令
- [ ] 1.5 填入 `{{TEST_COMMAND}}`：单类测试命令
- [ ] 1.6 填入 `{{FULL_BUILD_COMMAND}}`：完整构建命令
- [ ] 1.7 填入 `{{FITNESS_COMMAND}}`：质量门禁命令（先写占位，Tier 2 实现）
- [ ] 1.8 绘制模块依赖图（ASCII art），替换 `{{MAIN_APP}}`、`{{MODULE_A}}` 等占位符
- [ ] 1.9 填写 Key Conventions 节：列出 2-3 个最重要的项目约定
- [ ] 1.10 删除模板中的 `<!-- -->` 注释块和占位符说明
- [ ] 1.11 提交 `CLAUDE.md` 到仓库

### 强制性 Skill 配置

- [ ] 1.12 **OpenSpec**：运行 `openspec init` 或在项目根创建 `openspec/config.yaml`（参考 `templates/openspec-config.yaml.template`）
- [ ] 1.13 **Superpowers**：创建 `docs/superpowers/plans/` 和 `docs/superpowers/specs/` 目录
- [ ] 1.14 **Codegraph**：确认 MCP 配置中有 codegraph（检查 `~/.claude/settings.json` 中是否有 `"codegraph"` 条目）
- [ ] 1.15 复制 `templates/mandatory-skills/SKILLS.md.template` → `docs/methodology/core/mandatory-skills.md`，填入项目名

验证命令：
```bash
test -f openspec/config.yaml || echo "TODO: openspec init"
test -d docs/superpowers/plans || echo "TODO: mkdir -p docs/superpowers/plans docs/superpowers/specs"
grep -r "codegraph" ~/.claude/settings.* 2>/dev/null || echo "TODO: add codegraph MCP to settings.json"
```

详见 `docs/methodology/core/mandatory-skills.md`。

### 验证

AI Agent 在新会话中应该能：
- 说出项目的模块结构和依赖方向
- 用正确的命令编译和测试
- 遵循你指定的编码约定
- 使用 OpenSpec 管理变更流程
- 使用 Codegraph 快速探索代码

---

## Tier 2：自动化质量门禁（~30 分钟）

**目标：让 AI Agent 有明确的"完成条件"，失败能自动阻断。**

### 检查清单

- [ ] 2.1 创建 `docs/fitness/` 目录
- [ ] 2.2 按 `templates/fitness/README.md` 的迁移步骤拷贝 runner 和 check 脚本到 `docs/fitness/scripts/`，`chmod +x fitness.py`
- [ ] 2.3 拷贝 `templates/fitness/rules/*.md.template` 到 `docs/fitness/`（去掉 `.template` 后缀），按需删除不适用的维度
- [ ] 2.4 用 `grep -rn '{{' docs/fitness/` 列出占位符，按下表替换：
  - `{{SQL_UPDATE_PREFIX}}`、`{{MAX_IMPL_LINES}}`、`{{COVERAGE_THRESHOLD}}` 等标量占位符
  - `{{INFRA_MODULE}}` / `{{APP_MODULE}}` / `{{CONTROLLER_ROOTS}}` 等路径占位符
  - `{{BACKEND_TEST_COMMAND}}` / `{{TYPECHECK_COMMAND}}` / `{{BUILD_COMMAND}}` 等命令占位符
- [ ] 2.5 创建 `docs/fitness/README.md`（规则手册）和 `docs/fitness/verification-ledger.md`（验证账本）
- [ ] 2.6 创建 `docs/fitness/AI.md` + `ai.json`（架构边界规则要求）
- [ ] 2.7 运行 `python3 docs/fitness/scripts/fitness.py --tier fast --dry-run` 验证规则可解析
- [ ] 2.8 运行 `python3 docs/fitness/scripts/fitness.py --tier fast` 确认通过
- [ ] 2.9 更新 `CLAUDE.md` 中的 `{{FITNESS_COMMAND}}` 为实际命令

### SDD 配置

- [ ] 2.10 复制 `templates/openspec-config.yaml.template` → `openspec/config.yaml`
- [ ] 2.11 填入技术栈、模块结构、约定
- [ ] 2.12 复制 `templates/sdd-readme.md.template` → `docs/sdd/README.md`
- [ ] 2.13 填入实际的命令和工作流

### 路径文档

- [ ] 2.14 为项目根目录创建 `AI.md` + `ai.json`（参考 `templates/path-document.md.template`）
- [ ] 2.15 为 3-5 个核心模块目录创建 `AI.md` + `ai.json`
- [ ] 2.16 确保每个文件都有 8 个标准节

### 验证

- CI 或 pre-commit hook 运行 fitness gate
- Hard gate 失败能阻断流程
- AI Agent 在修改文件前读取了路径文档

---

## Tier 3：完整部署（~2 小时）

**目标：全面的工程化体系，多 Agent 协作就绪。**

### 检查清单

- [ ] 3.1 Fitness 规则覆盖 6+ 质量维度：
  - 架构边界检查
  - 代码规模限制
  - 安全基线扫描
  - 权限/认证注解检查
  - SQL/数据库迁移格式检查
  - 文档同步检查（AI.md ↔ ai.json）
- [ ] 3.2 为所有重要目录创建 `AI.md` + `ai.json` 配对
- [ ] 3.3 配置 SDD 工作流工具链（OpenSpec CLI 或等效工具）
- [ ] 3.4 安装和配置 Skills（/propose, /apply, /sync, /archive 等）
- [ ] 3.5 配置持久化记忆系统：
  - 确定记忆存储位置
  - 创建 `MEMORY.md` 索引文件格式
  - 定义记忆类型（user/feedback/project/reference）
- [ ] 3.6 配置 pre-commit / pre-push hooks 接入 fitness gate
- [ ] 3.7 创建 AI Agent 特定的 CI 检查（区分 AI 提交和人工提交）
- [ ] 3.8 编写团队上手文档（如何使用这套方法论做日常开发）
- [ ] 3.9 运行一次完整的 SDD 变更作为演练

### 验证

- 端到端：从需求到归档的完整 SDD 流程跑通
- 所有 fitness 维度有规则覆盖
- 团队能独立使用这套系统

---

## 定制点汇总

以下是在移植过程中需要做项目特定决策的所有点位：

### Tier 1 决策

| 定制点 | 占位符 | 决策 |
|--------|--------|------|
| 项目名称 | `{{PROJECT_NAME}}` | 简短描述 |
| 工作流名称 | `{{WORKFLOW_NAME}}` | RAMER 或其他 |
| 编译命令 | `{{BUILD_COMMAND}}` | 单模块的精确命令 |
| 测试命令 | `{{TEST_COMMAND}}` | 单类的精确命令 |
| 模块依赖图 | ASCII art 图 | 需要理解项目架构 |
| 关键约定 | Key Conventions 节 | 2-3 个最重要的编码模式 |

### Tier 2 决策

| 定制点 | 占位符 | 决策 |
|--------|--------|------|
| 质量维度 | fitness 规则文件 | 哪些维度对项目最重要？ |
| Hard Gate 规则 | `hard_gate: true` | 哪些失败必须阻断流程？ |
| SDD 工具 | openspec 或等效 | 用什么管理变更产物？ |
| 路径文档覆盖 | AI.md/ai.json 位置 | 哪些目录最需要上下文文档？ |

### Tier 3 决策

| 定制点 | 决策 |
|--------|------|
| Skills 平台 | Claude Code / Cursor / 自定义 / 多平台 |
| 记忆存储 | 文件系统 / 向量数据库 / 外部服务 |
| CI 集成 | GitHub Actions / GitLab CI / Jenkins / 其他 |
| Hook 策略 | AI 提交 vs 人工提交区分策略 |

---

## 适配不同技术栈

### Python 项目

- `CLAUDE.md` 构建命令：`pytest`、`ruff`、`mypy`
- 模块图：Python 包结构（`src/`、`tests/`、`lib/`）
- 约定：Repository 模式、Service 层、DTO（Pydantic/dataclass）
- Fitness 规则：`pytest --tb=short`、`ruff check .`、`mypy src/`

### Node.js / TypeScript 项目

- `CLAUDE.md` 构建命令：`pnpm build`、`pnpm test -- --testPathPattern=xxx`
- 模块图：monorepo 包结构（`packages/`、`apps/`）
- 约定：Service → Controller → Repository 分层、Zod schema
- Fitness 规则：`pnpm lint`、`pnpm test:run`、`pnpm typecheck`

### Go 项目

- `CLAUDE.md` 构建命令：`go build ./...`、`go test ./pkg/... -run TestXxx`
- 模块图：`cmd/`、`internal/`、`pkg/` 结构
- 约定：Interface 定义在消费方、`context.Context` 传递
- Fitness 规则：`go vet ./...`、`golangci-lint run`、`go test ./...`

### 多语言 / 混合项目

- 为每种语言单独建一个 fitness 规则文件
- `CLAUDE.md` 的架构图展示跨语言模块关系
- 路径文档说明每个目录的语言和框架

---

## 常见问题

**Q: 必须从 Tier 1 开始吗？**
A: 推荐按顺序来。每个 Tier 依赖前一个。跳过 Tier 1（没有 CLAUDE.md）会让 AI Agent 在"盲目"状态下工作。

**Q: 必须用 OpenSpec CLI 吗？**
A: 不必须。SDD 工作流是工具无关的。你可以用任何方式管理 proposal/specs/design/tasks 产物。OpenSpec 只是其中一种实现。

**Q: Fitness 执行器必须用 Python 吗？**
A: 不必须。核心是"规则在仓库中 + 可被人和机器读取 + 可执行"。你可以用 Makefile、shell 脚本、Node.js 脚本实现同样的效果。Python 版本的优势是零依赖 + 跨平台。

**Q: 路径文档太多，维护成本高怎么办？**
A: Tier 2 只需要 3-5 个核心目录。只给"经常被修改"和"边界容易出错"的目录写路径文档。不要在 Tier 1/2 追求全覆盖。

**Q: 方法论和现有 CI 怎么集成？**
A: Fitness gate 可以和 CI 并行运行。最简单的方式：在 CI 脚本中加一行 `python3 docs/fitness/scripts/fitness.py --tier normal`，失败阻断 pipeline。
