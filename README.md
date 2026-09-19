# Harness Engineering Kit

A repository-native control system for AI-assisted software changes. It makes context, decisions, approvals, verification, synchronization, production controls, and audit evidence executable instead of hiding them in a long root prompt.

Chinese documentation: [README.zh.md](README.zh.md)

> 📖 [Harness AI Coding Tutorial (Chinese)](docs/ai-coding-tutorial.zh.md): a hands-on walkthrough from "why engineering" to running one non-trivial change with real commands.

> 🎞️ [Harness Engineering Kit Overview deck (Chinese, 32 slides)](presentations/Harness-Engineering-Kit-全局导览.pptx): a full Why → What → How → Grow → Use tour with RAM/RAD worked examples. Regenerate with `python3 presentations/build_hek_deck.py`.

## Installed layout

Everything Harness installs, other than `openspec/`, lives under a single `.hek/`
directory. Uninstalling is one directory, and the rest of the repository is never
written to:

| Directory | Owner | Upgrade behaviour |
|---|---|---|
| `.hek/kit/` | Harness | Replaced wholesale |
| `.hek/fitness/` | Shared | Harness-seeded controls are replaced; checks the project added are left alone |
| `.hek/project/` | Project | Never overwritten |
| `.hek/context/` | Project | Never overwritten |
| `.hek/state/` | Generated | Receipts, lessons, and other run output |

`openspec/` stays at the repository root: OpenSpec resolves its own root from the
working directory, and the Skills it generates hardcode root-relative paths.
`hek init` migrates a pre-0.6 installation into this layout. It relocates and
deletes only inside the superseded `docs/methodology/` tree, preserves any
destination that already exists, keeps files edited between planning and applying,
and lists every human follow-up — see [Versioning and Upgrades](docs/versioning.md).

## Architecture

| Layer | Owns | Must not own |
|---|---|---|
| `AGENTS.md` / `CLAUDE.md` | Native authority adapter, safety, Skill route, requirement reflection | Commands, module maps, full methodology |
| `.hek/project/agent-policy.yaml` | Canonical project facts, commands, permissions, referenced paths | Task-specific design |
| `.hek/context/ai.json` | Compact machine-readable project map and routes to detailed context | Commands, policies, invariants, or detailed rules |
| `.hek/context/**/AI.md` | Local responsibilities, boundaries, navigation, local verification | Authority over native instructions or policy |
| `engineering` Skill | Task routing, lifecycle orchestration, evidence and fallback | Project conventions already defined above |
| Backend/frontend/fullstack profiles | Design and verification specialization | Independent lifecycle or command |

Authority is fixed: system/developer/user → native instruction hierarchy → `.hek/project/agent-policy.yaml` → `.hek/context/ai.json` → selected path `AI.md` → profile defaults.

Before code changes, `resolve_context.py` turns target paths and explicit `read_when` keywords into one fail-closed load order. Root context is mandatory; indexed ancestor `AI.md` files load before child details.

`context_cache.py` derives a stable digest for that exact load order and records provider `hit`, `miss`, or `bypass` outcomes. The long-task reference benchmark enforces a measured target of at least 99.5%; it does not modify host Agent settings or claim provider behavior without telemetry.

`.hek/fitness/**` is a protected control plane. Project Agents may read and execute it but may not modify it; every non-bootstrap, non-syntax-repair change requires external human approval bound to the complete change digest, with no size exemption.

## Lifecycle

```text
Explore → Propose → Apply → Verify → Sync → Archive
```

The exact artifacts, gates, states, drift transitions, and production extension are defined once in [Canonical Change Lifecycle](core/change-lifecycle.md). Backend RAM and frontend RAD finish during Explore/Propose; Apply consumes the approved contract.

Design first produces an implementation-ready developer review packet: architecture and relationship topology, runtime flows, responsibility boundaries, interfaces/data, cross-cutting qualities, delivery/rollback, decisions and alternatives, verification traceability, risks, and numbered confirmation items. `check_design.py` enforces the structure, and explicit developer confirmation is required before approval. See [Implementation-Ready Design Review](core/design-review.md).

OpenSpec `tasks.md` is the sole task definition and progress source. Engineering records `execution-evidence.json` for checked tasks, including ownership, verification, changed files, integration order, and any parallel/sequential execution choice. See [Task Evidence](core/task-orchestration.md).

