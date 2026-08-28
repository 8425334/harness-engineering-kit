# AI 辅助开发方法论

将 AI Coding Agent 引入软件开发流程的完整工程方法论。适用于任何技术栈、任何项目规模。

> **语言**: 中文 | [English](README.md)

---

## 快速部署

在新项目中部署本方法论，只需两步：

### 步骤 1：运行初始化脚本

在项目目录下，打开 **Claude Code** / **Codex** / **Cursor** 的命令行，执行：

```bash
bash docs/methodology/scripts/init.sh --tier 1
```

脚本会完成文件复制和目录创建（幂等，可重复运行）。

### 步骤 2：让 Agent 完成配置

在同一个会话中，告诉 Agent：

```
根据项目实际情况，填充 CLAUDE.md 和 openspec/config.yaml 中的 {{占位符}}，
画出模块依赖图，补充构建命令和约定。
```

Agent 会：
1. 读取项目结构（`package.json`、`pom.xml`、目录树等）自动推断技术栈和构建命令
2. 替换 `CLAUDE.md` 和 `openspec/config.yaml` 中所有 `{{PLACEHOLDER}}`
3. 绘制模块依赖图（ASCII art）
4. 验证强制性 Skill 可用性
5. 运行 `--check` 确认配置完整

### 常用命令

```bash
bash docs/methodology/scripts/init.sh --tier 1     # 最小可用（推荐起点）
bash docs/methodology/scripts/init.sh --tier 2     # 追加 Fitness 质量门禁
bash docs/methodology/scripts/init.sh --tier 3     # 追加 RAMER Agent + CI 集成
bash docs/methodology/scripts/init.sh --check      # 仅检查当前配置状态
bash docs/methodology/scripts/init.sh --dry-run    # 预览操作，不实际修改
```

| Tier | 时间 | 脚本创建 | Agent 补全 |
|------|------|----------|------------|
| 1 | 5 分钟 | CLAUDE.md + OpenSpec + Superpowers + mandatory-skills + fe-engineering | 填充占位符、模块图、构建命令、技术栈 |
| 2 | +10 分钟 | Fitness scripts + rules + SDD docs + 根路径文档 | 替换 fitness 参数、补充约定 |
| 3 | +15 分钟 | RAMER Agent + CI 提示 | 配置 CI 流水线、E2E 测试 |

> 脚本是**幂等**的 — 重复运行不会覆盖已有文件。详细手动步骤见 [TRANSPLANT.md](TRANSPLANT.md)。

---

## 一篇讲清：工程化交付

整套方法论归结为一句话：**工程化的本质是把"人脑里的规则"变成"仓库里的规则"**。四个概念按层次配合：

| 层次 | 概念 | 作用 |
|------|------|------|
| 基础设施 | **Harness Engineering** | 把上下文、工具、规则、门禁组合成 Agent 可运行的工程环境 |
| 决策层 | **OpenSpec** | 记录高成本决策：改什么、为什么、边界和取舍 |
| 执行层 | **RAMER**（后端）/ **RADIR**（前端） | 从需求到代码的可靠执行循环，由门禁验证 |

**工程化 vs 直接生成：**

| 维度 | 直接生成 | 工程化交付 |
|------|----------|------------|
| 任务起点 | 一句自然语言需求 | 目标、范围、约束、验收、非目标 |
| 上下文 | Agent 临时搜索 | 路径文档、真实代码、调用链 |
| 设计方式 | 边写边调整 | 先确认契约、职责和依赖方向 |
| 完成定义 | 代码生成或编译通过 | 测试、构建、门禁有执行证据 |
| 更适合 | 低风险局部改动 | 新能力、跨模块、接口和架构变化 |

**三条核心论点：**

1. **复杂需求先建模再编码** —— 别让 AI 边写边想，先把契约、对象和职责搞清楚
2. **代码生成不等于完成** —— 测试、构建、门禁都有证据，才算做完
3. **把教训沉淀进仓库** —— 每次犯错都是优化工程环境的机会，而不是下次重蹈覆辙的理由

---

## 核心概念

工程化交付依赖互相配合的四个概念：

| 概念 | 解决什么 |
|------|----------|
| Harness Engineering | Agent 的工程环境：上下文、规则、工具、门禁如何组合 |
| OpenSpec | 高成本决策的记录：改什么、为什么、边界和取舍 |
| RAMER | 后端执行循环：`READ → ANALYZE → MODEL → EXECUTE → REVIEW` |
| RADIR | 前端执行循环：`READ → ANALYZE → DECOMPOSE → IMPLEMENT → VERIFY` |

