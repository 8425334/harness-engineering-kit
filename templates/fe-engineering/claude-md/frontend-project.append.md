## 自动触发 FE-Engineering

修改任何前端代码时，**自动应用 fe-engineering RADIR 工作流**（无需手动 /fe）：
- **READ**: 读路径文档 (AI.md/ai.json) + 检测技术栈
- **ANALYZE**: 诊断现状（大文件/any/越层/缺三态）
- **DECOMPOSE**: 弹窗→modal, 表单→form, 表格→table, >300行→拆分
- **IMPLEMENT**: 4铁律强制（分层/类型/组件≤300行/三态覆盖）
- **VERIFY**: typecheck → build → gen-route → 4铁律自检
详见 `docs/methodology/core/frontend-engineering.md`
