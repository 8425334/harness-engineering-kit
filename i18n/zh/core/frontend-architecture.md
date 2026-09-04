# AI 原生前端架构与方法论

AI-Driven Modern Frontend Architecture & Methodology

将前端开发重新定义为三层协作模式，让 AI 在边界内完成逻辑实现，由人类定义"什么是好代码"，由自动化系统验证质量。

> 本文件聚焦**前端**的 AI 协作模式与架构边界。后端契约优先、组合/多态等通用原则详见 `abstraction-first.md`；质量门禁体系详见 `fitness-framework.md`。

## 1. 核心理念

我们将前端开发重新定义为三个层级的协作模式：

- **The Architect（人类）**：定义边界、规则、约束，以及"什么是好代码"。
- **The Enforcer（自动化系统）**：基于 Fitness Functions（适配度函数）和 Harness（测试框架），自动验证代码质量。
- **The Builder（AI）**：在边界内工作，完成逻辑实现。

**公式：**

```
System = (Prompt + Context) + (AI Inference) + (Fitness Validation)
```

## 2. AI 开发方法论（AIDM）

### 2.1 抽象优先协议

在让 AI 写代码前，必须先由 AI 生成抽象模型。

流程：

1. User："用户需要一个订单管理页面。"
2. AI Agent 1（Domain Modeler）：生成 TypeScript Interfaces、DTOs、Enums、State Schema。
3. AI Agent 2（Contract Validator）：根据 API 文档校验类型一致性。
4. AI Agent 3（Builder）：基于上述模型生成 UI 组件。

**规范：禁止直接让 AI 生成 jsx/tsx 文件，必须先生成 `types.ts` 和 `models.ts`。**

### 2.2 架构边界契约

利用 AI 理解自然语言的特性，强制其遵守"层级不可逾越"的规则。

Prompt 模板：

```text
你是一个 DDD 前端专家。
Context：你处于 presentation/components 层。
Strict Rules：
  - 绝对禁止直接调用 axios 或 fetch。
  - 绝对禁止直接访问 LocalStorage。
  - 所有数据必须通过 props 传入。
  - 所有事件必须通过 props 回调发出。
Task: 实现 <UserList /> 组件。
```

### 2.3 Fitness-Driven Development（FDD）

将 Fitness Framework 的思想融入 AI 交互。AI 交付的代码必须通过"适应度测试"才能合并。

检查点：

- **Security Baseline**：AI 生成的代码不能包含 `eval()` 或 `innerHTML`。
- **Arch Boundary Check**：静态分析（如 ESLint 插件）检查 Import 路径，确保 ui 层未导入 infrastructure 层。
- **Log Cleanup**：自动检测 AI 是否残留了 `console.log`。

## 3. 现代化前端架构设计

为了最大化 AI 效能并保持代码整洁，采用基于特性的分支结构与 React Server Components（RSC）结合的架构。

### 3.1 物理结构

```
src/
├── kernel/                   # AI 静态态分析配置与规则
│   ├── fitness/              # 自动化测试脚本
│   │   ├── check_safety.py   # 安全基线检查
│   │   └── check_boundary.py # 架构边界检查
│   └── prompts/              # 预设的高质量 System Prompts
├── domain/                   # 领域层 (High Precision)
│   ├── aggregates/           # 实体聚合根
│   ├── services/             # 领域服务 (纯函数，AI 极易生成)
│   └── types/                # 全局类型定义
├── application/              # 应用编排层
│   ├── hooks/                # React Hooks (AI 主要工作区)
│   └── controllers/          # 数据获取与分发逻辑
├── infrastructure/           # 基础设施层 (Low Mutation)
│   └── api/                  # API 客户端
└── presentation/             # 表现层
    ├── pages/                # 页面入口
    ├── components/           # 展示组件 (UI)
    └── templates/            # 布局模板
```

### 3.2 React Server Components（RSC）策略

AI 在生成 RSC 时效果最佳，因为它天然允许"混入服务端逻辑"，减少了客户端状态管理的复杂度。

AI 生成模式：

- **Server Component**：处理数据获取、权限校验（AI 负责写 SQL/Logic）。
- **Client Component**：处理复杂交互、Modal、动画（AI 负责写 React Hooks）。

## 4. 实施：AI 编码工作流

### 步骤 1：生成契约

- **输入**：需求文档。
- **AI 动作**：生成 OpenAPI Spec / JSON Schema。
- **产出**：`domain/types/user.type.ts`。

### 步骤 2：生成基础设施

- **输入**：OpenAPI Spec。
- **AI 动作**：生成 API Client 函数、Repository 接口。
- **产出**：`infrastructure/api/user.ts`。

### 步骤 3：编排逻辑

- **输入**：Domain Types + Repository Interface。
- **AI 动作**：编写 `useFetchUsers` Hook，处理 Loading/Error 状态。
- **产出**：`application/hooks/useFetchUsers.ts`。
- **Fitness Check**：确保 Hook 内部没有 `console.log`，错误处理覆盖了所有异常分支。

### 步骤 4：生成 UI

- **输入**：`useFetchUsers` Hook 的类型定义 + 设计稿描述。
- **AI 动作**：生成 TailwindCSS 或 CSS Modules 样式的组件。
- **产出**：`presentation/components/UserTable.tsx`。
- **Fitness Check**：Accessibility 检查（确保有 `aria-label`），组件 Props 完整性检查。

## 5. AI 规范与约束

为了避免 AI 产生"幻觉代码"，必须将其锁定在规范中。

### 5.1 Prompt 指令库

在项目中维护 `.ai/prompts/` 目录：

- `system.component.md`：定义组件编写标准。
- `system.hooks.md`：定义 Hooks 编写标准。
- `system.refactor.md`：定义重构标准。

### 5.2 拒绝模式

禁止 AI 在提示词中引入以下模式，除非明确授权：

- `any` 类型。
- `eval()` 或 `new Function()`。
- 硬编码的外部 API Key。
- 过度复杂的嵌套三元运算符。

### 5.3 自我修正循环

在受支持的 IDE 或编码 Harness 中配置 Agent 模式：

1. **编写代码**：AI 生成代码。
2. **触发 Linter**：IDE 自动运行 ESLint。
3. **AI 阅读报错**：Agent 接收错误信息。
4. **自我修复**：Agent 自动修复错误，直到 Linter 通过。
5. **运行测试**：触发 vitest。
6. **最终提交**：所有绿灯通过。

## 6. 总结

这套方法将 `methodology.zip` 中的严谨工程思想与 AI 的生成能力结合：

- **抽象优先**确保 AI 理解业务模型而非只关注语法。
- **架构边界**限制了 AI 的"创意"范围，防止它写上帝组件。
- **适配度函数**建立了 AI 的"道德标准"，强制其产出高质量代码。

**目标**：让前端团队从"编写者"进化为"审查者"和"架构师"，让 AI 成为那个不知疲倦的、严格遵守规范的"初级工程师"。
