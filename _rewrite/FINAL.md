## 为什么需要工程化？

一句话让 AI 写代码很容易，但让它在真实项目中**持续产出可靠代码**很难。差距不在模型能力，而在工程环境：

- **上下文缺失** — Agent 不知道模块边界、依赖方向、允许的命令和领域规则，只能靠临时搜索猜
- **契约缺失** — 需求直接进实现，边写边改，职责漂移、边界模糊，测试无从写起
- **验证缺失** — "编译通过"≠"行为正确"，没有门禁和证据，"代码生成了"常被当成"做完了"

本教程展示如何用**仓库化的方法论**把 AI 从"代码生成器"变成"工程伙伴"。核心不是 Prompt 技巧，而是把权威、规则、文档、门禁和反馈沉淀在仓库里，让每次会话都站在可靠的基础上。

> 这套方法论被封装为 **Harness Engineering Kit**：仓库内控制系统。本文的每一章都与 Kit 落地在真实项目里的产物一一对应，正文里的命令和文件都是真实可执行的。

### 术语表

下文反复出现的核心术语，先在这里集中定义（同一概念在 Kit 落地后的文件名会一并标出）：

| 术语 | 定义 |
|-|-|
| **Agent** | AI 编程助手（如 Claude Code、Codex、Cursor），能读代码、改代码、跑命令 |
| **上下文（Context）** | Agent 一次会话能"看到"的项目信息。Harness 把它分成两层：根 `ai.json`（机器可读索引，≤4096 字节）+ 被索引的路径 `AI.md`（人类可读细节，≤400 行） |
| **确定性上下文加载** | 改代码前由 `resolve_context.py` 把目标路径解析成**唯一、固定顺序**的加载链，解析失败就拒绝开工（fail-closed） |
| **Token** | LLM 处理文本的最小单位，输入输出都按 Token 计费；稳定的上下文前缀命中缓存后只需约 0.1× 成本 |
| **agent-policy.yaml** | 项目唯一事实源：命令、可读写路径、权限、交付引用都在这一个文件里 |
| **门禁（Gate）** | 每个生命周期阶段的通过/不通过检查（`check_phase.py`），只有拿到"通过"证据才能推进状态 |
| **Fitness** | 受保护的质量门禁目录 `docs/fitness/`。Agent 只能读取执行、不能修改；按 fast/normal/deep 分层 |
| **engineering Skill** | 编排非平凡代码变更的 Agent Skill：路由上下文、编排生命周期、记录证据 |
| **Profile（后端 RAM / 前端 RAD / 全栈）** | engineering Skill 的 Design 与验证特化，回答"这个需求该怎么建模、怎么验证" |
| **OpenSpec** | Harness 的子级规格写作/校验能力，产出 `proposal.md`、`spec.md`、`design.md`、`tasks.md`，不拥有生命周期 |
| **SDD** | 规格驱动交付：先写清"做什么、为什么、边界、WHEN/THEN 行为"，再实现 |
| **契约（Contract）** | 接口、类型、字段、错误、权限的明确约定；审批绑定契约摘要，契约一变授权即失效 |
| **需求反思（Requirement Reflection）** | 发送回答/产生副作用前把任务理解归类为 `ready / clarify / correct / blocked` 的回答级质量门 |
| **Self-Refine** | Profile 控制的内层循环 `生成 → 自我批判 → 优化 → 再检查`，在申请阶段门禁前收敛质量 |
| **经验记忆（Lesson）** | 把反复出现的失败 `记录 → 提炼 → 外部审批 → 激活 → 下次 Explore 预检`，供后续变更复用 |
| **提示词缓存（Prompt Cache）** | LLM 服务端对相同前缀的字节级缓存；Harness 用 `context_cache.py` 生成稳定前缀指纹并测量命中 |


## 一、LLM-Harness 原理

> **一句话主题**：LLM 负责"生成智能"，Harness 负责"组织、约束和验证智能"。理解所有工程化的前提，是先看清 LLM 的能力边界，以及它的"外挂"——仓库里的控制面、上下文、门禁和反馈——从哪来。

