## 七、实战教程：从接入到一次变更全流程

前面建立了理论基础。现在用真实命令把一个空项目接入 Harness，并完整跑一次非平凡变更。本教程不展示"AI 能写什么"，而是展示**工程化如何改变实现路径和最终结果**；具体执行产物以你本机运行为准。

> **阅读导航**：只想看结论可直接跳到 Step 10。
>
> Kit 仓库：`https://github.com/8425334/harness-engineering-kit`（或你的私有镜像）

### Step 1 把方法论接进项目

在目标项目目录里运行接入器（选择 **完整接入 / Tier 2**，再选择你已安装的 Agent，例如 Claude Code）：

```bash
cd your-project
npx --yes --package github:8425334/harness-engineering-kit hek init
# 也可以从本地 Kit 副本做「对话式接入」：
#   python3 <kit>/scripts/onboard.py --project-root . --source-root <kit> --plan --json   # 只读计划
#   python3 <kit>/scripts/onboard.py --project-root . --source-root <kit> --agent claude --tier 2 --apply --json
#   python3 <kit>/scripts/onboard.py --project-root . --source-root <kit> --agent claude --check --json
```

接入分两档：

| 档位 | 安装什么 | 适合 |
|-|-|-|
| Tier 1（轻量） | 核心控制面：入口、`agent-policy.yaml`、`ai.json`/`AI.md`、`profile.yaml`、OpenSpec 配置、生产策略脚手架 | 只想先有全局约定 |
| Tier 2（完整） | Tier 1 + Fitness 门禁脚本与规则 + 经验记忆 | 需要质量门禁（本教程默认） |

接入后应出现四类入口，它们对应第 §二 讲的概念：

| 入口 | 对应概念 | 作用 |
|-|-|-|
| 根 `CLAUDE.md` / `AGENTS.md` | 入口 | Agent 的必读与安全边界，路由到 engineering Skill |
| `docs/methodology/agent-policy.yaml` + `profile.yaml` | 策略/档位 | 项目命令、权限、交付引用；方法论档位与 Self-Refine 策略 |
| 根 `ai.json` + 路径 `AI.md` | 上下文 | 机器可读项目地图 + 路径细节，经 `resolve_context.py` 确定性加载 |
| `docs/fitness/**` + `.claude/skills/engineering` | 门禁/编排 | 分层质量门禁（只读控制面）与工程编排 Skill |

### Step 2 填占位、确认项目上下文

接入只是脚手架，接下来要让 Agent **用仓库事实填掉占位符**：`{{PROJECT_NAME}}`、`agent-policy.yaml` 里的真实命令（测试 / 构建 / Fitness 用什么）、`ai.json` 的项目一句话摘要与模块路由、路径 `AI.md`。`--check` 会用确定性检查保证链路闭合：入口的必读区必须调用 `resolve_context.py`，`ai.json` 必须登记根模块且不超 4096 字节，每条维护中的 `AI.md` 必须被索引。

改代码前，Agent 先跑：

```bash
python3 docs/methodology/scripts/resolve_context.py <target-path>
```

并**严格按返回顺序**读取：`agent-policy.yaml` → `profile.yaml` → 根 `ai.json` → 命中的 `AI.md`（父到子）。缺一步或解析失败都算阻塞。你可以在 `profile.yaml` 里按项目风险选档位（`light / standard / regulated / experimental`）——本 demo 是纯领域引擎，选 `standard` 即可，Fitness 命令以 `agent-policy.yaml` 声明为准。

### Step 3 用复杂需求检验

Demo 选择**企业级多业态订单优惠分摊引擎**——它有真实工程的典型挑战：规则持续增加、规则可组合、金额需精度一致。

| 业态 | 规则重点 |
|-|-|
| 普通零售 | 按不含税金额比例分摊，单商品不超过自身可优惠金额 |
| 跨境 | 先扣关税和运费，再按比例分摊，单商品上限为金额的 30% |
| 秒杀 | 按数量分摊，零头归订单最后一笔商品 |
| 团购 | 未成团报错，低价商品优先，剩余部分按金额比例分摊 |
| 会员专享 | 先用积分抵扣，最多抵扣总优惠的 50%，剩余部分复用零售规则 |

### Step 4 发起变更并完成 Explore

让 Agent 实现该需求。工程 Skill 先跑上下文解析与**需求反思**——这里大概率触发 `clarify`（示例：金额内部用分还是元？跨境的输入从哪来？是否要 REST 接口？），Agent 会停下来聚焦提问并给出推荐，确认后才继续。

然后创建 change（Harness 是父，OpenSpec 是子）：

