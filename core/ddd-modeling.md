# Domain-Driven Design Modeling

The most common mistake AI Agents make when facing complex business domains is skipping modeling and going straight to CRUD. The result is code that "runs" but has business concepts scattered across Services, Controllers, and SQL — any rule change requires hunting through the entire codebase. DDD provides a modeling language from strategy to tactics, giving domain knowledge a stable home in the code.

This document is stack-agnostic and universal. Project-specific mappings (which modules correspond to which contexts, which class is the aggregate root) belong in the project's own entry document (e.g., CLAUDE.md).

## Universal Principles

### Strategic Design

Strategic design answers "how the system is sliced into independent parts." Do strategy first, tactics second — the order is non-negotiable.

#### Ubiquitous Language

- Business experts, product, and development use the same vocabulary to describe the domain, and that vocabulary **appears directly in code identifiers**
- Reject technical translations when naming: if the business says "dispatch order", the code should use `DispatchOrder`, not `TaskItem` or `BizData`
- Once a ubiquitous language is established within a context, all artifacts (class names, field names, APIs, SQL, docs) must use it
- The same word can mean different things in different contexts — that's a boundary, not a conflict

#### Subdomain Classification

Break the business into three subdomain types to decide investment strategy:

| Type | Identifying Features | Investment Strategy |
|------|---------------------|---------------------|
| Core Domain | Source of competitive differentiation, most complex, most frequently changed | Build in-house, best modeling, strictest tests |
| Supporting Domain | Business-essential but not differentiating, some customization exists | Build in-house but keep simple, or wrap customized solutions |
| Generic Domain | Industry-standard, off-the-shelf solutions available | Buy / open source / standard implementation, don't invest for differentiation |

Judgment order: identify core domains first (be able to say in one sentence "our competitive advantage is X"), then classify the rest.

#### Bounded Context

- A bounded context = one complete and self-consistent domain model + one team's ownership boundary
- Within the boundary: ubiquitous language, model, and data model must be consistent; outside: consistency is not enforced
- Boundary ≈ module boundary ≈ physical deployment boundary (module/package in monolith, service in microservices)
- One subdomain can map to one or more bounded contexts; slice first by team size and model complexity, then adjust for performance/deployment needs

#### Context Map

Contexts inevitably interact. The context map describes the interaction relationships. Common patterns:

| Pattern | Relationship | When to Use |
|---------|-------------|-------------|
| Shared Kernel | Two contexts share part of a model; changes require both sides' agreement | Tightly collaborating teams, shared stable core |
| Customer/Supplier | Supplier prioritizes customer needs but can negotiate | Upstream/downstream teams with negotiation mechanism |
| Conformist | Customer is forced to follow supplier's model, no negotiation power | Upstream model is large and won't customize for you |
| Anti-Corruption Layer (ACL) | Customer builds a translation layer to isolate upstream model pollution | Integrating legacy/external systems, protecting core |
| Open Host Service (OHS) | Supplier exposes a standardized protocol externally | One supplier, multiple consumers |
| Separate Ways | No integration between contexts | Models differ greatly, integration cost exceeds value |

The ACL is the pattern AI Agents should master most — it explicitly turns "translate external model into our context's model" into code, rather than letting foreign concepts silently seep in.

### Tactical Design

Tactical design provides modeling building blocks within a bounded context.

#### Entity

- Has a unique identity; identity does not depend on attributes
- Attributes can change, but ID does not
- Contains behavior (methods) that belongs to it, not just a data container
- Test: two entities with all identical attributes but different IDs are two different objects

#### Value Object

- No unique identity; identity defined by attribute values
- Immutable — all fields final
- Can be safely shared, can be used as dictionary keys
- Test: two value objects with all identical attributes are the same object
- Prefer value objects over primitives: `Money(amount, currency)` not `BigDecimal amount + String currency`

#### Aggregate & Aggregate Root

An aggregate is a cluster of closely related objects treated as a consistency boundary from the outside:

- Each aggregate has one root entity (aggregate root); external code only holds references to the root
- Cross-aggregate references are **by ID only** — never hold object references to another aggregate
- Strong consistency within an aggregate: a single transaction modifies only one aggregate
- Eventual consistency between aggregates: async sync via domain events
- Keep aggregates small: don't cram the entire object graph into one aggregate; prefer splitting and linking by ID
- The root entity maintains invariants within the aggregate; all mutation entry points go through the root's methods

#### Domain Service

- Carries domain logic that **doesn't naturally belong to any single entity or value object**
- Stateless
- Distinguished from application services: domain services contain business rules; application services contain process orchestration (transactions, security, dispatching domain services/repositories)
- Naming should use business terminology (`PricingService`), not technical terminology (`PriceHelper`)

#### Application Service

- Orchestrates use cases: receives external request → loads aggregate → calls domain methods → persists → publishes events
- Contains no business rules; business rules sink into entities/domain services
- Controls transaction boundaries and security
- Interfaces named by use case (`submitOrder` / `DispatchOrderUseCase`); DTOs separate from domain objects

#### Repository

- Provides a persistence abstraction for aggregate roots that looks like an "in-memory collection"
- Interface belongs to the domain layer; implementation belongs to the infrastructure layer
- One repository per aggregate root; don't create separate repositories for non-root entities
- Repository returns aggregate root entities (or snapshots), not DataTables / Records

#### Domain Event

- Describes "something meaningful to the business that happened in the past"; named in past tense (`OrderPlaced`, `DispatchCompleted`)
- Published by aggregate roots or domain services after state changes
- Publisher doesn't care who consumes — this is the decoupling point
- Cross-aggregate eventual consistency relies on events, not distributed transactions

#### Factory

- When aggregate construction logic is complex or invariants must be guaranteed, encapsulate creation with a factory
- Simple construction can use `new` / builder directly — don't force a factory
- A factory can be a static method, a standalone Factory class, or a factory method on the aggregate root

### Modeling Discipline

| Rule | Violation |
|------|-----------|
| Cross-aggregate references by ID only | Aggregate A holds object reference to Aggregate B and calls its methods directly |
| Strong consistency within aggregate, eventual between | Modifying two aggregate roots in one transaction |
| Entities don't handle data access | Entity methods directly write SQL / call Mapper |
| Naming follows ubiquitous language | `UserInfo` / `TmOrder` / `BizData` |
| Domain objects don't depend on infrastructure | Entity / value object importing framework `@Service`, `@Component` |
| Application services contain no business rules | Writing pricing calculation, risk control rules in application service |

## Relationship with Existing Methodology

| Existing Methodology | Relationship to DDD |
|---------------------|---------------------|
| `abstraction-first.md` | ACL translation + contract-first = the engineering entry point for DDD modeling; writing domain contracts (interfaces / DTOs / domain objects) before implementation is exactly DDD tactical design execution order |
| `backend-profile.md` | Backend Model should be a domain model (aggregates / context map), not only a table ER diagram |
| `sdd-workflow.md` | The design section of proposals should use DDD vocabulary to describe which contexts and aggregates the change affects |
| `fitness-framework.md` | `check_ddd_compliance.py` validates "domain objects don't depend on infrastructure" (domain layer purity); deployed as fast hard gate, template at `templates/fitness/rules/ddd-compliance.md.template` |