### 1.1 LLM 的本质

LLM 并不是天然拥有流程、记忆和执行能力的"智能体"，它的核心动作只有一步：

> 输入上下文 → 预测下一个 Token → 继续预测 → 生成输出

由此带来五个天然特点：

- **上下文决定质量**——输入里有什么，输出上限就在哪；
- **上下文越长越贵**——Token 即成本，越长延迟越高；
- **调用无状态**——每次调用本身不"记住"上一次对话；
- **输出概率性**——可能犯错，需要外部验证；
- **不天然守流程**——不会自动按多步骤流程执行，除非外部系统约束它。

于是引出一个关键问题：

> 只把问题丢给 LLM，它会回答；但它不一定按正确流程完成任务。

这正是 Harness（仓库内工程运行时）存在的理由。

### 1.2 Embedding 与 Transformer

三个常被混为一谈的概念，先分清。两句话概括：

> **Embedding** 把信息变成模型能计算的语义表示——解决"找什么"。
>
> **Transformer** 在上下文中建立信息之间的关系——解决"怎么理解"。

完整链路是：文档 / 代码 / 用户需求 → Embedding 转成语义向量 → 与当前任务一起进入上下文 → Transformer 通过 Attention 建立关系 → LLM 预测并生成输出。在工程系统里，两者的用途边界很清晰：

| 能力 | 干什么 | 在工程系统里用在哪儿 |
|-|-|-|
| Embedding | 把内容编码成语义向量 | 文档检索、代码库检索、找相似历史任务、构建 RAG 上下文 |
| Transformer | 把检索内容与当前任务结合理解 | 决定注意力放哪、生成时对齐上下文 |

三者分工压成一句：

> Embedding 解决"找什么"，Transformer 解决"怎么理解"，LLM 解决"怎么生成"。

### 1.3 为什么需要 Harness

Harness 可以解释成一句话：

> 围绕 LLM 搭建的仓库内运行时，用来管理上下文、工具、状态、流程、缓存和验证。

LLM 像一个**能力很强但不懂项目管理的工程师**。Harness 给它补上：权威与规则文件、确定性的上下文加载、工具调用边界、生命周期状态、审批与门禁、失败后的修正与经验沉淀。

没有 Harness，一次提问换来一次回答：

```text
用户问题 → LLM → 一次性答案
```

有 Harness，同一句需求被推进成一个工程闭环：

```text
需求 → 加载上下文 → 分析/建模 → 契约与审批 → 受控执行 → 门禁验证 → 交付或修正
```

关键分界在这里：

> LLM 提供认知能力，Harness 提供工程确定性。

两者擅长的事几乎不重叠：

|  | LLM 擅长 | Harness 擅长 |
|-|-|-|
| 内容 | 理解自然语言、归纳推理、生成代码、发现模式 | 保持上下文一致、强制流程、控制权限边界 |
| 状态 | —（单次调用无状态） | 管理生命周期状态、复用阶段产物 |
| 验证 | 自述"应该没问题" | 用门禁 / 测试 / 证据自动验证 |

一句话：**LLM 回答"它能做"，Harness 决定"允许它怎么做、做完怎么证明"**。

### 1.4 Token Cache

成本与延迟的最大来源，是**每次请求都重复发送相同上下文**。一次编码任务要反复传入：项目规范、策略、架构文档、接口定义、数据库约束、历史任务信息。这些占了大量 Token，却几乎每次都不变。

Token Cache 的思想是：

> 稳定的前缀只计算一次，变化的任务部分单独处理。

- **固定上下文**（项目规则 + 架构文档 + 工具说明）→ 缓存复用
- **动态上下文**（本次用户问题 + 当前代码 + 执行结果）→ 每次更新

三个直接收益：**减少输入成本、降低首字延迟、提高多轮一致性**。

注意要区分四种缓存，它们缓存的不是同一个东西：

