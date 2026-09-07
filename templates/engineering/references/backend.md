# Backend Profile

Read the applicable project instructions first, then `docs/methodology/core/backend-profile.md` and, for domain-heavy work, `docs/methodology/core/ddd-modeling.md`.

During Design, follow `docs/methodology/core/design-review.md`. Use Model to define contracts, invariants, ownership, dependencies, persistence boundaries, compatibility, and implementation order. The topology and runtime-flow views must expose ports/adapters, trust boundaries, authorization, transaction/concurrency scope, schema evolution, idempotency, failure handling, and observability when applicable. During Apply, perform only scoped drift checks before implementation. Run the backend commands declared in `docs/methodology/agent-policy.yaml`; do not invent framework conventions or commands.

Required review evidence is selected by actual risk: contract tests for public APIs, migration rehearsal for schema changes, negative tests for authorization/data changes, and concurrency or performance evidence when relevant.
