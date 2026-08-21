# Frontend Engineering Capability Model

Defines a stack-agnostic frontend engineering capability standard. Whether Vue/React/Angular/Svelte, a strong frontend engineering practice should possess these capabilities.

> Companion global Skill: `/fe` command (`fe-engineering`), auto-detects tech stack in any frontend project and executes the RADIR workflow.

## 1. Four Iron Rules

### Rule 1: Layers Are Non-Negotiable

```
┌──────────────────────────────────────────────────────────────┐
│  Presentation Layer (views / components / pages)              │
│    ├── Responsibility: UI rendering, interaction orchestration│
│    ├── Depends on: hooks, types, API layer                    │
│    └── Forbidden: direct axios/fetch/request calls            │
├──────────────────────────────────────────────────────────────┤
│  API Layer (service/api / api)                                │
│    ├── Responsibility: Request paths, params, return types    │
│    ├── Depends on: request instance, type definitions         │
│    └── Forbidden: reverse-depend on presentation, mix UI state│
├──────────────────────────────────────────────────────────────┤
│  Request Layer (service/request / utils/http)                  │
│    ├── Responsibility: Unified request instance, auth,        │
│    │   interceptors, error handling                           │
│    ├── Depends on: HTTP library (axios/fetch)                 │
│    └── Forbidden: mix in business semantics                   │
└──────────────────────────────────────────────────────────────┘
```

**Check method**: grep the presentation layer — no direct imports of `axios`/`fetch`/low-level `request`.

### Rule 2: Types Are the Contract

- **Forbid `any`**: Unless there's a clear reason (third-party library defect, extremely hard to type dynamic content) + explanatory comment
- **API types sync with backend**: When API fields change, types, API methods, and consuming pages update in the same task
- **Enums derived from contract**: No frontend-invented enum values; status codes/business enums follow backend docs
- **TypeScript strict**: All new projects should enable strict mode

```
Anti-pattern:                          Correct:
const data: any = await api()         const data: Api.UserList = await api()
users.map((u: any) => u.name)         users.map((u: User) => u.name)
```

### Rule 3: Components Are Controlled

**Size limits**:
- Single file ≤ 300 lines (excluding blank lines and comment-only lines)
- Must split if exceeded

**Modals/Forms/Tables must be independent components**:

| Trigger | Split Target |
|---------|-------------|
| `v-if` controlled popup/drawer | `modules/<name>-modal.vue` / `<name>-drawer.vue` |
| Form fields > 5 | `modules/<name>-form.vue` |
| Table columns > 6 or complex column rendering | `modules/<name>-table.vue` |
| Logic used in 2+ places | `hooks/` or `components/` |
| File > 300 lines | Must decompose |

**Promotion rules**:
- Business components start in page `modules/`
- When used by 3+ pages/modules, promote to `src/components/`
- No "premature abstraction" — premature globalization is more harmful than local duplication

**Composition over inheritance**:
- Use `slot`/`props`/`emit` for composition
- Don't use `extends` for inheritance
- Don't rely on `$parent`/`$refs` for cross-component communication

### Rule 4: Three-State Coverage

Every data-fetching scenario must explicitly handle three states:

```
                    ┌──────────┐
                    │  Trigger  │
                    └─────┬────┘
                          │
                    ┌─────▼────┐
                    │ Loading  │──→ Skeleton / Spin / Skeleton
                    └─────┬────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
        ┌─────▼────┐ ┌───▼────┐ ┌───▼────┐
        │  Empty   │ │  Data  │ │ Error  │
        └──────────┘ └────────┘ └────────┘
             │                      │
       Empty illustration       Error message
         + guidance               + retry button
```

Form submissions also need three states:
- **Submitting**: Button loading + disabled
- **Success**: Success feedback + close modal/refresh list
- **Failure**: Error message + restore editable state

---

## 2. Component Decomposition Pattern

### Parent Component (Orchestration Layer, ≤150 lines)

```
Parent = assemble children + manage page-level state + coordinate child communication
```

- No complex templates (delegate to children)
- No complex logic (delegate to hooks)
- Only do: declare reactive data needed by children, handle child-emitted events

### Child Component (Implementation Layer, ≤300 lines)

- Receive data via `defineProps`
- Report events via `defineEmits`
- Never directly modify props (one-way data flow)

### Modal/Drawer Open/Close Pattern

```
Parent:
  const visible = ref(false)
  const currentData = ref<Item | null>(null)

  const handleOpen = (row: Item) => {
    currentData.value = row
    visible.value = true
  }

  const handleClose = () => {
    visible.value = false
    currentData.value = null
  }

Child:
  defineProps<{ visible: boolean; data: Item | null }>()
  defineEmits<{ close: []; submit: [] }>()
```

### Directory Structure Example

```
user-management/
├── index.vue                    # Orchestration, ~120 lines
├── modules/
│   ├── user-search.vue          # Search form, ~80 lines
│   ├── user-table.vue           # Data table, ~180 lines
│   ├── user-form-drawer.vue     # Create/edit form drawer, ~250 lines
│   └── user-delete-dialog.vue   # Delete confirmation, ~60 lines
├── hooks/
│   └── useUserList.ts           # List fetching + three-state, ~80 lines
└── AI.md / ai.json              # Module constraint docs
```

---

## 3. Quality Gates

### Automated Checks (CI / Pre-Commit)

