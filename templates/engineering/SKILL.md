---
name: engineering
description: Govern non-trivial code changes while delegating lifecycle actions to native OpenSpec Skills. Use for requested implementation or refactoring; do not use for read-only explanation, diagnosis, or review.
---

# Engineering

Engineering is a governance wrapper, not a competing lifecycle. OpenSpec owns change creation, artifact order, task progress, Sync, and Archive. Repository policy comes from applicable native instructions, `docs/methodology/agent-policy.yaml`, the resolved path context, and the selected profile.

## Onboarding

When the user asks to接入、初始化、升级或迁移 Harness, use [references/onboarding.md](references/onboarding.md). Generate the read-only plan, explain the exact file and OpenSpec Skill actions, ask for confirmation, then apply and run deterministic checks. Never copy OpenSpec Skill prompts into Harness; `openspec init` or `openspec update` owns them.

## Requirement Reflection

Before a consequential action, follow `docs/methodology/core/requirement-reflection.md`. Report only the result, evidence, assumptions, recommendation, and confirmation needed. Stop on material ambiguity, conflict, missing authorization, or missing evidence.

## Route

1. Run `resolve_context.py` for every target path and explicit task keyword, then read the returned order exactly.
2. Classify the scope as backend, frontend, or fullstack and read only the matching reference.
3. Run `preflight_lessons.py` before implementation planning closes. Complete `context-impact.json` for non-trivial work and use `context_cache.py` for stable-prefix telemetry.
4. Select the native OpenSpec Skill that matches the user's action:
   - explore or clarify: `openspec-explore`
   - create a complete proposal: `openspec-propose`
   - create a change: `openspec new change` (or `openspec-propose` for a complete proposal)
   - revise planning artifacts: `openspec-update-change`
   - implement: `openspec-apply-change`
   - validate artifact structure: `openspec validate --strict`
   - verify implementation consistency: `openspec-verify-change`
   - sync delta specs: `openspec-sync-specs`
   - archive: `openspec-archive-change`
5. Immediately after OpenSpec creates a change, attach `governance.json` with `init_governance.py`. Never create the OpenSpec change directory yourself.
6. Use OpenSpec `status`, `instructions`, `validate`, and artifact paths directly. Do not route them through a Harness dispatcher.

## Design Confirmation

The project-local `harness-engineering` OpenSpec schema supplies the implementation-ready `design.md` template. Run `check_design.py` and `check_phase.py <change-dir> DESIGN`, then present the recommendation, scope, topology, runtime flow, boundaries, interfaces/data, failure behavior, delivery/rollback, verification, risks, and every numbered confirmation item.

Require explicit developer confirmation before `approve_design.py` writes `approval.json`. The original request, generated artifacts, OpenSpec readiness, or silence is not approval. Contract changes after approval require renewed approval.

## Lifecycle

Follow the OpenSpec lifecycle exposed by its native Skills:

```text
openspec-explore → openspec-propose → openspec-apply-change → openspec-verify-change → openspec-sync-specs → openspec-archive-change
```

Engineering wraps that sequence with governance gates:

- Explore/Propose: context resolution, requirement reflection, lessons, context impact, Design Review, and OpenSpec strict artifact validation.
- Apply: require current `approval.json`; record actual task runs and integration in `execution-evidence.json` while OpenSpec remains the sole owner of `tasks.md` checkbox state.
- Verify/Review: invoke `openspec-verify-change`, run project tests/build/Fitness, `check_execution.py`, and `check_phase.py <change-dir> REVIEW`; record exact commands, changed-file digests, context updates, exceptions, and uncovered cases.
- Sync: let `openspec-sync-specs` perform the intelligent merge, then record source/destination digests and run the `SYNC` governance gate.
- Archive: require governance and production closure, then let `openspec-archive-change` perform the archive.

Harness has no second change state machine. Approval and evidence files are facts checked against OpenSpec artifacts, not lifecycle state transitions.

## Apply Orchestration

Before invoking `openspec-apply-change`, inspect runtime concurrency and isolation. OpenSpec `tasks.md` is the only task definition and progress source. If safe parallel work is available, group only dependency-independent tasks with disjoint write scopes; otherwise execute sequentially and record the fallback reason.

After each OpenSpec task succeeds, append one task run to `execution-evidence.json` with its OpenSpec task id, actor, isolation, timestamps, changed files, exact verification commands, and evidence. Then allow the OpenSpec Apply Skill to mark that task complete. Never maintain a second task graph or repair OpenSpec checkboxes from Harness evidence.

The coordinator owns integration, conflict resolution, final verification, and review evidence. If implementation reveals contract drift, stop, update the OpenSpec artifacts, invalidate stale approval, and request confirmation again.

## Evidence

Use `record_skill_event.py`, `record_failure.py`, `create_lesson_candidate.py`, and the governance templates as applicable. `execution-evidence.json` task ids must exactly equal the checked OpenSpec tasks at Review, and its changed files must equal `review-evidence.json` files. Project Agents must not edit `docs/fitness/**` except canonical first installation or an approved repair.

If OpenSpec or a required native Skill is unavailable, report the missing dependency and stop lifecycle work; do not recreate its workflow inside Engineering. Return the selected OpenSpec action, governance checks, changed files, exact verification, uncovered cases, and the next valid OpenSpec action.
