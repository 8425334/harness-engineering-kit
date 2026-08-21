# RAMER Agent Templates

可移植的 RAMER Agent 系统模板。复制到新项目即可获得自动化 RAMER 能力。

## 文件清单

```
ramer/
├── README.md                    # 本文件
├── SKILL.md.template            # /ramer skill 入口定义（自包含，无需替换占位符）
├── ramer-design.js.template     # 可选：设计工作流 (READ → ANALYZE → MODEL) 拆分模板
└── ramer-implement.js.template  # 可选：实现工作流 (EXECUTE → REVIEW) 拆分模板
```

## 迁移步骤

### 1. 拷贝模板

```bash
# 项目本地部署
mkdir -p .claude/skills/ramer
cp docs/methodology/templates/ramer/SKILL.md.template .claude/skills/ramer/SKILL.md

# 全局部署（跨项目可用）
mkdir -p ~/.claude/skills/ramer
cp docs/methodology/templates/ramer/SKILL.md.template ~/.claude/skills/ramer/SKILL.md
```

`SKILL.md.template` 是**自包含**的：无需替换占位符，RAMER 循环会从项目 `CLAUDE.md` 自动检测持久层框架、安全框架、fitness gate 命令、模块包路径与 DDD 参考实现。

### 2. 可选：按项目微调

自动检测无法覆盖的约定，直接在项目 `CLAUDE.md` 中声明，RAMER 循环会读取：

- **包路径约定**：业务基础包、基础设施模块目录
- **模块角色映射**：哪个模块 = domain 层、哪个 = data-access 层
- **ORM 特有模式**：Entity Quartet（MyBatis-Plus）或 Entity + Repository + DTO（JPA）
- **DDD 参考实现模块**：含 port/、adapter/、domain/model/ 的既有模块

### 3. 可选：拆分设计/实现工作流

如需把 READ→ANALYZE→MODEL 与 EXECUTE→REVIEW 拆成独立 workflow 编排，可同时部署：

```bash
mkdir -p .claude/workflows
cp docs/methodology/templates/ramer/ramer-design.js.template .claude/workflows/ramer-design.js
cp docs/methodology/templates/ramer/ramer-implement.js.template .claude/workflows/ramer-implement.js
```

默认 `SKILL.md` 已内置完整循环，拆分模板仅在需要跨 Agent/跨阶段编排时使用。

### 4. 验证

```bash
# 在项目中触发 RAMER
/ramer 新增一个简单的 CRUD 实体
```

## 编码原则（内置）

模板内置不可协商的编码原则，RAMER 循环在 MODEL 与 REVIEW 阶段强制应用：

- **抽象优先**：契约先于实现，接口先于具体类
- **组合优于继承**：继承深度 ≤ 1，优先 DI + 组合
- **多态优于分支**：嵌套 `if/else` ≥ 2 层或 `switch` ≥ 3 分支 → 考虑 Strategy/Factory/Handler 模式
- **不可变优先**：Value Object 全 final 字段，无 setter
- **ACL 隔离**：Adapter 必须做反腐蚀映射，不泄露基础设施类型