![核心概念流程](./assets/ai-coding-engineering-tutorial/01-core-concepts.png)

它们的关系是：**Harness 是基础设施，OpenSpec 是决策层，RAMER/RADIR 是执行层**。

---

## 后端工程化：RAMER 与后端铁律

后端工程化的核心挑战是**业务逻辑容易散落在 Service、模块边界和依赖方向容易失控**。RAMER 循环 + 几条铁律把"什么算合格的后端代码"变成可检查的规则。

![后端分层与依赖方向](./assets/ai-coding-engineering-tutorial/12-backend-layers.png)

| 铁律 | 内容 | 检查方式 |
|------|------|----------|
| 契约先行 | Controller / Remote 出入参必须 DTO / BO / VO，严禁 Entity；转换只在 Controller 层用 MapStruct | `grep` Controller 无 Entity 入参 |
| 依赖方向不失控 | `adapter → application → domain ← infrastructure`；domain 纯 Java、零框架 import | `grep` domain 无框架注解 |
| 多态优于分支 | 嵌套 if/else ≥2 或 switch ≥3 → Strategy / Factory / Handler；继承深度 ≤1 | 代码审查 |
| 门禁证据 | 测试、构建、Fitness 有执行证据才叫完成；调试日志三阶段自检 | fitness 门禁 |

**分层职责**：

| 层 | 职责 | 禁 |
|------|------|------|
| `domain` | 纯 Java 聚合 / 值对象 / 领域服务 / 仓储接口 | 依赖 Spring / Redis / MyBatis / 框架 |
| `application` | 用例编排、事务边界、安全 | 包含业务规则 |
| `infrastructure` | 仓储实现、PO、外部集成（实现 domain 的端口） | 反向依赖上层实现细节 |
| `adapter` | REST / RPC / 事件 / 定时适配（只消费 application 契约） | 包含业务逻辑 |

**契约先行是 AI 最容易破的**：直接拿 Entity 当接口出入参、到处手写 `BeanUtils.copyProperties`、把转换逻辑塞进 Service——这三条会让边界立刻模糊。正确姿势：Controller 用 DTO/BO/VO，Service 返回领域对象，转换只在 Controller 层。

---

## 前端工程化：RADIR 与四铁律

前端的核心挑战是**视图、状态、数据流三层容易混在一起**。四铁律把"什么算合格的前端代码"变成可检查的规则，任何框架通用。

![前端三层架构](./assets/ai-coding-engineering-tutorial/11-frontend-layers.png)

| 铁律 | 内容 | 检查方式 |
|------|------|----------|
| 层不可跨越 | 视图层禁止直接 `axios` / `fetch` / 底层 `request`，数据必须经 API 层 | `grep` 视图目录无底层请求 |
| 类型即契约 | 禁 `any`；API 字段变更时 types、API、页面同一次改完；枚举跟后端 | `tsc --noEmit` / `vue-tsc --noEmit` |
| 组件受控 | 单文件 ≤300 行；modal / 表单 / 表格独立成组件 | `wc -l` + 目录结构检查 |
| 三态覆盖 | 每个取数场景显式处理 loading / empty / error | 代码审查 + 模板检查 |

**组件分解**：父组件只做编排（≤150 行），子组件负责实现（≤300 行）。业务组件从页面 `modules/` 起步，被 3+ 处复用时才提升到全局组件——**不过早抽象**，提前全局化比局部重复更有害。

**三态覆盖是 AI 最容易漏的**：取数要有 loading（骨架 / Spin）、空态（插画 + 引导）、错误态（提示 + 重试）；表单提交也要有提交中 / 成功 / 失败三态。

前端质量门禁：`typecheck → build → gen-route → lint`。

---

## 反馈闭环：让项目越用越好

工程化不是一次性设置，而是**从错误中学习并固化**的持续过程。每次 Agent 犯错，都是改进工程环境的机会。

![AI 自我优化反馈闭环](./assets/ai-coding-engineering-tutorial/04-feedback-loop.png)

