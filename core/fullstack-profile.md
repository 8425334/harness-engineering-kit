# Fullstack Engineering Profile

Fullstack work uses one change, one behavior contract, one approval, and one final evidence set. It is not the old dual-command workflow.

Design follows [Implementation-Ready Design Review](design-review.md) and must define versioning, nullability, validation, errors, authorization, idempotency, retry/timeouts, timezone/precision, observability, generated types, and ownership across the API boundary. Backend Model and frontend Decompose are sections of the same `design.md`; its topology and runtime flows show both sides and the end-to-end contract.

Parallel agents are an optional execution mechanism, never a lifecycle. Design records backend, frontend, generated-contract, and integration work as dependency-ordered OpenSpec tasks in `tasks.md`. Workers may start only after approval, must use isolated or non-overlapping scopes, and must return evidence to one coordinator. Sequential execution records its fallback in `execution-evidence.json`. Review verifies field, enum, error, permission, route, and consumer alignment plus both project gate sets.
