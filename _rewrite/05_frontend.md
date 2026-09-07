## 五、前端工程化：RAD + 层不跨越

后端有 RAM，前端有 RAD——两者共享相同的工程哲学：**先读上下文、先分解、再实现，最后用门禁验证**。前端的核心挑战是**视图、状态、数据流三层容易混在一起**。

### 5.1 前端 RAD：分解必须在实现前

| 阶段 | 发生在 | 产出什么 | 回答 |
|-|-|-|-|
| **Read** | Explore | 产品行为、设计系统、路由、组件、API 类型、状态所有权、无障碍 | 前端该遵守哪些约定？ |
| **Analyze** | Explore/Spec | 用户状态、权限边界、响应式、兼容性、加载/空/错误、契约风险 | 交互与数据流是什么？ |
| **Decompose** | Design | 组件职责、数据/状态流、类型化 API 边界、校验、交互状态、实现顺序 | 谁负责什么、谁来取数？ |

Apply 只消费已审批的分解。验证命令同样来自 `agent-policy.yaml`：类型检查、聚焦行为测试、构建、无障碍与 API 对齐。

### 5.2 前端铁律：层不可跨越、类型即契约、组件受控、三态覆盖

前端规范对框架无关，落到任何框架都成立。第一铁律是**层不可跨越**：视图层不能直接碰底层请求。

```text
视图层（页面 / 组件）          —— 只消费 API 层导出的函数与类型
   │  数据必须逐层经 API 传递
API 层（services / api）      —— 每个接口一个模块，同时导出类型
   │
请求层（request 实例 / 拦截器） —— axios / fetch 只允许出现在这一层
```

| 铁律 | 内容 | 检查 |
|-|-|-|
| 层不可跨越 | 视图层禁止直接 `axios` / `fetch` / 底层 `request`，数据必须经 API 层 | grep 视图目录无底层请求（architecture-boundary） |
| 类型即契约 | 禁 `any`；API 字段 / 枚举变更时 types / API / 页面同一次改完并与后端对齐（rule：typed-contract / api-contract） | `tsc --noEmit` / `vue-tsc --noEmit` |
| 组件受控 | 组件有明确职责与受控边界（rule：component-size / controlled-components），行数上限由项目在治理配置中自定；modal / 表单 / 表格独立成组件 | 审查 + 目录结构检查 |
| 三态覆盖 | 每个取数场景显式处理 loading / empty / error（rule：loading-empty-error） | 审查 + 模板检查 |

**组件分解原则**：父组件只做编排，子组件负责实现，行数上限以项目约定为准；业务组件先在局部收敛，被多处复用时才提升到更全局的位置——**不过早抽象**。

**三态覆盖是 AI 最容易漏的**：取数要有 loading（骨架 / Spin）、空态（插画 + 引导）、错误态（提示 + 重试）；表单提交也要有提交中 / 成功 / 失败三态。前端验证里 typecheck / build 已进 Fitness 门禁，lint 暂不设为 Hard Gate、accessibility 与三态作为 Review 验证项——和后端一样，这些是**完成条件，不是可选步骤**。

### 5.3 前后端 Profile 对照

| 后端 RAM | 前端 RAD |
|-|-|
| 抽象优先（契约 → DTO / BO / VO） | 类型优先（types → API → 组件） |
| Model：领域边界 / 聚合 / 仓储 | Decompose：组件职责 / 数据流 / API 边界 |
| 组合优于继承 | slot / props / emit 组合 |
| 后端门禁：compile / test / fitness | 前端验证：typecheck / build（Fitness）+ lint / accessibility（Review） |

前后端同时改动时，不要各自跑一套流程——见 §八《进阶：多 Agent 并行（fullstack）》，全栈只用一个契约、一次审批。
