# RAMER Agent Automation

The RAMER cycle has evolved from a manual process into an autonomous Agent orchestration system — Skill as entry point, Workflow chaining phases, Agent executing specific tasks, with human confirmation only at the MODEL→EXECUTE boundary.

## Universal Principles

### From Manual RAMER to Agent RAMER

Traditional RAMER's five phases are manually driven, with humans making decisions and context switches at every step:

```
Manual: 👤 READ → 👤 ANALYZE → 👤 MODEL → 👤 EXECUTE → 👤 REVIEW
```

After agentification, except for the MODEL→EXECUTE confirmation point, all phases are completed autonomously by the Agent:

```
Agent: 🤖 READ → 🤖 ANALYZE → 🤖 MODEL → 👤 Confirm → 🤖🤖🤖 EXECUTE → 🤖 REVIEW
```

**Why keep the human confirmation point at MODEL→EXECUTE?** Because MODEL is the "decision point" — once interface design, aggregate boundaries, and dependency directions are set, all subsequent code is generated from these decisions. This is the only phase requiring human value judgment. The remaining phases (reading docs, listing impacts, writing code, running gates) are mechanical work that Agents can do faster and more accurately than humans.

### Architecture Adaptivity

RAMER Agent's key innovation: **it doesn't assume all requirements use one architecture style**. During the ANALYZE phase, the Agent auto-selects based on requirement complexity:

| Signal | Style | Contract Output |
|--------|-------|----------------|
| Simple CRUD, no business invariants | **crud** | Entity Quartet (Entity/VO/BO/Mapper/XML) |
| Complex business rules, state machines, invariants | **ddd** | Aggregate + ValueObject + DomainService + Port + Adapter |
| Multiple external system orchestrations, existing port/adapter patterns | **hexagonal** | Port + Adapter + ApplicationService |
| Mixed scenarios | **hybrid** | Combine CRUD + DDD |

**Key constraint**: If the target area already has port/adapter/domain/model structure, the Agent must continue the hexagonal pattern, not revert to traditional layering.

### System Architecture

```
/ramer <requirement>
     │
     ▼
┌─ Skill (SKILL.md) ─────────────────────────────┐
│ Orchestration: Chain Design → Confirm → Implement│
└────────────────────┬───────────────────────────┘
                     │
     ┌───────────────┴───────────────┐
     ▼                               ▼
┌─ Workflow: ramer-design ──┐  ┌─ Workflow: ramer-implement ──┐
│ READ Agent                │  │ EXECUTE Agents (parallel)      │
│   → run find_ai_context   │  │   → write files per layer rule│
│   → detect arch style     │  │   domain: zero framework import│
│   → output: context summary│  │   application: inject ports   │
│        ↓                  │  │   infrastructure: ACL mapping │
│ ANALYZE Agent             │  │   interface: permission annot │
│   → arch decision tree    │  │        ↓                      │
│   → bounded context def   │  │ REVIEW Agent                  │
│   → output: impact analysis│  │   → fitness gate             │
│        ↓                  │  │   → DDD dependency check      │
│ MODEL Agent               │  │   → three-way consistency    │
│   → DDD or CRUD contract  │  │   → output: pass/fail + fix  │
│   → output: design (JSON) │  │                              │
└───────────────────────────┘  └──────────────────────────────┘
```

### Structured Design Contract Output

MODEL Agent produces schema-constrained structured JSON, not free text. This eliminates the information loss of "AI speaks human language, human translates to code":

```json
{
  "architecture": {
    "style": "ddd",
    "boundedContext": "driver-dispatch",
    "dependencyRule": "domain -> nothing; port -> domain; adapter -> port + infra; application -> domain + port"
  },
  "aggregates": [{
    "name": "DriverDispatchSession",
    "invariants": ["Driver cannot be in two dispatch tasks simultaneously"],
    "methods": [{"signature": "void assign(VehicleId id)", "enforcesInvariant": "Driver status = IDLE"}]
  }],
  "valueObjects": [{
    "name": "DriverStatus",
    "wraps": "String",
    "selfEncapsulates": true
  }],
  "ports": [{
    "name": "DriverDispatchRepository",
    "portType": "repository",
    "rationale": "Abstract dispatch aggregate persistence, isolate MyBatis-Plus implementation details"
  }],
  "adapters": [{
    "name": "MyBatisDriverDispatchRepositoryAdapter",
    "implements": "DriverDispatchRepository",
    "antiCorruptionLayer": "DriverDispatchTask (MyBatis Entity) -> DriverDispatchSession (Aggregate)"
  }],
  "applicationServices": [{
    "name": "DriverDispatchApplicationService",
    "useCases": ["assignDriver", "completeTask"],
    "portsInjected": ["DriverDispatchRepository", "NotificationGateway"],
    "domainServicesUsed": ["DriverDispatchDomainService"]
  }],
  "implementationPlan": [
    {"step": 1, "file": ".../domain/model/DriverDispatchSession.java", "layer": "domain", "dependsOn": []},
    {"step": 2, "file": ".../port/DriverDispatchRepository.java", "layer": "infrastructure", "dependsOn": [1]},
    {"step": 3, "file": ".../adapter/MyBatisDriverDispatchRepositoryAdapter.java", "layer": "infrastructure", "dependsOn": [2]}
  ]
}
```

### Per-Layer Implementation Discipline

EXECUTE Agent applies different implementation rules based on the `layer` field:

| Layer | Rule | Forbidden |
|-------|------|-----------|
| **domain** | Pure Java, zero framework imports | `@Service`, `@Component`, `@TableName`, `RedisTemplate` |
| **port** | Interface, methods only use domain types | Return `SysUserVo`/`PageResult` etc. infrastructure types |
| **adapter** | `@Component`, implement port, ACL mapping | Leak infrastructure types through port interface |
| **application** | `@Service`, inject **port interfaces**, publish events | Inject adapter classes; contain business rules |
| **interface** | `@RestController`, permission annotation per endpoint | Contain business logic |

### Quality Assurance

REVIEW Agent runs two-layer checks:

**General layer** (fitness gate):
- Architecture boundary (domain layer must not depend on infrastructure layer)
- Code size (single class ≤ 800 logical lines)
- Permission annotations (every Controller endpoint has required annotation)
- Javadoc coverage (changed public methods must have)
- Debug log cleanup (no `System.out`/`console.log`)
- SQL migration location (`script/sql/update/`)

**DDD-specific layer** (only for ddd/hexagonal/hybrid styles):
- **Dependency inversion**: domain layer has zero Spring/MyBatis/Redis imports
- **Port injection audit**: Application Service's injected fields are all port interfaces, no adapter classes
- **ACL documentation**: Every Adapter has anti-corruption layer mapping documentation
- **Port rationale**: Every Port interface has existence rationale Javadoc

### Skill Deployment

The RAMER Agent system deploys through three files, usable project-local or globally:

```
.claude/                        # Project-local
├── skills/ramer/SKILL.md      # Entry skill
├── workflows/ramer-design.js  # Design workflow
└── workflows/ramer-implement.js # Implementation workflow

~/.claude/                      # Global (cross-project)
├── skills/ramer/SKILL.md
├── workflows/ramer-design.js
└── workflows/ramer-implement.js
```

After global deployment, `/ramer` is available in any project. Local copies override the global version.

**Templates**: Portable `.template` versions at `docs/methodology/templates/ramer/`, with placeholder reference and migration steps. See `templates/ramer/README.md`.
