# 工作区联邦模型技术方案（1.0.0）

本文档是 1.0.0 重构的唯一权威技术方案。目标读者是上下文已被清空、只拿到本文件与代码库的实施者或 Agent。文档内所有路径、字段名、常量、函数名均以当前代码库为准，不依赖任何外部对话。

实施分支：`dev-1.0.0`（基线 `main` @ e72095e，Kit `VERSION` = 0.6.0）。

## 0. 如何使用本文档

- 第 3 节的数据契约和第 4 节的不变量是**规范性内容**，字段名与约束不得自由发挥。
- 第 7 节是逐文件的改动清单，含函数签名；第 8 节是测试计划；第 10 节是分期与可执行验收。
- 第 12 节列出需要人工拍板的开放问题；未拍板前按"推荐默认值"实施。

术语：

| 术语 | 含义 |
| --- | --- |
| unit | 一个可独立构建、独立验证、独立交付的工程，等于一个 Git 仓 |
| identity | unit 在自身仓内的自描述文件 `.hek/project/identity.yaml` |
| workspace_id | 一组协作 unit 的稳定逻辑标识，**不是路径** |
| projection | 由 discover 实时聚合出的组级视图，不落盘为权威 |
| verdict | 由 CI 给出的权威判定，本地运行结果仅供参考 |
| contract | unit 对外发布或对内消费的机器可读接口产物（OpenAPI、proto、schema 等） |

## 1. 背景、目标与非目标

### 1.1 背景

当前 Kit 的安装边界是"一个 Git 仓根一份 harness"（`.hek/` + `openspec/` + 原生 root adapter），见 `scripts/layout.py` 的 `HEK` 布局。当多个独立工程需要协同（`client-api`、`backend-api`、`backend-ui`、`client-flutter-app` 平级）时，缺的是组级编排。

已否决的两条路线：

1. **中心清单 + 中心仓**：在 workspace 根维护一份手写 `workspace.yaml` 并为其单独建仓。否决理由：它复制了 unit 本就拥有的事实（身份、契约关系），会产生第二权威并必然滞后；且 `units[].path` 与本地 clone 布局耦合，不同开发者会解析出不同结果。
2. **工程级嵌套**：`backend-ui` 作为独立仓嵌在 `backend-api/` 目录内。否决理由：父仓 CI、测试命令、证据链都覆盖不到子仓，跨仓改动无法原子提交，且与 OpenSpec 的"向上解析仓根"假设冲突。

### 1.2 目标

- 多个独立工程之间可以协同，且**任何共享事实都有唯一权威位置**。
- 组级视图**不落盘**：由各 unit 自描述实时聚合，随 clone 布局无关。
- 权威判定来自 CI 的 verdict，而不是某台机器上的文件状态。
- 能机器校验的一致性全部定义成不变量（第 4 节），不依赖人的自觉。
- 现有单仓安装零改动可用（无 identity 时全部联邦逻辑关闭）。

### 1.3 非目标

- **不支持工程级嵌套**：unit 的仓根不允许位于另一个 unit 的仓根之内。
- 不引入中心仓、中心清单、注册中心（可选生成 inventory 见 5.8）。
- 不引入第二套生命周期：`openspec/` 仍是唯一变更载体，`governance.json` 只做扩展。
- 不做跨仓自动提交或自动开 PR。

**待确认项（见 12.1）**：单仓内部的目录层级与 module 路由（`ai.json` 的 `modules[].path` 指向仓内子目录）不属于"工程级嵌套"，本方案保留其现有能力。若 1.0.0 要求一并移除，需另行修订 §3.1 与 §4。

## 2. 概念模型

一句话原则：**共享事实必须住在它所描述的东西旁边；组级视图只做投影，不落盘。**

