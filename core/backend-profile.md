# Backend Engineering Profile

This is a Design and verification specialization used by the unified `engineering` Skill, not a standalone workflow or command.

RAM belongs before implementation:

- **Read** during Explore: load authoritative policy, nearest path context, relevant code, tests, contracts, and history.
- **Analyze** during Explore/Spec: identify invariants, owners, trust boundaries, callers, compatibility, data migration, failure modes, and operational risk.
- **Model** during Design: follow [Implementation-Ready Design Review](design-review.md); choose domain boundaries, interfaces, persistence rules, authorization, idempotency, transaction/concurrency behavior, observability, and implementation order, and make them visible in topology, runtime flow, and responsibility views.

Apply consumes the approved model. Verify the actual risks with focused tests, compilation/build, architecture fitness, contract tests, migration rehearsal, and security or concurrency evidence when applicable. Commands come from `agent-policy.yaml`.
