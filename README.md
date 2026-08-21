# AI-Assisted Development Methodology

A complete engineering methodology for integrating AI Coding Agents into the software development lifecycle. Stack-agnostic, scale-adaptive.

> **Language**: [中文文档](README.zh.md) | English

---

## Quick Start

Deploy this methodology into a new project in two steps:

### Step 1: Run the Init Script

Open the terminal in **Claude Code** / **Codex** / **Cursor** and run:

```bash
bash docs/methodology/scripts/init.sh --tier 1
```

The script handles file copying and directory creation (idempotent — safe to re-run).

### Step 2: Let the Agent Complete Configuration

In the same session, tell the agent:

```
Fill the {{placeholders}} in CLAUDE.md and openspec/config.yaml based on
the actual project. Draw the module dependency diagram, fill in build
commands and conventions.
```

The agent will:
1. Read the project structure (`package.json`, `pom.xml`, directory tree, etc.) to auto-detect the tech stack and build commands
2. Replace all `{{PLACEHOLDER}}` instances in `CLAUDE.md` and `openspec/config.yaml`
3. Draw a module dependency diagram (ASCII art)
4. Verify mandatory skill availability
5. Run `--check` to confirm completeness

### Common Commands

```bash
bash docs/methodology/scripts/init.sh --tier 1     # Minimum viable (recommended start)
bash docs/methodology/scripts/init.sh --tier 2     # Add Fitness quality gate
bash docs/methodology/scripts/init.sh --tier 3     # Add RAMER Agent + CI integration
bash docs/methodology/scripts/init.sh --check      # Verify current setup status
bash docs/methodology/scripts/init.sh --dry-run    # Preview without modifying
```

| Tier | Time | Script Creates | Agent Completes |
|------|------|---------------|-----------------|
| 1 | 5 min | CLAUDE.md + OpenSpec + Superpowers + mandatory-skills + fe-engineering | Fill placeholders, module diagram, build commands, tech stack |
| 2 | +10 min | Fitness scripts + rules + SDD docs + root path document | Replace fitness parameters, add conventions |
| 3 | +15 min | RAMER Agent + CI hints | Configure CI pipeline, E2E tests |

> The script is **idempotent** — re-running won't overwrite existing files. For detailed manual steps, see [TRANSPLANT.md](TRANSPLANT.md).

---

## What This Is

This directory contains a proven AI-assisted development methodology built from real-world project experience. Four core components:

| Component | Document | Description |
|-----------|----------|-------------|
| **SDD** (Spec-Driven Development) | `core/sdd-workflow.md` | Spec-first development process — all non-trivial changes require specs before implementation |
| **Fitness** (Quality Gate) | `core/fitness-framework.md` | Tiered quality check system defining AI Agent "completion conditions" |
| **Harness Engineering** | `core/harness-engineering.md` | AI Agent engineering system: entry config, path documents, skills, memory, compaction preservation |
| **Mandatory Skills** | `core/mandatory-skills.md` | 3 required Agent skills: OpenSpec, Superpowers, Codegraph |

On top of these components sit unified development methodologies:
- **Backend**: **RAMER Cycle** (`core/ramer-cycle.md` + `core/ramer-agent.md`) — abstraction-first, contract-before-implementation, fitness gate
- **Frontend**: **FE-Engineering RADIR Workflow** (`core/frontend-engineering.md`) — 4 iron rules, component decomposition
- **Coordination**: **Multi-Agent Parallel Mode** (`core/multi-agent.md`) — contract-first dual-agent execution for frontend-backend tasks
- **General**: **Abstraction-First Modeling** (`core/abstraction-first.md`), **DDD Modeling** (`core/ddd-modeling.md`), **Debug Log Discipline** (`core/debug-log-discipline.md`)

## Who Needs This

- **Tech Leads** — Elevate AI coding from "individual skill" to "team engineering capability"
- **Developers** — Quickly establish an AI-assisted development workflow in new projects
- **Teams** — Need a replicable, verifiable methodology portable across projects

## Directory Structure

```
docs/methodology/
├── README.md                           # English entry (this file)
├── README.zh.md                        # Chinese entry
├── LICENSE                             # MIT
├── CONTRIBUTING.md                     # Contribution guide
├── CHANGELOG.md                        # Version history
├── VERSION                             # 0.1.0
├── .github/                            # Issue/PR templates
├── scripts/
│   └── init.sh                         # One-click init script
├── core/                               # Universal principles (English, stack-agnostic)
│   ├── ramer-cycle.md                  # RAMER Cycle
│   ├── ramer-agent.md                  # RAMER Agent automation
│   ├── abstraction-first.md            # Abstraction-first modeling
│   ├── ddd-modeling.md                 # Domain-Driven Design modeling
│   ├── debug-log-discipline.md         # Debug log discipline
│   ├── frontend-architecture.md        # AI-native frontend architecture (AIDM + FDD + RSC)
│   ├── frontend-engineering.md         # Frontend engineering capability model (4 iron rules + component decomposition)
│   ├── multi-agent.md                  # Multi-agent parallel mode (frontend-backend coordination)
│   ├── mandatory-skills.md             # Mandatory Skill configuration
│   ├── sdd-workflow.md                 # SDD workflow
│   ├── fitness-framework.md            # Fitness quality gate
│   └── harness-engineering.md          # Harness engineering
├── i18n/
│   ├── glossary.md                     # Terminology reference (zh ↔ en)
│   └── zh/core/                        # Chinese translations (12 files)
├── examples/
│   └── coil-backend-api/               # Adaptation example: Java Spring Boot + Vue 3 monorepo
└── templates/                          # Copy-and-use templates
    ├── CLAUDE.md.template              # AI entry config
    ├── openspec-config.yaml.template   # SDD config
    ├── sdd-readme.md.template          # SDD process doc
    ├── path-document.md.template       # Path document (AI.md + ai.json)
    ├── fitness/                        # Fitness checks, executable self-tests, Java AST scanner, rules
    ├── ramer/                          # RAMER Agent templates
    ├── multi-agent/                    # Claude/Codex multi-agent parallel skill template
    ├── compaction/                     # Claude hooks + explicit Codex preservation fallback
    ├── fe-engineering/                 # Frontend engineering integration templates
    └── mandatory-skills/               # Mandatory Skill declaration templates
```

## Core Principles

1. **Documentation first, design second, implementation last** — Don't touch code without reading path documents
2. **Contract-first** — Define interfaces/DTOs, confirm design, then implement
3. **DDD as skeleton** — Strategic (bounded context) sets boundaries; tactical (aggregates/entities/events) sets structure
4. **Composition over inheritance** — Inheritance depth ≤ 1, prefer DI + composition
5. **Polymorphism over branching** — Nested `if/else` ≥ 2 or `switch` ≥ 3 → Strategy/Factory/Handler
6. **Three-phase debug logging** — Log after coding, self-check expectations via tests, clean up temporary logs
7. **Completion conditions must be executable** — Rules in the repo, readable by humans, executable by scripts
8. **Frontend-backend parallel execution** (`core/multi-agent.md`) — After contract definition, dual agents develop in parallel, then merge and verify
9. **Complete Agent Skill configuration** — Agent must have OpenSpec, Superpowers, and Codegraph; missing any means degraded capability

## Relationship with VibeCoding

This methodology focuses on the **engineering process layer** (SDD + Fitness + Harness), complementary to VibeCoding (code generation discipline layer):

- VibeCoding defines **how to write good code** (PACE routing, RIPER-7 phases, state persistence)
- This methodology defines **how to organize engineering** (change workflow, quality gates, Agent system configuration)

The two can be adopted independently or combined.
