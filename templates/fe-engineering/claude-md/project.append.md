## Mandatory Workflow: Auto-Triggered RAMER / FE-Engineering

**No code changes before applicable path documents are read and the model/design is clear.**

> **自动触发**：根据目标文件位置自动选择工作流，无需手动调用。
> - 修改 Java 后端代码 → 自动 RAMER 循环
> - 修改前端代码（`{{FRONTEND_DIR}}`）→ 自动 FE-Engineering RADIR 工作流
> - 详见 `docs/methodology/core/ramer-agent.md` 和 `docs/methodology/core/frontend-engineering.md`

---

## Frontend ({{PROJECT_NAME}})

{{FRAMEWORK}} 项目。修改前端代码时**自动触发 fe-engineering RADIR 工作流**（4铁律 + 组件分解 + VERIFY 门禁）。

**API calls must go through `{{API_PATH}}`** — never use low-level request utilities directly from views/components.

详见 `{{FRONTEND_DIR}}/AI.md` 和 `docs/methodology/core/frontend-engineering.md`。
