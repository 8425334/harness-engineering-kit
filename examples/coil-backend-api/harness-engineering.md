# harness-engineering.md — coil-backend-api Adaptation

## CLAUDE.md Instance

This project's `CLAUDE.md` (~135 lines) contains:
- 5-step RAMER cycle with detailed instructions
- Module dependency diagram (ASCII art showing `ruoyi-admin → coil-* → ruoyi-common` chain)
- Exact build commands (single-module compile, single-class test, full package)
- Entity Quartet pattern detail table
- Key architectural patterns (Dispatch Lifecycle, Domain Events, Support Classes, WMS Integration)
- SDD 5-step workflow + commands
- Fitness gate invocation and check item list

## Path Document Distribution

This repository has 100+ `ai.json`/`AI.md` pairs covering:
- Root (global architecture constraints)
- Every top-level module (`coil-app/`, `coil-service/`, `ruoyi-modules/`)
- Key sub-modules and business directories

## Memory System

Memory is stored at `~/.claude/projects/<project-path>/memory/`, managed via `MEMORY.md` index file.

## Skills

This project provides through Claude Code Skills system:

**Mandatory Skills (all projects must have):**
- OpenSpec — `/opsx:explore`, `/opsx:propose`, `/opsx:apply`, `/opsx:sync`, `/opsx:archive` — SDD change lifecycle
- Superpowers — `docs/superpowers/plans/` + `docs/superpowers/specs/` — long-term reference docs
- Codegraph — MCP code intelligence tool (explore/search/impact)

**Workflow Skills:**
- `/opsx:continue` — continue unfinished apply
- `/ramer` — RAMER full-auto design-implement cycle (READ→ANALYZE→MODEL→confirm→EXECUTE→REVIEW), supports CRUD/DDD/Hexagonal/Hybrid architecture
- `/fe` — FE-Engineering RADIR workflow (READ→ANALYZE→DECOMPOSE→IMPLEMENT→VERIFY), auto-detects tech stack

**Auxiliary Skills:**
- review, security-review, etc.
