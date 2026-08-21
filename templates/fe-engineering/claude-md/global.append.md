## 自动方法论路由

根据工作上下文**自动**应用对应的工程方法，无需手动调用：

### 后端开发（修改后端代码文件）
→ **自动应用 RAMER 循环**：READ（读路径文档）→ ANALYZE（分析模块边界）→ MODEL（抽象优先，契约先于实现）→ EXECUTE（实现）→ REVIEW（fitness 门禁）

### 前端开发（修改前端代码文件）
→ **自动应用 fe-engineering RADIR 工作流**：READ（检测技术栈+读路径文档）→ ANALYZE（诊断现状）→ DECOMPOSE（组件分解设计）→ IMPLEMENT（4铁律强制）→ VERIFY（typecheck+build+route+i18n）
→ 详见 `docs/methodology/core/frontend-engineering.md`

### 判断规则
- 目标文件在 `{{FRONTEND_DIR}}` 或包含前端特征目录（`src/views/`、`src/components/`、`src/service/api/`）→ 前端工作流
- 目标文件在 `{{BACKEND_DIR_PATTERN}}` 等后端模块 → 后端 RAMER 工作流
- 纯查询/阅读 → 不触发工作流，直接回答

## 多 Agent 并行模式（前后端联动）

> 详见 `docs/methodology/core/multi-agent.md`。可一键触发：`/multi-agent <需求描述>`（前后端联动时自动启用，包含契约定义 → 双 Agent 并行 → 合并验证全流程）。

当任务**同时涉及前端和后端**代码变更时，自动启用双 Agent 并行执行。

### 流程

1. **契约定义（主 Agent）**：识别前后端边界 → 提取共享数据契约（API 端点/字段/枚举）→ 用户确认
2. **并行执行**：Agent-BE（RAMER）+ Agent-FE（FE-Engineering）通过 `run_in_background: true` 同时启动，基于契约各自实现
3. **合并验证（主 Agent）**：字段对齐 → 枚举一致 → 路由同步 → 权限同步

### 降级

- 子 Agent 不可用 → 序列执行（先后端契约，再前端表现层）
- 单侧任务 → 不启用并行
