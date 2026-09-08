# Spec-Driven Development

OpenSpec's configured schema is the single source of truth for proposal, specs,
design, and tasks artifacts. The repository's `harness-engineering` schema adds
implementation-ready design sections, developer confirmation, and exact task
verification without changing OpenSpec ownership.

- Propose creates `proposal.md`, delta specs, `design.md`, and `tasks.md`.
- Engineering reviews context impact and records external approval before Apply.
- Apply executes OpenSpec tasks and records governance execution evidence.
- Verify runs strict artifact validation, `openspec-verify-change`, and `fitness.py --stage review --change <id>` with a digest-bound JSON report before the Engineering REVIEW gate.
- Sync snapshots each canonical spec first (an empty snapshot represents a capability that did not yet exist), runs `openspec-sync-specs`, `openspec validate --specs`, and `fitness.py --stage sync --change <id>` before the Engineering SYNC gate.

Use `openspec-update-change` when planning artifacts need reconciliation; never
restore a duplicate lifecycle or task-plan compatibility layer.