| Check | Command (auto-detected) | Severity |
|-------|------------------------|----------|
| Type check | `tsc --noEmit` / `vue-tsc --noEmit` | FAIL |
| Build validation | `vite build` / `webpack --mode production` | FAIL |
| Route sync | `pnpm gen-route` (if applicable) | FAIL |
| Lint | `eslint` / `oxlint` | WARN |

### 4 Iron Rules Self-Check

| Check | Method | Severity |
|-------|--------|----------|
| Layer violation | grep views/components for `axios`/`fetch`/low-level `request` | FAIL |
| any type | grep `: any` in changed files | FAIL |
| File too large | `wc -l` check changed files | REWORK (>300 lines) |
| Modal not split | Check if `dialog`/`drawer`/`modal` is in page file | REWORK |
| Missing three-state | Check if API call sites cover loading/empty/error in template | REWORK |
| Route out of sync | New pages registered in routes | FAIL |
| i18n out of sync | New text in locales | WARN |

### Pre-Delivery Manual Confirmation

- UI interaction behavior (modal open/close, form submit/reset)
- Permission button display matches backend permission codes
- Backend field alignment (new/modified API fields synced in frontend)

---

## 4. Tech Stack Adaptation

This model works with any frontend framework. Core mappings:

| Concept | Vue 3 | React | Angular | Svelte |
|---------|-------|-------|---------|--------|
| Presentation | `.vue` SFC | `.tsx`/`.jsx` | `.component.ts` + `.html` | `.svelte` |
| Component comm | props + emit | props + callback | @Input + @Output | props + event |
| Global state | Pinia | Zustand/Redux | NgRx/Signal | Svelte Store |
| Types | `vue-tsc` | `tsc` | `ngc` | `svelte-check` |
| Build | Vite | Vite/Webpack | Angular CLI | Vite |
| Styles | Scoped CSS / UnoCSS | CSS Modules / Tailwind | Component Styles | Scoped CSS |

The `/fe` skill auto-detects the tech stack from `package.json` on startup and adapts commands and path conventions accordingly.

---

## 5. Correspondence with Backend Methodology

| Backend | Frontend |
|---------|----------|
| RAMER Cycle | RADIR Workflow |
| /ramer skill | /fe skill (fe-engineering) |
| Abstraction-first (ACL → DTO/BO/VO) | Component decomposition (requirement → component tree → implementation) |
| Composition over inheritance | slot/props/emit composition |
| Contract-first (Interface → Impl) | Type-first (Type → API → Component) |
| Fitness quality gate | VERIFY quality gate |
| DDD domain modeling | DDD frontend layers (presentation/application/domain/infrastructure) |

---

## 6. Transplant Guide

### Enabling in a New Project

**Tier 1 (immediate, 5 min)**:
1. Add to project root `CLAUDE.md`:
   ```markdown
   ## Frontend
   Use /fe command for frontend development, following 4 iron rules + component decomposition.
   See `docs/methodology/core/frontend-engineering.md`.
   ```

**Tier 2 (1 hour)**:
1. Create `AI.md` / `ai.json` path documents for core business directories
2. Configure ESLint layer check rules (forbid views from directly importing axios)
3. Add typecheck + build blocking in CI

**Tier 3 (ongoing)**:
1. Configure Fitness frontend check scripts (file size, any type, three-state coverage)
2. Introduce E2E testing (Playwright / Cypress)
3. Establish frontend component library & design system

---

## 7. Multi-Agent Parallel Mode

> Multi-agent coordination is a cross-cutting orchestration pattern, not frontend-specific. Full treatment (contract template, launch rules, merge verification, degradation): **`core/multi-agent.md`** + Skill `/multi-agent` (`templates/multi-agent/SKILL.md.template`).

When a task spans **both frontend and backend** code changes, dual-agent parallel execution is automatically enabled instead of sequential execution.

### 7.1 Execution Architecture

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
│ fitness.py gate    │  │ typecheck + build gate     │
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

### 7.2 Contract Definition Template

The format output by the main Agent during the contract definition phase:

```markdown
## Shared Contract

### Endpoint: POST /api/v1/users/assign-role
| Direction | Field | Type | Required | Description |
|-----------|-------|------|----------|-------------|
| Request | userId | Long | Yes | User ID |
| Request | roleId | Long | Yes | Role ID |
| Response | success | Boolean | Yes | Operation result |
| Response | message | String | No | Error message |

### Enum: UserStatus
| Value | Meaning |
|-------|---------|
| ACTIVE | Active |
| INACTIVE | Inactive |
| SUSPENDED | Suspended |
```

### 7.3 Parallel Launch

Both Agents start simultaneously via `run_in_background: true`, executing independently.

- **Agent-BE** (`general-purpose`): Prompt includes RAMER cycle + project architecture + contract fields
- **Agent-FE** (`general-purpose`): Prompt includes RADIR workflow + 4 iron rules + contract fields

The main Agent does not poll-wait; it is notified automatically when both sides complete for merge verification.

### 7.4 Degradation Strategy

| Scenario | Strategy |
|----------|----------|
| Sub-agent unavailable (quota/unreachable) | Sequential execution: implement backend contract layer first, then frontend presentation layer |
| Single-side task (frontend-only or backend-only) | Don't enable parallel; use the corresponding workflow directly |
| Contract change (fields need adjustment during implementation) | Sub-agents coordinate changes through the main Agent; both sides sync updates |
