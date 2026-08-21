# 前端工程能力模型

Frontend Engineering Capability Model

定义一套技术栈无关的前端工程能力标准。无论 Vue/React/Angular/Svelte，优秀的前端工程应具备以下能力。

> 配套全局 Skill：`/fe` 命令（`fe-engineering`），在任何前端项目中自动检测技术栈并执行 RADIR 工作流。

## 1. 四铁律

### 铁律 1：分层不可逾越

```
┌──────────────────────────────────────────────────────────────┐
│  表现层 (views / components / pages)                         │
│    ├── 职责：UI 渲染、交互编排、用户事件响应                  │
│    ├── 依赖：hooks、types、API 层                             │
│    └── 禁止：直接调用 axios/fetch/request                     │
├──────────────────────────────────────────────────────────────┤
│  API 层 (service/api / api)                                  │
│    ├── 职责：请求路径、参数、返回类型封装                     │
│    ├── 依赖：request 实例、类型定义                           │
│    └── 禁止：反向依赖表现层、混入 UI 状态                     │
├──────────────────────────────────────────────────────────────┤
│  请求层 (service/request / utils/http)                        │
│    ├── 职责：统一请求实例、鉴权、拦截器、错误处理              │
│    ├── 依赖：HTTP 库（axios/fetch）                           │
│    └── 禁止：混入业务语义                                     │
└──────────────────────────────────────────────────────────────┘
```

**检查方法**：grep 表现层目录，不应出现 `axios`/`fetch`/底层 `request` 的直接 import。

### 铁律 2：类型即契约

- **禁止 `any`**：除非有明确理由（第三方库缺陷、动态内容极难类型化）+ 注释说明
- **API 类型与后端同步**：接口字段变化时，类型、API 方法、消费页面在同一任务内更新
- **枚举从契约派生**：不前端自造枚举值，状态码/业务枚举以后端文档为准
- **TypeScript strict**：所有新项目应开启 strict mode

```
反模式：                             正确：
const data: any = await api()       const data: Api.Coil.DriverList = await api()
users.map((u: any) => u.name)       users.map((u: User) => u.name)
```

### 铁律 3：组件受控

**规模限制**：
- 单文件 ≤ 300 行（不含空行和纯注释行）
- 超过必须拆分

**模态/表单/表格必须独立组件**：

| 触发条件 | 拆分目标 |
|----------|----------|
| `v-if` 控制的弹窗/抽屉 | `modules/<name>-modal.vue` / `<name>-drawer.vue` |
| 表单字段 > 5 个 | `modules/<name>-form.vue` |
| 表格列 > 6 列或有复杂列渲染 | `modules/<name>-table.vue` |
| 逻辑被 2+ 处使用 | `hooks/` 或 `components/` |
| 文件 > 300 行 | 必须分解 |

**提升规则**：
- 业务组件先放页面 `modules/`
- 被 3+ 页面/模块使用时，提升到 `src/components/`
- 不做"提前抽象" — 过早全局化比局部重复更有害

**组合优于继承**：
- 用 `slot`/`props`/`emit` 做组合
- 不用 `extends` 做继承
- 不依赖 `$parent`/`$refs` 跨组件通信

### 铁律 4：三态覆盖

每个数据获取场景必须显式处理三种状态：

```
                    ┌──────────┐
                    │  触发请求  │
                    └─────┬────┘
                          │
                    ┌─────▼────┐
                    │ Loading  │──→ 骨架屏 / Spin / Skeleton
                    └─────┬────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
        ┌─────▼────┐ ┌───▼────┐ ┌───▼────┐
        │  Empty   │ │  Data  │ │ Error  │
        └──────────┘ └────────┘ └────────┘
             │                      │
       空状态插画              错误提示
        + 引导文案              + 重试按钮
```

表单提交也需三态：
- **提交中**：按钮 loading + 禁用
- **成功**：成功反馈 + 关闭弹窗/刷新列表
- **失败**：错误提示 + 恢复可编辑

---

## 2. 组件分解模式

### 父组件职责（编排层，≤150 行）

```
父组件 = 组装子组件 + 管理页面级状态 + 协调子组件通信
```

- 不写复杂模板（委托给子组件）
- 不写复杂逻辑（委托给 hooks）
- 只做：声明子组件需要的响应式数据、处理子组件 emit 的事件

