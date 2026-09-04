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
| Deterministic scripts | Resolve context and enforce policy, approvals, state transitions, sync, archive, and metrics |

The Skill is intentionally small. It must not duplicate repository rules already available from native instructions or policy. Supporting tools such as OpenSpec, code navigation, test runners, browsers, and multi-agent execution are capabilities selected by need; their absence never silently removes a gate.

## Context Loading

Load in this order: native instructions → `resolve_context.py` output (`agent-policy.yaml` → methodology profile → root `ai.json` → indexed `AI.md` from parent to child) → matching Engineering profile → task code/contracts/tests. Path matches select the root and every indexed ancestor module. Explicit `read_when` keywords select matching modules plus their indexed ancestors. Every explicit keyword must resolve; otherwise the chain fails closed. The index routes; Markdown explains. Neither duplicates policy or overrides a higher layer.

## Closed Loop

The lifecycle is defined only in `change-lifecycle.md`. Every non-trivial change has a machine-readable state and append-only event stream. Approval binds exact artifacts. Review records exact commands and gaps. Sync verifies content digests. Production changes link technical and operational state by `change_id`.

Self-Refine is a supporting inner loop for improving work before a gate. It is profile-controlled and bounded, with optional or required `self-refine-evidence.json`. It improves discovery and remediation but does not weaken authority, approval, deterministic verification, or production controls.

Project Lesson Memory extends that loop across changes. Failures are captured as evidence, promoted only after external review, and retrieved during Explore through `preflight_lessons.py`; active lessons remain advisory until a deterministic control is separately approved.

## Platform Boundary

Claude project discovery uses `.claude/skills/engineering`; the Codex adapter uses `.agents/skills/engineering`. `manifest.yaml` is a Harness availability contract. File checks prove installation integrity, while runtime `skill.triggered` and `skill.fallback` events reveal actual selection behavior.
