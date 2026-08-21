# Fitness Templates

可移植的 Fitness 框架模板。复制到新项目，填占位符即可获得与本项目等价的质量门禁能力。

## 文件清单

```
fitness/
├── README.md                              # 本文件
├── fitness.py.template                    # Fitness runner（跨平台，零依赖）
├── check_ai_json_sync.py.template         # AI.md ↔ ai.json 漂移检查
├── check_architecture_boundary.py.template # 架构边界基线检查
├── check_security_baseline.py.template    # Agent 危险配置扫描
├── check_sql_updates.py.template          # SQL 迁移位置检查
├── check_java_impl_size.py.template       # Java 实现类行数上限
├── check_java_parameter_limit.py.template # Java 参数对象门禁（positional args ≤ 3）
├── check_magic_values.py.template         # 魔法值禁用检查
├── check_manual_object_mapping.py.template # 禁止手写机械对象映射（强制映射器）
├── check_java_documentation_contract.py.template # Java 文档契约（类/方法/字段注释）
├── check_code_block_simple_class_names.py.template # 文档代码块全限定类名检查
├── check_mapper_inline_sql.py.template    # Mapper 内联 SQL 外置检查
├── check_mapper_xml_parity.py.template    # Mapper 接口方法 ↔ XML statement 一致性
├── check_req_governance.py.template       # 产品需求文档治理检查（规则文档需按项目自建）
├── JavaParameterScanner.java.template     # Java 21 Compiler Tree API callable 扫描器
├── test_*.py.template                     # 通用复杂门禁零依赖自测（6 个）
├── check_sdd_quality.py.template          # SDD 配置与 change 结构检查
├── check_permission_management.py.template # Controller 权限注解检查
├── check_test_coverage.py.template        # 测试文件存在性 + JaCoCo 覆盖率
├── check_ddd_compliance.py.template       # DDD 领域层纯度检查
├── check_debug_log_cleanup.py.template    # 调试日志清理检查
└── rules/                                 # 规则 markdown 模板（fitness.py 扫描这些文件）
    ├── architecture-boundary.md.template
    ├── backend-quality.md.template
    ├── ddd-compliance.md.template
    ├── debug-log-cleanup.md.template
    ├── docs-quality.md.template
    ├── security.md.template
    ├── sql-quality.md.template
    ├── sdd-quality.md.template
    ├── test-coverage.md.template
    ├── permission-management.md.template
    ├── frontend-quality.md.template
    ├── java-documentation.md.template
    ├── magic-values.md.template
    └── object-mapping.md.template
```

## 迁移步骤

### 1. 拷贝脚本

```bash
mkdir -p docs/fitness/scripts docs/fitness
cp docs/methodology/templates/fitness/fitness.py.template docs/fitness/scripts/fitness.py
cp docs/methodology/templates/fitness/check_*.py.template docs/fitness/scripts/
cp docs/methodology/templates/fitness/test_*.py.template docs/fitness/scripts/
cp docs/methodology/templates/fitness/JavaParameterScanner.java.template docs/fitness/scripts/
# 重命名：去掉 .template 后缀
cd docs/fitness/scripts && for f in *.template; do mv "$f" "${f%.template}"; done && cd -
chmod +x docs/fitness/scripts/fitness.py
```

### 2. 拷贝规则

```bash
mkdir -p docs/fitness
cp docs/methodology/templates/fitness/rules/*.md.template docs/fitness/
cd docs/fitness && for f in *.md.template; do mv "$f" "${f%.template}"; done && cd -
```

按需删除不适用的规则文件（例如 Java 项目删除 `frontend-quality.md`，非 Java 项目删除 `backend-quality.md`、`test-coverage.md`、`permission-management.md` 等基于 Java 的检查）。

### 3. 创建文档基础设施

```bash
# 规则手册和验证账本（docs-quality 规则要求这两个文件存在）
touch docs/fitness/README.md docs/fitness/verification-ledger.md
# Fitness 目录自身的 AI 入口（架构边界规则要求）
touch docs/fitness/AI.md docs/fitness/ai.json
```

### 4. 替换占位符

用 `grep -rn '{{' docs/fitness/` 列出所有占位符，按下表逐项替换。

### 5. 试运行

