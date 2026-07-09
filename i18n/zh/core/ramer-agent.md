# RAMER Agent 自动化

RAMER 循环从手工流程进化为自主 Agent 编排系统——Skill 作入口，Workflow 串联阶段，Agent 执行具体任务，人工仅在 MODEL→EXECUTE 边界做一次确认。

## 通用原则

### 从手工 RAMER 到 Agent RAMER

传统 RAMER 的五个阶段由开发者手动推进，每一步都需要人做决策和上下文切换：

```
手工: 👤 READ → 👤 ANALYZE → 👤 MODEL → 👤 EXECUTE → 👤 REVIEW
```

Agent 化后，除了 MODEL→EXECUTE 的确认点，其余阶段由 Agent 自主完成：

```
Agent: 🤖 READ → 🤖 ANALYZE → 🤖 MODEL → 👤 确认 → 🤖🤖🤖 EXECUTE → 🤖 REVIEW
```

**为什么保留人在 MODEL→EXECUTE 的确认点？** 因为 MODEL 是"决策点"——接口设计、聚合边界、依赖方向一旦确定，后续代码全部据此生成。这是唯一需要人做价值判断的环节。其余阶段（读文档、列影响、写代码、跑门禁）都是机械性工作，Agent 可以比人更快更准。

### 架构自适应

Agent RAMER 的关键创新：**不假设所有需求都是一种架构风格**。ANALYZE 阶段 Agent 根据需求复杂度自动选择：

| 信号 | 风格 | 产出契约 |
|------|------|---------|
| 简单 CRUD，无业务不变量 | **crud** | Entity Quartet (Entity/VO/BO/Mapper/XML) |
| 复杂业务规则、状态机、不变量 | **ddd** | Aggregate + ValueObject + DomainService + Port + Adapter |
| 多外部系统编排、已有 port/adapter 模式 | **hexagonal** | Port + Adapter + ApplicationService |
| 混合场景 | **hybrid** | 组合 CRUD + DDD |

**关键约束**：若目标区域已有 port/adapter/domain/model 结构，Agent 必须延续 hexagonal 模式，不能退回传统分层。

### 系统架构

```
/ramer <需求>
     │
     ▼
┌─ Skill (SKILL.md) ─────────────────────────────┐
│ 编排层：串联 Design → 确认 → Implement          │
└────────────────────┬───────────────────────────┘
                     │
     ┌───────────────┴───────────────┐
     ▼                               ▼
┌─ Workflow: ramer-design ──┐  ┌─ Workflow: ramer-implement ──┐
│ READ Agent                │  │ EXECUTE Agents (并行)         │
│   → 跑 find_ai_context.py │  │   → 按 layer 规则写文件       │
│   → 检测架构风格          │  │   domain: 零框架 import       │
│   → 输出: 上下文摘要      │  │   application: 注入 port      │
│        ↓                  │  │   infrastructure: ACL 映射    │
│ ANALYZE Agent             │  │   interface: Sa-Token 权限    │
│   → 架构决策树            │  │        ↓                      │
│   → 限界上下文定义        │  │ REVIEW Agent                 │
│   → 输出: 影响分析        │  │   → fitness gate             │
│        ↓                  │  │   → DDD 依赖反转检查         │
│ MODEL Agent               │  │   → 三向一致性检查           │
│   → DDD 契约或 CRUD 契约  │  │   → 输出: 通过/失败 + 修复  │
│   → 输出: 设计契约 (JSON) │  │                              │
└───────────────────────────┘  └──────────────────────────────┘
```

### 设计契约的结构化输出

MODEL Agent 产出的不是自由文本，而是 Schema 约束的结构化 JSON。这消除了"AI 说人话、人再翻译成代码"的信息损失：

