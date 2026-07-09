---
name: fe-engineering
description: 前端工程能力：RADIR 工作流（READ→ANALYZE→DECOMPOSE→IMPLEMENT→VERIFY），自动检测技术栈，强制4铁律+组件分解+质量门禁。使用 /fe <需求描述> 触发。
---

# 前端工程 Skill — RADIR 工作流

适用 **所有前端项目**（Vue/React/Angular/Svelte 等）。自动检测技术栈，按 4 铁律 + 组件分解模式执行。

## 触发方式

```
/fe <需求描述>         # 完整工作流：新模块/新功能/重构
/fe check              # 仅质量检查：对当前改动执行 VERIFY
/fe decompose <path>   # 仅组件分解分析：诊断大文件并建议拆分方案
```

---

## RADIR 工作流

```
[R] READ → [A] ANALYZE → [D] DECOMPOSE → [I] IMPLEMENT → [R] VERIFY
```

### R — READ（读取上下文）

1. 检测项目技术栈：

   ```
   package.json → 依赖分析
   ├── vue         → Vue 3 + (Naive UI / Element Plus / Ant Design Vue / ...)
   ├── react       → React + (Ant Design / MUI / Shadcn / ...)
   ├── angular     → Angular + ...
   └── svelte      → Svelte + ...
   ```

   同时检测：TypeScript、CSS 方案（Tailwind / UnoCSS / CSS Modules / Scoped CSS）、状态管理（Pinia / Zustand / Redux）、构建工具（Vite / Webpack）

2. 读取路径文档（若存在）：
   - 目标目录 `AI.md` / `ai.json` → 模块约束
   - 父目录逐级向上 → 项目级约束
   - `CLAUDE.md` → 全局规则

3. 读取相关代码：
   - 目标目录下所有 `.vue/.tsx/.jsx/.ts` 文件
   - 关联的 API 层（`service/api` / `api/` 等）
   - 关联的类型定义（`typings/` / `types/`）
   - 关联的路由配置和 i18n

### A — ANALYZE（分析需求 + 现有代码）

1. 理解需求范围：
   - 涉及哪些页面/组件？
   - 需要哪些 API 接口？
   - 需要新增/修改哪些类型定义？
   - 影响路由、i18n、权限吗？

2. 诊断现状（如为重构）：
   - 单文件是否 > 300 行？
   - 是否存在直接 `request`/`axios`/`fetch` 调用？
   - 是否存在 `any` 类型？
   - 弹窗/抽屉/表单/表格是否混在页面中？
   - 是否缺少 Loading/Empty/Error 状态？

3. 输出分析摘要（≤200字），等待用户确认。

### D — DECOMPOSE（组件分解设计）

**这是前端特有的关键阶段。** 在写代码前，先设计组件树。

#### 强制拆分规则

| 触发条件 | 拆分动作 |
|----------|----------|
| 页面中有 `v-if`/`visible` 控制的弹窗/抽屉 | 拆为独立 `modules/<name>-modal.vue` 或 `<name>-drawer.vue` |
| 表单字段 > 5 个 | 拆为独立 `modules/<name>-form.vue` |
| 表格列 > 6 列或有复杂列渲染 | 拆为独立 `modules/<name>-table.vue` |
| 一段逻辑被 2+ 个位置使用 | 提取到 `hooks/` 或 `components/` |
| 文件 > 300 行 | 必须分解 |

#### 组件通信契约

父组件 → 子组件：
```
父组件 index.vue（编排层，≤150 行）
  ├── props: 数据传给子组件
  ├── @event: 接收子组件事件
  └── provide/注入: 深层依赖（谨慎使用）
```

子组件 → 父组件：
```
子组件 modules/<name>-xxx.vue（实现层，≤300 行）
  ├── defineProps: 接收父组件数据
  ├── defineEmits: 向父组件报告事件
  └── 不直接修改 props，通过 emit 通知父组件修改
```

Modal/Drawer 调用模式：
```
父组件暴露 open/close 方法：
  const visible = ref(false)
  const editData = ref(null)
  const handleEdit = (row) => { editData.value = row; visible.value = true }
  const handleClose = () => { visible.value = false; editData.value = null }

子组件接收 visible + data：
  <operate-drawer :visible="visible" :data="editData" @close="handleClose" @submit="handleSubmit" />
```

#### 输出设计

