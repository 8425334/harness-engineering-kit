# Implementation-Ready Design Review

Design is a developer-facing approval packet, not a short list of internal thoughts. It must let a reviewer understand the proposed system, challenge material choices, and predict implementation and verification before any production code is changed.

## Required Design Packet

Use `templates/workflow/design.md.template` and answer every section from repository evidence. The packet must include:

1. a concise recommendation, scope, non-goals, constraints, and material assumptions;
2. current-state entry points, owners, dependencies, limitations, and evidence paths;
3. a target architecture and relationship-topology diagram showing boundaries and dependency direction;
4. a responsibility table naming what each component owns, depends on, and must not own;
5. runtime sequence or data-flow diagrams for the main path and materially different failure or asynchronous paths;
6. interface and data details including fields, types, nullability, validation, errors, versioning, persistence, and compatibility;
7. applicable security, permission, reliability, concurrency, observability, performance, UX, and accessibility behavior;
8. implementation order, migration or rollout, rollback, and explicit stop conditions;
9. numbered decisions with the chosen option, evidence-based reason, rejected alternatives, trade-offs, and consequences;
10. risk-to-verification traceability plus exact commands or evidence sources;
11. open questions and a numbered developer-confirmation checklist.

Do not omit a conditional concern silently. Write `Not applicable — <evidence-based reason>` when a topic such as persistence, migration, authorization, performance, or accessibility truly does not apply. A material unknown that can change architecture, public behavior, data, security, rollout, or verification remains a blocking open question.

## Diagram Rules

Use Mermaid in `design.md` so the design remains diffable and reviewable in the repository. At minimum, include:

- one architecture/relationship topology diagram with callers, owned components, dependencies, boundaries, and dependency direction;
- one runtime flow diagram showing the main interaction and important validation, authorization, persistence, external-call, or error points.

Add data models, state machines, deployment topology, or additional sequences only when the change actually needs them. Every diagram needs nearby prose explaining the important boundary and failure implications; the diagram must not be the only description.

## Profile Emphasis

- Backend designs emphasize domain ownership, invariants, ports/adapters, transaction and concurrency boundaries, authorization, schema evolution, idempotency, and observability.
- Frontend designs emphasize route and component ownership, state and event flow, API/type boundaries, interaction states, accessibility, responsive behavior, and design-system reuse.
- Fullstack designs show both sides and the shared contract, including generated types, version/null/error alignment, permission enforcement, retry/timeouts, and end-to-end ownership.

## Review Response Before Apply

After `check_design.py <change-dir>` and the normal `DESIGN` gate pass, present the design to the developer before requesting approval. Do not respond with only file links or a generic “ready to implement.” The response must summarize:

- the recommendation and why;
- scope and explicit non-goals;
- the architecture/topology diagram and responsibility boundary;
- the key runtime flow;
- interfaces, data, compatibility, security, and failure behavior;
- implementation waves and exact verification strategy;
- migration, rollout, rollback, residual risks, and blocking questions;
- numbered confirmation items, with a recommended answer and trade-off wherever a choice remains.

Link the complete `design.md`, specs, and task plan for detailed inspection. Stop after requesting explicit confirmation. The conversation confirmation must identify the reviewed change or decisions; optionally reflect it by checking the `C<n>` items, but keep the checklist and contract content stable. Only then may `approve_design.py` bind the contract digests and allow Apply. Silence, prior implementation intent, or approval of a different digest is not approval.