### 子组件职责（实现层，≤300 行）

- 通过 `defineProps` 接收数据
- 通过 `defineEmits` 报告事件
- 不直接修改 props（单向数据流）

### Modal/Drawer 开闭模式

```
父组件:
  const visible = ref(false)
  const currentData = ref<Item | null>(null)

  const handleOpen = (row: Item) => {
    currentData.value = row
    visible.value = true
  }

  const handleClose = () => {
    visible.value = false
    currentData.value = null
  }

子组件:
  defineProps<{ visible: boolean; data: Item | null }>()
  defineEmits<{ close: []; submit: [] }>()
```

### 目录结构示例

```
user-management/
├── index.vue                    # 编排层，~120 行
├── modules/
│   ├── user-search.vue          # 搜索表单，~80 行
│   ├── user-table.vue           # 数据表格，~180 行
│   ├── user-form-drawer.vue     # 新增/编辑表单抽屉，~250 行
│   └── user-delete-dialog.vue   # 删除确认弹窗，~60 行
├── hooks/
│   └── useUserList.ts           # 列表数据获取 + 三态管理，~80 行
└── AI.md / ai.json              # 本模块约束文档
```

---

## 3. 质量门禁

### 自动化检查（CI / 本地提交前）

| 检查项 | 命令（自动检测） | 阻断级别 |
|--------|------------------|----------|
| 类型检查 | `tsc --noEmit` / `vue-tsc --noEmit` | FAIL |
| 构建验证 | `vite build` / `webpack --mode production` | FAIL |
| 路由同步 | `pnpm gen-route`（如适用） | FAIL |
| Lint | `eslint` / `oxlint` | WARN |

### 4 铁律自检

| 检查项 | 方法 | 阻断级别 |
|--------|------|----------|
| 分层违规 | grep views/components 中的 `axios`/`fetch`/底层 `request` | FAIL |
| any 类型 | grep `: any` 在改动文件中 | FAIL |
| 文件过大 | `wc -l` 检查改动文件 | REWORK (>300行) |
| 弹窗未拆分 | 检查 template 中 `dialog`/`drawer`/`modal` 是否在页面文件中 | REWORK |
| 缺三态 | 检查 API 调用处对应的 template 是否覆盖 loading/empty/error | REWORK |
| 路由不同步 | 新增页面是否注册路由 | FAIL |
| i18n 不同步 | 新增文案是否在 locales 中 | WARN |

### 交付前人工确认

- UI 交互行为（弹窗打开/关闭、表单提交/重置）
- 权限按钮展示与后端权限编码一致
- 后端字段对齐（接口新增/修改字段前端已同步）

---

## 4. 技术栈适配

本模型适用于任何前端框架。各框架的核心映射：

| 概念 | Vue 3 | React | Angular | Svelte |
|------|-------|-------|---------|--------|
| 表现层 | `.vue` SFC | `.tsx`/`.jsx` | `.component.ts` + `.html` | `.svelte` |
| 组件通信 | props + emit | props + callback | @Input + @Output | props + event |
| 全局状态 | Pinia | Zustand/Redux | NgRx/Signal | Svelte Store |
| 类型 | `vue-tsc` | `tsc` | `ngc` | `svelte-check` |
| 构建 | Vite | Vite/Webpack | Angular CLI | Vite |
| 样式 | Scoped CSS / UnoCSS | CSS Modules / Tailwind | Component Styles | Scoped CSS |

`/fe` skill 启动时自动检测 `package.json` 确定技术栈，适配对应命令和路径约定。

---

## 5. 与后端方法论的对应关系

| 后端 | 前端 |
|------|------|
| RAMER 循环 | RADIR 工作流 |
| /ramer skill | /fe skill（fe-engineering） |
| 抽象优先 (ACL → DTO/BO/VO) | 组件分解 (需求 → 组件树 → 实现) |
| 组合优于继承 | slot/props/emit 组合 |
| 契约优先 (Interface → Impl) | 类型优先 (Type → API → Component) |
| Fitness 质量门禁 | VERIFY 质量门禁 |
| DDD 领域建模 | DDD 前端分层 (表现/应用/领域/基础设施) |

---

## 6. 移植指南

### 在新项目中启用