| 缓存 | 缓存什么 | 对应问题 |
|-|-|-|
| Prompt Cache | 重复的 Prompt 前缀（系统指令、项目规则、工具定义） | 每次都全价重读一遍规则 |
| KV Cache | 生成过程中已算出的 Key/Value（Transformer 内部） | 每生成一个 Token 都重算全部历史 |
| Embedding Cache | 文档 / 代码片段的向量 | 相同内容反复做 Embedding |
| 业务结果缓存 | 已完成检索 / 分析 / 工具调用结果 | 同样的答案反复查 |

所以工程化设计有一条隐含纪律：**让每轮请求的前缀尽量稳定、增量尽量小**。Kit 落地了一个仓库侧协议：`context_cache.py` 对固定上下文生成稳定指纹（`prefix_digest`），宿主据此获得前缀缓存身份，并在每次请求记录 `hit / miss / bypass`，长程任务的实测目标命中率 ≥99.5%。详见 Kit 的 `core/context-cache-protocol.md`。

### 1.5 从"一次生成"到"工程闭环"

早期方法论把执行过程包装成后端一条完整的 RAMER 循环（Read→Analyze→Model→Execute→Review）、前端另一条 RADIR 循环，互相独立。实践下来发现两个问题：

1. **验证被塞进"循环末尾"**——同一个 Agent 又写又验，缺乏独立阶段，容易把"代码生成了"当成"做完了"；
2. **前后端各一套工作流**——前后端联动需求被迫跑两套平行循环，契约没有唯一的归属。

当前架构把这两点合并了：**一份统一生命周期 + 一个 engineering Skill + 按领域特化的 Profile**。后端建模（RAM）和前端分解（RAD）不再各是一条完整循环，而是"设计"环节的特化；执行与验证统一收进生命周期，由确定性门禁负责。

> 一句话：把一次不可控的生成，变成一条**有上下文、有契约、有审批、有执行、有验证**的生命周期。

### 1.6 生命周期 × Token Cache

生命周期每个阶段都会产生可复用的上下文，这正是它与 Token Cache 的结合点：

| 生命周期阶段 | 可缓存 / 可复用的产物 |
|-|-|
| Explore（上下文） | `agent-policy.yaml`、`profile.yaml`、`ai.json`、命中的 `AI.md`——由 `resolve_context.py` 排出固定顺序，`context_cache.py` 对其原始字节做稳定指纹 |
| Propose（契约） | 提案、行为 Spec、Design、`task-plan.json` 任务图 |
| Apply（执行） | 每个任务的成功 run 记录与执行证据 |
| Review / Sync | 门禁结果、审查证据、同步摘要 |

同一个任务常要多次回到对话：第一轮加载策略与路径上下文，第二轮产出 Spec/Design，第三轮按已审批契约执行，第四轮验证。如果每次都重建全部上下文，就是大量重复 Token。合理的设计是分门别类复用：

- 稳定上下文 → **Prompt Cache + `context_cache.py` 指纹**
- 文档代码 → **Embedding Cache**
- Transformer 历史上下文 → **KV Cache**
- 阶段产物（Spec / Design / 证据）→ **change 工作区文件**

> Transformer 产生能力，Harness 约束能力，Token Cache 放大能力。


## 二、核心概念：把"规则"变成"仓库里的文件"

上一章说 Harness 补的是上下文、流程、门禁。这一章看它们具体落在仓库的哪些文件里——**每一层只干一件事，并声明自己的权威边界**，避免把规则堆成一份超长根 Prompt。