OpenSpec is the lifecycle owner. Engineering calls its native `openspec-*` Skills and CLI directly, then attaches governance evidence with `governance.json`; there is no second lifecycle or dispatcher. See [OpenSpec Integration](core/openspec-orchestration.md).

Installed root adapters automatically route non-trivial implementation, bug-fix,
refactoring, API, database, and UI requests to the project-local `engineering`
Skill. Users do not need to type `/engineering`; explicit invocation remains a
valid override. This contract is installed for Claude, Codex, OpenCode, Cursor,
Gemini, and Trae in each platform's native project Skill directory.

If Apply is interrupted, resume the native OpenSpec Apply workflow after checking `openspec status --change <id> --json`; Engineering only verifies that execution evidence matches OpenSpec's checked tasks.

Production delivery extends—not replaces—the Engineering lifecycle. A production-scoped change cannot archive until its linked production record is `CLOSED` with observability, staged rollout, stop conditions, rollback, and audit evidence.

Self-Refine is an optional or Profile-required inner loop for draft and implementation quality: `Generate → Self-Critique → Refine → Re-check`. It produces auditable evidence without replacing approval, deterministic gates, or production controls. See [Self-Refine Feedback Loop](core/self-refine.md).

Requirement Reflection is the response-level gate: before sending a task answer or taking a side effect, the Agent checks whether the request is clear, consistent with repository evidence, and authorized. Ambiguity or conflict pauses consequential work, asks for focused confirmation, and includes the recommended plan. See [Requirement Reflection and Clarification](core/requirement-reflection.md).

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

Claude Code, Codex, OpenCode, Cursor, and Gemini CLI are supported. WorkBuddy and Trae Work are supported through a manual handoff because they do not expose a stable CLI contract. For scripts or explicit selection:

```bash
npx --yes --package github:8425334/harness-engineering-kit hek init --agent codex --open --yes
npx --yes --package github:8425334/harness-engineering-kit hek init --agent opencode --open --yes
npx --yes --package github:8425334/harness-engineering-kit hek init --direct --yes
npx --yes --package github:8425334/harness-engineering-kit hek agents
npx --yes --package github:8425334/harness-engineering-kit hek init --plan --json
npx --yes --package github:8425334/harness-engineering-kit hek doctor --json
npx --yes --package github:8425334/harness-engineering-kit hek repair --yes
npx --yes --package github:8425334/harness-engineering-kit hek handoff --agent workbuddy
npx --yes --package github:8425334/harness-engineering-kit hek handoff --agent trae-work --json
npx --yes --package github:8425334/harness-engineering-kit hek uninstall --plan --json
npx --yes --package github:8425334/harness-engineering-kit hek uninstall --yes
npx --yes --package github:8425334/harness-engineering-kit hek uninstall --yes --keep-project-facts
```

### Workspace federation

Several independent repositories can cooperate without a central repository. Each unit commits `.hek/project/identity.yaml`, and the group view is projected on demand:

```bash
npx --yes --package github:8425334/harness-engineering-kit hek init --unit-id backend-api --yes
npx --yes --package github:8425334/harness-engineering-kit hek workspace discover --root .. --json
npx --yes --package github:8425334/harness-engineering-kit hek workspace verify --root .. --json
npx --yes --package github:8425334/harness-engineering-kit hek workspace context src/api/order.ts --json
npx --yes --package github:8425334/harness-engineering-kit hek workspace guard --path src/api/order.ts --session-root . --json
npx --yes --package github:8425334/harness-engineering-kit hek workspace exec backend-api -- hek check
npx --yes --package github:8425334/harness-engineering-kit hek workspace compat --contract backend-api-http --json
npx --yes --package github:8425334/harness-engineering-kit hek workspace graph --json
npx --yes --package github:8425334/harness-engineering-kit hek workspace status --root .. --json
```