| 重复问题 | 沉淀位置 | 效果 |
|----------|----------|------|
| Agent 不知道模块职责 | 路径 `AI.md` / `ai.json` | 下次会话自动获得上下文 |
| 复杂需求直接进入实现 | OpenSpec 与 MODEL 确认点 | 强制先设计再写码 |
| 规则总是塞进 `ServiceImpl` | RAMER Skill、架构示例、规模门禁 | 引导向模型驱动 |
| DTO、权限或依赖方向反复出错 | Fitness Hard Gate | 自动拦截常见错误 |
| 边界场景经常遗漏 | 自动化测试 | 测试即规格，防止回归 |

**五个核心判断**：

| 判断 | 落地方式 |
|------|----------|
| 复杂度上升后，Prompt 不够用 | 把稳定规则放进仓库 |
| 需求越复杂，越要先建模 | 先契约、对象、职责和变化轴 |
| 文件拆分不是架构 | 先确认模型，再让边界自然落成文件 |
| 代码生成不等于完成 | 测试、构建、Fitness 和 Review 都要有证据 |
| AI 的长期收益来自反馈 | 把重复问题沉淀成文档、Skill、测试和门禁 |

---

## 多 Agent 并行：前后端联动

需求同时改前后端时，按 API 契约切分，双 Agent 后台并行，能省掉一半以上的等待。

![多 Agent 并行](./assets/ai-coding-engineering-tutorial/09-multi-agent-parallel.png)

| 阶段 | 动作 | 产出 |
|------|------|------|
| 阶段0 契约定义 | 主 Agent 提取共享契约：API 端点/方法、请求字段+类型、返回字段+类型、枚举/状态码；**先和用户确认** | 契约摘要 |
| 阶段1 并行实现 | Agent-BE 走 RAMER、Agent-FE 走 RADIR，后台同时启动，互不等待 | 后端 + 前端代码 |
| 阶段2 合并验证 | 主 Agent 对齐字段 / 枚举 / 路由 / 权限；不一致 → 修复 → 再验 | 通过的门禁 |

**契约是并行的地基**：必须在启动两个 Agent 前和用户确认清楚，否则中途改契约要两边同步，反而更慢。**单侧任务**直接用对应工作流；子 Agent 不可用时退化为串行。

---

## 上下文能力与提示词缓存

工程化不只提升质量，还直接降低成本。LLM 服务端缓存是**字节精确的前缀匹配**：只要请求前缀没变，命中缓存的部分按约 0.1× 计费。在 Agent 编码循环里，每次请求 ≈ 上一次会话 + 一小段新内容（Δ），命中率 ≈ `(total − Δ) / total`——前缀越稳、Δ 越小，成本越低。

![提示词缓存前缀](./assets/ai-coding-engineering-tutorial/10-context-cache-prefix.png)

**三种做法让前缀稳定、Δ 最小**：

| 做法 | 作用 |
|------|------|
| 冻结 system prompt（CLAUDE.md 确定性加载、版本化） | 每次请求前缀逐字节一致，第一次就命中 |
| 把 docs 当地图用、定向读取，让压缩极少触发 | 历史不被重写，Δ 保持小 |
| 工作流顺序确定、工具调用合并 | 单轮工具调用 block ≤ 15，落在缓存断点可回看窗口内 |

**五维上下文能力**：

| 维度 | 口诀 | 解决 |
|------|------|------|
| 窗口与压缩 | 装得下 | 上下文装不下的问题 |
| 跨会话记忆 | 记得住 | 会话间丢失的问题 |
| 注入精度 | 装得准 | 太宽泛没用的问题 |
| 缓存效率 | 用得省 | 反复全价重算的问题 |
| 每 token 推理深度 | 想得深 | 每个 token 换多少质量 |

**操作纪律**：会话中**绝不重写顶层 system prompt**——需要更新约定时，用追加的 `{"role":"system"}` 消息代替。

---

## 接入教程：用 Demo 跑通完整链路

下面的教程展示**工程化方法论如何改变实现路径和最终结果**。用一个真实案例（**企业级多业态订单优惠分摊引擎**）跑通完整链路。

### 第 1 步：把方法论放进项目

```bash
bash docs/methodology/scripts/init.sh --tier 2
```

或用 Claude Code 一步初始化：`/init init from /docs/harness-engineering-kit`

确认四个入口存在：

| 入口 | 作用 |
|------|------|
| `CLAUDE.md` / `AGENTS.md` | Agent 的全局工作约定、模块图和命令 |
| `AI.md` + `ai.json` | 路径级职责、允许依赖和局部事实 |
| `openspec/config.yaml` | SDD（规格驱动开发）变更的目录和规则 |
| `docs/fitness/` | Fitness（质量健康度检查）的维度、执行器和验证账本 |

