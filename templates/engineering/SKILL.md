---
name: engineering
description: Orchestrate non-trivial code changes through repository context, specification, design approval, implementation, verification, sync, and archive. Use for requested implementation or refactoring; do not use for read-only explanation, diagnosis, or review.
---

# Engineering

Operate as the task-level orchestrator. Project policy and code rules come from applicable `AGENTS.md`/`CLAUDE.md`, `docs/methodology/agent-policy.yaml`, and path documents; never redefine or weaken them here.

## Onboarding

When the user asks to接入、初始化、升级或迁移 Harness, use [references/onboarding.md](references/onboarding.md) before routing a code change. This is a repository operation performed in the conversation, not a request for the user to run `init.sh` manually. First run the read-only plan; show the detected state and file actions; ask for confirmation before `--apply`; then run the deterministic checks and report evidence. Legacy files are preserved unless the user explicitly approves a separate cleanup change.

## Route

1. Run `resolve_context.py` for every target path and explicit task keyword, then read its exact parent-to-child load order. A resolution failure blocks implementation.
2. Classify the change as `backend`, `frontend`, or `fullstack`. An explicit user mode wins unless it conflicts with the actual scope.
3. Read only the matching reference:
   - Backend: [references/backend.md](references/backend.md)
   - Frontend: [references/frontend.md](references/frontend.md)
   - Fullstack: [references/fullstack.md](references/fullstack.md)
4. Create the canonical `openspec/changes/<change-id>/` workspace with `init_change.py` for non-trivial work. Declare the observed trigger as `native-selection`, `explicit-selection`, or `manual-fallback`; the fallback form requires a reason. Small reversible changes may use the selected profile directly with focused verification.
5. For every non-trivial change, complete `context-impact.json`. Read [references/context.md](references/context.md) when any context signal may apply.
6. Apply the project Profile's Self-Refine policy before requesting a phase gate. Keep iterations bounded; when evidence is required, write `self-refine-evidence.json` after the final verification pass.
7. Before closing Explore, run `preflight_lessons.py` for every target path and explicit task keyword. Record matching lessons and feed them into Self-Refine; record Fitness, test, diff, phase, and production failures with `record_failure.py`.

## Lifecycle

Use the single lifecycle defined in `docs/methodology/core/change-lifecycle.md`:

```text
Explore → Propose (Spec → Design → Approval) → Apply → Sync → Archive
```

Advance state only with `methodology_state.py`. The corresponding `check_phase.py` gate must pass. Approval binds every contract artifact; contract drift invalidates it. Production-scoped changes additionally require a linked production record to reach `CLOSED` before archive.

Self-Refine is an inner `Generate → Self-Critique → Refine → Re-check` loop. It can prepare remediation but cannot approve changes, replace tests, or weaken any gate.

## Evidence

Record starts, fallbacks, and human interventions with `record_skill_event.py`; gate failures are recorded automatically. Review evidence must contain exact commands, exit codes, changed-file digests, and every required `ai.json`/`AI.md` update. Project Agents must not edit `docs/fitness/**` except canonical first installation or a demonstrable pre-existing Python syntax repair. Any other Fitness change has no size exemption and requires external human approval matching `check_fitness_protection.py`'s digest. If the Skill or a supporting capability is unavailable, record `skill.fallback` and follow the same lifecycle manually—never silently skip a gate.

When a failure is reusable, create `lesson-candidate.json` with `create_lesson_candidate.py`. Only an external approval using `approve_lesson.py` may activate it under `docs/methodology/lessons/`; candidates and lessons never replace deterministic gates.

Return the selected mode, current state, changed files, verification evidence, uncovered cases, and the next valid transition.
