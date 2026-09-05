# Harness 对话式接入手册

本文是给项目成员和 Agent 使用的操作说明。接入不再要求项目成员手动执行 `init.sh`；Agent 负责盘点、生成计划、修改文件和校验，项目成员只需要确认范围和项目事实。

## 一、统一对话协议

所有接入都遵循同一条链路：

```text
只读盘点 → 输出计划 → 用户确认 → 执行接入 → 填写项目事实 → 校验 → 生成回执
```

Agent 必须先运行只读计划，不能收到第一条消息就写文件。用户确认只覆盖计划中列出的文件和动作；计划变化后必须重新确认。

每次准备发送计划、事实摘要或完成结论时，Agent 都要先做需求反思：检查目标、范围、完成标准、约束、证据和授权。如果发现会影响结果的歧义、与仓库事实冲突、缺少授权或证据，必须暂停有后果的操作，说明依据，给出最佳方案并向用户确认；不能静默猜测，也不能把推荐方案当成已批准需求。详见[需求反思与澄清](../i18n/zh/core/requirement-reflection.md)。

Agent 使用的命令（由 Agent 执行，不要求用户复制到终端）：

```bash
python3 <kit>/scripts/onboard.py \
  --project-root . --source-root <kit> --tier 2 --plan --json
```

其中 `<kit>` 是 Harness Engineering Kit 的本地绝对路径。Agent 能从当前 Skill 定位时直接使用；无法定位时，应向用户索要路径，不得猜测或下载远程安装脚本。

## 二、纯新项目接入

### 1. 用户第一条消息

将下面内容直接发给项目 Agent：

```text
请把当前 Git 项目接入 Harness Engineering Kit，按“纯新项目”处理。

先只读检查，不要修改任何文件。请识别项目技术栈、构建/测试入口和模块结构，运行 onboarding 计划并告诉我：
1. 检测到的状态；
2. 将创建、同步、保留的文件；
3. 使用 Tier 2 的原因；
4. 需要我确认的项目事实和风险。

不要删除或覆盖现有的 AGENTS.md、CLAUDE.md、ai.json、AI.md、agent-policy.yaml、profile.yaml 或 OpenSpec 配置；不要安装依赖、访问生产环境或修改旧架构文件。等我确认计划后再执行。
```

### 2. Agent 预期回复

Agent 应给出类似以下摘要，而不是直接报告“已完成”：

```text
状态：fresh
计划：创建根上下文、策略、Profile、OpenSpec、方法论脚本、Engineering Skill、Fitness 和生产控制模板
保留：未发现已有项目配置
待确认：项目名称、负责人、技术栈、test/build/fitness 命令、可读写路径和拒绝路径
下一步：请确认按此计划执行
```

### 3. 用户确认消息

确认前先检查 Agent 列出的命令和路径是否真实。确认示例：

```text
确认按刚才的 fresh / Tier 2 计划执行。项目名是“订单服务”，负责人是 team-order；请根据仓库现有 pom.xml 和测试目录填写技术栈与命令。不能确定的值保留为待确认项，不要臆造。
```

### 4. Agent 执行顺序

Agent 在收到确认后应：

1. 用 `--apply` 执行已确认计划。
2. 读取仓库事实，填写根 `ai.json`、`AI.md`、`docs/methodology/agent-policy.yaml`、`docs/methodology/profile.yaml` 和 `openspec/config.yaml` 中的占位符。
3. 对每条命令实际运行一次轻量验证；命令不确定时先停下来询问用户。
4. 用 `--check --json` 执行根上下文、策略、Profile、Fitness 和双平台 Skill 校验。
5. 将结果写入 `docs/methodology/onboarding.json`，并报告未解决占位符、失败检查和后续动作。

## 三、增量更新/老版本升级

### 1. 用户第一条消息

适用于已接入旧版架构、存在部分 Harness 文件，或需要从旧版本同步到当前版本：

```text
请对当前 Git 项目执行 Harness 增量更新。

先只读盘点并判断是 partial、legacy 还是 current，比较当前项目与 Harness Kit 的版本和文件差异。请分别列出：
1. 必须同步的官方脚本、核心文档、workflow 模板和 Engineering Skill；
2. 必须保留的项目自定义配置；
3. 发现的旧 ramer、fe-engineering、multi-agent、Cursor 或 Codex 入口；
4. 是否存在需要单独审批的删除、Fitness 变更或命令变更。

默认只做增量同步，不删除旧文件，不重写项目事实，不改变业务代码。等我确认后再执行。
```