### 第 2 步：用复杂需求检验

Demo 选择**企业级多业态订单优惠分摊引擎**，因为它具备真实工程的典型挑战：规则持续增加、规则可组合、金额需精度一致。

| 业态 | 规则重点 |
|------|----------|
| 普通零售 | 按不含税金额比例分摊，单商品不超过自身可优惠金额 |
| 跨境 | 先扣关税和运费，再按比例分摊，单商品上限为金额的 30% |
| 秒杀 | 按数量分摊，零头归订单最后一笔商品 |
| 团购 | 未成团报错，低价商品优先，剩余部分按金额比例分摊 |
| 会员专享 | 先用积分抵扣，最多抵扣总优惠的 50%，剩余部分复用零售规则 |

### 第 3 步：用 OpenSpec 固化决策

```text
/opsx:propose <需求内容>
```

建议用 Plan mode，让 Agent 在实现前把边界问题问出来。生成四类工件：

```text
openspec/changes/order-discount-allocation/
├── proposal.md                         # 为什么做、影响哪里、非目标
├── design.md                           # 架构选择、规则表、包结构、风险
├── tasks.md                            # 按依赖顺序拆解的实现任务
└── specs/discount-allocation/spec.md   # 需求、约束和 WHEN/THEN 场景
```

### 第 4 步：从 Spec 读出模型

这是 RAMER 的 MODEL 阶段——从规格中提取领域模型和规则模型：

![优惠分摊引擎流程](./assets/ai-coding-engineering-tutorial/05-discount-flow.png)

**关键决策**：
- `switch` ≥3 用 Strategy/Registry（多态优于分支）
- 金额内部整数分，输出两位小数（精度一致性）
- 业务错误通过 `AllocationResult` 返回，不用异常（错误即值）
- 新业态 = 新增枚举 + 注册规则 spec，不改核心（开闭原则）

### 第 5 步：按 Tasks 实现并验证

```text
/opsx:apply order-discount-allocation
```

```bash
python3 docs/fitness/scripts/fitness.py --tier fast
mvn -q compile
mvn test
```

**调试日志三阶段**：编码时在分支入口 / 状态流转 / 外部调用处加临时调试日志 → 跑测试时**逐条自检验证数据流**（分支是否走对、状态是否 A→B、调用参数是否匹配契约）→ 通过后清理临时输出、保留框架业务日志。

> 单测绿 ≠ 行为正确：测试只证明没崩，日志自检证明行为对。

**边界意识**：Spec 明确不做 REST、数据库迁移和真实税率推算。Agent 主动新增 Controller 或 Mapper 是越过非目标——这验证了 OpenSpec 中"非目标"的价值。

### 第 6 步：接入完成的判断

工程化交付的"完成"不是代码生成，而是**整个系统能持续工作**：

- Agent 能说清模块结构、依赖方向和构建命令
- 非平凡需求会先生成 Proposal、Design、Specs 和 Tasks
- 修改代码前读取最近路径的 `AI.md` 和 `ai.json`
- Fitness 失败时指出文件、规则、原因和修复入口
- 失败反馈回写到文档、Skill、测试或门禁，下次复用

完整链路：`Propose → Apply → Verify → Sync → Archive`

---

## 谁需要用

- **技术负责人** — 将 AI Coding 从"个人技巧"提升为"团队工程能力"
- **开发者** — 在新项目中快速建立 AI 辅助开发的工作流
- **团队** — 需要可复制、可验证、可在多项目间移植的方法论

## 核心原则

1. **文档先行，设计后行，实现最后** — 不读路径文档不动代码
2. **契约优先** — 先定义接口/DTO，确认设计，再写实现
3. **领域建模以 DDD 为骨架** — 战略（限界上下文）定边界，战术（聚合/实体/事件）定结构
4. **组合优于继承** — 继承深度 ≤ 1，优先 DI + 组合
5. **多态优于分支** — 嵌套 if/else ≥ 2 或 switch ≥ 3 → Strategy/Factory/Handler
6. **调试日志三阶段** — 编码后打日志、跑测试自检预期、通过后清理临时日志
7. **完成条件必须可执行** — 规则在仓库中，可被人阅读，也可被脚本执行
8. **前后端联动并行执行** (`core/multi-agent.md`) — 契约定义后，前后端双 Agent 并行开发，合并验证
9. **完备的 Agent Skill 配置** — Agent 必须具备 OpenSpec、Superpowers、Codegraph 三项基础能力，缺失即降级
10. **上下文能力与提示词缓存** (`core/context-capability.md`) — 保持提示词前缀字节稳定、单轮增量最小；五维上下文能力模型（窗口、记忆、注入、缓存、推理深度）

