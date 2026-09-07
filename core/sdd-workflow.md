# Spec-Driven Development

OpenSpec's configured schema is the single source of truth for proposal, specs,
design, and tasks artifacts. The repository's `harness-engineering` schema adds
implementation-ready design sections, developer confirmation, and exact task
verification without changing OpenSpec ownership.

- Propose creates `proposal.md`, delta specs, `design.md`, and `tasks.md`.
- Engineering reviews context impact and records external approval before Apply.
- Apply executes OpenSpec tasks and records governance execution evidence.
- Verify runs strict artifact validation, `openspec-verify-change`, and Engineering governance gates before Sync or Archive.

Use `openspec-update-change` when planning artifacts need reconciliation; never
restore a duplicate lifecycle or task-plan compatibility layer.