`discover` and `verify` report units, contract edges and diagnostics as JSON and exit 2 when blocked, and `status` answers which unit is not onboarded and which consumer's declared range no longer accepts its provider's published version. `guard` decides whether a write target belongs to the current session from Git facts alone, so a nested unit or a sibling repository is blocked before any code is written. Engineering-level nesting is no longer supported; the split migration may use a one-off, time-boxed waiver, but `verify` keeps reporting blocked until the structure is actually split. Each participating unit owns its own OpenSpec change and spec — when A, B and C participate there are three local specs linked through `governance.json.workspace.related_changes`, and the workspace root never owns a spec. See [Workspace Federation](core/workspace-federation.md).

For a desktop Agent without a CLI, first install the project controls with `hek init --direct --yes`, then run `hek handoff --agent workbuddy` or `hek handoff --agent trae-work`. Open the project in that Agent, copy the generated prompt, and let it read the repository's `AGENTS.md`/`CLAUDE.md` and `.hek/project/agent-policy.yaml`. `handoff` never launches an unknown desktop application and never writes project files.

Interactive `init` asks for the install scope first (full or lightweight, chosen with the arrow keys when `--tier` is not given), then opens the selected Agent and lets that Agent perform onboarding. The selected Agent receives only its native root adapter (`CLAUDE.md` for Claude Code, `GEMINI.md` for Gemini CLI, and `AGENTS.md` for Codex/OpenCode and compatible Agents) and its matching project Skill. Pick the skip entry in the agent menu for the compatibility deterministic flow, which installs all supported adapters, and it falls back automatically when no agent is installed. Non-interactive runs never launch an external process unless `--open` is supplied, and `--open` there requires `--agent`/`HEK_AGENT`. `--json` switches to machine-readable output: it never opens an agent and never prompts — without `--yes` init prints the read-only plan and exits 2; with `--yes` it applies, checks, and prints one JSON receipt (including an `errors` receipt when apply fails and rolls back). Use `HEK_AGENT` instead of `--agent`, or `--prompt` to customize the first prompt sent to terminal agents (prompts are delivered as a single line so Windows `cmd.exe` cannot truncate them). The default prompt understands and answers directly in the user's language without a Chinese→English→Chinese translation pass. Static rules form a stable prefix, while project paths, tier, Agent, and authorization stay in the dynamic suffix for better context-cache reuse.

A fresh project's placeholders must be filled from real repository facts before the post-init check passes, so an unattended `init --direct --yes` on a fresh project installs the scaffolding and then intentionally exits 2; upgrade runs on an already-configured project pass directly. Use `--no-check` for scaffold-only automation, or open an Agent (`--agent <id> --open --yes`) to complete the fill-and-check loop after the deterministic install.

`hek init` is Agent-driven: it asks for the install scope, selects an installed Agent, opens that Agent's CLI in the resolved project root, and passes the Kit path plus the onboarding contract and selected Agent target. The Agent reads project facts, generates the read-only plan, asks for confirmation, fills project-specific values, applies the canonical script, and runs deterministic checks. Tier 1 (lightweight) installs the core control plane plus the minimal staged Fitness executor and SDD sync rule required by lifecycle gates; the default Tier 2 (full) additionally installs the complete Fitness rule set and lesson memory. Each run writes `.hek/state/onboarding.json` with the source version, file digests, created/updated/preserved files, and verification result. Use `--direct` only when a headless compatibility install is explicitly wanted; it ignores `--agent` and `HEK_AGENT` and installs all supported adapters.

Version-aware upgrades compare the installed `.hek/VERSION` with the Kit version, synchronize all canonical resources for lower-to-higher upgrades, block downgrades, and report any release-specific migration review. See [Versioning and Upgrades](docs/versioning.md).

`hek uninstall` reverses onboarding. It stays read-only until confirmed with `--yes` (or `--apply`), reads the `.hek/state/onboarding.json` receipt, and deletes only the assets Harness installed whose bytes still match the recorded digests. Files the install preserved, project-owned facts, files edited afterwards, and symlinked targets stay in place and are reported, and directories that become empty are pruned. Each apply writes `.hek/state/uninstall.json`. Use `--keep-project-facts` to also retain `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`, `ai.json`, `AI.md`, `agent-policy.yaml`, `profile.yaml`, and `openspec/config.yaml`; `--json` prints the machine-readable plan (without `--yes`, exit 2) or the receipt. When no receipt exists it falls back to removing only files that are still byte-identical to the Kit source, and anything it cannot verify is kept.

