# SDD Workflow (Spec-Driven Development)

SDD is a spec-driven development process: non-trivial changes must be documented as specs before entering implementation. It solves the fundamental problems of AI Agent development — "where to start" and "when is it done."

## Universal Principles

### Five-Phase Workflow

```
Explore (optional) → Propose → Apply → Sync → Archive
```

| Phase | Responsibility | Output |
|-------|---------------|--------|
| **Explore** | Think through the problem, clarify requirements, explore solutions | No mandatory output (optional step) |
| **Propose** | Create change proposal, generate full artifact set | proposal + specs + design + tasks |
| **Apply** | Implement step by step per task list | Code changes + tests |
| **Sync** | Merge delta specs into main spec repository | Updated `specs/` directory |
| **Archive** | Archive completed change | Archive directory `archive/YYYY-MM-DD-<name>/` |

### Four Artifact Types

Each SDD change generates artifacts in dependency order:

| Artifact | Order | Question It Answers |
|----------|-------|---------------------|
| **Proposal** | 1st | Why do it? What to do? What's affected? |
| **Specs** | 2nd | What should the system do? What are the specific scenarios for each requirement? |
| **Design** | 3rd | How to implement? What are the technical decisions? Why X not Y? |
| **Tasks** | 4th | How many steps? What to do in each? What's the dependency order? |

### Spec Writing Conventions

- Requirements use **SHALL** / **MUST** (not should/may)
- Every requirement has at least one scenario: `#### Scenario: <name>` + `WHEN/THEN`
- Requirements organized by capability in folders
- Scenarios are the source of future test cases

### Task Grouping Order

Tasks must be ordered by architecture dependency (each task only depends on previous ones):

```
1. Contract Layer (Interfaces / DTOs / Entities)
2. Domain Logic Layer (Services / Support)
3. API Layer (Controllers)
4. Data Access Layer (Mappers / XML)
5. Database Migration (SQL)
6. Verification (Compile + Test + Fitness Gate)
7. Frontend (Components + API files)
```

### When NOT to Use SDD

| Change Type | Use SDD? |
|-------------|----------|
| New feature / new domain object | **Yes** |
| Cross-module modification | **Yes** |
| Bug fix / single-line change | **No** (go directly RAMER + fitness) |
| Small refactoring | **Depends on scope** |

**Decision criterion**: If the change involves only a single file, adds no new domain objects, and doesn't change cross-module contracts, you can skip SDD.