```bash
python3 docs/fitness/scripts/fitness.py --tier fast --dry-run   # 只打印命令
python3 docs/fitness/scripts/fitness.py --tier fast              # 实际执行
```

## 占位符参考

| 占位符 | 出现位置 | 含义 / 示例 |
|--------|----------|-------------|
| `{{AI_MD_CONVERTER}}` | check_ai_json_sync.py | AI.md → ai.json 转换脚本的相对路径，如 `scripts/ai_md_to_json.py`。该脚本依赖项目的 AI.md 标题约定，需自备。 |
| `{{INFRA_MODULE}}` | check_architecture_boundary.py / rules | 基础设施模块目录名，如 `ruoyi-common` / `common`。空串可禁用该检查。 |
| `{{INFRA_FORBIDDEN_PART}}` | check_architecture_boundary.py | 不应出现在基础设施模块中的业务包路径片段，如 `org/dromara/coil` 中的 `coil`。 |
| `{{APP_MODULE}}` | check_architecture_boundary.py | 应用/领域模块目录名，如 `coil-app` / `app`。空串可禁用该检查。 |
| `{{APP_FORBIDDEN_GLOB}}` | check_architecture_boundary.py | 应用模块下禁止的文件 glob，如 `*Controller.java`、`*View.java`。 |
| `{{EXTRA_EXCLUDED_DIRS}}` | check_security_baseline.py | 安全扫描排除目录（文档中可引用危险模式作为示例），如 `docs/ai-docs`。 |
| `{{SQL_UPDATE_PREFIX}}` | check_sql_updates.py / rules | SQL 迁移目录（带尾斜杠），如 `script/sql/update/`、`db/migrations/`。 |
| `{{MAX_IMPL_LINES}}` | check_java_impl_size.py / rules | Java 实现类有效逻辑行上限，如 `800`。 |
| `{{MAX_PARAMETERS}}` | check_java_parameter_limit.py / rules | Java 位置参数上限，如 `3`。 |
| `{{MAPPER_SOURCE_ROOTS}}` | check_mapper_inline_sql.py / check_mapper_xml_parity.py | 生产 Mapper 源码扫描根元组。 |
| `{{MAPPER_XML_ROOTS}}` | check_mapper_xml_parity.py | Mapper XML 扫描根元组。 |
| `{{MAPPER_XML_GLOB}}` | check_mapper_xml_parity.py | Mapper XML glob，如 `**/mapper/**/*.xml`。 |
| `{{ENTITY_BASE_CLASS}}` | rules/object-mapping.md | 持久化实体基类名，如 `BaseEntity`。 |
| `{{MAPPER_UTIL}}` | rules/object-mapping.md | 对象映射工具类，如 `MapstructUtils.convert`。 |
| `{{BACKEND_SOURCE_ROOT}}` | rules/object-mapping.md | 全量审计的后端源码根，如 `app/`、`src/main/java`。 |
| `{{CONTROLLER_ROOTS}}` | check_permission_management.py | Controller 扫描路径前缀元组。 |
| `{{EXCLUDED_CONTROLLER_PREFIXES}}` | check_permission_management.py | Controller 扫描排除前缀（demo 模块、openapi 适配器等）。 |
| `{{MAPPING_ANNOTATIONS}}` | check_permission_management.py | HTTP 路由注解元组（Spring：`@GetMapping` 等）。 |
| `{{ACCESS_ANNOTATIONS}}` | check_permission_management.py / rules | 访问控制注解元组（Sa-Token / Spring Security 等）。 |
| `{{PERMISSION_ANNOTATION}}` | check_permission_management.py / rules | 携带权限码字面量的注解，如 `@SaCheckPermission`、`@PreAuthorize`。 |
| `{{SQL_CATALOG_ROOT}}` | check_permission_management.py / rules | 权限码 SQL 种子脚本根目录，如 `script/sql`。 |
| `{{COVERAGE_THRESHOLD}}` | check_test_coverage.py / rules | 行覆盖率阈值（整数），如 `65`。 |
| `{{BUSINESS_MODULE_PREFIXES}}` | check_test_coverage.py | 业务模块路径前缀元组。 |
| `{{BUSINESS_JACOCO_PACKAGES}}` | check_test_coverage.py | JaCoCo 报告中的业务包前缀元组。 |
| `{{BUSINESS_MODULE_PATHS}}` | check_test_coverage.py | 用于按模块汇总覆盖率的模块路径元组。 |
| `{{TEST_REQUIRED_SUFFIXES}}` | check_test_coverage.py | 需要测试文件的生产类后缀元组。 |
| `{{EXCLUDED_SUFFIXES}}` | check_test_coverage.py | 免测试文件要求的生产类后缀元组。 |
| `{{EXCLUDED_PATH_KEYWORDS}}` | check_test_coverage.py / check_debug_log_cleanup.py | 免测试文件要求 / 调试日志检查豁免的路径关键字元组。两个脚本各自维护一份。 |
| `{{DOMAIN_PATH_KEYWORDS}}` | check_ddd_compliance.py / rules | 标识领域层文件的路径关键字元组，如 `("/domain/", "/model/")`。 |
| `{{FORBIDDEN_INFRA_IMPORTS}}` | check_ddd_compliance.py / rules | 领域层禁止 import 的基础设施包前缀元组（Spring DI、Controller、JdbcTemplate、MyBatis Mapper 等）。 |
| `{{FORBIDDEN_INFRA_ANNOTATIONS}}` | check_ddd_compliance.py / rules | 领域层禁止使用的注解名元组（`@Service` / `@Component` / `@Mapper` 等）。 |
| `{{FORBIDDEN_DEBUG_PATTERNS}}` | check_debug_log_cleanup.py | 调试日志禁止模式元组，形式 `(suffix, regex, label)`，按文件后缀匹配。框架级 logger 不在内。 |
| `{{AI_CONTEXT_SCRIPT}}` | rules/docs-quality.md | 路径文档加载脚本路径，如 `$HOME/.codex/skills/<project>-guide/scripts/find_ai_context.py`。无该工具可删除对应 metric。 |
| `{{BACKEND_TEST_COMMAND}}` | rules/backend-quality.md | 后端测试命令，如 `mvn -pl app/business -am test -DskipTests=false`。 |
| `{{FRONTEND_DIR}}` | rules/frontend-quality.md | 前端项目目录，如 `web/`、`frontend/`。 |
| `{{TYPECHECK_COMMAND}}` | rules/frontend-quality.md | 前端类型检查命令，如 `pnpm typecheck`、`tsc --noEmit`。 |
| `{{BUILD_COMMAND}}` | rules/frontend-quality.md | 前端构建命令，如 `pnpm build`、`npm run build`。 |

