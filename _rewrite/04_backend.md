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
