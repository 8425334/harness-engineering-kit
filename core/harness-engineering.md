# Harness Engineering Architecture

Harness Engineering makes an AI coding environment predictable through explicit authority, minimal context loading, executable gates, and durable evidence.

## Responsibility Boundaries

| Component | Responsibility |
|---|---|
| Native root adapter | Establish scope, authority, safety, required reads, and route to `engineering` |
| `agent-policy.yaml` | Store the single canonical set of project commands, paths, permissions, and delivery references |
| Root `ai.json` | Give initialization a compact project/module map and route to details |
| Path `AI.md` | Add local responsibility, boundary, navigation, and verification context |
| `engineering` Skill | Route a requested code change and orchestrate lifecycle/state/evidence |
| Profile reference | Specialize Design and verification for backend, frontend, or fullstack |
| Deterministic scripts | Resolve context and enforce policy, approvals, task graphs, execution evidence, state transitions, sync, archive, and metrics |

The Skill is intentionally small. It must not duplicate repository rules already available from native instructions or policy. Supporting tools such as OpenSpec, code navigation, test runners, browsers, and multi-agent execution are capabilities selected by need; their absence never silently removes a gate.

OpenSpec is explicitly subordinate to this lifecycle. Harness creates and owns
the change, state, approval, execution, Sync, and Archive; OpenSpec contributes
only allowlisted authoring/validation input through `dispatch_openspec.py`. See
[Harness and OpenSpec Parent-Child Orchestration](openspec-orchestration.md).

During Design, `task-plan.json` converts Tasks into an approval-bound DAG with dependencies, disjoint write scopes, contract references, acceptance criteria, and verification. During Apply, the coordinator adapts execution to available Agent/isolation capabilities, records sequential fallback when necessary, and owns deterministic integration evidence. See [Task Graph and Parallel Execution](task-orchestration.md).

## Context Loading

Load in this order: native instructions → `resolve_context.py` output (`agent-policy.yaml` → methodology profile → root `ai.json` → indexed `AI.md` from parent to child) → matching Engineering profile → task code/contracts/tests. Path matches select the root and every indexed ancestor module. Explicit `read_when` keywords select matching modules plus their indexed ancestors. Every explicit keyword must resolve; otherwise the chain fails closed. The index routes; Markdown explains. Neither duplicates policy or overrides a higher layer.

## Closed Loop

The lifecycle is defined only in `change-lifecycle.md`. Every non-trivial change has a machine-readable state and append-only event stream. Approval binds exact artifacts. Review records exact commands and gaps. Sync verifies content digests. Production changes link technical and operational state by `change_id`.

Self-Refine is a supporting inner loop for improving work before a gate. It is profile-controlled and bounded, with optional or required `self-refine-evidence.json`. It improves discovery and remediation but does not weaken authority, approval, deterministic verification, or production controls.

Project Lesson Memory extends that loop across changes. Failures are captured as evidence, promoted only after external review, and retrieved during Explore through `preflight_lessons.py`; active lessons remain advisory until a deterministic control is separately approved.

## Workspace Ownership

In an instrumented repository the active change workspace
`openspec/changes/<change-id>/` is owned by this lifecycle, not by any
standalone tool lane. A live change directory is valid only when it carries a
canonical `change.json` (schema_version 3) whose `change_id` matches the
directory, created by `init_change.py` and advanced by `methodology_state.py`.
An OpenSpec-only directory (proposal/design/specs/tasks but no `change.json`)
is unmanaged: gate checks fail closed until it is registered
(`trigger=manual-fallback`) or archived/removed. The OpenSpec CLI is a
child authoring/validation capability under `engineering`; change-scoped calls
must cross `dispatch_openspec.py`, and its standalone agent lane (`/opsx:*`)
must not create, implement, sync, or archive a change.
`check_change_workspace.py` enforces this invariant in every phase gate and,
where installed, as a Claude Code PreToolUse hook.

## Platform Boundary

Claude project discovery uses `.claude/skills/engineering`; the Codex adapter uses `.agents/skills/engineering`. `manifest.yaml` is a Harness availability contract. File checks prove installation integrity, while runtime `skill.triggered` and `skill.fallback` events reveal actual selection behavior.