The check fails for an oversized or structurally invalid `ai.json`, unindexed or oversized `AI.md`, missing policy, placeholders, broken referenced paths, invalid task graphs/execution evidence, invalid profiles, missing Skill resources, stale installed Skill content, or unsupported platform adapters. The Engineering Skill is installed and checked for Claude Code, Codex, OpenCode, Cursor, Gemini, and Trae. The legacy `ramer`, `fe-engineering`, and `multi-agent` entries are intentionally not supported.

`hek doctor` and `hek repair` handle a broken conversation-time environment. `doctor` is a read-only diagnosis; `repair` prints the same plan and applies it after `--yes` (or `--apply`). They cover an `engineering` Skill that is missing or stale for the active Agent, a Python runtime or installed control script that is unusable, and a control plane that is incomplete or drifted from the Kit. Repair restores only canonical Kit resources, recreates missing control-plane directories, re-syncs the Skill tree and the OpenSpec lifecycle Skills when their CLI is available, and is idempotent per operation. It never rewrites existing project-owned facts, never installs interpreters or packages, never rewrites an existing `.hek/fitness/**` baseline, never downgrades an installation, and never writes outside the project root; anything that needs a human is reported as a `manual` finding with its exact remedy. The Agent scope comes from `--agent`, then the onboarding receipt, then only Skill trees that already exist. Each apply writes `.hek/state/repair.json`. In an installed project the same engine runs from `.hek/kit/scripts/repair.py`, defaulting `--source-root` to the path recorded by onboarding.

Resolve task context with the installed project controls. See the [CLI Onboarding Playbook](templates/engineering/references/onboarding.md) for the execution contract.

## Change Controls

```bash
openspec new change add-capability --schema harness-engineering
python3 .hek/kit/scripts/init_governance.py add-capability \
  --title "Add capability" --mode fullstack --owner team \
  --trigger explicit-selection

python3 .hek/kit/scripts/approve_design.py openspec/changes/add-capability \
  --actor reviewer --source pull-request --approval-id PR-123

openspec status --change add-capability --json
openspec validate add-capability --type change --strict --no-interactive
```

Use `check_phase.py` for governance gates, `check_design.py` for the implementation-ready design packet, `check_execution.py` for OpenSpec task evidence, `record_skill_event.py` for explicit fallback/intervention events, and `skill_metrics.py` for structured adoption metrics.

Use `preflight_lessons.py` before Explore closes, `record_failure.py` for Fitness/test/diff/production failures, `create_lesson_candidate.py` to propose reusable prevention, `retrieve_lessons.py` to inspect active lessons, and `approve_lesson.py` to activate an externally approved lesson.

## Canonical Documents

- [Harness AI Coding Tutorial (Chinese)](docs/ai-coding-tutorial.zh.md)
- [Harness Architecture](core/harness-engineering.md)
- [Change Lifecycle](core/change-lifecycle.md)
- [Implementation-Ready Design Review](core/design-review.md)
- [SDD Workflow](core/sdd-workflow.md)
- [Governance](core/methodology-governance.md)
- [Self-Refine Feedback Loop](core/self-refine.md)
- [Requirement Reflection and Clarification](core/requirement-reflection.md)
- [Self-Repair and Runtime Integrity](core/self-repair.md)
- [Task Graph and Parallel Execution](core/task-orchestration.md)
- [Project Lesson Memory](core/lesson-memory.md)
- [Backend Profile](core/backend-profile.md)
- [Frontend Profile](core/frontend-profile.md)
- [Fullstack Profile](core/fullstack-profile.md)
- [Production Controls](templates/production/README.md.template)
- [Transplant Guide](TRANSPLANT.md)

`manifest.yaml` is a Harness availability contract, not a claim that every platform has a native manifest format. Platform auto-selection must be observed at runtime; deterministic installation and resource integrity are verified by `verify_skill.py` and `smoke_test_skills.py`.

## Verification

Run the complete release-facing verification locally:

```bash
npm run verify
```

This covers the Node CLI, Python control scripts, an install-and-run test of the generated npm package, the Engineering Skill source contract, and the backend/frontend/fullstack lifecycle smoke test. CI runs the unit and package-consumer tests on Linux, macOS, and Windows, including the minimum supported Node.js 18 release.
