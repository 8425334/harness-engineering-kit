# Changelog

All notable changes to the AI-Assisted Development Methodology will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] — 2026-09-05

### Changed
- Added the standalone Node.js `hek` CLI alias with interactive AI-agent selection, deterministic PATH detection, safe non-interactive behavior, and optional post-onboarding agent panel launch.
- Added conversational onboarding: `scripts/onboard.py` classifies fresh, partial, legacy, and current projects, presents a read-only plan, applies only after confirmation, preserves legacy entries, and records `docs/methodology/onboarding.json`. The old `init.sh` is now a compatibility forwarder.
- Tier 1 now installs the production control scaffold (`docs/methodology/production/README.md`, `policy.yaml`, and the change-record template) so the `agent-policy.yaml` reference resolves at every tier; Fitness gate scripts, Fitness rules, and lesson memory remain Tier 2.
- `hek init --json` is a real machine mode now: without `--yes` it prints the read-only plan and exits 2; with `--yes` it applies, checks, and prints one JSON receipt instead of silently skipping the install.
- Interactive `hek init` falls back to the deterministic flow when no AI agent is installed, and `0`/`skip` at the prompt declines agent-driven onboarding; invalid selections are retried before failing.
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
