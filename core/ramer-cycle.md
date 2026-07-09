# RAMER Cycle

RAMER is the mandatory workflow for AI-assisted development. These five phases must be completed before any non-trivial code change.

> **Automated execution**: RAMER is implemented as a fully automated Agent system (`/ramer` skill). See `ramer-agent.md`. This document defines RAMER's **principles and phase content**; ramer-agent.md is the **automated execution layer**.

## Universal Principles

```
[R] READ → [A] ANALYZE → [M] MODEL → [E] EXECUTE → [R] REVIEW
```

### R — READ (Load Context)

Before modifying any code, load context documents for the target path. The AI Agent cannot rely on guesses from training data — it must get real constraints from the current repository.

**Do:**
- Read path documents for the target directory (AI.md / ai.json)
- Read parent directory path documents, moving up to the root
- Extract responsibility boundaries, dependency constraints, and prohibitions
- Identify affected modules and cross-module concerns

**Don't:**
- Skip documents and jump straight to code
- Assume conventions from "similar projects" apply to the current one

### A — ANALYZE (Analyze Boundaries)

Understand the requirement, existing code, and module boundaries. Identify the change type (new feature / modification / fix), determine affected modules and cross-module dependencies.

**Do:**
- Determine change type and impact scope
- Identify cross-module coordination points (need Domain Events? need interfaces?)
- Decide whether full SDD process is needed or a quick fix is sufficient

**Don't:**
- Start designing without understanding boundaries
- Expand a local fix into an unrelated refactoring

### M — MODEL (Abstract Modeling)

**This is RAMER's most critical step.** Never start from concrete implementation. First translate the requirement through the abstraction layer:

```
Verbal Requirement → [ACL] → Domain Model (OO Contract) → Multi-Module Code
```

**Fixed coding order (contract-first):**
1. Define interfaces / abstract classes / DTOs in the owning module
2. Present the design, wait for confirmation (ensure Single Responsibility & Open/Closed compliance)
3. Only after confirmation, implement concrete classes (program to interface)

**Two iron rules:**
- **Composition over inheritance**: Inheritance depth ≤ 1, prefer DI + composition
- **Polymorphism over branching**: Nested if/else ≥ 2 layers or switch ≥ 3 branches → Strategy/Factory/Handler

### E — EXECUTE (Implement)

Implement concrete classes strictly according to the confirmed contract. Keep changes minimal and local.

**Do:**
- Program to interfaces
- Only modify what the current task needs
- Follow existing project patterns and naming conventions

**Don't:**
- Expand the scope of impact
- Mix in unrelated refactoring
- Break stable existing structures for "convenience"

### R — REVIEW (Verify)

Run quality gate, verify boundary compliance, check consistency.

**Do:**
- Run fitness gate (at minimum `--tier fast`)
- Verify module boundaries are not broken
- Check Mapper/XML/Entity three-way consistency (where applicable)
- Confirm whether path documents need updating
