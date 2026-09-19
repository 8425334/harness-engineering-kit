## Context

当前 Kit 以一个 Git 仓为安装边界，OpenSpec 通过向上解析仓根管理本地 change。联邦方案增加多个平级 unit 的聚合视图，但不能把各 unit 的 spec、生命周期或任务进度提升到 workspace 层。实现目标和字段约束已经整理在 `docs/spec/workspace-federation.zh.md`。

当前源码仓刚完成 OpenSpec 本地初始化，尚未安装 `.hek/project/agent-policy.yaml`，因此治理附件不能在本仓伪造；Apply 前必须在有效 Harness policy 环境中补齐治理记录。

## Goals / Non-Goals

**Goals:**

- 保证每个参与 unit 独立持有自己的 OpenSpec change、spec、design、tasks、证据和归档结果。
- 通过 `related_changes` 建立可校验的跨 unit 引用，而不是建立中央 spec。
- 实现 identity、projection、契约图、spec 引用校验、嵌套/越界 guard 和 CLI wrapper。
- 保持单仓无 identity 的兼容路径，并用 triple fixture 验证 A/B/C 三工程三 spec。

**Non-Goals:**

- 不自动跨仓提交、创建 PR 或合并多个 unit 的 change。
- 不把 provider 的契约 spec 复制到 consumer 仓作为第二权威。
- 不在本 change 内实施具体业务工程的 API 或 UI 功能。

## Decisions

- **D1: Unit-local authority.** 每个参与 unit 使用自己的 OpenSpec change；spec 路径必须位于该 unit 的 change 目录内。
- **D2: Reference-only federation.** `governance.workspace.related_changes` 只保存 unit/change/spec 引用，provider 的直接变更由 `derived_from` 表示。
- **D3: No central spec.** projection 和 inventory 只提供派生视图；发现 workspace 根 spec 时 fail-closed。
- **D4: Two validation scopes.** unit 本地检查验证自身文件和外部引用格式；聚合 verify 在全量 checkout 后验证所有成员文件和路径归属。
- **D5: Ordered delivery.** 先实现 identity/projection 和结构 guard，再实现 related spec 校验、compat、CI 模板和全量验收。

## Risks / Trade-offs

- [Risk] 某个成员仓未 checkout 会让完整 federation verify blocked → [Mitigation] 本地 unit 检查允许只验证外部引用格式，聚合 verify 明确返回 `spec.missing`，不伪造通过。
- [Risk] 各 unit 的 change 生命周期不同步 → [Mitigation] 每个 unit 独立执行 OpenSpec gate，聚合结果只有在所有成员通过后才可宣称完成。
- [Risk] 现有嵌套仓被 I14 阻断 → [Mitigation] 提供仅限拆分迁移的一次性 waiver，并让 verify 持续保持 blocked。
- [Risk] Kit 源码仓缺少有效 policy，治理附件无法生成 → [Mitigation] 在 Apply 前补齐安装态 policy 和治理记录，禁止手工创建伪造 governance.json。
