---
name: engineering
description: Orchestrate non-trivial code changes through repository context, specification, design approval, implementation, verification, sync, and archive. Use for requested implementation or refactoring; do not use for read-only explanation, diagnosis, or review.
---

# Engineering

Operate as the task-level orchestrator. Project policy and code rules come from applicable `AGENTS.md`/`CLAUDE.md`, `docs/methodology/agent-policy.yaml`, and path documents; never redefine or weaken them here.

## Onboarding

When the user asks to接入、初始化、升级或迁移 Harness, use [references/onboarding.md](references/onboarding.md) before routing a code change. This is a repository operation performed in the conversation, not a request for the user to run `init.sh` manually. First run the read-only plan; show the detected state and file actions; ask for confirmation before `--apply`; then run the deterministic checks and report evidence. Legacy files are preserved unless the user explicitly approves a separate cleanup change.

## Requirement Reflection

After drafting every task response, run the response-level requirement reflection described in `docs/methodology/core/requirement-reflection.md` before sending the response or taking a side effect. Classify the result as `ready`, `clarify`, `correct`, or `blocked`.

- For `ready`, state material assumptions, the plan, and verification before acting within the authorized scope.
- For `clarify`, stop consequential writes and ask focused questions for ambiguities that could change the result; include the recommended option and its trade-off.
- For `correct`, show the repository or technical evidence that conflicts with the request, propose the smallest viable correction, and wait for confirmation.
- For `blocked`, explain the missing authorization or evidence and provide the safest next plan.

Never silently select between materially different interpretations or present a recommendation as an approved requirement. After confirmation changes the requirement, update the plan and repeat the reflection. Do not expose private chain-of-thought; report only the finding, evidence, recommendation, and confirmation needed.

## Route

1. Run `resolve_context.py` for every target path and explicit task keyword, then read its exact parent-to-child load order. A resolution failure blocks implementation.
2. Classify the change as `backend`, `frontend`, or `fullstack`. An explicit user mode wins unless it conflicts with the actual scope.
3. Read only the matching reference:
   - Backend: [references/backend.md](references/backend.md)
   - Frontend: [references/frontend.md](references/frontend.md)
   - Fullstack: [references/fullstack.md](references/fullstack.md)
4. Create the canonical `openspec/changes/<change-id>/` workspace with `init_change.py` for non-trivial work. Declare the observed trigger as `native-selection`, `explicit-selection`, or `manual-fallback`; the fallback form requires a reason. Small reversible changes may use the selected profile directly with focused verification.
   Record the approved requirement reflection with `requirement_reflection.py record` before closing Explore; its digest is part of the approval contract.
5. For every non-trivial change, complete `context-impact.json`. Read [references/context.md](references/context.md) when any context signal may apply.
   Generate the stable context prefix with `context_cache.py fingerprint`; record provider results as `hit`, `miss`, or `bypass` without changing host Agent configuration.
6. Apply the project Profile's Self-Refine policy before requesting a phase gate. Keep iterations bounded; when evidence is required, write `self-refine-evidence.json` after the final verification pass.
7. Before closing Explore, run `preflight_lessons.py` for every target path and explicit task keyword. Record matching lessons and feed them into Self-Refine; record Fitness, test, diff, phase, and production failures with `record_failure.py`.
8. Confirm the parent-child contract: every live `openspec/changes/<id>/` must carry the canonical `change.json` relationship created by `init_change.py`. Harness is the parent and owns change identity, state, approval, implementation, Sync, and Archive. OpenSpec is a child used only through `dispatch_openspec.py` for allowlisted JSON `status`, `instructions`, `validate`, `show`, or `templates` operations. Read `docs/methodology/core/openspec-orchestration.md`; never enter a standalone `/opsx:*` lifecycle or call change-scoped OpenSpec directly.
9. During Design, create matching `tasks.md` and `task-plan.json`. Read `docs/methodology/core/task-orchestration.md`, declare stable task ids, dependencies, exclusive write scopes, contract references, acceptance criteria, focused verification, and coordinator integration commands, then run `check_task_plan.py <change-dir> --phase DESIGN`.