## 目录结构

```
docs/methodology/
├── README.md                           # 本文件（含一键迁移指南）
├── TRANSPLANT.md                       # 详细移植指南（Tier 1/2/3 手动步骤）
├── assets/                             # 配图（本 README 引用的图解）
│   └── ai-coding-engineering-tutorial/
├── scripts/
│   └── init.sh                         # 一键迁移脚本
├── core/                               # 通用原则（技术栈无关）
│   ├── ramer-cycle.md                  # RAMER 循环
│   ├── ramer-agent.md                  # RAMER Agent 自动化
│   ├── abstraction-first.md            # 抽象优先建模
│   ├── ddd-modeling.md                 # 领域驱动设计建模
│   ├── debug-log-discipline.md         # 调试日志纪律
│   ├── frontend-architecture.md        # AI 原生前端架构（AIDM + FDD + RSC）
│   ├── frontend-engineering.md         # 前端工程能力模型（4铁律 + 组件分解）
│   ├── multi-agent.md                  # 多 Agent 并行模式（前后端联动）
│   ├── mandatory-skills.md             # 强制性 Skill 配置
│   ├── sdd-workflow.md                 # SDD 流程
│   ├── fitness-framework.md            # Fitness 质量门禁
│   ├── context-capability.md           # 上下文能力与提示词缓存
│   └── harness-engineering.md          # Harness 工程化
└── templates/                          # 复制即用的模板
    ├── CLAUDE.md.template              # AI 入口配置
    ├── openspec-config.yaml.template   # SDD 配置
    ├── sdd-readme.md.template          # SDD 流程文档
    ├── path-document.md.template       # 路径文档 (AI.md + ai.json)
    ├── fitness/                        # Fitness 框架模板
    │   ├── README.md                   # 占位符参考 + 迁移步骤
    │   ├── fitness.py.template         # Fitness runner
    │   ├── check_*.py.template         # 18 个可移植检查脚本
    │   ├── test_*.py.template          # 6 个通用复杂门禁可执行自测
    │   ├── JavaParameterScanner.java.template # Java 21 AST 参数扫描器
    │   └── rules/*.md.template         # 14 个维度规则模板
    ├── ramer/                          # RAMER Agent 模板
    │   ├── README.md                   # 迁移步骤
    │   ├── SKILL.md.template           # /ramer skill 定义（自包含）
    │   ├── ramer-design.js.template    # 可选：设计工作流
    │   └── ramer-implement.js.template # 可选：实现工作流
    ├── multi-agent/                    # Claude/Codex 多 Agent 并行模板
    │   ├── README.md                   # 迁移步骤
    │   └── SKILL.md.template           # /multi-agent skill 定义（自包含）
    ├── compaction/                     # Token 压缩保持模板
    │   ├── README.md                   # 迁移步骤
    │   ├── round-contract.md.template  # 本轮契约文件
    │   ├── save-state.sh.template      # PreCompact 存盘 hook
    │   ├── settings-hooks.json.template # PreCompact + SessionStart 接线片段
    │   ├── codex-round-contract.md.template # Codex 本轮契约
    │   └── codex-save-state.sh.template # Codex 显式存档脚本
    ├── fe-engineering/                 # 前端工程集成模板
    │   ├── README.md                   # 迁移步骤
    │   ├── SKILL.md                    # /fe skill 定义
    │   ├── claude-md/                  # CLAUDE.md 追加片段
    │   └── ai-config/                  # AI.md + ai.json 片段
    └── mandatory-skills/               # 强制性 Skill 声明模板
        └── SKILLS.md.template          # 3 Skill 配置模板
```

## 与 VibeCoding 的关系

本方法论关注 **工程过程层**（SDD + Fitness + Harness），与 VibeCoding（代码生成纪律层）互补：

- VibeCoding 定义 **如何写好代码**（PACE 路由、RIPER-7 阶段、状态持久化）
- 本方法论定义 **如何组织工程**（变更流程、质量门禁、Agent 系统配置）

两者可按需独立采用，也可组合使用。
