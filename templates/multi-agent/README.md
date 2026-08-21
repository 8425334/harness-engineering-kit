# Multi-Agent Parallel Templates

前后端联动双 Agent 并行模式的可移植模板。复制到新项目即可获得双 Agent 并行开发能力。

## 文件清单

```
multi-agent/
├── README.md                    # 本文件
└── SKILL.md.template            # /multi-agent skill 入口定义（自包含，无需替换占位符）
```

## 迁移步骤

### 1. 拷贝模板

```bash
# 项目本地部署
mkdir -p .claude/skills/multi-agent
cp docs/methodology/templates/multi-agent/SKILL.md.template .claude/skills/multi-agent/SKILL.md

# 全局部署（跨项目可用）
mkdir -p ~/.claude/skills/multi-agent
cp docs/methodology/templates/multi-agent/SKILL.md.template ~/.claude/skills/multi-agent/SKILL.md
```

### 2. 配置路由规则

在项目根 `CLAUDE.md` 添加方法论路由：

```markdown
- 前端（*.vue / *.tsx / *.ts）→ fe-engineering RADIR（/fe）
- 后端（*.java / Mapper XML / *.sql）→ RAMER 循环（/ramer）
- 前后端联动 → /multi-agent（契约先行，双 Agent 并行）
```

### 3. 验证

```bash
/multi-agent 新增一个需要后端接口 + 前端页面的业务功能
```

## 依赖

- **Agent-BE**：依赖 RAMER 循环 skill（`templates/ramer/SKILL.md.template`）
- **Agent-FE**：依赖 fe-engineering skill（`templates/fe-engineering/SKILL.md`）
- **契约先行**：依赖抽象优先建模原则（`core/abstraction-first.md`）

详见 `core/multi-agent.md`（英文）与 `i18n/zh/core/multi-agent.md`（中文）。