| 概念 | 归属位置 | 是否落盘 | 是否提交 | 生命周期 |
| --- | --- | --- | --- | --- |
| unit 身份与契约边 | 各 unit 仓内 `.hek/project/identity.yaml` | 是 | 是 | 与代码同 PR 演进 |
| 命令、权限、上下文配置 | 各 unit 仓内 `.hek/project/agent-policy.yaml` | 是 | 是 | 现状不变 |
| 契约产物 | 各 unit 仓内（由 identity 的 `artifact` 指向） | 是 | 是 | 随发布打 tag |
| 组级视图 projection | 本地缓存 `.hek/state/workspace-projection.json` | 是（缓存） | 否 | 按内容哈希失效 |
| 权威判定 verdict | CI 运行结果 | 否 | 否 | 每次 CI 重新计算 |
| 会话根 | 被改 unit 的仓根 | 否 | 否 | 每次会话 |

## 3. 数据契约

### 3.1 `.hek/project/identity.yaml`

每个 unit 仓内一份，随代码提交。**只放身份与契约边**；命令、权限、上下文配置一律留在 `agent-policy.yaml`，不在此复制（避免第二权威）。

```yaml
schema_version: 1
kind: harness-unit

workspace_id: coil-platform        # 同一 workspace 的所有 unit 取值必须一致
unit_id: backend-ui                # 在 workspace_id 内唯一
kind: frontend                     # backend | frontend | mobile | library | docs | infra
repo_url: git@example.com:coil/backend-ui.git   # 可选；消费者侧兼容校验需要
owner: team-web                    # 可选

publishes:
  - contract: backend-ui-static
    artifact: dist/manifest.json   # unit 仓相对路径，归一化 POSIX
    format: static-manifest        # openapi-3.1 | proto3 | graphql-sdl | json-schema | static-manifest | custom
    version_source: "file:dist/VERSION"        # openapi:info.version | file:<unit 相对路径>
    breaking_policy: additive-only             # additive-only | semver

consumes:
  - contract: backend-api-http
    provider_repo: git@example.com:coil/backend-api.git
    version: "^1.4.0"                          # semver range
    snapshot: .hek/project/contracts/backend-api-http.snapshot.json  # 可选，用于兼容比对
    verify: "hek workspace compat --contract backend-api-http"
```

