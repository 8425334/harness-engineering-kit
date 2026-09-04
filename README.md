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

## CLI Onboarding

### Standalone CLI (`hek`)

The repository ships a dependency-free Node.js entry point. It does not need to be published to npm: run it from GitHub or a local checkout with `npx`:

```bash
cd your-project
npx --yes --package github:8425334/harness-engineering-kit hek init
# or use a local checkout
npx --yes --package /path/to/harness-engineering-kit hek init
```

Choose an installed AI agent, confirm the plan, and the selected agent panel opens with an onboarding prompt. Plain `npx hek init` requires an npm-published package or a locally installed dependency; this project does not rely on that form.

Claude Code, Codex, Cursor, and Gemini CLI are supported. For scripts or explicit selection:

```bash
npx --yes --package github:8425334/harness-engineering-kit hek init --agent codex --yes
npx --yes --package github:8425334/harness-engineering-kit hek init --agent claude --yes --no-open
npx --yes --package github:8425334/harness-engineering-kit hek agents
npx --yes --package github:8425334/harness-engineering-kit hek init --plan --json
```

Interactive `init` opens an agent only after onboarding succeeds. Non-interactive runs never launch an external process unless `--open` is supplied. Use `HEK_AGENT` instead of `--agent`, or `--prompt` to customize the first prompt sent to terminal agents.

`hek init` first produces a read-only plan and classifies the project as `fresh`, `partial`, `legacy`, or `current`. Interactive runs then ask for confirmation, apply the plan, run deterministic checks, and open the selected Agent. Tier 1 installs core controls; the default Tier 2 also includes Fitness, production controls, and lesson memory. Each run writes `docs/methodology/onboarding.json` with the source version, file digests, preserved legacy files, and verification result.

The check fails for an oversized or structurally invalid `ai.json`, unindexed or oversized `AI.md`, missing policy, placeholders, broken referenced paths, invalid profiles, missing Skill resources, stale installed Skill content, or unsupported platform adapters. Cursor and the legacy `ramer`, `fe-engineering`, and `multi-agent` entries are intentionally not supported.

Resolve task context with the installed project controls. See the [CLI Onboarding Playbook](templates/engineering/references/onboarding.md) for the execution contract.

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