### 2. Agent 处理规则

这里的 Tier 是“本次执行后的目标安装范围”，不是增量升级的前置条件，也不能据此推断旧版本已经完整安装了 Tier 1。任何低版本到高版本升级，即使项目已有部分 Tier 1 文件，Agent 仍必须比较并同步目标版本的全部 Tier 1 核心资源（方法论文档、控制脚本、workflow 模板、版本文件、Engineering Skill，以及缺失的生产控制脚手架）。`--tier 1` 只表示暂不补装 Fitness 和经验记忆等 Tier 2 可选资源；它不表示跳过 Tier 1 更新。版本关系、降级阻断和特殊发布迁移由 [版本化管理](versioning.md) 统一处理，不在对话文案中硬编码某一对版本号。

如果项目存在旧入口但没有合法的 `docs/methodology/VERSION`，状态应报告为 `unversioned` 或 `invalid` 并停止自动写入；Agent 必须根据仓库证据确认实际基线后再补版本，不能臆造版本号。

| 检测状态 | Agent 做什么 | 不做什么 |
|---|---|---|
| `partial` | 补齐缺失入口，保留已有项目配置 | 不用模板覆盖已有事实 |
| `legacy` | 安装当前控制面，输出旧架构清单 | 不自动删除旧 Skill 或配置 |
| `current` | 同步官方资源，检查版本漂移 | 不改项目自定义策略 |

旧架构项目确认示例：

```text
确认按 legacy 增量升级执行：同步官方 Harness 资源，保留现有 ramer/fe-engineering 配置并在回执中列出。暂不删除旧入口；如果删除是校验通过的必要条件，请先停止并给出单独清理计划。
```

Agent 执行命令：

```bash
python3 <kit>/scripts/onboard.py \
  --project-root . --source-root <kit> --tier 2 --apply --json
```

同步完成后，Agent 必须重新读取项目上下文，再填写或更新必要的版本字段，最后执行：

```bash
python3 <kit>/scripts/onboard.py \
  --project-root . --source-root <kit> --check --json
```

如果旧入口导致校验失败，Agent 不应为了“变绿”直接删除文件；应报告具体冲突，并等待用户发起“清理旧入口”的独立变更。

## 四、接入完成标准

只有同时满足以下条件，Agent 才能说“接入完成”：

- `AGENTS.md`/`CLAUDE.md` 保持原生指令权威，且能路由到 Engineering Skill。
- `ai.json`、`AI.md`、策略、Profile 和 OpenSpec 配置没有未填写占位符。
- `docs/methodology/VERSION`、方法论脚本、workflow 模板和 `.claude/.agents` 下的 Engineering Skill 已同步。
- `ai.json`/`AI.md` 引用路径存在，`resolve_context.py` 能解析根路径。
- Fitness 保护、策略、Profile 和两个平台 Skill 校验通过；失败项有明确记录。
- `docs/methodology/onboarding.json` 记录状态、版本、动作、摘要、保留的旧文件和校验结果。
- 未经用户单独确认，没有删除旧文件、覆盖项目配置、安装依赖、执行生产写入或修改 `docs/fitness/**`。

## 五、常见追问

**问：WorkBuddy、Trae Work 这类没有 CLI 的 Agent 怎么接入？**

先用 `hek init --direct --yes` 写入项目控制面，再运行 `hek handoff --agent workbuddy` 或 `hek handoff --agent trae-work`。在对应桌面 Agent 中打开项目，复制 handoff 输出的提示词即可。框架依赖项目内的 `AGENTS.md`、`CLAUDE.md`、`agent-policy.yaml`、`ai.json` 和 `AI.md`，不依赖厂商私有插件或猜测性的启动命令。

**问：能不能一句话直接接入？**

可以，但仍必须让 Agent 先给只读计划。例如：“请接入当前项目，先识别状态并给出计划，确认后执行。”

**问：我只想要最小接入？**

在第一条消息中明确“使用 Tier 1，只安装核心控制面（含 agent-policy.yaml 引用的生产策略脚手架）；暂不安装 Fitness/经验记忆模板”。其余确认和校验流程不变。

**问：旧文件什么时候删？**

接入阶段不删。等增量更新校验完成后，再发起单独的清理变更，列出每个删除项、替代入口、回滚方式并重新确认。

**问：Agent 找不到 Kit 路径怎么办？**

提供 Kit 的绝对路径，例如 `/path/to/harness-engineering-kit`。Agent 不应自行从网络下载脚本。
