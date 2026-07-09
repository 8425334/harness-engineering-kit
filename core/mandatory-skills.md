# Agent Mandatory Skill Configuration

Defines the 3 foundational skills that every AI Coding Agent **must have** in a project. These skills are prerequisites for any non-trivial task — missing any one significantly degrades capability.

> When setting up a new project via `init` or Tier 1 transplant, ensure these 3 skills are configured. See each skill's "Verification" section for checking.

## 1. OpenSpec — SDD Change Lifecycle

### Responsibility

Manages the complete software change lifecycle: from requirements exploration, solution design, and spec definition through task decomposition and archival.

### Core Capabilities

| Command | Phase | Description |
|---------|-------|-------------|
| `/opsx:explore` | Explore | Requirements analysis, architecture thinking, solution comparison |
| `/opsx:propose` | Propose | Generate proposal + design + specs + tasks |
| `/opsx:apply` | Implement | Implement step by step per tasks |
| `/opsx:sync` | Sync | Delta specs → main specs |
| `/opsx:archive` | Archive | Complete change, archive to main spec repository |

### Applicable Scenarios

- New feature development
- Cross-module refactoring
- New domain object creation
- Any non-trivial change

### Configuration

The project root must have `openspec/config.yaml` defining schema, context, and rules. Template at `docs/methodology/templates/openspec-config.yaml.template`.

### Verification

```bash
ls openspec/config.yaml 2>/dev/null && echo "OK" || echo "MISSING: run openspec init"
openspec list --json 2>/dev/null && echo "OK" || echo "MISSING: openspec CLI not available"
```

### Degradation

When OpenSpec is unavailable, fall back to manual SDD (hand-write proposal/design/tasks files), but lose automated state tracking.

---

## 2. Superpowers — Long-Term Plans & Spec Reference

### Responsibility

Maintains the project's **long-term** reference documents: design decision records (ADR), persistent specs, architecture references. Complements OpenSpec's **temporary** change lifecycle.

### Core Capabilities

| Directory | Purpose | Lifecycle |
|-----------|---------|-----------|
| `docs/superpowers/plans/` | Design decision records, architecture plans | Long-term (project lifetime) |
| `docs/superpowers/specs/` | Persistent spec references | Long-term (updated as features evolve) |

### Division of Labor with OpenSpec

```
OpenSpec (temporary)                 Superpowers (long-term)
──────────────────                   ──────────────────────
Manages "how to do this change"      Records "why we did it this way"
proposal.md → archived after merge   plans/*.md → continuously maintained
specs delta → sync to main specs     specs/*.md → updated as features evolve
Change complete → archive            Key decisions post-archive → recorded in plans/
```

### Applicable Scenarios

- Record major architecture decisions (e.g., "why we chose approach A over B")
- Maintain specs that span multiple change lifecycles (e.g., domain model, API contracts)
- Store long-term context that AI Agents can reference

### Configuration

```bash
mkdir -p docs/superpowers/plans docs/superpowers/specs
```

### Verification

```bash
test -d docs/superpowers/plans && test -d docs/superpowers/specs && echo "OK" || echo "MISSING"
```

### Degradation

When Superpowers directory doesn't exist, long-term decision records are scattered across git commit messages or PR descriptions, making them hard to find.

---

## 3. Codegraph — Code Knowledge Graph

### Responsibility

Provides millisecond-level code intelligence: symbol search, call chain tracing, impact analysis. Replaces inefficient `grep + read` loops and is the core tool for AI Agent code understanding.

### Core Capabilities

| Tool | Purpose | Example |
|------|---------|---------|
| `codegraph_explore` | **Primary exploration tool** — understand area/flow/architecture | "how does driver dispatch work" → directly returns relevant source |
| `codegraph_search` | Quick symbol name lookup | `codegraph_search("AuthService")` → all matching locations |
| `codegraph_node` | Complete single symbol definition (with callers/callees) | View function signature + body |
| `codegraph_callers` | Who calls this symbol | Locate upstream dependencies |
| `codegraph_callees` | What this symbol calls | Trace downstream dependencies |
| `codegraph_impact` | Change impact analysis | Assess impact scope before refactoring |
| `codegraph_files` | Project file tree | Understand directory structure |

### Usage Principles

1. **Explore first, search second, grep last**: `codegraph_explore` typically answers 80% of code understanding questions in a single call
2. **Don't re-read**: When codegraph has already returned full source, don't use Read to re-read the same file
3. **Impact analysis before refactoring**: Run `codegraph_impact` before modifying any symbol referenced in multiple places

### Configuration

Codegraph is configured as an MCP Server in `settings.json`:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "npx",
      "args": ["@anthropic/codegraph-mcp-server"]
    }
  }
}
```

### Verification

```bash
# Check if codegraph is in MCP config
grep -r "codegraph" ~/.claude/settings.json ~/.claude/settings.local.json 2>/dev/null && echo "OK" || echo "WARN: codegraph MCP not found in settings"
```

### Degradation

When Codegraph is unavailable, fall back to `grep` + `Read` loops. Efficiency drops but functionality is not blocked. First-time use requires `codegraph init` to build the index.

---

## Skill Dependency Matrix

| Scenario | OpenSpec | Superpowers | Codegraph |
|----------|:--------:|:-----------:|:---------:|
| Bug fix | ○ | - | ● |
| New feature (single module) | ● | ○ | ● |
| New feature (cross-module) | ● | ● | ● |
| Refactoring | ● | ● | ● |
| Code review | - | - | ● |
| Architecture decision | - | ● | ● |
| New project init | ● | ● | ● |

> ● = Required &nbsp;&nbsp; ○ = Recommended &nbsp;&nbsp; - = Not needed

---

## New Project Integration

During `init` or Tier 1 transplant, check in order:

```bash
# 1. OpenSpec
test -f openspec/config.yaml || echo "TODO: openspec init"

# 2. Superpowers
test -d docs/superpowers/plans || echo "TODO: mkdir -p docs/superpowers/plans docs/superpowers/specs"

# 3. Codegraph
grep -r "codegraph" ~/.claude/settings.* 2>/dev/null || echo "TODO: add codegraph MCP to settings.json"
```

See `docs/methodology/TRANSPLANT.md` for complete Tier 1/2/3 transplant steps.
