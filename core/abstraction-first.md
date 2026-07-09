# Abstraction-First Modeling

The greatest risk with AI Agents is not code that doesn't run — it's code that "looks like it runs but breaks system boundaries." Abstraction-first modeling eliminates this risk by mandating contract definition before implementation.

> For DDD strategic + tactical modeling (bounded contexts, aggregates, domain events, etc.), see `ddd-modeling.md`. This document focuses on universal engineering principles: ACL translation, contract-first, composition/polymorphism.

## Universal Principles

### ACL Translation Layer

Every requirement must pass through three-layer translation before reaching implementation:

```
Verbal Requirement → [ACL Translation] → Domain Model (OO Contract) → Concrete Code
```

- **A (Abstraction)**: Distill the requirement into stable abstract concepts
- **C (Contract)**: Define interfaces, DTOs, and contractual relationships between domain objects
- **L (Logic)**: Implement concrete logic within the contract's constraints

### Contract-First Coding Order

This is not advice — it is a **mandated order**:

1. **Write the contract first**: Define interfaces / abstract classes / DTOs in the owning module (no implementation)
2. **Present and confirm**: Show the design to reviewers, confirm compliance with Single Responsibility and Open/Closed principles
3. **Then implement**: Write concrete classes against the interface, keeping changes minimal and local

Consequences of violating this order: concrete implementations will shape interface design in reverse, leading to coupling, leaking abstractions, and hard-to-test code.

### Composition Over Inheritance

**Rule: Inheritance depth ≤ 1.** If deeper nesting is needed, use composition + dependency injection instead.

Why this matters especially for AI Agents:
- AI tends to generate deep inheritance trees (common in training data)
- Deep inheritance makes change impact uncontrollable
- Composition lets each component be independently tested, replaced, and understood

**How:**
- Use `@Autowired` / DI container to inject dependencies, not `extends`
- Small interfaces, small classes, clear responsibilities
- If a class name contains "Base" or "Abstract" more than one level deep, redesign

### Polymorphism Over Branching

**Rule: Nested if/else ≥ 2 layers or switch ≥ 3 branches → use Strategy/Factory/Handler pattern.**

Why this matters especially for AI Agents:
- AI is naturally good at generating if/else branching code
- Branch code passes tests easily but is hard to extend
- Each new condition increases risk for existing branches

**How:**
- 2+ nested layers: extract Strategy interface + multiple implementations
- 3+ switch branches: use Factory pattern or Handler registry
- Replace switch with `Map<Type, Handler>` or Spring's `List<Interface>` auto-injection