```bash
python3 docs/methodology/scripts/init_change.py order-discount-allocation \
  --title "多业态订单优惠分摊引擎" --mode backend --owner team \
  --trigger explicit-selection --profile-path docs/methodology/profile.yaml
```

Explore 结束前跑一次经验预检（`preflight_lessons.py`），并补全上下文决策。工作区长这样（注意与上一代架构的差别：`change.json` 里写死了 Harness 父 / OpenSpec 子的契约，独立 `/opsx:*` 不再是合法入口）：

```text
openspec/changes/order-discount-allocation/
├── change.json                  # schema v3：状态机 + 父子契约
├── context-pack.md              # 已解析上下文包摘要
├── impact-analysis.md           # 影响分析：范围/风险/待改对象
├── context-impact.json          # 计划交付文件 + ai.json/AI.md 是否需更新（审批绑定）
├── evidence/
│   ├── events.jsonl             # 追加式事件流
│   ├── lesson-preflight.json    # 经验预检结果
│   └── failure-events.jsonl     # 失败观察（如无则空）
├── proposal.md                  # 为什么做、影响哪里、非目标
├── specs/
│   └── discount-allocation/
│       └── spec.md              # 需求 + WHEN/THEN 场景
├── design.md                    # 架构选择、模型、任务、风险
├── tasks.md                     # 人工可读任务列表（运行态勾选）
└── task-plan.json               # 审批绑定的任务 DAG（权威）
```

推进状态只能走 `methodology_state.py`，且阶段门禁必须通过：

```bash
python3 docs/methodology/scripts/methodology_state.py openspec/changes/order-discount-allocation EXPLORED --actor agent
# 门禁失败会输出 BLOCKED 与缺失证据
```

### Step 5 写 Spec：把行为固化下来

OpenSpec 只通过调度器被调用，产出业务提案与**实现中立的行为 Spec**：

```bash
python3 docs/methodology/scripts/dispatch_openspec.py \
  openspec/changes/order-discount-allocation instructions --artifact proposal
python3 docs/methodology/scripts/dispatch_openspec.py \
  openspec/changes/order-discount-allocation instructions --artifact specs
```

```text
#### Scenario：跨境订单先扣关税运费再按比例分摊
    WHEN 订单业态为跨境，且关税与运费合计不超过可优惠总额
    THEN 先扣除关税与运费，再对剩余可优惠额按不含税金额比例分摊
    AND 任一单商品分摊额不超过其可优惠金额的 30%
```

**边界意识**：Spec 要明确"不做 REST、不做数据库迁移、不做真实税率推算"。如果 Agent 擅自新增 Controller 或 Mapper，就是越过非目标——这正是"非目标"的价值。

### Step 6 Design：从 Spec 读出模型，把任务变成 DAG

这是后端 RAM 的 Model 阶段，产出 `design.md`。先识别领域模型与规则模型：

**领域模型**：`OrderSettlement`（聚合根）、`Money`（整数分保存）、`ItemLine`（商品行）、`BusinessType`（枚举）、`AllocationResult`（结果，含正常值 / 未成团 / 金额不足等业务错误——**错误即值，不用异常**）。

**规则模型**：`BusinessTypeRuleSpec` 声明预处理步骤 + 核心分配器 + 余数策略 + 单商品上限。跨境与会员复用已有步骤组合成新管线，新增业态 = 新增枚举 + 注册一条 spec，不改核心（开闭原则）。

再把实现拆成受审批绑定的任务 DAG。示例（波次 W1→W3，`task-plan.json` 与 `tasks.md` ID 必须一致，Design 时全部未勾选）：

| 任务 | 内容 | 依赖 | 写范围（示意） | 是否可并行 |
|-|-|-|-|-|
| T1 | 领域模型与枚举（`OrderSettlement`、`Money`、`BusinessType`…） | — | `domain/model/**` | —（根） |
| T2 | 规则注册表与各业态 `RuleSpec` | T1 | `domain/rule/**` | 否（与 T3 写范围不重叠则并行） |
| T3 | 分配器与步骤管线（比例/等量/关税/积分/低价优先） | T1 | `domain/service/impl/**` | 可并行于 T2 之后 |
| T4 | 应用层编排与验证、结果组装 | T2, T3 | `application/**` | 否（依赖合并） |
| T5 | 单测 + 编译 + Fitness 快速门禁 | T4 | `test/**` | 否 |

```bash
python3 docs/methodology/scripts/dispatch_openspec.py \
  openspec/changes/order-discount-allocation instructions --artifact design
python3 docs/methodology/scripts/check_task_plan.py \
  openspec/changes/order-discount-allocation --phase DESIGN
```

