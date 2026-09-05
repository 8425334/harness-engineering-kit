# Fullstack Profile

Read both backend and frontend references plus `docs/methodology/core/fullstack-profile.md`.

The coordinator owns one shared behavior contract covering versioning, nullability, validation, errors, authorization, idempotency, retry/timeouts, timezone/precision, and observability. Produce backend Model and frontend Decompose sections in one Design artifact.

Represent backend, frontend, generated-contract, and integration work in the shared `task-plan.json` DAG. Parallel execution is optional and depends on platform support. Use isolated worktrees or non-overlapping file scopes; sequential fallback retains the same graph and contract. Before Review passes, verify request/response fields, enums, errors, permissions, routes, generated types or consumer tests, and both sides' project gates.