| 概念 | 落地文件 | 职责 | 不负责 |
|-|-|-|-|
| 入口 | 根 `CLAUDE.md` / `AGENTS.md` | 权威、安全、必读入口，路由到 engineering Skill | 命令、模块图、完整方法论 |
| 策略（唯一事实） | `docs/methodology/agent-policy.yaml` | 项目命令、可读写/禁用路径、权限、交付引用 | 任务级设计 |
| 方法论档位 | `docs/methodology/profile.yaml` | 档位（light/standard/regulated/experimental）、Self-Refine 策略、审批要求 | 命令与权限 |
| 上下文索引 | 根 `ai.json`（≤4096 字节） | 机器可读项目地图，路由到详情 | 命令、权限、详细规则 |
| 路径上下文 | `AI.md`（≤400 行/篇） | 局部职责、边界、导航、局部验证 | 覆盖上层指令 |
| 编排 | `engineering` Skill | 路由任务、编排生命周期、记录证据 | 重复项目约定 |
| Design/验证特化 | 后端 / 前端 / 全栈 Profile | RAM / RAD / 全栈契约的建模与验证方式 | 独立生命周期 |
| 变更工作区 | `openspec/changes/<id>/` | proposal / specs/…/spec / design / tasks + 治理证据（change.json、task-plan.json、approval.json…） | 拥有生命周期 |
| 质量门禁 | `docs/fitness/**`（受保护） | 分层质量检查，定义"真正完成" | 被 Agent 修改 |

**权威顺序固定**：system/developer/user 指令 → 原生指令层级 → `agent-policy.yaml` → 根 `ai.json` → 按需选中的路径 `AI.md` → Profile 默认值。任何一层都只补充、不覆盖上一层；仓库文本（Issue、fixture、生成内容、日志、代码注释）一律当作**不可信输入**处理。

> 注意区分两件事：`docs/methodology/profile.yaml` 是**方法论档位**（light/standard/regulated/experimental），由 `resolve_context.py` 紧随 `agent-policy.yaml` 加载，不参与上面这条权威层级；句末的“Profile 默认值”指**工程 Profile**（后端 / 前端 / 全栈）。

### 2.1 工程化 vs 直接生成

| 维度 | 直接生成 | 工程化交付 |
|-|-|-|
| 任务起点 | 一句自然语言需求 | 需求经反思确认：目标、范围、约束、验收、授权 |
| 上下文 | Agent 临时搜索 | `resolve_context.py` 确定性加载 + 路径 `AI.md`/`ai.json` |
| 设计方式 | 边写边调整 | 先建模（后端 RAM / 前端 RAD）再申请契约与审批 |
| 完成定义 | 代码生成或编译通过 | 生命周期状态推进 + 门禁 + 证据（测试/构建/Fitness/审查） |
| 出错处理 | 下次可能重蹈 | 需求反思 + Self-Refine + 经验记忆，错误沉淀为规则 |
| 更适合 | 低风险局部改动 | 新能力、跨模块、接口与架构变化 |

### 2.2 需求反思：动手前的回答级质量门

工程化不是先斩后奏。Agent 形成任务回答草稿后、发送或产生副作用前，必须把对需求的理解归入四类之一（见 `requirement-reflection.md`）：

| 结果 | 判断条件 | Agent 行动 |
|-|-|-|
| `ready` | 目标、范围、完成标准、约束、授权足够明确 | 说明重要假设，在授权范围内行动 |
| `clarify` | 歧义可能改变实现/结果/成本/安全 | 停止写入，聚焦提问并给推荐方案 |
| `correct` | 需求与仓库事实/约束/不变量冲突 | 展示证据与最小可行修正，等确认 |
| `blocked` | 缺授权或证据，无法继续 | 说明阻塞点与最安全的下一步 |

规则只有一条：**不要在多个实质不同的解释之间静默选择**。歧义影响结果就停下来问，并把推荐选项一起给出。

### 2.3 统一生命周期：状态、门禁、证据

每个非微小变更都对应一条生命周期，唯一由 `methodology_state.py` 推进状态、`check_phase.py` 校验阶段门禁：

```text
Explore → Propose（Spec → Design → Approval）→ Apply → Sync → Archive
```

