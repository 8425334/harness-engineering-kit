# Harness Engineering

Harness Engineering is the engineering system for AI Agents — not a single tool, but a set of patterns that make the codebase an Agent-readable, verifiable, and correctable runtime environment.

## Universal Principles

Harness Engineering's core model:

```
         Feedback Loop
             ▲
             │
System Readability ─── Defense Mechanism ─── Automated Feedback
```

1. **System Readability**: Make the repo structure understandable by AI — CLAUDE.md, path documents, module diagrams
2. **Defense Mechanism**: Constrain the AI's action space — Fitness rules, architecture boundary checks, permission controls
3. **Feedback Loop**: Enable the AI to self-correct — compile errors, test results, fitness reports

---

## Component 1: CLAUDE.md — AI Entry Configuration

`CLAUDE.md` (or `AGENTS.md`) is the repo's AI entry point. It's the first document the AI Agent reads when entering the project.

### Six Mandatory Sections

| Section | Content | Why Required |
|---------|---------|-------------|
| **Mandatory Workflow** | Project development cycle definition (e.g., RAMER cycle) | Agent needs to know "what to do first" |
| **Architecture Overview** | Module dependency diagram (which module can depend on which) | Agent needs to know boundaries |
| **Build & Run Commands** | Exact commands for compile, test, package | Agent needs fast feedback loops |
| **Key Conventions** | Domain-specific patterns (e.g., Entity Quartet) | Agent needs to know project-specific conventions |
| **SDD Reference** | Pointer to SDD process documentation | Agent needs to know change workflow |
| **Fitness Gate** | Quality gate description and invocation | Agent needs to know completion conditions |

### Writing Principles

- Entry points matter more than explanations — guide the Agent to the right place, don't make it understand the entire project
- Exact commands beat descriptive instructions — "run `mvn -pl my-service -am compile -q`" beats "compile the project"
- Module dependency diagrams in ASCII art — clear at a glance for both Agent and human

---

## Component 2: Path Document System (AI.md + ai.json)

Path documents are directory-level context guides. When the AI Agent needs to modify files in a directory, it first reads that directory's path documents.

### Dual-File Pattern

| File | Format | Purpose |
|------|--------|---------|
| `AI.md` | Markdown | Human-readable narrative guide |
| `ai.json` | JSON | Machine-readable structured constraints |

Both are semantically identical, just in different formats. Fitness rules check their synchronization.

### AI.md Eight Standard Sections

1. **Scope** — Which directories does this document govern
2. **Directory Responsibilities** — What this directory is responsible for
3. **Modifiable Scope** — What changes are allowed
4. **Prohibitions** — What must never be done
5. **Dependency Constraints** — What it depends on, what depends on it, allowed/forbidden dependency directions
6. **Performance Requirements** — Query, IO, cache, concurrency constraints
7. **Testing Requirements** — What changes need tests, test types
8. **Delivery Notes** — What must be synced on change (SQL scripts, config, docs)

### ai.json Structure

```json
{
  "$version": "1.0",
  "scope": "Current directory and subdirectories, unless overridden by child AI.md",
  "responsibilities": ["List of this directory's responsibilities"],
  "allowed": ["List of allowed operations"],
  "forbidden": ["List of forbidden operations"],
  "dependencies": {
    "allow": [],
    "deny": [],
    "rules": ["List of dependency rules"]
  },
  "performance": ["Performance constraints"],
  "testing": ["Testing requirements"],
  "delivery": ["Delivery checklist items"],
  "ext": {}
}
```

### Priority Chain

When multiple path documents cover the same directory:

```
Nearest ai.json > Nearest AI.md > Parent AI.md > Root AI.md > AGENTS.md
```

**Child directory documents can refine parent rules but cannot violate them.** When local rules conflict with global rules, prioritize architecture consistency and boundary stability.

### Which Directories Should Have Path Documents

- Repository root
- Top-level module directories
- Complex business module directories
- Directories with special boundaries, rules, or performance sensitivity

### New Directory Rule

When creating a new non-trivial directory, create `AI.md` first, then add code.

---

## Component 3: Skill Workflow Automation

Skills are reusable workflow scripts triggered via slash commands. Common operations:

| Skill | Purpose |
|-------|---------|
| `propose` | Create change proposal + generate full artifact set |
| `apply` | Implement step by step per task list |
| `sync` | Sync delta specs to main spec repository |
| `archive` | Archive completed change |
| `explore` | Exploratory thinking, clarify requirements |

Skills make workflows independent of team memory — every execution is consistent and repeatable.

### Mandatory Skills

All projects must configure 3 foundational skills. See `docs/methodology/core/mandatory-skills.md`:

| Skill | Category | Responsibility |
|-------|----------|---------------|
| OpenSpec | SDD Workflow | Change lifecycle management (/opsx:*) |
| Superpowers | Reference System | Long-term design decisions & spec references |
| Codegraph | Code Intelligence | Symbol search, call chain tracing, impact analysis |

Missing any one skill degrades the Agent's capabilities. Must be verified during Tier 1 of init/transplant.

---

## Component 4: Persistent Memory System

AI Agents need to remember user preferences, project context, and feedback across sessions.

### Four Memory Types

| Type | What It Stores | Example |
|------|---------------|---------|
| **user** | User role, preferences, knowledge background | "User is a senior backend dev, less React experience" |
| **feedback** | Corrections and confirmations | "Don't mock the database — caused a production incident last time" |
| **project** | Ongoing work, goals, decisions | "Merge freeze next Thursday, non-critical PRs on hold" |
| **reference** | Pointers to external systems | "Bugs tracked in Linear project INGEST" |

### Memory File Format

```markdown
---
name: <name>
description: <one-line description>
type: user | feedback | project | reference
---

<content>
```

### What NOT to Store as Memory

- Code patterns, architecture conventions (belong in code or CLAUDE.md)
- Git history (`git log` is the authoritative source)
- Debug solutions (the fix is in the code, context is in the commit message)
- Temporary task state (use task tracking, not memory)