## Lifecycle

Use the single lifecycle defined in `docs/methodology/core/change-lifecycle.md`:

```text
Explore → Propose (Spec → Design → Approval) → Apply → Sync → Archive
```

Advance state only with `methodology_state.py`. The corresponding `check_phase.py` gate must pass. Each gate also enforces the Harness-parent/OpenSpec-child invariant (`check_change_workspace.py`): an unmanaged or incorrectly related OpenSpec change directory fails closed. Approval binds the parent contract artifacts; contract drift invalidates it. Production-scoped changes additionally require a linked production record to reach `CLOSED` before archive.

Self-Refine is an inner `Generate → Self-Critique → Refine → Re-check` loop. It can prepare remediation but cannot approve changes, replace tests, or weaken any gate.

## Apply Orchestration

After Approval, act as the only coordinator. Inspect the Agent runtime for native concurrent-worker support and the repository for worktree or reliable disjoint-scope isolation. Initialize `execution-evidence.json` from its template with an empty `task_runs` array and pending integration. Use `check_task_plan.py`'s deterministic waves: dispatch all safe, parallel-eligible tasks in the current ready wave when supported; otherwise execute the same DAG sequentially and record the concrete fallback reason. Never claim parallel execution unless different actors actually overlap in time.

Give each worker only its task entry, resolved path context, listed contract references, write scope, acceptance criteria, and focused verification. Workers may not change lifecycle/approval artifacts, expand scope, integrate another worker, or mark the whole change complete. Prefer one branch/worktree per worker; shared-workspace concurrency requires disjoint write scopes.

Wait for every dispatched task and inspect its changed files and focused verification. Immediately after a task succeeds, write its run record from `task-run.json.template` and invoke `record_task_completion.py complete <change-dir> <task-id> --run <task-run.json>`; this is the only completion operation and it automatically ticks the matching OpenSpec `tasks.md` item. Never tick a box manually or defer all ticks until the end. If Apply is interrupted, keep the change in `IMPLEMENTING` and invoke `record_task_completion.py resume <change-dir> --actor <agent> --json`; it reconciles validated evidence, repairs checkbox projection, and returns the next ready wave. A changed file without a validated run is still pending and must pass focused verification before completion. Integrate only successful results in `integration.merge_order`. If integration exposes a contract change, stop Apply and enter `CONTRACT_CHANGED`; do not repair the contract silently. The coordinator reruns every `integration.final_verification` command, completes integration evidence, and runs `check_task_plan.py <change-dir> --phase REVIEW` before the normal Review gate. Runtime completion, reassignment, retry, and checkbox state do not alter the approved `task-plan.json`.

## Evidence

Record starts, fallbacks, and human interventions with `record_skill_event.py`; gate failures are recorded automatically. `execution-evidence.json` must identify actual capability, strategy, isolation, workers, commit/diff or shared-workspace result references, task-owned files, focused results, conflicts, merge order, and coordinator verification. Review requires one successful run per approved task and exact equality between those runs and checked `tasks.md` ids; use `record_task_completion.py sync <change-dir>` only to repair the projection from evidence. Review evidence must contain exact commands, exit codes, changed-file digests, and every required `ai.json`/`AI.md` update; its file set must exactly match execution evidence. Project Agents must not edit `docs/fitness/**` except canonical first installation or a demonstrable pre-existing Python syntax repair. Any other Fitness change has no size exemption and requires external human approval matching `check_fitness_protection.py`'s digest. If the Skill or a supporting capability is unavailable, record `skill.fallback` and follow the same lifecycle manually—never silently skip a gate.

When a failure is reusable, create `lesson-candidate.json` with `create_lesson_candidate.py`. Only an external approval using `approve_lesson.py` may activate it under `docs/methodology/lessons/`; candidates and lessons never replace deterministic gates.

Return the selected mode, current state, changed files, verification evidence, uncovered cases, and the next valid transition.