### Step 7 人工审批：绑定契约摘要

Design 满足后，把外部审批绑定到完整契约摘要：

```bash
python3 docs/methodology/scripts/approve_design.py \
  openspec/changes/order-discount-allocation \
  --actor reviewer --source pull-request --approval-id PR-42
```

审批后，任务图是权威；**复选只是运行态进度**。此后任何 Spec/Design/任务图/写范围的改动都会让授权失效，进入 `CONTRACT_CHANGED`。

### Step 8 Apply：按波次执行，逐任务留证据

状态推进到 `IMPLEMENTING` 后，由唯一协调者按任务图调度。平台支持且有安全隔离（分支/工作树或互不相交写范围）时，就绪波次可并行；否则按同一张图顺序执行并记录降级原因——**缺并行能力不减少任务、审批或门禁**。

每个任务成功后立刻记录 run，并**自动勾选**对应 `tasks.md` 项：

```bash
python3 docs/methodology/scripts/record_task_completion.py complete \
  openspec/changes/order-discount-allocation T1 --run evidence/task-run-T1.json
```

> 只有 `record_task_completion.py complete` 能勾选任务——绝不能手改复选框、也不能攒到最后一起勾。若 Apply 被中断，保持 `IMPLEMENTING`，用 `resume` 从已校验证据恢复并拿到下一就绪波次。

### Step 9 验证与 Review：门禁 + 证据才算完成

任务全部完成并逐条记录 run 后，从 `IMPLEMENTING` 经 `VERIFYING` 推进到 `VERIFIED`——`VERIFIED` 的门禁就是 REVIEW。验证命令以 `agent-policy.yaml` 声明为准，形如：

```bash
python3 docs/methodology/scripts/methodology_state.py openspec/changes/order-discount-allocation VERIFYING --actor agent   # EXECUTE 门禁：任务全绿才可进入验证
python3 docs/fitness/scripts/fitness.py --tier fast
mvn -q compile && mvn test
python3 docs/methodology/scripts/methodology_state.py openspec/changes/order-discount-allocation VERIFIED --actor agent    # 触发 REVIEW 门禁
```

**调试日志三阶段**：编码时在分支入口 / 状态流转 / 外部调用处加临时调试日志 → 跑测试时**逐条自检验证数据流**（分支是否走对、状态是否 A→B、调用参数是否匹配契约）→ 通过后清理临时输出、保留框架业务日志。

> 单测绿 ≠ 行为正确：测试只证明没崩，日志自检证明行为对。

Review 门禁强制检查三件事：

- 改动文件摘要与 `context-impact.json` 声明的计划文件**完全一致**（缺文件或多了越界文件都失败）；
- 每个已审批任务都有一次成功的 run，`tasks.md` 勾选 ID 与成功 run **精确一致**；
- 若本次改动职责/边界/契约/路由，`AI.md` 与 `ai.json` 的对应更新已在改动集内（`check_context_docs.py` 校验）。

**接入完成的判断**：

- Agent 能说清模块结构、依赖方向、构建与门禁命令，改代码前先跑 `resolve_context.py`
- 非平凡需求会生成 Proposal → Spec → Design（含 Model）→ 审批 → 任务图，而不是直接开写
- 门禁失败时能指出文件、规则、原因与修复入口；失败会回写到经验记忆供下次预检

### Step 10 Sync → Archive：把已验证行为写回权威文档

验证通过后进入 Sync：把行为与实现差异同步回权威 Spec/文档，并证明摘要一致；随后 Archive 归档证据与学习结论。本次 Demo 是纯领域引擎、无生产影响，Archive 前只需补学习结论即可：

```text
Explore → Propose(Spec → Design → Approval) → Apply → Sync → Archive
                                                  ↑（验证/Review 在 Apply 内）
                                          本教程已完整走到这里
```

若同一 change 是**生产范围**（`--delivery-scope production`），Archive 会被生产闭环拦住：关联生产记录必须走完 `RELEASE_READY → DEPLOYED → OBSERVING → CLOSED`（或带证据回滚到 `CLOSED`）之后才能归档。

**演练结论**：

1. **先写 Spec 改变实现路径**：多业态没有变成五百行条件分支，而是 `BusinessTypeRuleSpec` + 步骤管线 + 注册表
2. **契约先于代码，审批绑定契约**：模型、任务图、写范围在动手前一次性说清，中途改契约要重新走审批
3. **代码生成不等于完成**：状态推进、门禁、逐任务证据缺一不可
4. **反馈有归属**：门禁失败有事件记录，可复用模式经审批成为经验，越用越好
