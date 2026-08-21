# Multi-Agent Parallel Mode (Frontend-Backend Coordination)

When a task spans **both frontend and backend** code changes, sequential execution wastes wall-clock time. Dual-agent parallel execution — one Agent-BE following the **RAMER Cycle**, one Agent-FE following the **FE-Engineering RADIR Workflow** — divides the work cleanly at the API contract boundary and merges the results afterward.

> Companion Skill: `/multi-agent <requirement>` (`templates/multi-agent/SKILL.md.template`). It detects the task boundary, defines the shared contract, launches both background agents, and merges/verifies the two sides.

## 1. When to Use

- New business features (backend API + frontend page)
- Modifying existing features that touch both sides
- API contract changes (field additions/deletions/renames)
- Cross-module refactoring spanning both layers

**Single-side tasks must NOT enable parallel mode** — use the corresponding workflow directly (`/ramer` for backend, `/fe` for frontend).

## 2. Execution Architecture

```
User Requirement (frontend + backend)
       │
       ▼
┌─ Phase 0: Contract Definition (Main Agent)──────────────────┐
│                                                              │
│  1. Identify frontend/backend boundaries                     │
│  2. Extract shared data contract:                            │
│     API endpoint + HTTP method                               │
│     Request param fields + types                             │
│     Response fields + types                                  │
│     Enums/status codes                                       │
│  3. Output contract summary, confirm with user, then parallel│
│                                                              │
└──────────────────────────────────────────────────────────────┘
       │
       ├──────────────────────┐
       ▼                      ▼
┌─ Agent-BE ──────────┐  ┌─ Agent-FE ─────────────────┐
│ background          │  │ background                 │
│                     │  │                            │
│ RAMER: R→A→M→E→R   │  │ RADIR: R→A→D→I→V          │
│                     │  │                            │
│ Implement per       │  │ Implement per              │
│ contract:           │  │ contract:                  │
│ DTO/BO/VO          │  │ types/API wrappers         │
│ Controller/Service │  │ views/components           │
│ Mapper/XML         │  │ routes/i18n                │
│ fitness gate       │  │ typecheck + build gate     │
└────────────────────┘  └────────────────────────────┘
       │                      │
       └──────────┬───────────┘
                  ▼
┌─ Phase 2: Merge Verification (Main Agent)───────────────────┐
│                                                              │
│  1. Field alignment: backend response vs frontend types      │
│  2. Enum consistency: backend values vs frontend constants   │
│  3. Route sync: new pages registered in routes               │
│  4. Permission sync: button codes match backend permissions  │
│  5. Mismatch → fix → re-verify                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## 3. Phase 0 — Contract Definition (the Critical Step)

The contract is the foundation of parallel execution. It must be confirmed with the user **before** launching the two agents.

### 3.1 API Contract Template

```yaml
endpoints:
  - method: GET/POST/PUT/DELETE
    path: /api/xxx/xxx
    summary: endpoint purpose
    request:
      params:  # Query parameters
        - name: pageNum, type: int, required: true, desc: page number
      body:  # Request body fields
        - name: fieldName, type: string, required: true, desc: field description
    response:
      - name: id, type: long, desc: primary key
      - name: fieldName, type: string, desc: field description
    enums:
      - name: StatusEnum, values: [ACTIVE, INACTIVE, DELETED]
```

### 3.2 Detecting the Boundary

Detect from the project `CLAUDE.md` and directory structure:

- **Backend target dirs**: Java modules (e.g. `coil-service/`, `coil-app/`, `ruoyi-*`)
- **Frontend target dirs**: frontend project source (e.g. `coil-backend-ui/src/` or the framework-equivalent `src/`)
- **Contract sharing**: API type definition files, enum constant files

### 3.3 Human Confirmation

Present the contract and confirm with the user: API endpoint list, request/response fields, enum values. Only after confirmation do the two agents launch in parallel.

## 4. Phase 1 — Parallel Launch

After confirmation, launch both background agents simultaneously.

- **Agent-BE** (`general-purpose`): Prompt includes the RAMER cycle (`core/ramer-cycle.md` + `core/ramer-agent.md`), project architecture context from CLAUDE.md, contract field details, target dirs, and the fitness gate command.
- **Agent-FE** (`general-purpose`): Prompt includes the RADIR workflow + 4 iron rules (`core/frontend-engineering.md`), tech stack detected from `package.json`, contract field details, target dirs, and the typecheck + build gate commands.

### Launch Rules

1. Both agents start via `run_in_background: true`
2. Each executes independently, neither waits for the other
3. The main agent does **not poll** — it is notified automatically when both complete
4. Once both are done, the main agent enters merge verification

## 5. Phase 2 — Merge Verification

After both agents complete, the main agent cross-verifies:

| Check | Backend vs Frontend |
|-------|---------------------|
| Field alignment | Controller response fields vs frontend `types`; request params vs API call args; detect missing/misnamed fields |
| Enum consistency | Backend enum class values vs frontend constants; complete status-code mapping |
| Route sync | New pages registered in route config; menu config updated |
| Permission sync | Backend permission annotations vs frontend button permission codes |

**Fix loop**: On any mismatch → fix directly → re-verify. Mismatches that cannot be auto-fixed → list the diff and ask the user to resolve manually.

## 6. Degradation Strategy

| Scenario | Strategy |
|----------|----------|
| Sub-agent unavailable (quota/unreachable) | Sequential execution: implement the backend contract layer first, then the frontend presentation layer |
| Single-side task | Don't enable parallel; use the corresponding workflow directly |
| Contract confirmation rejected | Re-discuss requirements, adjust the contract, re-confirm |
| Contract change mid-implementation | Sub-agents coordinate changes through the main agent; both sides sync updates |

## 7. Relationship to Other Methodology

| Component | Document |
|-----------|----------|
| Backend cycle | `core/ramer-cycle.md` + `core/ramer-agent.md` |
| Frontend cycle | `core/frontend-engineering.md` (4 iron rules + component decomposition) |
| Contract-first | `core/abstraction-first.md` |
| Quality gates | `core/fitness-framework.md` (backend) + `core/frontend-engineering.md` §3 (frontend) |

## 8. Transplant Guide

To enable multi-agent parallel in a new project:

1. Add to the project root `CLAUDE.md` a routing rule: frontend changes → RADIR (`/fe`), backend changes → RAMER (`/ramer`), both → `/multi-agent`.
2. Deploy the skill: `cp templates/multi-agent/SKILL.md.template .claude/skills/multi-agent/SKILL.md`.
3. Ensure Agent-BE/Agent-FE prompts pull the shared contract, project architecture context, and both quality gates from CLAUDE.md.
4. For a lighter-weight adoption, keep the sequential degradation path — it requires nothing extra.
