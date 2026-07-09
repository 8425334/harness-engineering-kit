# FE-Engineering 集成模板

将前端工程能力模型（4铁律 + 组件分解 + 多Agent并行）移植到新项目。

## 前置条件

- 项目已有 `CLAUDE.md`（根目录）
- 前端项目目录存在（Vue/React/Angular/Svelte 均可）
- 全局 Skill 目录 `~/.claude/skills/` 可用

## 占位符说明

移植时替换以下占位符：

| 占位符 | 含义 | 示例 |
|--------|------|------|
| `{{PROJECT_NAME}}` | 前端项目名 | `coil-backend-ui` |
| `{{FRONTEND_DIR}}` | 前端项目目录 | `coil-backend-ui/` |
| `{{BACKEND_DIR_PATTERN}}` | 后端模块 glob | `coil-service/*`, `coil-app/*`, `ruoyi-*` |
| `{{VIEWS_PATH}}` | 视图目录 | `src/views/coil/` |
| `{{API_PATH}}` | API 层路径 | `src/service/api/coil/` |
| `{{TYPES_PATH}}` | 类型定义路径 | `src/typings/api/` |

---

## Tier 1：即刻启用（5 分钟）

### 1.0 检查强制性 Skill

FE-Engineering 依赖 3 个基础 Agent Skill。使用 `/fe` 前确认已配置：

```bash
# OpenSpec — SDD 变更流程
test -f openspec/config.yaml || echo "TODO: openspec init"

# Superpowers — 长期参考文档
test -d docs/superpowers/plans || echo "TODO: mkdir -p docs/superpowers/plans docs/superpowers/specs"

# Codegraph — 代码智能（MCP）
grep -r "codegraph" ~/.claude/settings.* 2>/dev/null || echo "TODO: add codegraph MCP to settings.json"
```

详见 `docs/methodology/core/mandatory-skills.md`。

### 1.1 安装全局 Skill

```bash
cp -r docs/methodology/templates/fe-engineering/SKILL.md ~/.claude/skills/fe-engineering/SKILL.md
```

> 如果 SKILL.md 在模板目录中不存在，说明 skill 已在全局安装（`~/.claude/skills/fe-engineering/SKILL.md`），跳过此步。

### 1.2 更新全局 CLAUDE.md

在 `~/.claude/CLAUDE.md` 的"自动方法论路由"章节后，追加 `claude-md/global.append.md` 的内容。

### 1.3 更新项目 CLAUDE.md

在项目根 `CLAUDE.md` 中：
- 将 "Mandatory Workflow" 章节更新为引用自动触发
- 在 "Frontend" 章节中添加 fe-engineering 引用

参考 `claude-md/project.append.md`。

### 1.4 更新前端项目 AI.md

在前端项目根目录 `AI.md` 顶部添加引用：

```markdown
> **前端工程能力模型**：本项目遵循 [前端工程 4 铁律 + 组件分解模式](../../docs/methodology/core/frontend-engineering.md)。使用 `/fe <需求描述>` 触发前端工程 RADIR 工作流。
```

---

## Tier 2：深度集成（1 小时）

### 2.1 创建路径文档

为核心业务目录创建 `AI.md` / `ai.json` 对：

```
{{FRONTEND_DIR}}/src/views/<module>/
├── AI.md              # 模块约束（编辑范围、禁止事项、依赖规则）
├── ai.json            # 结构化约束（供工具读取）
├── index.vue          # 页面编排层
└── modules/           # 子组件
```

模板：参考 `ai-config/ai-md.append.md` 和 `ai-config/ai-json.engineering.json`。

### 2.2 配置 ESLint 分层检查

在 `eslint.config.js` 中添加禁止跨层导入规则：

```js
// 禁止 views/components 直接导入 axios/fetch
rules: {
  'no-restricted-imports': ['error', {
    patterns: [{
      group: ['axios', 'fetch'],
      message: '请通过 src/service/api 封装接口调用'
    }]
  }]
}
```

### 2.3 CI 中加入类型 + 构建阻断

```yaml
# GitHub Actions 示例
- name: Type Check
  run: pnpm typecheck
- name: Build
  run: pnpm build:dev
```

---

## Tier 3：完整落地（持续）

### 3.1 Fitness 前端检查脚本

参考 `docs/fitness/scripts/fitness.py` 的模式，添加前端专项检查：

| 检查项 | 方法 | 阻断 |
|--------|------|------|
| 文件规模 | `wc -l` > 300 行 | REWORK |
| any 类型 | grep `: any` | FAIL |
| 分层违规 | grep `axios\|fetch` in views/ | FAIL |
| 缺三态 | 检查 template 中 loading/empty/error | REWORK |
| 路由同步 | 新页面是否在 routes.ts 中 | FAIL |
| i18n 同步 | 新文案是否在 locales 中 | WARN |

### 3.2 E2E 测试

引入 Playwright 或 Cypress，覆盖关键用户路径。

### 3.3 组件库 / 设计系统

建立 `src/components/common/` 通用组件库，配合 Storybook 文档。