```json
{
  "architecture": {
    "style": "ddd",
    "boundedContext": "driver-dispatch",
    "dependencyRule": "domain -> nothing; port -> domain; adapter -> port + infra; application -> domain + port"
  },
  "aggregates": [{
    "name": "DriverDispatchSession",
    "invariants": ["司机不可同时处于两个调度任务中"],
    "methods": [{"signature": "void assign(VehicleId id)", "enforcesInvariant": "司机状态=空闲"}]
  }],
  "valueObjects": [{
    "name": "DriverStatus",
    "wraps": "String",
    "selfEncapsulates": true
  }],
  "ports": [{
    "name": "DriverDispatchRepository",
    "portType": "repository",
    "rationale": "抽象调度聚合的持久化，隔离 MyBatis-Plus 实现细节"
  }],
  "adapters": [{
    "name": "MyBatisDriverDispatchRepositoryAdapter",
    "implements": "DriverDispatchRepository",
    "antiCorruptionLayer": "DriverDispatchTask (MyBatis Entity) -> DriverDispatchSession (Aggregate)"
  }],
  "applicationServices": [{
    "name": "DriverDispatchApplicationService",
    "useCases": ["assignDriver", "completeTask"],
    "portsInjected": ["DriverDispatchRepository", "NotificationGateway"],
    "domainServicesUsed": ["DriverDispatchDomainService"]
  }],
  "implementationPlan": [
    {"step": 1, "file": ".../domain/model/DriverDispatchSession.java", "layer": "domain", "dependsOn": []},
    {"step": 2, "file": ".../port/DriverDispatchRepository.java", "layer": "infrastructure", "dependsOn": [1]},
    {"step": 3, "file": ".../adapter/MyBatisDriverDispatchRepositoryAdapter.java", "layer": "infrastructure", "dependsOn": [2]}
  ]
}
```

### 每层的实现纪律

EXECUTE Agent 根据 `layer` 字段应用不同的实现规则：

| Layer | 规则 | 禁止 |
|-------|------|------|
| **domain** | 纯 Java，零框架 import | `@Service`, `@Component`, `@TableName`, `RedisTemplate` |
| **port** | 接口，方法签名只用 domain 类型 | 返回 `SysUserVo`/`PageResult` 等基础设施类型 |
| **adapter** | `@Component`，实现 port，ACL 映射 | 通过 port 接口泄漏基础设施类型 |
| **application** | `@Service`，注入 **port 接口**，发布事件 | 注入 adapter 类；包含业务规则 |
| **interface** | `@RestController`，每个端点 Sa-Token | 包含业务逻辑 |

### 质量保障

REVIEW Agent 运行两层检查：

**通用层**（fitness gate）：
- 架构边界（领域层不反向依赖基础设施层）
- 代码规模（单类 ≤ 800 逻辑行）
- 权限注解（每个 Controller 端点有 Sa-Token）
- Javadoc 覆盖（变更的 public 方法必须有）
- 调试日志清理（无 `System.out`/`console.log`）
- SQL 迁移位置（`script/sql/update/`）

**DDD 专项层**（仅在 ddd/hexagonal/hybrid 风格时）：
- **依赖反转**：domain 层零 Spring/MyBatis/Redis import
- **Port 注入审计**：Application Service 的 `@RequiredArgsConstructor` 字段全是 port 接口，无 adapter 类
- **ACL 文档**：每个 Adapter 有防腐层映射说明
- **Port 理由**：每个 Port 接口有存在理由的 Javadoc

### 技能部署

RAMER Agent 系统通过三个文件部署，可以按项目本地或全局使用：

```
.claude/                        # 项目本地
├── skills/ramer/SKILL.md      # 入口 skill
├── workflows/ramer-design.js  # 设计工作流
└── workflows/ramer-implement.js # 实现工作流

~/.claude/                      # 全局（跨项目可用）
├── skills/ramer/SKILL.md
├── workflows/ramer-design.js
└── workflows/ramer-implement.js
```

全局部署后 `/ramer` 在任何项目中可用。项目本地副本覆盖全局版本。

**模板**：可移植的 `.template` 版本位于 `docs/methodology/templates/ramer/`，包含占位符参考和迁移步骤。详见 `templates/ramer/README.md`。