| 阶段 | 状态目标 | 门禁 | 说明 |
|-|-|-|-|
| Explore | `EXPLORED` | EXPLORE | 读取上下文，产出影响分析与上下文决策，预检经验 |
| Spec | `CONTRACT_READY` | SPEC | 业务提案 + 可观测行为 Spec（WHEN/THEN） |
| Design | `DESIGN_READY` | DESIGN | 技术 Design + `tasks.md` + 审批绑定的 `task-plan.json` 任务图 |
| Approval | `APPROVED` | EXECUTE | 外部身份审批，绑定全部契约摘要 |
| Apply | `IMPLEMENTING → VERIFYING → VERIFIED` | EXECUTE → REVIEW | 按任务图执行，逐任务记录证据并勾选进度；验证/Review 在 Apply 内完成 |
| Sync | `SYNCED` | SYNC | 已验证行为同步回权威 Spec/文档，摘要一致 |
| Archive | `ARCHIVED` | ARCHIVE | 归档证据；生产变更需生产闭环先到 `CLOSED` |

设计之外还有三条异常轨道：契约漂移 → `CONTRACT_CHANGED`（需回 `CONTRACT_READY` 重新审批）、仓库漂移 → `DRIFT_DETECTED`、验证失败 → `REMEDIATING`。审批绑定的是契约摘要——Design/Spec/任务图任一变化，原授权即失效。

### 2.4 OpenSpec 是子级，不是第二条生命周期

`openspec/changes/<id>/` 是唯一活跃变更工作区，但它的"父亲"是 Harness 生命周期：`init_change.py` 负责创建 change 并写入父子契约（`change.json`），OpenSpec 只通过 `dispatch_openspec.py` 提供白名单内的写作/校验（`status` / `instructions` / `validate` / `show` / `templates`）。**不再有独立的 `/opsx:*` 生命周期**——这是它与上一代架构最大的区别。工程化交付依赖的各个概念不是互相独立的流程，而是同一份生命周期里职责不同的部分。


## 三、从线性实现到模型驱动

理论概念需要通过具体案例才能理解。下面用一个风控变量加工的例子，展示后端 Profile 中"建模优先"（Model）如何改变代码结构。

**场景**：从学历、学籍、学校排名和 985/211 标签中加工多个风控变量。

### 3.1 线性实现的问题

AI 面对这类需求最容易的做法是"照着字段往下写"：一个 `ServiceImpl` 注入所有 Mapper 和 Redis，把每个变量的取数、换算、缓存、异常处理都写在方法里：

```java
public class EducationFeatureServiceImpl {
    private EducationRecordMapper educationRecordMapper;
    private StudentStatusRecordMapper studentStatusRecordMapper;
    private SchoolRankMapper schoolRankMapper;
    private SchoolTagMapper schoolTagMapper;
    private RedisTemplate<String, String> redisTemplate;
    // ...所有变量逻辑都塞进这一个类
}
```

**问题**：新增变量、替换数据源、调整语义都要改同一个类。领域概念只存在于方法名里，无法独立测试和复用。这正是"先建模、再实现"要解决的。

### 3.2 模型驱动的实现

按后端 RAM 的方法：先 **Read** 相关取数与既有契约，再 **Analyze** 出边界与变化轴，最后在 **Model** 阶段识别领域模型和职责：

| 模型 | 职责 |
|-|-|
| `EducationProfile` | 聚合学历记录和学籍状态 |
| `SchoolReferenceIndex` | 提供排名与 985/211 标签查询 |
| `EducationFeatureContext` | 封装一次计算所需的数据 |
| `EducationFeatureCalculator` | 定义单个变量的计算契约 |
| `EducationFeatureResult` | 表达正常值、无数据和业务异常 |
| `EducationFeatureEngine` | 调度计算器并隔离单变量失败 |
| `EducationProfileRepository` | 屏蔽 Mapper、缓存和查询细节 |

**先定义契约**（接口、类型、字段的明确约定，Model 阶段的核心产出）：

```java
public interface EducationFeatureCalculator {
    String variableCode();
    EducationFeatureResult calculate(EducationFeatureContext context);
}
```

最终 `ServiceImpl` 只保留编排：

