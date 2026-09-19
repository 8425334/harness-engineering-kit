## Purpose

为多个平级 Git unit 提供不依赖中央仓的联邦协作能力，并确保每个参与工程的行为规格、变更生命周期和验证证据都由该工程自身持有。

## ADDED Requirements

### Requirement: Each participating unit owns an independent spec

每个参与 federation change set 的 unit MUST 在自身仓内创建一个独立 OpenSpec change，并在该 change 下至少拥有一份 `openspec/changes/<change-id>/specs/**/*.md`。当 A、B、C 三个 unit 都产生实现、配置、测试或契约变更时，系统 MUST 能定位到三份分别属于 A、B、C 的本地 spec；一个 unit 不得用其他 unit 的 spec 代替自己的实现规格。

#### Scenario: Three participating units create three local specs

- **WHEN** A、B、C 三个 unit 共同参与同一次 federation change set
- **THEN** A、B、C 各自拥有一个本地 OpenSpec change 和至少一份属于该 change 的 spec，且不存在 workspace 根 spec

### Requirement: Related changes reference local specs without copying authority

每个参与 unit 的 `governance.workspace.related_changes` MUST 包含本 unit 和其他参与 unit 的 `unit`、`change_id` 与 spec 路径引用。引用 MUST 指向对应 unit 的 change 目录；spec 内容的唯一权威 MUST 保持在所属 unit 仓内。

#### Scenario: Related changes are complete and aligned

- **WHEN** 聚合验证读取三个 unit 的 governance 引用
- **THEN** 每个 unit、change_id 和 spec 路径一一对应，三份 spec 均存在且没有重复 unit 或错误归属

### Requirement: Workspace must not own a central spec

workspace 根 MUST NOT 创建 `openspec/changes/`、`specs/` 或 `workspace-spec.md` 作为跨工程权威。workspace projection MAY 报告 spec 状态或诊断，但 MUST NOT 承载 spec 内容或替代任何 unit 的 OpenSpec 文件。

#### Scenario: Central spec is rejected

- **WHEN** 聚合验证发现 workspace 根存在中央 spec 或中央 OpenSpec change
- **THEN** 验证返回 blocked，并报告明确的 spec 归属错误

### Requirement: Federation validation is fail-closed

聚合 `verify` MUST 校验所有 related change 的 change_id、unit 归属、spec 路径和文件存在性。成员仓未 checkout、引用失效、change_id 不匹配或 spec 缺失 MUST 返回 blocked；单个无 identity 的 Git 仓在单仓模式下 MUST 保持既有 federation-disabled 行为。

#### Scenario: Missing member spec blocks the change set

- **WHEN** related_changes 引用了一个不可见或缺失的成员 spec
- **THEN** `verify` 返回退出码 2，并报告 `spec.missing` 或 `spec.reference`
