# Specification-Driven Delivery

SDD is the contract-producing part of the canonical Engineering lifecycle, not a second lifecycle.

`openspec/changes/<change-id>/` is the only active change workspace. OpenSpec proposal/spec/design/tasks and Harness context, state, approval, and evidence artifacts are co-located there.

Workspace ownership is a deterministic parent-child contract, not a convention. `init_change.py` is the only creator of a live change and `methodology_state.py` the only state machine; `check_change_workspace.py` fails every phase gate when a live `openspec/changes/<id>/` lacks the canonical Harness-parent/OpenSpec-child relationship. Change-scoped OpenSpec authoring and validation are dispatched by Harness through `dispatch_openspec.py`; the child never owns creation, approval, implementation, Sync, or Archive. See [Harness and OpenSpec Parent-Child Orchestration](openspec-orchestration.md).

- Explore produces context, impact evidence, and an approval-bound `context-impact.json` decision covering every planned file.
- Propose produces the business proposal, observable behavior specs, technical design, dependency-ordered `tasks.md`, an approval-bound `task-plan.json` DAG, and external approval.
- Apply executes ready DAG tasks concurrently when safely supported (or sequentially with recorded fallback). Each successful task is recorded through `record_task_completion.py`, which immediately synchronizes its `tasks.md` checkbox, before final integration and Review evidence.
- Sync copies verified behavior into canonical specs/docs and proves equal digests.
- Archive closes the technical record after any linked production record is closed.

Behavior specs use `#### Scenario`, `WHEN`, and `THEN`, remain implementation-neutral, and include validation, errors, authorization, precision/time, compatibility, and failure behavior as applicable. Design records the choices needed to realize those behaviors. Approval covers both, so changing either invalidates execution authorization.

Review must digest exactly the files declared in `context-impact.json`. Changes to project summary, module topology, context routes, or entrypoints require `ai.json`; changes to responsibilities, boundaries, invariants, dependencies, contracts, or local verification require the affected indexed `AI.md`.

Before requesting a phase gate, the author may run the bounded Self-Refine loop (`Generate → Self-Critique → Refine → Re-check`) against the requirement, scenarios, design decisions, tasks, or implementation. A required Profile records this in `self-refine-evidence.json` at Review. Self-feedback can identify gaps and prepare remediation, but tests, digests, approval, and external review remain authoritative.