```java
public VarLogicResponse computeEducationFeatures(VarLogicRequest request) {
    EducationProfile profile = profileRepository.findBy(request.getIdentityNo());
    SchoolReferenceIndex schoolIndex = schoolReferenceProvider.currentIndex();
    EducationFeatureContext context = contextFactory.create(profile, schoolIndex);
    List<EducationFeatureResult> results = featureEngine.calculate(context);
    return responseAssembler.assemble(results);
}
```

### 3.3 对比总结

| 维度 | 线性实现 | 模型驱动实现 |
|-|-|-|
| `ServiceImpl` | 业务逻辑的容器 | 应用编排入口 |
| 新增变量 | 修改原 Service | 新增 Calculator，Engine 不变 |
| 测试方式 | 构造大类的全部依赖 | 分别测试规则、Engine 和取数 |

**关键洞察**：模型驱动不是"先写接口再写实现"的形式主义，而是让领域概念**可见、可独立变化、可独立测试**。领域知识与实现的对应关系（哪些对象是聚合、谁持有哪个仓储）应记录在项目自身的入口与路径文档里，让 Agent 在建模前就能读到。


## 四、后端工程化：RAM + 分层依赖

后端的核心挑战是**业务逻辑容易散落在 Service、模块边界和依赖方向容易失控**。后端 Profile 把建模动作收敛为 RAM，把"什么算合格"变成可检查的规则。

### 4.1 后端 RAM：建模必须在实现前

| 阶段 | 发生在 | 产出什么 | 回答 |
|-|-|-|-|
| **Read** | Explore | 权威策略、最近路径上下文、相关代码、测试、契约、历史 | Agent 的上下文对吗？ |
| **Analyze** | Explore/Spec | 不变量、所有权、信任边界、调用方、兼容性、迁移、失败模式 | 这到底改动了什么？ |
| **Model** | Design | 领域边界、接口、持久化规则、权限、幂等、事务/并发、实现顺序 | 输入输出、依赖方向、禁律是否可验证？ |

Apply 只消费已审批的模型。**Apply 期间只能做局部漂移检查，不能静默重做设计**。验证命令一律来自 `agent-policy.yaml`，由真实风险决定深度：公开接口跑契约测试、改 Schema 做迁移演练、动权限/数据做负向测试，而不是每次都跑全量。

### 4.2 分层与依赖方向

依赖方向是后端最容易失控的地方。铁律只有一条：**领域层不依赖任何框架，基础设施层实现领域层的端口**。

```text
        adapter   (REST / RPC / 事件 / 定时：只消费 application 契约，做 DTO 转换)
           │
        application  (用例编排、事务边界、安全：不含业务规则)
           │
        domain   ←------ infrastructure (实现 domain 的仓储接口 / PO / 外部集成)
    （纯 Java：聚合 / 值对象 / 领域服务 / 仓储接口，零框架 import）
```

| 层 | 职责 | 禁 |
|-|-|-|
| `domain` | 纯 Java 聚合 / 值对象 / 领域服务 / 仓储接口 | 依赖 Spring / Redis / MyBatis 等框架 |
| `application` | 用例编排、事务边界、安全 | 包含业务规则 |
| `infrastructure` | 仓储实现、PO、外部集成（实现 domain 端口） | 反向依赖上层实现细节 |
| `adapter` | REST / RPC / 事件 / 定时适配（只消费 application 契约） | 包含业务逻辑 |

> 领域层纯度（domain-purity）是 Fitness 的常驻检查项——domain 一旦出现框架注解就会被拦下；依赖方向的"反向依赖"目前主要由 Review 与架构边界规则约束（Maven/Gradle/npm 依赖图自动检查属后续扩展）。

### 4.3 后端验收规则：契约先行、多态优于分支

