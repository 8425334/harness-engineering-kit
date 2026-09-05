# Changelog

All notable changes to the AI-Assisted Development Methodology will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] — 2026-09-05

### Changed
- Added the standalone Node.js `hek` CLI alias with interactive AI-agent selection, deterministic PATH detection, safe non-interactive behavior, and optional post-onboarding agent panel launch.
- Added conversational onboarding: `scripts/onboard.py` classifies fresh, partial, legacy, and current projects, presents a read-only plan, applies only after confirmation, preserves legacy entries, and records `docs/methodology/onboarding.json`. The old `init.sh` is now a compatibility forwarder.
- Tier 1 now installs the production control scaffold (`docs/methodology/production/README.md`, `policy.yaml`, and the change-record template) so the `agent-policy.yaml` reference resolves at every tier; Fitness gate scripts, Fitness rules, and lesson memory remain Tier 2.
- `hek init --json` is a real machine mode now: without `--yes` it prints the read-only plan and exits 2; with `--yes` it applies, checks, and prints one JSON receipt instead of silently skipping the install.
- Interactive `hek init` asks for the install scope with an arrow-key menu (Tier 2 default), falls back to the deterministic flow when no AI agent is installed or the skip entry is chosen, and never produces an invalid selection.
- `--direct` fully disables agent launching and ignores `--agent`/`HEK_AGENT` with a notice; non-interactive `--open` without an agent selection is rejected.
- `hek` resolves the target project through the same plan step in every flow, so running from a subdirectory opens the Agent at the repository root, and the agent prompt uses the resolved Python executable (respecting `HARNESS_PYTHON`, with a Windows `py -3` fallback).
- `--list-agents` now works without a subcommand, and value options accept `--option=value`.
- Added project Lesson Memory: structured failure capture, reviewed lesson promotion, Explore preflight retrieval, and archive learning closure.
- Added a bounded, profile-controlled Self-Refine inner loop with auditable evidence and optional independent checking; it cannot replace approval or deterministic gates.
- Restored root `ai.json` as a strict, compact machine-readable context index capped at 4096 bytes; every maintained `AI.md` must be indexed.
- Defined `AI.md` as the detailed human- and machine-readable context layer, capped at 400 lines and forbidden from overriding native instructions or `agent-policy.yaml`.
- Added approval-bound `context-impact.json` and Review gates that require context updates when code changes responsibilities, boundaries, invariants, dependencies, contracts, verification, topology, routes, summaries, or entrypoints.
- Added deterministic context validation to installation, change initialization, every lifecycle phase, Fitness, and Skill guidance.
- Added fail-closed `resolve_context.py` assembly for target paths and `read_when` routes, with mandatory root context and parent-to-child detail loading.
- Protected `docs/fitness/**` from project-Agent changes with full-delta digest binding, narrow bootstrap/syntax-repair exemptions, and externally injected human approval.

