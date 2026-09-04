# Self-Refine Feedback Loop

Self-Refine is the inner quality loop of Harness Engineering. It improves an artifact or implementation through bounded self-feedback; it does not create a second lifecycle and it never replaces external approval, deterministic gates, human review, or production evidence.

```text
Generate → Self-Critique → Refine → Re-check
```

## Placement

The canonical lifecycle remains:

```text
Explore → Propose (Spec → Design → Approval) → Apply → Sync → Archive
```

The inner loop may run inside Explore, Spec, Design, Apply, and Verify. It must finish before the corresponding phase gate is requested. Backend RAM and frontend RAD can use the same loop when their analysis exposes omissions or contradictions.

## Profile policy

Self-Refine is configured in `docs/methodology/profile.yaml` so teams can choose the right amount of process:

| Policy | Meaning |
|---|---|
| `disabled` | Do not require a refinement record; objective gates still apply. |
| `recommended` | Use the loop when useful; record evidence when it is run. |
| `required` | Every non-trivial change must submit `self-refine-evidence.json` at Review. |
| `required-independent` | Required, plus an independent human or agent check recorded in the evidence. |

`max_iterations` is bounded from 1 to 10. A loop that cannot resolve an issue within the bound records the unresolved risk and escalates to the normal gate or an owner; it must not hide the issue by declaring success.

## Critique contract

Each refinement checks the artifact against the approved requirement, applicable profile, and risk-specific criteria. The record identifies:

- the artifact or changed area;
- concrete findings, not a generic quality claim;
- the resolution or reason the finding remains open;
- uncovered risks and the next owner or gate;
- an independent check when the selected policy requires it.

The standard evidence file is `self-refine-evidence.json`. It is process evidence, not part of the approval contract, so it cannot silently authorize a contract change. Any change to Spec, Design, or Tasks still invalidates approval and follows `CONTRACT_CHANGED`.

## Trust boundaries

Self-feedback is not independent proof: the same model may share the original mistake. Use deterministic checks, tests, external review, or a separate evaluator for high-risk claims. Do not copy a reflection directly into `agent-policy.yaml`, `ai.json`, `AI.md`, or Fitness rules without the normal change and approval controls. Record model/tool fallback and human intervention in the append-only event stream.

## Completion

Self-Refine is complete when the configured iteration bound is respected, each selected finding has a resolution or explicit uncovered-risk entry, and the phase's normal gate passes. A passing self-refine record cannot turn a failed test, missing approval, digest mismatch, or production stop condition into a pass.

## Research basis

This practice is informed by Madaan et al., *Self-Refine: Iterative Refinement with Self-Feedback* (NeurIPS 2023). Reflexion (Shinn et al., 2023) is a related pattern for carrying lessons across tasks; any such memory remains advisory until it is reviewed through the normal methodology change controls.
