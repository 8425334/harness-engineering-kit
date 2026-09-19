## Why

工作区联邦方案目前只有一份技术设计文档，尚未把多工程 spec 的归属、关联和执行边界落到 OpenSpec change。若 A、B、C 三个工程共同参与一次变更，却只建立一份 workspace spec，会丢失各工程的责任边界、独立审批和独立归档事实。

## What Changes

- 为每个参与联邦变更的 unit 建立独立 OpenSpec change 和本地 spec。
- 通过 `governance.workspace.related_changes` 引用各 unit 的 change 与 spec，不复制 spec 内容。
- 禁止 workspace 根建立中央 spec、中央 `openspec/changes/` 或合并后的 `workspace-spec.md`。
- 实现 identity、projection、契约图、嵌套/越界 guard、跨 unit spec 引用校验和对应 CLI。
- 保持无 identity 单仓的既有行为兼容，并将三工程三 spec 纳入聚合验证。

## Capabilities

### New Capabilities

- `workspace-federation`: 聚合独立 unit 的身份、契约关系和跨 unit change/spec 引用，并在写入前及 CI 阶段执行边界门禁。

### Modified Capabilities

- None. 当前 Kit 尚无已归档的 workspace federation capability。

## Impact

- 影响 `scripts/`、`bin/`、templates、测试夹具、README 和版本迁移文件。
- 新增 `.hek/project/identity.yaml`、projection、`governance.workspace.related_changes` 和跨 unit spec 引用契约。
- 改变工程级嵌套仓的写入行为；无 identity 的单仓保持 federation 逻辑关闭，但 I14 结构门禁仍生效。
- 当前 Kit 源码仓没有安装态 `.hek` policy，因此 governance 附件必须在具备有效 Harness policy 的环境中补齐后才能进入 Apply。