设计完成后，以 ASCII 目录树呈现目标结构。例如：
```
driver/
├── index.vue                     # 编排层，~120 行
├── modules/
│   ├── driver-search.vue         # 搜索表单，~80 行
│   ├── driver-table.vue          # 数据表格，~180 行
│   ├── driver-operate-drawer.vue # 新增/编辑抽屉，~250 行
│   └── driver-detail-modal.vue   # 详情弹窗，~120 行
└── AI.md / ai.json
```

等待用户确认后进入实现。

### I — IMPLEMENT（实现）

#### 实现顺序（契约优先）

1. **类型定义**：`typings/api/` 或 `types/` — API 请求/返回类型
2. **API 层**：`service/api/` 或 `api/` — 接口方法封装
3. **子组件**（由简到繁，由内到外）：
   - 先实现纯展示组件（table、detail）
   - 再实现表单组件（form、search）
   - 最后实现交互组件（modal、drawer）
4. **父组件**（编排层）：组装子组件，协调通信
5. **路由**：注册路由、菜单
6. **i18n**：国际化文案

#### 4 铁律强制遵守

**铁律 1：分层不可逾越**
```
表现层 (views/components) → API 层 (service/api) → 请求层 (service/request)
       ↓                           ↓                        ↓
  只依赖 hooks/types         只依赖 request/types      只依赖 HTTP 库
  禁止直接调 request          禁止反向依赖页面         禁止混入业务语义
```

**铁律 2：类型即契约**
- 禁止 `any`（除非有明确理由 + `// eslint-disable-next-line` + 注释说明）
- API 类型必须与后端字段同步
- 枚举/常量从后端契约派生，不前端自造
- TypeScript strict mode 下的类型必须完整

**铁律 3：组件受控**
- 每个文件 ≤ 300 行
- 弹窗/抽屉/表单/表格必须独立组件
- 业务组件不过早全局化（先放 `modules/`，被 3+ 页面使用时再提升到 `components/`）
- 组合优于继承（用 slot/props/emit，不用 extends）

**铁律 4：三态覆盖**
- 每个数据获取场景必须处理：
  - **Loading**：骨架屏或加载指示器
  - **Empty**：空状态插画 + 引导文案
  - **Error**：错误提示 + 重试按钮
- 表单提交必须处理：提交中禁用、成功反馈、失败提示

### V — VERIFY（质量门禁）

按顺序执行检查，任一步失败即停止并修复：

#### 1. 类型检查
```bash
# 自动检测执行
pnpm typecheck || npm run typecheck || npx tsc --noEmit || vue-tsc --noEmit
```

#### 2. 构建验证
```bash
# 自动检测执行
pnpm build:dev || npm run build:dev || npm run build
```

#### 3. 路由同步（如有 gen-route 脚本）
```bash
pnpm gen-route   # SoybeanAdmin / 自定义路由生成
```

#### 4. Lint
```bash
pnpm lint   # 仅在最终收口时执行，注意改动范围
```

#### 5. 4 铁律自检清单

| 检查项 | 方法 |
|--------|------|
| 分层：views 中有无直接 `request`/`axios`/`fetch`？ | grep 搜索 |
| 类型：有无新增 `any`？ | grep 搜索改动文件中的 `: any` |
| 组件：有无文件 > 300 行？ | `wc -l` 检查 |
| 组件：弹窗/抽屉是否拆为独立组件？ | 检查 template 中 dialog/drawer 是否在独立文件 |
| 三态：数据获取处有无 loading/empty/error？ | 检查 API 调用处的模板 |
| 交付：路由/i18n/权限是否同步？ | 对比改动文件与路由/i18n 目录 |

#### 6. 路径文档同步

若新增复杂业务域目录，补充 `AI.md` / `ai.json`。

---

## 适用范围说明

本 Skill **技术栈无关**，适用于：
- Vue 3 (SFC + Composition API / Options API)
- React (JSX/TSX + Hooks)
- Angular (Component-based)
- Svelte
- 任何其他前端框架

核心原则（4 铁律、组件分解、契约优先）适用于所有前端工程。具体命令和路径根据项目 `package.json` 和目录结构自动调整。

---

## 交付标准

任务完成后输出：
1. 改动的文件列表（按层级）
2. 组件分解结果（原始结构 → 目标结构）
3. 质量检查结果（typecheck / build / route / i18n）
4. 需要人工确认的点（UI 交互、权限、后端字段对齐）
