# RAMER Agent Templates

可移植的 RAMER Agent 系统模板。复制到新项目，填占位符即可获得自动化 RAMER 能力。

## 文件清单

```
ramer/
├── README.md                    # 本文件
├── SKILL.md.template            # /ramer skill 入口定义
├── ramer-design.js.template     # 设计工作流 (READ → ANALYZE → MODEL)
└── ramer-implement.js.template  # 实现工作流 (EXECUTE → REVIEW)
```

## 迁移步骤

### 1. 拷贝模板

```bash
# 项目本地部署
mkdir -p .claude/skills/ramer .claude/workflows
cp docs/methodology/templates/ramer/SKILL.md.template .claude/skills/ramer/SKILL.md
cp docs/methodology/templates/ramer/ramer-design.js.template .claude/workflows/ramer-design.js
cp docs/methodology/templates/ramer/ramer-implement.js.template .claude/workflows/ramer-implement.js

# 全局部署（跨项目可用）
mkdir -p ~/.claude/skills/ramer ~/.claude/workflows
cp docs/methodology/templates/ramer/SKILL.md.template ~/.claude/skills/ramer/SKILL.md
cp docs/methodology/templates/ramer/ramer-design.js.template ~/.claude/workflows/ramer-design.js
cp docs/methodology/templates/ramer/ramer-implement.js.template ~/.claude/workflows/ramer-implement.js
```

### 2. 替换占位符

用 `grep -rn '{{' .claude/skills/ramer/ .claude/workflows/ramer-*` 列出所有占位符，按下表替换。

### 3. 验证

```bash
# 在项目中触发 RAMER
/ramer 新增一个简单的 CRUD 实体
```

## 占位符参考

### 路径与命令

| 占位符 | 出现位置 | 含义 | 示例 |
|--------|----------|------|------|
| `{{AI_CONTEXT_SCRIPT}}` | SKILL.md, ramer-design.js | 路径文档加载脚本 | `python3 ~/.codex/skills/myproject-guide/scripts/find_ai_context.py` |
| `{{FITNESS_COMMAND}}` | SKILL.md, ramer-implement.js | Fitness gate 命令 | `python3 docs/fitness/scripts/fitness.py --tier fast` |

### 持久层框架

| 占位符 | 出现位置 | 含义 | MyBatis-Plus 示例 | JPA 示例 |
|--------|----------|------|-------------------|----------|
| `{{ORM_ENTITY_BASE}}` | ramer-design.js, ramer-implement.js | 实体基类 | `TenantEntity` | (不需要) |
| `{{ORM_ID_STRATEGY}}` | ramer-design.js, ramer-implement.js | 主键策略注解 | `@TableId(type = ASSIGN_ID)` | `@Id @GeneratedValue` |
| `{{ORM_LOGIC_DELETE}}` | ramer-design.js, ramer-implement.js | 逻辑删除注解 | `@TableLogic` | `@SQLDelete` |
| `{{ORM_MAPPER_BASE}}` | ramer-design.js, ramer-implement.js | Mapper 基类签名 | `BaseMapperPlus<Entity, Vo>` | `JpaRepository<Entity, Long>` |
| `{{ORM_AUTO_MAPPER}}` | ramer-design.js, ramer-implement.js | Entity↔VO 映射 | `@AutoMapper(target = Entity.class)` | (手写或 MapStruct) |

### 安全框架

| 占位符 | 出现位置 | 含义 | Sa-Token 示例 | Spring Security 示例 |
|--------|----------|------|--------------|---------------------|
| `{{AUTH_FRAMEWORK}}` | SKILL.md, ramer-design.js, ramer-implement.js | 权限框架名 | `Sa-Token` | `Spring Security` |
| `{{AUTH_ANNOTATION}}` | ramer-design.js | 权限注解 | `@SaCheckPermission("xxx:list")` | `@PreAuthorize("hasRole('ADMIN')")` |

### 模块与包

| 占位符 | 出现位置 | 含义 | 示例 |
|--------|----------|------|------|
| `{{BASE_PACKAGE}}` | ramer-implement.js | 业务基础包路径 | `org.dromara.coil` |
| `{{INFRA_MODULE}}` | ramer-implement.js | 基础设施模块目录 | `ruoyi-common` |
| `{{SQL_MIGRATION_PATH}}` | ramer-design.js | SQL 迁移目录 | `script/sql/update/` |

### 上下文

| 占位符 | 出现位置 | 含义 |
|--------|----------|------|
| `{{DDD_REFERENCE_CONTEXT}}` | SKILL.md, ramer-design.js | 项目 DDD 参考实现说明。描述项目已有的 hexagonal-ddd 模块（如有），包含具体 aggregate/valueObject/port/adapter 的类名和路径。无 DDD 实践的项目可用通用描述替代。 |

### 不在模板中的项目特定内容

以下内容在模板中为通用 DDD 方法论描述，部署后可能需要根据项目调整：

- **包路径约定**：`org.dromara.coil.domain` 等具体包名在 agent prompt 中硬编码为通用 DDD 约定。如果项目有不同包结构，在 `CLAUDE.md` 中声明，Agent 会从中读取。
- **模块角色映射**：`coil-common` = domain 层、`coil-dal` = data-access 层等映射关系来自 CLAUDE.md 的模块依赖图。
- **特定 ORM 模式**：Entity Quartet（五件套）是 MyBatis-Plus 项目的特定模式。JPA 项目可能需要调整为 Entity + Repository + DTO 三件套。
