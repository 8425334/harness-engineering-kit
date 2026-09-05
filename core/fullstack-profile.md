# Fullstack Engineering Profile

Fullstack work uses one change, one behavior contract, one approval, and one final evidence set. It is not the old dual-command workflow.

Design must define versioning, nullability, validation, errors, authorization, idempotency, retry/timeouts, timezone/precision, observability, generated types, and ownership across the API boundary. Backend Model and frontend Decompose are sections of the same `design.md`.

Parallel agents are an optional execution mechanism, never a lifecycle. Design records backend, frontend, generated-contract, and integration work in the shared `task-plan.json` DAG. Workers may start only after approval, must use isolated or non-overlapping scopes, and must return evidence to one coordinator. Sequential execution follows the identical graph, contract, and gates. Review verifies field, enum, error, permission, route, and consumer alignment plus both project gate sets.
