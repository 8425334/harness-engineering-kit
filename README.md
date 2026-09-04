# Harness Engineering Kit

A repository-native control system for AI-assisted software changes. It makes context, decisions, approvals, verification, synchronization, production controls, and audit evidence executable instead of hiding them in a long root prompt.

Chinese documentation: [README.zh.md](README.zh.md)

## Architecture

| Layer | Owns | Must not own |
|---|---|---|
| `AGENTS.md` / `CLAUDE.md` | Native authority adapter, safety, required reads, Skill route | Commands, module maps, full methodology |
| `agent-policy.yaml` | Canonical project facts, commands, permissions, referenced paths | Task-specific design |
| Root `ai.json` | Compact machine-readable project map and routes to detailed context | Commands, policies, invariants, or detailed rules |
| Path `AI.md` | Local responsibilities, boundaries, navigation, local verification | Authority over native instructions or policy |
| `engineering` Skill | Task routing, lifecycle orchestration, evidence and fallback | Project conventions already defined above |
| Backend/frontend/fullstack profiles | Design and verification specialization | Independent lifecycle or command |

Authority is fixed: system/developer/user → native instruction hierarchy → `agent-policy.yaml` → root `ai.json` → selected path `AI.md` → profile defaults.

Before code changes, `resolve_context.py` turns target paths and explicit `read_when` keywords into one fail-closed load order. Root context is mandatory; indexed ancestor `AI.md` files load before child details.

`docs/fitness/**` is a protected control plane. Project Agents may read and execute it but may not modify it; every non-bootstrap, non-syntax-repair change requires external human approval bound to the complete change digest, with no size exemption.

## Lifecycle

```text
Explore → Propose (Spec → Design → Approval) → Apply → Sync → Archive
```

The exact artifacts, gates, states, drift transitions, and production extension are defined once in [Canonical Change Lifecycle](core/change-lifecycle.md). Backend RAM and frontend RAD finish during Explore/Propose; Apply consumes the approved contract.

Production delivery extends—not replaces—the Engineering lifecycle. A production-scoped change cannot archive until its linked production record is `CLOSED` with observability, staged rollout, stop conditions, rollback, and audit evidence.

Self-Refine is an optional or Profile-required inner loop for draft and implementation quality: `Generate → Self-Critique → Refine → Re-check`. It produces auditable evidence without replacing approval, deterministic gates, or production controls. See [Self-Refine Feedback Loop](core/self-refine.md).

Project Lesson Memory extends this loop across changes: failures become reviewed, retrievable prevention guidance and can later be promoted to deterministic controls. See [Project Lesson Memory](core/lesson-memory.md).

## Conversational Onboarding

Project members no longer need to run `init.sh` manually. In the target repository's Agent conversation, ask:

```text
Onboard this project to the Harness Engineering Kit. First inspect read-only and classify it as fresh, partial, legacy, or current. Show the files to create, update, and preserve. Do not delete old ramer/fe-engineering/multi-agent or Cursor entries; wait for my confirmation before applying and verifying the complete onboarding.
```

The `engineering` Skill routes integrated projects to the onboarding playbook. The Agent first runs a read-only plan:

```bash
python3 <kit>/scripts/onboard.py --project-root . --source-root <kit> --plan --json
```

After confirmation it runs `--apply` and then `--check`. Tier 1 installs core controls; complete onboarding defaults to Tier 2 (Fitness, production controls, and lesson memory). Each run writes `docs/methodology/onboarding.json` with the source version, file digests, preserved legacy files, and verification result. `scripts/init.sh` remains only as a compatibility forwarder for old automation, not as the onboarding entrypoint.

The check fails for an oversized or structurally invalid `ai.json`, unindexed or oversized `AI.md`, missing policy, placeholders, broken referenced paths, invalid profiles, missing Skill resources, stale installed Skill content, or unsupported platform adapters. Cursor and the legacy `ramer`, `fe-engineering`, and `multi-agent` entries are intentionally not supported.

Resolve task context directly with `python3 docs/methodology/scripts/resolve_context.py <target-path> [<target-path> ...]`. Add exact semantic routes with repeated `--keyword <read_when>` arguments.

See the [Conversational Onboarding Playbook](templates/engineering/references/onboarding.md) for the execution contract. The copy-ready Chinese conversation guide is [here](docs/onboarding-conversation.zh.md).

## Change Controls

```bash
python3 docs/methodology/scripts/init_change.py add-capability \
  --title "Add capability" --mode fullstack --owner team \
  --trigger explicit-selection \
  --profile-path docs/methodology/profile.yaml

python3 docs/methodology/scripts/approve_design.py openspec/changes/add-capability \
  --actor reviewer --source pull-request --approval-id PR-123

python3 docs/methodology/scripts/methodology_state.py \
  openspec/changes/add-capability EXPLORED --actor agent
```

Use `check_phase.py` for direct gate inspection, `record_skill_event.py` for explicit fallback/intervention events, and `skill_metrics.py` for structured adoption metrics.

Use `preflight_lessons.py` before Explore closes, `record_failure.py` for Fitness/test/diff/production failures, `create_lesson_candidate.py` to propose reusable prevention, `retrieve_lessons.py` to inspect active lessons, and `approve_lesson.py` to activate an externally approved lesson.

## Canonical Documents

- [Harness Architecture](core/harness-engineering.md)
- [Change Lifecycle](core/change-lifecycle.md)
- [SDD Workflow](core/sdd-workflow.md)
- [Governance](core/methodology-governance.md)
- [Self-Refine Feedback Loop](core/self-refine.md)
- [Project Lesson Memory](core/lesson-memory.md)
- [Backend Profile](core/backend-profile.md)
- [Frontend Profile](core/frontend-profile.md)
- [Fullstack Profile](core/fullstack-profile.md)
- [Production Controls](templates/production/README.md.template)
- [Transplant Guide](TRANSPLANT.md)

`manifest.yaml` is a Harness availability contract, not a claim that every platform has a native manifest format. Platform auto-selection must be observed at runtime; deterministic installation and resource integrity are verified by `verify_skill.py` and `smoke_test_skills.py`.