字段约束（全部由 `scripts/check_identity.py` 机器校验）：

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `schema_version` | int | 是 | 必须为 `1` |
| `kind` | str | 是 | 必须为 `harness-unit` |
| `workspace_id` | str | 是 | 正则 `^[a-z0-9][a-z0-9-]{1,63}$`，不得含 `/` 或 `\` |
| `unit_id` | str | 是 | 同上正则；在同一 `workspace_id` 内唯一 |
| `kind` | str | 是 | 取值须在枚举内 |
| `repo_url` | str | 否 | 非空即须为可解析 URL |
| `owner` | str | 否 | 非占位符 |
| `publishes[].contract` | str | 是 | 同上正则 |
| `publishes[].artifact` | str | 是 | 归一化 POSIX、仓相对、不得逃逸、不得以 `/` 结尾 |
| `publishes[].format` | str | 是 | 枚举内 |
| `publishes[].version_source` | str | 是 | 形如 `<scheme>:<arg>`，`scheme ∈ {file, openapi}` |
| `publishes[].breaking_policy` | str | 否 | 默认 `additive-only` |
| `consumes[].contract` | str | 是 | 同上正则 |
| `consumes[].provider_repo` | str | 是 | 可解析 URL |
| `consumes[].version` | str | 是 | 合法 semver range |
| `consumes[].snapshot` | str | 否 | 归一化 POSIX、仓相对 |
| 顶层键集合 | — | — | 必须恰好为 `{schema_version, kind, workspace_id, unit_id, kind, repo_url, owner, publishes, consumes}` 中去掉可选键后的集合；未知键报错 |

### 3.2 projection（`hek workspace discover --json` 输出）

```json
{
  "schema_version": 1,
  "kind": "workspace-projection",
  "workspace_id": "coil-platform",
  "roots": ["/abs/path/a", "/abs/path/b"],
  "digest": "sha256:...",
  "units": [
    {"unit_id": "backend-api", "path": "backend-api", "harness_root": "backend-api",
     "kit_version": "1.0.0", "identity_sha256": "...", "tracked": true, "repo_url": "..."}
  ],
  "contracts": [
    {"contract": "backend-api-http", "provider": "backend-api", "consumers": ["backend-ui"],
     "version": "1.4.2", "artifact": "openapi.yaml", "format": "openapi-3.1",
     "breaking_policy": "additive-only"}
  ],
  "diagnostics": [
    {"level": "blocked", "code": "identity.missing", "unit_id": "client-api", "message": "..."}
  ]
}
```

`digest` 是所有 unit 的 `identity_sha256` 按 `unit_id` 排序后计算的内容哈希，用于缓存失效。

`diagnostics[].code` 取值（与第 4 节不变量一一对应）：`identity.missing`、`identity.schema`、`identity.duplicate`、`identity.untracked`、`unit.nested`、`unit.no-harness`、`contract.orphan`、`contract.duplicate-provider`、`contract.cycle`、`kit.version-mismatch`。

### 3.3 `governance.json` 的可选 `workspace` 段

顶层新增可选键 `workspace`。现有校验不会因它失败：`scripts/openspec_common.py` 的 `validate_orchestration()` 只比较 `record["orchestration"]` 子对象，`scripts/check_change_workspace.py` 不校验顶层键集合（实施前用一次 `rg "set\\(record\\)" scripts/` 复核）。

```json
{
  "workspace": {
    "workspace_id": "coil-platform",
    "unit_id": "backend-ui",
    "role": "consumer",
    "derived_from": "add-order-batch-export",
    "contracts": [
      {
        "contract": "backend-api-http",
        "provider": "backend-api",
        "from_version": "1.4.0",
        "to_version": "1.5.0",
        "breaking": false,
        "verification": ".hek/state/compat-backend-api-http.json"
      }
    ]
  }
}
```

约束：`role ∈ {provider, consumer, independent}`；`breaking` 为 `true` 时必须带 `derived_from`；`verification` 指向的证据文件必须存在（由门禁校验）。

## 4. 不变量

| # | 不变量 | 判定方式 | 失败后果 |
| --- | --- | --- | --- |
| I1 | `.hek/project/identity.yaml` 存在且 schema 合法 | `check_identity.py` | blocked |
| I2 | `workspace_id` / `unit_id` 符合正则且不含路径分隔符 | 正则校验 | blocked |
| I3 | `harness_root == git rev-parse --show-toplevel(unit root)`，且含 `.hek/VERSION` 与 `agent-policy.yaml` | `git` 推导 + 文件存在性 | blocked |
| I4 | 不存在工程级嵌套：任一 unit 的仓根不得位于另一 unit 仓根之内 | 仓根前缀比对 | blocked |
| I5 | 每个 `consumes[].contract` 恰好被一个可见 unit `publishes` | 图聚合；区分"未 clone"与"无人发布" | blocked / warning |
| I6 | 契约图无环 | DFS | blocked |
| I7 | 契约、证据、派发中的路径一律 unit-scoped，无裸相对路径 | 结构校验 + `unit_id` 存在性 | blocked |
| I8 | 同一 unit 的 `AI.md` 只存在于其自身 harness root（`.hek/context/**`） | 现有 `check_context_docs.py` 逻辑，不新增副本 | blocked |
| I9 | breaking 契约变更必须带 `breaking: true`、弃用窗口说明与消费者验证证据 | `governance.workspace` 校验 | blocked |
| I10 | 同一 `workspace_id` 内所有 unit 的 `.hek/VERSION` 一致 | projection 比对 | blocked |
| I11 | 单任务上下文 `input_bytes` 不超预算；跨工程任务不得加载无关 unit 的 L1 | `check_context_budget` | blocked |
| I12 | `identity.yaml` 必须被 Git 跟踪 | `git ls-files --error-unmatch` | blocked |
| I13 | 消费者引用的 provider 版本必须可寻址（tag 存在）且与声明一致 | 消费者 CI 拉取校验 | blocked |

单仓兼容：仓内不存在 `identity.yaml` 时，I1–I7、I9–I13 全部跳过，行为与 0.6.0 完全一致。

## 5. 关键流程

### 5.1 discover 聚合算法

```text
输入：--root（可重复）、可选 --depth（默认 1）、--refresh

1. 根集合解析
   roots = --root 参数
   若未提供：从 cwd 向上查找，直到命中"包含 ≥2 个 Git 仓的目录"或工作区标记；均未命中 → 单 unit 模式，直接返回
2. 候选枚举
   对每个 root：root 自身（若为 Git 仓）+ 其下 depth 层内含 .git 的目录
3. 记录收集
   对每个候选：读取 `.hek/project/identity.yaml`；缺失 → 记为 `identity.missing` 诊断，跳过
   记录 unit_id、仓根（git rev-parse）、identity 内容 sha256、.hek/VERSION、是否被跟踪
4. 分组
   按 workspace_id 分组；出现多个 workspace_id 时全部返回并各自校验
5. 图构建
   publishes → provider 映射；重复 provider → `contract.duplicate-provider`
   consumes → 边；找不到 provider 且 provider_repo 不在可见集合 → `contract.orphan`（warning，可能只是未 clone）
   环检测 → `contract.cycle`
6. 不变量校验（I1–I7、I10、I12）
7. 输出 projection + 缓存
```

### 5.2 缓存与失效

- 位置：当前 unit 的 `.hek/state/workspace-projection.json`。
- 缓存键：projection `digest`。请求时重算 digest，与缓存不一致则重建。
- `--refresh` 强制重建。
- 该文件**不得提交**，见 §5.7 的 `.gitignore` 片段。

### 5.3 会话根与路径规则

1. 默认在 unit 仓根启动 Agent 会话，保持现有全部机制（adapter、`openspec/` 根解析、相对路径、policy、fitness）不变。
2. Codex 用 `codex -C <unit>`；Claude Code 在 unit 目录启动（实测只有 `--add-dir`，无换根参数）。统一入口 `hek workspace exec <unit> -- <cli>`。
3. 契约、证据、派发中的路径一律 `{"unit": "<unit_id>", "path": "<unit 仓相对路径>"}`（I7）。
4. 控制脚本的 root 判定改为三态：cwd 是 unit 根 / cwd 是 workspace 根（命中多个仓）/ 都不是。命中 workspace 根且未指定 unit 时**报错退出**，不得静默当作项目根。现状风险：`scripts/onboard.py:179 project_root()` 在非 Git 目录回落到 cwd，会把编排层当成 fresh 项目。
5. 不提交根 adapter。需要时由 `hek workspace discover` 现场生成到 stdout 或临时文件。

### 5.4 跨工程变更流程

责任方向 = 依赖方向：**消费者负责验证它依赖的契约**。provider 不需要知道消费者列表，因此不需要中心仓，也不需要注册中心。

```text
1. provider 在自己仓内开 change（openspec），修改契约，递增契约版本
2. provider 打 tag / 发布契约产物（版本可寻址）
3. consumer 在自己仓内开 change，更新 consumes.version 与 snapshot
4. consumer CI 跑 `hek workspace compat --contract <id>`，比对 provider 产物与本地 snapshot
5. consumer 的 governance.workspace 记录 derived_from = provider 的 change_id
6. 各自独立 archive
```

breaking 变更：provider 必须在 `publishes[].breaking_policy: semver` 下显式标注，并在 change 中给出弃用窗口；consumer 在窗口内可以继续按旧版本验证。I9 阻止"悄悄破坏"。

### 5.5 上下文预算

加载分层与硬预算（常量取自现有代码，勿改）：

| 层 | 内容 | 进入条件 | 预算 |
| --- | --- | --- | --- |
| L0 常驻 | 根 adapter、`agent-policy.yaml`、`profile.yaml`、`.hek/context/ai.json` | 每次任务 | 索引 ≤ 8192 字节（`MAX_INDEX_BYTES`），modules ≤ 50（`MAX_MODULES`） |
| L1 路径触发 | owning module 的 `AI.md` 与祖先链 | 目标路径前缀匹配 | 每份 ≤ 800 行 / 65536 字节 |
| L2 关键词触发 | `read_when` 命中的其他 module | 关键词精确命中 | 命中才追加 |
| L3 按需检索 | 契约 snapshot、历史 change、经验条目 | 跨工程或踩坑时 | 检索进入，收敛到具体文件 |

规则：

- workspace 层不持有任何上下文文档，不建第二份 `AI.md`。
- 跨工程任务的常驻上下文 = coordinator 的 L0/L1 + 契约 snapshot，不得挂载其他 unit 的 L1。
- 复用 `scripts/context_cache.py` 的 `input_bytes` 与 hit/miss/bypass 度量；长任务命中率沿用默认门槛 `0.995`。
- 禁止把 `rg`/`rglob` 式探索作为常规上下文获取手段；`hek workspace context <path>` 必须能确定性回答"该读什么"。

### 5.6 CI 模型

| 层 | 位置 | 内容 |
| --- | --- | --- |
| unit CI | 各 unit 仓 | `hek check`（既有）+ `check_identity.py`（I1、I2、I12） |
| 消费者兼容 CI | 各 consumer 仓 | 按 `consumes` 拉取 provider 版本，跑 `hek workspace compat`（I5、I9、I13） |
| 聚合预演（可选） | 任一 unit 仓的手动触发任务 | checkout 全量 unit 后 `hek workspace verify`（I3、I4、I6、I10、I11） |

不要求中心仓的 CI。新增 workflow 模板沿用 `.github/workflows/ci.yml` 的写法。

### 5.7 `.gitignore` 片段（写入各 unit 仓）

```gitignore
# Harness 本地缓存（不得提交）
.hek/state/workspace-projection.json
.hek/state/*.cache.json
```

`.hek/state/` 下的回执与证据（`onboarding.json`、`repair.json`、`compat-*.json`）仍需提交，用于审计，因此使用精确文件名而不是整目录忽略。

### 5.8 与 OpenSpec 的衔接

- `openspec/` 仍由各 unit 仓各自持有，跨工程变更由各 unit 各自开 change，通过 `governance.workspace.derived_from` 关联。
- `scripts/check_change_workspace.py` 的 `REQUIRED_SCHEMA = "harness-engineering"` 与 `.openspec.yaml` 校验不变。
- 不新增生命周期阶段，不新增调度器。

### 5.9 可选的生成式 inventory

当组织需要"不 checkout 全量仓也能回答谁消费谁"（API 目录、审计）时，可由 `hek workspace discover --json` 的产物发布为 artifact 或写入只读 registry。**该产物必须由工具生成，禁止人工编辑**；它不参与门禁判定（判定仍在 consumer CI）。

## 6. 工具面（CLI）

### 6.1 命令

| 命令 | 作用 | 阶段 |
| --- | --- | --- |
| `hek workspace discover [--root <dir>]... [--depth N] [--refresh] [--json]` | 聚合投影，供人读或机器消费 | P0 |
| `hek workspace verify [--root <dir>]... [--json]` | 校验 I1–I7、I10、I12 | P0 |
| `hek workspace context <path> [--json]` | 回答路径归属、应加载上下文、是否跨工程、预估字节数 | P0 |
| `hek workspace exec <unit> -- <cmd...>` | 切到 unit 根启动 CLI，注入 `HEK_UNIT` / `HEK_WORKSPACE` | P0 |
| `hek workspace compat --contract <id> [--json]` | 消费者侧兼容校验，产出 `.hek/state/compat-<id>.json` | P1 |
| `hek workspace graph [--json]` | 打印契约图的邻接表 | P1 |
| `hek workspace run <unit>|all <fast_test|test|build|fitness>` | 聚合执行（仅限独立结构） | P2 |
| `hek workspace pin [--version X]` | 记录 kit 版本 pin 并校验一致性（I10） | P2 |

退出码约定与现有脚本一致：`0` 通过，`2` blocked（`scripts/check_change_workspace.py` 已有先例）。

### 6.2 JS 入口改动点

`bin/harness-engineering-kit.js`：

- `VALUE_OPTIONS`（第 50 行）增加 `--root`、`--depth`、`--contract`、`--unit`。
- `parseArgs()`（第 119 行起）增加 `--` 终止符：其后所有 token 存入 `result.options.rest`，`exec` 子命令据此透传。
- `main()`（第 872 行起）在既有 if 链末增加 `if (parsed.command === 'workspace') return runWorkspace(parsed.options);`。
- `usage()` 增加 workspace 段落。
- `scripts/workspace_ctl.py` 通过既有的 `invoke()` 机制调用，保持 Python 实现为唯一逻辑源。

## 7. 代码改动清单

### 7.1 新增

| 文件 | 关键接口 |
| --- | --- |
| `scripts/workspace.py` | `load_identity(unit_root: Path) -> Identity`；`discover(roots: list[Path], depth: int = 1) -> Projection`；`validate_projection(projection) -> list[Diagnostic]`；`digest_units(units) -> str`；`unit_scoped_path(payload) -> tuple[str, str]`（解析并校验 I7） |
| `scripts/check_identity.py` | `validate(unit_root: Path) -> list[str]`；CLI `--root`，退出码 0/2 |
| `scripts/workspace_ctl.py` | `main(argv) -> int`；子命令 `discover/verify/context/exec/compat/graph/run/pin` |
| `templates/identity.yaml.template` | 占位符：`{{WORKSPACE_ID}}`、`{{UNIT_ID}}`、`{{UNIT_KIND}}`、`{{REPO_URL}}` |
| `templates/fitness/check_contract_pin.py.template` | 校验 `consumes` 的 snapshot 与声明版本一致（I13 的本地部分） |
| `templates/fitness/check_context_budget.py.template` | 校验单任务 `input_bytes` 与跨 unit 上下文引用（I11） |
| `templates/ci/workspace-compat.yml.template` | 消费者侧兼容校验 workflow |
| `core/workspace-federation.md`（及 `i18n/zh/core/` 对应文件） | 第 2、4、5 节的运行时摘要，供 `ai.json` 的 `entrypoints` 引用 |
| `tests/test_workspace.py`、`tests/test_workspace_ctl.py` | 见第 8 节 |
| `tests/fixtures/workspace/**` | 夹具：`single/`、`pair-ok/`、`pair-orphan/`、`nested/`、`version-mismatch/`、`untracked-identity/` |

### 7.2 修改

| 文件 | 改动点 | 风险 |
| --- | --- | --- |
| `scripts/layout.py` | 新增 `identity_rel()` 返回 `.hek/project/identity.yaml`、新增 `contracts_dir` 访问器 | 低，纯新增 |
| `scripts/onboard.py` | `--check` 末尾追加 identity 校验（缺失则跳过）；新增 `--unit-id` 用于生成 identity 草稿；`project_root()`（第 179 行）三态判定（§5.3 第 4 条） | 中，必须保证无 identity 时行为字节级一致 |
| `scripts/resolve_context.py` | 输出新增 `unit_id`、`cross_unit` 字段；跨 harness root 时 fail-closed 并提示改用 workspace change | 中，返回结构新增字段，调用方需同步 |
| `scripts/check_change_workspace.py` | 校验 `governance.workspace`：字段集合、`role` 枚举、`breaking` 与 `derived_from` 的联动、`verification` 文件存在性 | 中，旧 change 无该键时跳过 |
| `scripts/openspec_common.py` | 保持 `orchestration_contract()` 不变；新增 `workspace_contract()` 供校验复用 | 高，禁止改动现有严格比较逻辑 |
| `templates/agent-policy.yaml.template` | 增加可选 `workspace: {workspace_id, unit_id}` 引用（仅引用，不复制事实） | 低 |
| `templates/AGENTS.md.template` | 增加 1 行指向 `core/workspace-federation.md`；注意 `check_root_context.py` 的 `MAX_LINES = 34` | 中，超行即失败 |
| `tests/test_onboard.py` | 增补"无 identity 时零行为变化"的回归用例 | 低 |
| `docs/versioning.md`、`migrations/releases.json`、`VERSION` | 1.0.0 版本与迁移条目 | 中 |
| `README.md`、`README.zh.md` | CLI 清单增加 workspace 段落 | 低 |

### 7.3 不改动

- `scripts/check_context_docs.py`：现有 `ai.json` 校验规则（`MAX_INDEX_BYTES=8192`、`MAX_MODULES=50`、context 必须为 `.hek/context/<module_path>/AI.md`、必须含 `path: "."`）保持不变。联邦模型不引入第二份上下文文档。
- `scripts/context_cache.py`：`fingerprint()` / `record()` / `report()` / `benchmark()` 签名不变，仅被新门禁复用。
- `scripts/layout.py` 的 `HEK` / `LEGACY` 布局表：1.0.0 不改安装布局。

### 7.4 删除

- `docs/workspace-topology.zh.md`（已被本文档取代，且其中 T2/T3 嵌套内容与本方案冲突）。

## 8. 测试计划

### 8.1 夹具

| 夹具 | 构造 | 用途 |
| --- | --- | --- |
| `single/` | 一个 Git 仓 + `.hek/`，无 identity | 回归：联邦逻辑全关 |
| `pair-ok/` | 两个平级仓，identity 互相对齐 | 通过用例 |
| `pair-orphan/` | consumer 声明了无人 publishes 的 contract | I5 |
| `nested/` | unit B 的仓根位于 unit A 仓根内 | I4 |
| `version-mismatch/` | 两仓 `.hek/VERSION` 不同 | I10 |
| `untracked-identity/` | identity 存在但未 `git add` | I12 |
| `cycle/` | 两个 unit 互相 consumes | I6 |

夹具通过 `git init` + 最小 `.hek/` 骨架在临时目录构造，不提交二进制。

### 8.2 用例

| 用例 | 断言 |
| --- | --- |
| `test_discover_layout_independent` | 同一组 unit 放在两种不同目录结构下，`digest` 相同 |
| `test_discover_single_unit_skips_federation` | `single/` 无诊断，输出为空 workspace |
| `test_verify_nested_blocked` | `nested/` 报 `unit.nested` 且退出码 2 |
| `test_verify_orphan_contract` | `pair-orphan/` 报 `contract.orphan` |
| `test_verify_cycle_blocked` | `cycle/` 报 `contract.cycle` |
| `test_verify_version_mismatch` | `version-mismatch/` 报 `kit.version-mismatch` |
| `test_verify_untracked_identity` | `untracked-identity/` 报 `identity.untracked` |
| `test_unit_scoped_path_rejects_bare` | 裸相对路径被 I7 拒绝 |
| `test_exec_sets_env_and_cwd` | `exec` 注入 `HEK_UNIT`/`HEK_WORKSPACE` 且 cwd 为 unit 根 |
| `test_three_state_root_detection` | workspace 根调用未指定 unit 时报错退出，不判定 fresh |
| `test_context_budget_exceeded` | 超预算返回 blocked |
| `test_governance_workspace_optional` | 无 `workspace` 键的旧 change 仍然通过 |
| `test_backward_compatible_onboard` | 无 identity 时 onboard plan/check 输出与基线一致 |

### 8.3 端到端

1. `pair-ok/` 上跑 `hek workspace discover --json` → projection 含两个 unit、一条契约边。
2. 修改 provider 契约版本，consumer 未更新 → consumer 的 `compat` 退出码 2。
3. consumer 更新 `consumes.version` 与 snapshot 后 → `compat` 退出码 0，产出证据文件。
4. 在 consumer 仓跑 `hek check` → 既有校验与新 identity 校验同时通过。

## 9. 迁移

| 从 | 到 | 动作 |
| --- | --- | --- |
| 0.6.0 单仓安装 | 1.0.0 单仓 | 无需动作；identity 缺失即跳过联邦逻辑 |
| 多个平级独立仓 | 联邦 | 各仓新增 `.hek/project/identity.yaml`（`hek onboard --unit-id <id>` 生成草稿），补 `.gitignore` 片段 |
| 工程级嵌套（异仓） | 联邦 | 子仓移出父仓目录成为平级仓，各自装 harness，补 identity；父仓从权限中移除子仓路径 |
| 中心 `workspace.yaml` 草案 | 联邦 | 删除中心文件；把其中的 unit 与契约信息分别落到各 unit 的 identity |
| vendored 完整 kit | 版本 pin | 保留 `.hek/project`、`.hek/context`、`.hek/fitness`；`.hek/kit` 由 pin 版本获取。离线要求高时可保留 vendored 拷贝，但必须由 pin 生成并校验 digest |

`VERSION` 升到 `1.0.0`，`migrations/releases.json` 增加 1.0.0 条目，说明"工程级嵌套不再支持"。版本比较逻辑（`docs/versioning.md`：升级/降级/漂移）不变。

## 10. 分期与验收

### P0：自描述与聚合

交付：`workspace.py`、`check_identity.py`、`workspace_ctl.py` 的 `discover/verify/context/exec`、`identity.yaml.template`、`.gitignore` 片段、`core/workspace-federation.md`、夹具与 8.2 中 P0 相关用例。

验收命令与期望：

```bash
python scripts/check_identity.py --root tests/fixtures/workspace/pair-ok/backend-api        # 退出码 0
python scripts/workspace_ctl.py discover --root tests/fixtures/workspace/pair-ok --json     # 含 2 units、1 contract
python scripts/workspace_ctl.py verify --root tests/fixtures/workspace/nested --json        # 退出码 2，code=unit.nested
python scripts/workspace_ctl.py context tests/fixtures/workspace/pair-ok/backend-api/src/x.java --json   # 含 unit_id、cross_unit=false
python scripts/workspace_ctl.py exec backend-api -- python -c "import os;print(os.getcwd())"            # 输出 unit 根
```

P0 判定标准：单仓夹具全部通过且既有测试（`tests/test_onboard.py`、`tests/test_layout.py`）无回归。

### P1：跨工程闭环

交付：`compat` 与 `graph`、`check_contract_pin`、`workspace.compat` 证据、consumer CI 模板、`governance.workspace` 校验、`resolve_context` 的 `unit_id`/`cross_unit` 输出、`check_context_budget`。

验收：8.3 端到端四步全部通过；`pair-orphan`、`cycle`、`version-mismatch` 三个夹具在 `verify` 下退出码 2。

### P2：规模化与治理

交付：`run`、`pin`、workspace 级 CI 模板、可选的生成式 inventory、`hek workspace status`（harness 版本与契约滞后报告）。

验收：`status` 必须能指出哪个 unit 未接 harness、哪个 consumer 落后于 provider 版本。

## 11. 风险与反模式

| 风险/反模式 | 后果 | 对策 |
| --- | --- | --- |
| 让每人在本地跑 `hek init` | 编排层随人漂移 | 安装是一次性提交动作；`.hek/` 随 clone 分发 |
| identity 未提交 | 他人视角缺失该 unit | I12 |
| 手写中心清单 | 第二权威，必然滞后 | 只允许生成式 inventory，禁止参与门禁 |
| 允许工程级嵌套 | 父仓 CI 覆盖不到子仓 | I4 直接 blocked |
| 用 `--add-dir` 在一个会话里横跨多个 unit | 指令根与相对路径基准错乱 | 默认 unit 根开会话；`--add-dir` 仅用于读契约 |
| 把契约当文档写 | 体积膨胀、无法 diff | 契约只放机器可读产物，配 snapshot |
| 各 unit 的 kit 版本不一致 | 门禁时真时假 | I10 + `pin` |

## 12. 开放问题

12.1 **单仓内的子目录 module 是否保留**：本方案保留（那不是工程级嵌套）。若要求一并移除，需修订 §3.1 与 §4，并评估 `ai.json` 的 `modules[].path` 兼容性。推荐默认：保留。

12.2 **kit 分发形态**：推荐"pin 版本 + 按需获取"。若团队要求仓自包含或离线，改为"vendored + digest 校验"，代价是每个 unit 多一份 kit 拷贝。

12.3 **`compat` 的比对深度**：推荐先做结构级 diff（新增字段通过、删除/改类型 blocked），不引入运行时集成测试。若契约不含机器可读 schema，则降级为"人工审批 + 版本号校验"。

12.4 **CI 平台**：模板以 GitHub Actions 为默认（仓库现有 `.github/workflows/ci.yml`）。若实际使用其他平台，只改 `templates/ci/` 而不动门禁逻辑。
