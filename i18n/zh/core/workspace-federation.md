# 工作区联邦

多个相互独立的 Git unit 协同工作，不引入中心仓。任何共享事实都住在它所描述的东西旁边，
组级视图按需实时投影，而不是落盘成第二权威。

## 模型

| 概念 | 归属位置 | 是否提交 | 生命周期 |
| --- | --- | --- | --- |
| unit 身份与契约边 | 各 unit 的 `.hek/project/identity.yaml` | 是 | 与代码同 PR 演进 |
| 命令、权限、上下文 | 各 unit 的 `.hek/project/agent-policy.yaml` | 是 | 现状不变 |
| unit spec 与 change | 各 unit 的 `openspec/changes/<change-id>/` | 是 | 由该 unit 独立提案、审批、实现、归档 |
| federation change set 引用 | 各 unit 的 `governance.json.workspace` | 是 | 只引用，不承载 spec 内容 |
| 契约产物 | `identity.publishes[].artifact` 指向的位置 | 是 | 随发布打 tag |
| 组级投影 | `.hek/state/workspace-projection.json`（缓存） | 否 | 按内容 digest 失效 |
| 权威判定 | CI 运行结果 | 否 | 每次重新计算 |

unit 指一个可独立构建、独立验证、独立交付的 Git 仓；federation change set 指同一次
跨 unit 变更中各 unit 本地 change 的集合，只保存引用关系。

## 不变量

1. 每个参与 unit 各自拥有一个 OpenSpec change 和至少一份本地 `specs/**/*.md`。
   A、B、C 三个工程参与时必须存在三份本地 spec，禁止合并成 workspace spec。
2. workspace 根不得出现 `openspec/changes/`、`specs/` 或 `workspace-spec.md`。
   投影可以报告 spec 诊断，但不得承载 spec 内容。
3. identity 必须机器校验通过：schema、id 正则、URL 形态、artifact/snapshot 路径、
   semver range 以及 Git tracking。
4. `harness_root` 必须等于该 unit 的 Git 仓根，且含 `.hek/VERSION` 与
   `agent-policy.yaml`。
5. 禁止工程级嵌套：任一 unit 的仓根不得位于另一 unit 仓根之内；写入目标必须属于
   拥有该会话的仓。
6. 每个 `consumes[].contract` 恰由一个可见 unit 发布，其 `repo_url` 与声明的
   `provider_repo` 一致；契约图必须无环。
7. 同一 `workspace_id` 内所有 unit 的 Kit 版本一致。
8. 单仓无 `identity.yaml` 时保持联邦逻辑关闭；结构边界门禁不关闭。

## 命令

| 命令 | 作用 |
| --- | --- |
| `hek workspace discover [--root <dir>]... [--depth N] [--json]` | 聚合投影 |
| `hek workspace verify [--root <dir>]... [--json]` | 校验不变量，blocked 时退出码 2 |
| `hek workspace context <path> [--json]` | 回答路径归属、应加载上下文与 `input_bytes` |
| `hek workspace exec <unit> -- <cmd...>` | 在 unit 根启动命令并注入 `HEK_UNIT`/`HEK_WORKSPACE` |
| `hek workspace guard --path <path> [--session-root <dir>] [--json]` | 写入前门禁，退出码 2 即禁止编码 |
| `hek workspace compat --contract <id> [--json]` | 消费者侧兼容证据 |
| `hek workspace graph [--json]` | 契约图邻接表 |
| `hek workspace run <unit>\|all <fast_test\|test\|build\|fitness>` | 本地聚合执行 |
| `hek workspace pin [--version X]` | 记录并校验 Kit 版本 pin |

退出码与 Kit 其余部分一致：`0` 通过，`2` blocked。

## 工作准则

- 每个 unit 仓根开一个 Agent 会话。需要用 `--add-dir` 或等价只读范围时，只用于读契约，
  不用于改其他 unit。
- 责任方向等于依赖方向：消费者负责验证它依赖的契约，因此不需要中心仓或注册中心。
- 跨 unit 的契约、证据、派发路径一律使用
  `{"unit": "<unit_id>", "path": "<unit 仓相对路径>"}`；`identity.yaml` 内的路径天然
  以自身 unit 为作用域。
- 跨 unit 任务的常驻上下文是 coordinator 的根上下文加契约 snapshot，不得挂载其他
  unit 的 `AI.md` 链。
- 结构嵌套在任何写入前被阻断。唯一例外是绑定变更摘要与截止时间、经外部人工审批的
  一次性豁免，位于 `.hek/state/waivers/nested-<id>.json`。豁免期内 guard 返回
  `nesting.waived` 放行迁移，但 `verify` 仍报 blocked，直到结构真正拆分。
- 目录名（`docs/methodology`、`docs/sdd`）不能证明安装归属。只有 `.hek/VERSION`，或同时
  存在 `docs/methodology/scripts/` 与 `docs/methodology/core/` 且版本属于已发布集合，
  才算证据。

## 诊断码

`workspace.mixed`、`identity.missing`、`identity.schema`、`identity.duplicate`、
`identity.untracked`、`unit.nested`、`unit.no-harness`、`contract.orphan`
（provider 未 clone 为 `warning`，可见但未发布为 `blocked`）、
`contract.provider-mismatch`、`contract.duplicate-provider`、`contract.cycle`、
`kit.version-mismatch`、`spec.missing`、`spec.reference`、`spec.duplicate`。
guard 另产出 `nested.detected`、`boundary.cross-repo`、`harness.mismatch`、
`legacy.unverified`（warning）、`nesting.waived`（info）。
