## 0. Governance Prerequisite

- [ ] 0.1 在具备有效 `.hek/project/agent-policy.yaml` 的 Harness 环境中为 `workspace-federation-refactor` 创建 `governance.json`，校验 `python scripts/check_change_workspace.py --root <project-root>` 通过；当前源码仓缺少该 policy，未满足前不得进入 Apply。

> 0.1 仍未满足：本源码仓没有安装态 `.hek/` policy，禁止伪造 `governance.json`。实现已完成并验证，但本 change 在此之前不得进入 Apply/Archive。

## 1. Requirements and Contract Baseline

- [x] 1.1 将 `docs/spec/workspace-federation.zh.md` 作为需求基线，核对 identity、projection、I1-I15、三工程三 spec 和禁止中央 spec 规则；验证 `openspec validate workspace-federation-refactor --strict` 能识别 proposal/spec/design/tasks 依赖。
- [x] 1.2 固化 `.hek/project/identity.yaml`、`governance.workspace.related_changes`、projection 和诊断码的字段集合；为每个未知键、错误 unit/change/spec 路径编写失败断言。

## 2. Per-Unit Specs and Change References

- [x] 2.1 实现本地 change/spec 归属校验：每个参与 unit 只有一个 related change 引用，至少有一份本地 spec，change_id 与目录名一致；验证 `triple-ok` 三个 unit 各有本地 spec。
- [x] 2.2 实现跨 unit related_changes 校验：外部引用只校验格式，本地聚合 verify 校验成员仓、spec 文件和 change 目录归属；验证缺失成员返回 `spec.missing`，错误引用返回 `spec.reference`。
- [x] 2.3 实现 workspace 根中央 spec 拦截；验证存在 `workspace-spec.md`、根 `specs/` 或根 `openspec/changes/` 时退出码为 2。

## 3. Identity, Projection and Contract Graph

- [x] 3.1 实现 `check_identity.py` 和 identity 模板，覆盖 `unit_kind`、URL、artifact/snapshot、顶层键集合和 Git tracking；验证 `pair-ok` 通过、`untracked-identity` blocked。
- [x] 3.2 实现 discover projection、root_index、workspace.mixed、unit 重复和 digest 失效；验证 layout-independent digest、版本/tracking 变化失效和混合 workspace blocked。
- [x] 3.3 实现 contract provider/consumer 图、provider URL 匹配、orphan 分级、cycle 和 kit version 校验；验证 `pair-orphan` blocked、`pair-uncloned` warning、`cycle` 和 `version-mismatch` blocked。

## 4. Guard and Context Boundaries

- [x] 4.1 实现 Git root、harness root、嵌套仓和跨仓 session-root 检测；验证 `nested`、`nested-no-identity` 和 cross-repo guard 均返回退出码 2。
- [x] 4.2 实现 `workspace context` 的 unit_id/cross_unit 输出与 `MAX_INPUT_BYTES` 门禁；验证跨 unit 不加载无关 L1，超预算返回 blocked。
- [x] 4.3 将 guard 接入 engineering Skill、写操作 hook、agent policy writable_paths 和 unit CI；验证 guard blocked 时 Apply 不得开始。

## 5. CLI, Compatibility and Delivery

- [x] 5.1 实现 Python `workspace_ctl.py` 的 discover/verify/context/exec/guard/compat/graph/run/pin 子命令和退出码；验证 P0 命令清单及 JSON 输出。
- [x] 5.2 实现 Node wrapper 的 workspace 子命令、位置参数、重复 `--root`、`--` 透传和 `HEK_SESSION_ROOT` 注入；运行 Node CLI 测试并核对 Python 入口结果一致。
- [x] 5.3 实现 compat、contract pin、consumer CI、governance.workspace 校验和 evidence 输出；验证 provider 版本变化时 consumer compat 退出码 2，更新 snapshot 后退出码 0。
- [x] 5.4 更新 templates、README、版本迁移和 `.gitignore`，确保 `VERSION`、`package.json` 与 migration manifest 一致；运行现有 onboarding/layout 测试。

## 6. Integration Verification

- [x] 6.1 构造 `single`、`pair-ok`、`triple-ok`、nested、orphan、cycle、version-mismatch 和 untracked fixtures；运行 Python/Node 全量测试。
- [x] 6.2 在 `triple-ok` 执行 `hek workspace verify --json`，确认三个本地 change、三份 spec、完整 related_changes 和无 workspace spec；记录 JSON 结果作为验证证据。
- [x] 6.3 执行 `openspec validate workspace-federation-refactor --strict`、现有 `npm test` 和文档 diff 检查；未通过项必须在 Apply 前解决。