### Fixed
- Onboarding receipts label newly created files as `created` and byte-identical syncs as `unchanged` instead of reporting every copy as `updated`.
- A failed `--apply` rolls back every file and workspace directory it created, not only previously existing files it overwrote.
- Agent launch arguments are quoted on Windows so prompts containing spaces are delivered intact.
- Retiring a lesson no longer bricks the Explore gate: non-active lessons with a valid status are skipped by retrieval and preflight instead of being reported as validation errors.
- `hek check` now prints the check outcome (`ONBOARDING CHECK PASSED/FAILED`) instead of a misleading read-only plan, and `--apply` prints a result summary with the receipt path.
- `--json` apply failures print the JSON receipt with an `errors` field instead of an empty stdout, and `--json` never prompts for confirmation or opens an agent (with an explicit notice when `--agent`/`--open` is ignored).
- Agent prompts are single-line on every platform so Windows `cmd.exe` cannot truncate the onboarding contract at a newline.
- Rollback resets rollout progress: after `ROLLED_BACK`, redeployment must restart from the first declared stage instead of skipping the stage that triggered the rollback; production closure accepts rolled-back-then-closed changes.
- `approve_design.py` refuses to overwrite an existing `approval.json` (a revised contract needs a new change or an audited removal) and records a `design.approved` event.
- `check_production_readiness.py` validates `audit_log` as a project-relative path, `rollout.stages` as a unique stage array, `schema_version`, `state`, boolean `technical_done`/`operational_done`, and a positive integer observation window.
- Lifecycle records reject non-object JSON with a clean `BLOCKED`/exit 2 instead of an `AttributeError` traceback, and non-UTF-8 artifacts fail the gate while still recording `phase.blocked`.
- `init_change.py` derives the project root only from the canonical policy location (no more `parents[2]` crash on shallow custom paths), keeps `--root` inside the project, and copies the profile/risk values from the project `profile.yaml`, which the phase gate now cross-checks.
- `skill_metrics.py` counts archived change workspaces (`openspec/changes/archive/<id>/`) and fails when the changes root does not exist.
- Audit JSON writes are atomic (temp file + rename) and serialized by a best-effort lock, so concurrent scripts cannot lose events or truncate `change.json`.
- The kit-only `smoke_test_skills.py` is no longer installed into target projects (where it could only fail) and reports a clear error when run outside a kit checkout.
- Onboarding no longer creates unused `docs/superpowers/` directories, and the orphaned `sdd-context-pack`/`sdd-impact-analysis`/`mandatory-skills` templates were removed from the package.
- Failure event ids normalize the UTC suffix correctly (`...Z`) and reuse a single timestamp for the id and the recorded `at`.
- Lesson validation requires `keywords` to be a non-empty string array and type-checks `source_events`/`rules`/`paths`, so malformed candidates are blocked instead of crashing `approve_lesson.py` or silently matching nothing.
- Review commands require an integer `exit_code`; JSON `false` no longer passes as a successful zero.
- `verify_skill.py` reports a single actionable error when its kit source is missing instead of a wall of missing-file errors.

## [0.2.0]

### Changed
- Replaced independent RAMER, FE-Engineering, and multi-agent workflows with one `engineering` Skill and backend/frontend/fullstack profiles.
- Established one lifecycle: Explore → Propose (Spec → Design → Approval) → Apply → Sync → Archive.
- Reduced root `AGENTS.md`/`CLAUDE.md` templates to native authority adapters; moved project facts to validated `agent-policy.yaml`.
- Consolidated duplicated context into supplemental path documents as an intermediate simplification.
- Added digest-bound approvals, structured review/sync/archive evidence, append-only events, and fail-closed state transitions.
- Linked production delivery to Engineering by `change_id`; production-scoped changes cannot archive before observation or rollback closure.
- Installed project Skills at `.claude/skills/engineering` and `.agents/skills/engineering`; removed Cursor and legacy entry compatibility.
- Made installation checks fail closed and added full backend/frontend/fullstack lifecycle smoke coverage.

## [0.1.0]

### Added
- Core methodology: RAMER cycle, abstraction-first modeling, DDD modeling, debug log discipline
- SDD (Spec-Driven Development) workflow and OpenSpec integration
- Fitness quality gate framework with 14 reusable rule dimensions, fail-closed pattern matching, and executable gate self-tests
- Harness engineering system: CLAUDE.md, path documents (AI.md + ai.json), agent skills, memory, and compaction preservation
- Mandatory skills declaration: OpenSpec, Superpowers, Codegraph
- Frontend engineering capability model: 4 iron rules, RADIR workflow, component decomposition
- Multi-agent parallel mode: contract-first, dual background agents (BE + FE)
- Java quality templates: parameter-object limit with Java 21 AST scanner, Mapper SQL/XML parity, documentation, magic values, and object mapping
- Claude automatic compaction hooks plus explicit Codex save/recovery fallback
- One-click init script with Tier 1/2/3 progression
- Portable templates for CLAUDE.md, OpenSpec config, fitness, RAMER agent, FE-engineering, mandatory skills
- Chinese translations in `i18n/zh/core/`
- Example adaptation: coil-backend-api in `examples/coil-backend-api/`
- Context capability & prompt caching: new core doc `core/context-capability.md` (Chinese mirror `i18n/zh/core/context-capability.md`) — byte-stable prompt-caching prefix invariant, five-dimension context capability model, glossary terms, and a CLAUDE.md template section
