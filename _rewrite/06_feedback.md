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
