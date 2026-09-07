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