**Tier 1（即刻，5 分钟）**：
1. 在项目根目录 `CLAUDE.md` 中加入：
   ```markdown
   ## Frontend
   使用 /fe 命令进行前端开发，遵循 4 铁律 + 组件分解模式。
   详见 `docs/methodology/core/frontend-engineering.md`。
   ```

**Tier 2（1 小时）**：
1. 为核心业务目录创建 `AI.md` / `ai.json` 路径文档
2. 配置 ESLint 分层检查规则（禁止 views 直接 import axios）
3. 在 CI 中加入 typecheck + build 阻断

**Tier 3（持续）**：
1. 配置 Fitness 前端检查脚本（文件规模、any 类型、三态覆盖）
2. 引入 E2E 测试（Playwright / Cypress）
3. 建立前端组件库与设计系统

---

## 7. 多 Agent 并行模式

> 多 Agent 协调是跨切面编排模式，并非前端专属。完整说明（契约模板、启动规则、合并验证、降级策略）：**`core/multi-agent.md`** + Skill `/multi-agent`（`templates/multi-agent/SKILL.md.template`）。

当任务**同时涉及前端和后端**代码变更时，自动启用双 Agent 并行执行，而非序列执行。

### 7.1 执行架构

```
用户需求（前后端联动）
       │
       ▼
┌─ 阶段 0: 契约定义（主 Agent）─────────────────────────────┐
│                                                           │
│  1. 识别前后端边界                                         │
│  2. 提取共享数据契约：                                     │
│     API 端点 + HTTP 方法                                   │
│     请求参数字段 + 类型                                    │
│     返文字段 + 类型                                        │
│     枚举/状态码                                            │
│  3. 输出契约摘要，向用户确认后进入并行阶段                  │
│                                                           │
└───────────────────────────────────────────────────────────┘
       │
       ├──────────────────────┐
       ▼                      ▼
┌─ Agent-BE ──────────┐  ┌─ Agent-FE ─────────────────┐
│ background          │  │ background                 │
│                     │  │                            │
│ RAMER: R→A→M→E→R   │  │ RADIR: R→A→D→I→V          │
│                     │  │                            │
│ 基于契约实现:       │  │ 基于契约实现:              │
│ DTO/BO/VO          │  │ types/API 封装             │
│ Controller/Service │  │ views/components           │
│ Mapper/XML         │  │ 路由/i18n                  │
│ fitness.py 门禁    │  │ typecheck + build 门禁     │
└────────────────────┘  └────────────────────────────┘
       │                      │
       └──────────┬───────────┘
                  ▼
┌─ 阶段 2: 合并验证（主 Agent）─────────────────────────────┐
│                                                           │
│  1. 字段对齐：后端返文 vs 前端类型                         │
│  2. 枚举一致：后端枚举值 vs 前端常量                       │
│  3. 路由同步：新增页面是否注册路由                         │
│  4. 权限同步：按钮编码与后端权限一致                       │
│  5. 不一致 → 修复 → 重新验证                               │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### 7.2 契约定义模板

主 Agent 在契约定义阶段输出的格式：

```markdown
## 共享契约

### 接口：POST /api/v1/users/assign-role
| 方向 | 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| 请求 | userId | Long | 是 | 用户ID |
| 请求 | roleId | Long | 是 | 角色ID |
| 返文 | success | Boolean | 是 | 操作结果 |
| 返文 | message | String | 否 | 错误信息 |

### 枚举：UserStatus
| 值 | 含义 |
|----|------|
| ACTIVE | 在职 |
| INACTIVE | 离职 |
| SUSPENDED | 停用 |
```

### 7.3 并行启动

两个 Agent 通过 `run_in_background: true` 同时启动，各自独立执行。

- **Agent-BE** (`general-purpose`): 提示词包含 RAMER 循环 + 项目架构 + 契约字段
- **Agent-FE** (`general-purpose`): 提示词包含 RADIR 工作流 + 4铁律 + 契约字段

主 Agent 不轮询等待，双方完成后自动通知进行合并验证。

### 7.4 降级策略

| 场景 | 策略 |
|------|------|
| 子 Agent 不可用（超限/不可达） | 序列执行：先实现后端契约层，再实现前端表现层 |
| 单侧任务（仅前端或仅后端） | 不启用并行，直接用对应工作流 |
| 契约变更（实现中发现字段需调整） | 子 Agent 通过主 Agent 协调变更，双方同步更新 |