| 规则 | 内容 | 谁检查 |
|-|-|-|
| 契约先行（ACL） | Controller/Remote 出入参用 DTO/BO/VO，严禁直接拿 Entity 当接口；同名字段映射集中走 MapStruct，不手写 `BeanUtils.copyProperties` 把转换散落各层 | 人工 Review + Fitness（object-mapping / architecture-boundary） |
| 多态优于分支 | 嵌套 if/else ≥2 或 switch ≥3 → Strategy / Factory / Handler（registry） | 代码审查 |
| 领域对象零框架 | domain 纯 Java，不 import `@Service` 等 | Fitness（ddd-compliance） |
| Mapper/DB 一致性 | Mapper 接口与 XML 一一对应，不写内联 SQL 绕过映射；改库先想迁移 | Fitness（backend-quality：mapper-xml-parity / mapper-inline-sql；sql-quality：迁移） |
| 权限与安全 | 权限管理走统一门面，不留硬编码密钥与危险配置 | Fitness（permission-management / security） |
| 门禁证据 | `compile → test → fitness` 有执行证据才算完成（profile 另含边界检查与 API 契约验证）；调试日志三阶段自检 | 阶段门禁 + Review |

**契约先行是 AI 最容易破的一条**：直接拿 Entity 当接口出入参、到处手写 `BeanUtils.copyProperties`、把转换塞进 Service——这三条会让边界立刻模糊。后端质量门禁（编译 / 测试 / Fitness）是**完成条件，不是可选步骤**。


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


## 六、反馈闭环：把错误变成工程的养料

工程化不是一次性设置，而是**从错误中学习并固化**的持续过程。每次 Agent 犯错、每次门禁失败，都是改进工程环境的机会。反馈不是"事后补文档"，而是被编进流程的四层机制：

1. **需求反思（回答级）**：发答案/动手前先归类 `ready / clarify / correct / blocked`——把"误解需求"拦在开工前（见 §2.2）。
2. **Self-Refine（门禁前）**：在 Explore/Spec/Design/Apply 内跑 `生成 → 自我批判 → 优化 → 再检查`，收敛后再申请阶段门禁。策略由 `profile.yaml` 控制（`disabled / recommended / required / required-independent`），`max_iterations` 限制迭代次数，达到上限仍未解决的问题必须如实记录未覆盖风险。
3. **确定性门禁（阶段级）**：`check_phase.py` / Fitness 用脚本判断"过了没有"，不靠 Agent 自述。
4. **人工 Review / 审批（信任级）**：Spec、Design、审批、经验激活都必须有外部身份，Self-Refine 永远不能替代它们。

Self-Refine 是有界辅助：同一个模型可能重复同一个错误，所以它**不能**批准契约、替代失败的确定性门禁，也不能直接写进权威策略或 Fitness 控制面。

### 6.1 经验记忆：失败 → 审批 → 激活 → 复用

单次 Self-Refine 只覆盖一次变更。经验记忆把**跨变更反复出现**的失败变成可检索的预防指导：

```text
失败 → record_failure.py 采集 → create_lesson_candidate.py 提炼
     → approve_lesson.py（外部审批）激活 → Explore 前 preflight_lessons.py 预检 → 验证
```

| 位置 | 含义 | 权威级别 |
|-|-|-|
| `evidence/failure-events.jsonl` | Fitness/门禁/测试/差异/生产的不可变观察 | 仅证据 |
| `lesson-candidate.json` | Agent 提议的模式、根因、预防、验证 | 待审核 |
| `docs/methodology/lessons/*.json` | 外部审批后激活的项目经验 | 辅助预防指导 |
| Fitness / 策略规则 | 已证明反复出现的确定性约束 | 规范控制 |

关键纪律：**一次观察通常只生成"候选"，不直接生成"规则"**；相同签名反复出现、经外部审核后，才可升级为强制预检查或确定性 Fitness 规则。Agent 必须把 `docs/fitness/**` 当只读控制面——想改门禁就 `check_fitness_protection.py` 拿到摘要、停下来申请外部人工审批，任何规模都不豁免（除规范首次安装与可证明的既有语法修复外）。

### 6.2 常见问题与沉淀位置