## 不在模板中的项目特定检查

以下检查因含大量项目特定关键字或业务规则，未模板化。如需类似能力，参考本项目实现自行编写：

- `check_wx_api_boundary.py` — 小程序接口与设计稿双向同步检查。依赖项目特定的设计稿目录结构。

## 模板化脚本注意事项

- `check_java_parameter_limit.py.template` 依赖一个 Java 21 source-file-mode 扫描器（Compiler Tree API），把 callable 签名输出为 JSON；模板中该扫描器路径与三个 JSON 配置（config / baseline / exceptions）以 `{{...}}` 占位。未部署扫描器的项目可删除对应 metric。
- `test_*.py.template` 是门禁自身的可执行契约。部署某个复杂检查器时应同时部署其自测，并在对应 rule 中注册为 fast hard gate；自测失败说明门禁不可被信任，不能仅关闭自测继续交付。
- `check_req_governance.py.template` 的 REQ 总数、状态分布、owner 词表和特殊 sequence 均属项目契约，因此其 selftest 也必须由项目按自身基线编写，不能复用某个示例项目的 fixture。
- `check_java_documentation_contract.py.template` 中如需收紧，可按项目术语补充状态流转关键字；默认实现已通用化。
- `check_req_governance.py.template` 治理的是「产品需求文档 → 基线 → 索引 → 交付证据」的文档契约；各项路径、REQ 总数/状态分布、当前基线版本、owner 词表均为 `{{...}}` 占位。**该维度没有配套的规则文档模板**——具体 REQ 编号、基线语义与索引结构属项目特有，需按项目自建 `req-governance.md` 规则文件并在其中声明 `req_governance_checks` metric。
