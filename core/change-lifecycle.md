# Canonical Change Lifecycle

This is the only lifecycle owned by Harness Engineering. Backend, frontend, and fullstack profiles specialize Design and verification; they do not create independent workflows.

```text
Explore → Propose (Spec → Design → Approval) → Apply → Sync → Archive
```

## Phase Contract

| Phase | Required artifacts | Gate | Resulting state |
|---|---|---|---|
| Explore | `change.json`, `context-pack.md`, `impact-analysis.md`, `context-impact.json`, `evidence/lesson-preflight.json` | `EXPLORE` | `EXPLORED` |
| Propose / Spec | `proposal.md`, `specs/<capability>/spec.md` | `SPEC` | `CONTRACT_READY` |
| Propose / Design | `design.md`, `tasks.md` | `DESIGN` | `DESIGN_READY` |
| Approval | external identity plus digests of every contract artifact | `EXECUTE` | `APPROVED` |
| Apply | approved contract, completed tasks, changed-file digests, exact verification commands | `EXECUTE`, then `REVIEW` | `IMPLEMENTING → VERIFYING → VERIFIED` |
| Sync | verified behavior copied to canonical specs/docs with matching digests | `SYNC` | `SYNCED` |
| Archive | archive evidence; learning conclusion; production closure when applicable | `ARCHIVE` | `ARCHIVED` |

Advance state only with `methodology_state.py`. A failed gate records `phase.blocked`. Contract drift after approval moves to `CONTRACT_CHANGED`; repository drift moves to `DRIFT_DETECTED`; failed verification moves to `REMEDIATING`.

Self-Refine is a bounded inner loop inside the phases, not an additional state machine:

```text
Generate → Self-Critique → Refine → Re-check → phase gate
```

Its policy is selected by the project Profile. When required, Review must include `self-refine-evidence.json`; the record documents findings and resolutions but cannot approve contract changes or replace objective verification. See [Self-Refine Feedback Loop](self-refine.md).

## Contract Boundary

The approval contract is the exact content of context, impact, context-update decisions, proposal, all behavior specs, design, and tasks. `context-impact.json` lists every planned deliverable and declares whether root `ai.json` or indexed `AI.md` details must change. `approve_design.py` records the external approval source and stable approval ID plus SHA-256 digests. The script proves integrity, not approver authenticity; CI or the approval system must verify identity and authorization.

Explore also records the active project lessons matched by the task in `evidence/lesson-preflight.json`. Recorded failures must reach a lesson candidate or an explicit non-generalizable decision before Archive; this learning conclusion does not change the approval contract.

Backend RAM (`Read → Analyze → Model`) and frontend RAD (`Read → Analyze → Decompose`) occur inside Explore and Propose. Apply may perform a small drift check, but it must not silently redesign the approved contract.

## Production Extension

Technical completion and production completion are separate state machines linked by the same `change_id`:

```text
RELEASE_READY → DEPLOYED(stage 1..n) → OBSERVING → CLOSED
                  ↘ ROLLED_BACK ───────────────────↗
```

A production-scoped Engineering change cannot archive until its linked production record is `CLOSED`. Every declared rollout stage advances in order with evidence; stop conditions can route to an evidenced rollback and closure. The record must carry observability, rollback ownership, rollback rehearsal, and an audit log confined to the project production directory.

## Trivial Changes

A profile may allow a workspace-free path only when the change is local, reversible, does not alter a public contract/schema/trust boundary, and does not affect production controls. The final response must still report changed files, exact verification, and uncovered cases.