| 重复问题 | 沉淀位置 | 效果 |
|-|-|-|
| Agent 不知道模块职责 / 边界 | 路径 `AI.md` + 根 `ai.json` 索引 | 下次会话确定性加载到局部上下文 |
| 需求有歧义就闷头实现 | 需求反思（`clarify` / `correct`） | 动手前把误解拦下 |
| 复杂需求直接进实现 | Spec / Design / 审批确认点 | 强制先写清边界再写码 |
| 规则总是塞进 `ServiceImpl` | 后端 RAM Model + DDD 建模文档 | 引导向模型驱动 |
| DTO / 权限 / 依赖方向反复出错 | Fitness Hard Gate | 自动拦截常见错误 |
| 实现质量参差、改完才返工 | Self-Refine + 阶段门禁 | 门禁前收敛，返工变少 |
| 边界场景 / 失败反复发生 | 经验记忆（记录→审批→激活→预检） | 防止重蹈，越用越好 |

### 6.3 五个核心判断

| 判断 | 落地方式 |
|-|-|
| 复杂度上升后，Prompt 不够用 | 把稳定规则放进仓库：`agent-policy.yaml` / Profile / 路径文档 |
| 需求越复杂，越要先建模 | 先契约、对象、职责和变化轴（RAM Model / RAD Decompose） |
| 文件拆分不是架构 | 先确认模型，再让边界自然落成文件 |
| 代码生成不等于完成 | 状态推进 + 门禁 + 测试/构建/Fitness/Review 证据 |
| AI 的长期收益来自反馈 | Self-Refine + 经验记忆，把重复问题沉淀成文档、规则与门禁 |

**一句话总结**：工程化的本质是把"人脑里的规则"变成"仓库里的规则"，让 Agent 每次会话都站在更可靠的基础上。


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


## 八、进阶：多 Agent 并行（全栈联动）

上一代"前后端联动"靠两条独立工作流（后端一条循环、前端另一条）各自跑完再合并——契约没有唯一归属，串行浪费墙钟时间，并行又容易出现两边对不齐。

当前架构把全栈联动收进**同一个变更、一份契约、一次审批、一张任务图**：全栈 Profile 不再是一条独立循环。

### 8.1 一个变更，一份契约

- 用 `--mode fullstack` 创建 **一个** change（不是前端一个、后端一个）。
- Design 把**后端 Model 与前端 Decompose 写进同一份 `design.md`**，并先定义跨越 API 两侧的共享行为契约：版本/兼容、可空性/默认值、校验、错误结构、权限、幂等、重试/超时、时区/精度、可观测字段、生成类型与所有权。
- 后端、前端、生成契约、集成工作全部进入**同一张 `task-plan.json` DAG**，一次审批绑定整份契约。

| 关键点 | 内容 |
|-|-|
| 契约是地基 | 启动任何实现前，请求/响应字段、枚举、错误、权限、路由必须和用户确认清楚 |
| 并行是可选机制 | 只有 Agent 运行时支持并发、且仓库有安全隔离（分支/工作树或不重叠写范围）才并行 |
| 证据回交协调者 | Worker 只拿自己的任务与契约引用，互不集成；集成与最终验证只由协调者做 |
| 串行不是降级 | 串行执行用同一张图、同一份契约、同一套门禁，只是不并行 |

### 8.2 Apply：就绪波次

协调者按任务图调度就绪波次：BE、FE、生成契约各自在隔离工作区里实现，依赖满足后进入下一波；集成任务把两侧结果合到一起，随后协调者统一跑最终验证（字段对齐、枚举一致、错误与权限语义、路由、生成类型或消费方测试，以及两侧项目门禁）。

Review 强制校验：请求/响应字段与枚举、错误与权限语义、路由，以及两侧文件摘要与任务 run 的**精确一致**。

> **何时用**：新业务功能、跨模块改造、API 契约变更——只要同时碰前后端。
>
> **何时不用**：单侧任务直接用后端 / 前端 Profile；平台不支持并发或隔离时退化为同图串行。
>
> **一句话**：并行不是默认选项，是契约清晰时的加速器。契约不清晰，串行更稳。


