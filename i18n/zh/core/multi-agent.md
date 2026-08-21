# 多 Agent 并行模式（前后端联动）

当任务**同时涉及前端和后端**代码变更时，串行执行浪费大量等待时间。双 Agent 并行——Agent-BE 遵循 **RAMER 循环**、Agent-FE 遵循 **FE-Engineering RADIR 工作流**——在 API 契约边界处干净地划分工作，最后合并验证双方产出。

> 配套 Skill：`/multi-agent <需求描述>`（`templates/multi-agent/SKILL.md.template`）。自动检测任务边界、定义共享契约、并行启动两个后台 Agent、合并验证字段对齐。

## 1. 适用场景

- 新增业务功能（需要后端接口 + 前端页面）
- 修改现有功能（前后端都需要改）
- API 契约变更（字段增删改）
- 跨模块重构（同时跨越两层）

**单侧任务不得启用并行模式**——直接用对应工作流（后端 `/ramer`，前端 `/fe`）。

## 2. 执行架构

```
用户需求（前后端联动）
       │
       ▼
┌─ 阶段 0: 契约定义（主 Agent）─────────────────────┐
│                                                    │
│  1. 识别前后端边界                                  │
│  2. 提取共享数据契约：                              │
│     API 端点 + HTTP 方法                            │
│     请求参数字段 + 类型                             │
│     返文字段 + 类型                                 │
│     枚举/状态码                                     │
│  3. 输出契约摘要，向用户确认后进入并行               │
│                                                    │
└────────────────────────────────────────────────────┘
       │
       ├──────────────────┐
       ▼                  ▼
┌─ Agent-BE ────────┐  ┌─ Agent-FE ───────────────┐
│ (background)      │  │ (background)             │
│                   │  │                          │
│ RAMER: R→A→M→E→R │  │ RADIR: R→A→D→I→V        │
│                   │  │                          │
│ 基于契约实现:     │  │ 基于契约实现:            │
│ DTO/BO/VO        │  │ types/API 封装           │
│ Controller/Service│  │ views/components         │
│ Mapper/XML        │  │ 路由/i18n                │
│ fitness 门禁      │  │ typecheck+build 门禁     │
└──────────────────┘  └──────────────────────────┘
       │                  │
       └────────┬─────────┘
                ▼
┌─ 阶段 2: 合并验证（主 Agent）─────────────────────┐
│                                                    │
│  1. 字段对齐：后端返文字段 vs 前端类型定义           │
│  2. 枚举一致：后端枚举值 vs 前端常量                 │
│  3. 路由同步：新增页面是否注册                       │
│  4. 权限同步：按钮编码是否一致                       │
│  5. 不一致 → 修复 → 重新验证                        │
│                                                    │
└────────────────────────────────────────────────────┘
```

## 3. 阶段 0 — 契约定义（关键步骤）

契约是并行执行的基础。必须**在启动两个 Agent 前**与用户确认。

### 3.1 API 契约模板

```yaml
endpoints:
  - method: GET/POST/PUT/DELETE
    path: /api/xxx/xxx
    summary: 接口用途
    request:
      params:  # Query 参数
        - name: pageNum, type: int, required: true, desc: 页码
      body:  # Request Body 字段
        - name: fieldName, type: string, required: true, desc: 字段说明
    response:
      - name: id, type: long, desc: 主键
      - name: fieldName, type: string, desc: 字段说明
    enums:
      - name: StatusEnum, values: [ACTIVE, INACTIVE, DELETED]
```

### 3.2 检测前后端边界

根据项目 CLAUDE.md 和目录结构自动检测：
- **后端目标目录**：Java 模块（如 `coil-service/`、`coil-app/`、`ruoyi-*`）
- **前端目标目录**：前端工程源码（如 `coil-backend-ui/src/` 或框架对应的 `src/`）
- **契约共享方式**：API 类型定义文件、枚举常量文件

### 3.3 人工确认

契约定义完成后，向用户确认：API 端点列表、请求/返文字段、枚举值。确认后才并行启动两个 Agent。

## 4. 阶段 1 — 并行启动

确认契约后，同时启动两个后台 Agent。

- **Agent-BE**（`general-purpose`）：Prompt 包含 RAMER 循环（`core/ramer-cycle.md` + `core/ramer-agent.md`）、从 CLAUDE.md 读取的项目架构上下文、契约字段详情、目标目录、fitness gate 命令。
- **Agent-FE**（`general-purpose`）：Prompt 包含 RADIR 工作流 + 4 铁律（`core/frontend-engineering.md`）、从 `package.json` 检测的技术栈、契约字段详情、目标目录、typecheck + build 门禁命令。

### 并行启动规则

1. 两个 Agent 通过 `run_in_background: true` 同时启动
2. 各自独立执行，不互相等待
3. 主 Agent **不轮询**，双方完成后自动收到通知
4. 双方完成后，主 Agent 进入合并验证阶段

## 5. 阶段 2 — 合并验证

双方 Agent 完成后，主 Agent 执行交叉验证：

| 检查 | 后端 vs 前端 |
|------|-------------|
| 字段对齐 | Controller 返文字段 vs 前端 `types`；请求参数 vs API 调用参数；检测遗漏/命名不一致 |
| 枚举一致性 | 后端枚举类值 vs 前端常量；状态码映射完整 |
| 路由同步 | 新增页面是否注册到路由配置；菜单配置是否更新 |
| 权限同步 | 后端权限注解 vs 前端按钮权限编码 |

**修复循环**：发现不一致 → 直接修复 → 重新验证。无法自动修复 → 列出差异，请用户手动处理。

## 6. 降级策略

| 场景 | 策略 |
|------|------|
| 子 Agent 不可用（配额/不可达） | 序列执行：先后端契约实现，再前端表现层 |
| 单侧任务 | 不启用并行，直接用对应工作流 |
| 契约确认被拒绝 | 重新讨论需求，调整契约后再次确认 |
| 实现过程中契约变更 | 子 Agent 通过主 Agent 协调变更，双方同步更新 |

## 7. 与其他方法论的关系

| 组件 | 文档 |
|------|------|
| 后端循环 | `core/ramer-cycle.md` + `core/ramer-agent.md` |
| 前端循环 | `core/frontend-engineering.md`（4 铁律 + 组件分解） |
| 契约先行 | `core/abstraction-first.md` |
| 质量门禁 | `core/fitness-framework.md`（后端）+ `core/frontend-engineering.md` §3（前端） |

## 8. 移植指南

在新项目启用多 Agent 并行：

1. 在项目根 `CLAUDE.md` 添加路由规则：前端变更 → RADIR（`/fe`），后端变更 → RAMER（`/ramer`），前后端联动 → `/multi-agent`。
2. 部署 skill：`cp templates/multi-agent/SKILL.md.template .claude/skills/multi-agent/SKILL.md`。
3. 确保 Agent-BE/Agent-FE 的 Prompt 从 CLAUDE.md 获取共享契约、项目架构上下文与两个质量门禁。
4. 轻量采纳可只走串行降级路径——无需额外配置。
