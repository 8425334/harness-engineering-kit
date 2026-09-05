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

If you want to type `hek init` directly in any target project, install the command globally from GitHub once (this does not use the npm package registry or require publishing a package):

```bash
npm install --global git+https://github.com/8425334/harness-engineering-kit.git
cd target-project
hek init
```

The `npx` form is intentionally ephemeral; without a global install, use the full `npx --package ... hek init` command each time.

Claude Code, Codex, Cursor, and Gemini CLI are supported. WorkBuddy and Trae Work are supported through a manual handoff because they do not expose a stable CLI contract. For scripts or explicit selection:

```bash
npx --yes --package github:8425334/harness-engineering-kit hek init --agent codex --open --yes
npx --yes --package github:8425334/harness-engineering-kit hek init --direct --yes
npx --yes --package github:8425334/harness-engineering-kit hek agents
npx --yes --package github:8425334/harness-engineering-kit hek init --plan --json
npx --yes --package github:8425334/harness-engineering-kit hek handoff --agent workbuddy
npx --yes --package github:8425334/harness-engineering-kit hek handoff --agent trae-work --json
```

For a desktop Agent without a CLI, first install the project controls with `hek init --direct --yes`, then run `hek handoff --agent workbuddy` or `hek handoff --agent trae-work`. Open the project in that Agent, copy the generated prompt, and let it read the repository's `AGENTS.md`/`CLAUDE.md` and `docs/methodology/agent-policy.yaml`. `handoff` never launches an unknown desktop application and never writes project files.

Interactive `init` asks for the install scope first (full or lightweight, chosen with the arrow keys when `--tier` is not given), then opens the selected Agent and lets that Agent perform onboarding; pick the skip entry in the agent menu for the deterministic flow, and it falls back automatically when no agent is installed. Non-interactive runs never launch an external process unless `--open` is supplied, and `--open` there requires `--agent`/`HEK_AGENT`. `--json` switches to machine-readable output: it never opens an agent and never prompts — without `--yes` init prints the read-only plan and exits 2; with `--yes` it applies, checks, and prints one JSON receipt (including an `errors` receipt when apply fails and rolls back). Use `HEK_AGENT` instead of `--agent`, or `--prompt` to customize the first prompt sent to terminal agents (prompts are delivered as a single line so Windows `cmd.exe` cannot truncate them).

A fresh project's placeholders must be filled from real repository facts before the post-init check passes, so an unattended `init --direct --yes` on a fresh project installs the scaffolding and then intentionally exits 2; upgrade runs on an already-configured project pass directly. Use `--no-check` for scaffold-only automation, or open an Agent (`--agent <id> --open --yes`) to complete the fill-and-check loop after the deterministic install.

`hek init` is Agent-driven: it asks for the install scope, selects an installed Agent, opens that Agent's CLI in the resolved project root, and passes the Kit path plus the onboarding contract. The Agent reads project facts, generates the read-only plan, asks for confirmation, fills project-specific values, applies the canonical script, and runs deterministic checks. Tier 1 (lightweight) installs the core control plane, including the production policy scaffold referenced by `agent-policy.yaml`; the default Tier 2 (full) additionally installs Fitness gate scripts, Fitness rules, and lesson memory. Each run writes `docs/methodology/onboarding.json` with the source version, file digests, created/updated/preserved files, and verification result. Use `--direct` only when a headless deterministic install is explicitly wanted; it ignores `--agent` and `HEK_AGENT`.

Version-aware upgrades compare the installed `docs/methodology/VERSION` with the Kit version, synchronize all canonical resources for lower-to-higher upgrades, block downgrades, and report any release-specific migration review. See [Versioning and Upgrades](docs/versioning.md).

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
