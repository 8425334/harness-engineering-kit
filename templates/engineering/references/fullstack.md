# Fullstack Profile

Read both backend and frontend references plus `docs/methodology/core/fullstack-profile.md`.

The coordinator owns one shared behavior contract covering versioning, nullability, validation, errors, authorization, idempotency, retry/timeouts, timezone/precision, and observability. Follow `docs/methodology/core/design-review.md`; produce backend Model and frontend Decompose sections in one Design artifact. The topology must show both sides, shared/generated contracts, external dependencies, and ownership. Runtime flows must show the end-to-end success path and material error, permission, retry, and timeout paths.

Represent backend, frontend, generated-contract, and integration work as dependency-ordered OpenSpec tasks in `tasks.md`. Parallel execution is optional and belongs in `execution-evidence.json`; use isolated worktrees or non-overlapping file scopes. Before Review passes, verify request/response fields, enums, errors, permissions, routes, generated types or consumer tests, and both sides' project gates.
