# Project Lesson Memory

Lesson memory turns recurring change failures into reviewed, retrievable prevention guidance. It is the durable companion to the per-change Self-Refine loop; it is not model fine-tuning and it is not an automatic authority source.

## Closed loop

```text
Failure → Capture → Distill → Approve → Activate → Retrieve → Preflight → Verify
```

The source of truth is split by trust level:

| Location | Meaning | Authority |
|---|---|---|
| `evidence/failure-events.jsonl` | Immutable observations from Fitness, phase gates, tests, diffs, or production | Evidence only |
| `lesson-candidate.json` | Agent-proposed pattern, root cause, prevention, and verification | Pending review |
| `docs/methodology/lessons/*.json` | Externally approved project lesson | Advisory prevention guidance |
| Fitness or policy rules | Deterministic enforcement of a proven recurring pattern | Normative control |

## Operating contract

Record a failure with `record_failure.py`, including its rule, category, message, paths, signature, and evidence. Use `create_lesson_candidate.py` after Self-Refine identifies a reusable pattern. An authorized reviewer promotes it with `approve_lesson.py`; activation binds the candidate digest and approval reference. The approval script never edits `docs/fitness/**`.

Every non-trivial change runs `preflight_lessons.py` before Explore closes. It records the active lessons matched by task keywords, rules, paths, and scope, including an explicit no-match result. The Engineering Skill must feed those lessons into Self-Refine and the phase plan.

Archive requires a candidate or an explicit `lesson-decision.json` when failure events were recorded. A decision may state that the observed failure is not generalizable, but must name the source events and a reason. This prevents failures from disappearing without an accountable conclusion.

## Promotion and recurrence

One observation normally creates a candidate, not a rule. Repeated matching signatures can justify a mandatory preflight or a deterministic Fitness rule after external review. Track recurrence, false positives, unresolved risks, and escaped defects; retire lessons when the owning contract or rule changes.

## Trust and retention

Lessons are advisory until a reviewer activates them. Retrieval is bounded and path/scoped; it must not load arbitrary repository prose as instructions. Do not store secrets, personal data, production dumps, or unverified commands. Memory cannot bypass approval, tests, digest checks, protected Fitness controls, or production closure.
