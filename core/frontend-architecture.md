# AI-Native Frontend Architecture & Methodology

Redefining frontend development as a three-layer collaboration model: AI implements logic within boundaries, humans define "what good code is," and automated systems verify quality.

> This document focuses on **frontend** AI collaboration patterns and architecture boundaries. For backend contract-first, composition/polymorphism principles, see `abstraction-first.md`. For the quality gate system, see `fitness-framework.md`.

## 1. Core Philosophy

We redefine frontend development as a three-tier collaboration model:

- **The Architect (Human)**: Defines boundaries, rules, constraints, and "what good code is."
- **The Enforcer (Automation)**: Automatically validates code quality through Fitness Functions and Harness (test framework).
- **The Builder (AI)**: Works within boundaries to implement logic.

**Formula:**

```
System = (Prompt + Context) + (AI Inference) + (Fitness Validation)
```

## 2. AI Development Methodology (AIDM)

### 2.1 Abstraction-First Protocol

Before letting AI write code, AI must first generate the abstract model.

Flow:

1. User: "I need an order management page."
2. AI Agent 1 (Domain Modeler): Generate TypeScript Interfaces, DTOs, Enums, State Schema.
3. AI Agent 2 (Contract Validator): Validate type consistency against API docs.
4. AI Agent 3 (Builder): Generate UI components based on the above models.

**Rule: Never let AI generate jsx/tsx files directly — must generate `types.ts` and `models.ts` first.**

### 2.2 Architecture Boundary Contract

Leverage AI's ability to understand natural language to enforce "layers are non-negotiable" rules.

Prompt template:

```text
You are a DDD frontend expert.
Context: You are in the presentation/components layer.
Strict Rules:
  - Absolutely no direct calls to axios or fetch.
  - Absolutely no direct access to LocalStorage.
  - All data must come through props.
  - All events must emit through props callbacks.
Task: Implement the <UserList /> component.
```

### 2.3 Fitness-Driven Development (FDD)

Integrate Fitness Framework thinking into AI interaction. AI-delivered code must pass "fitness tests" before merging.

Check points:

- **Security Baseline**: AI-generated code must not contain `eval()` or `innerHTML`.
- **Arch Boundary Check**: Static analysis (e.g., ESLint plugin) verifies import paths, ensuring the UI layer doesn't import infrastructure.
- **Log Cleanup**: Auto-detect whether AI left `console.log` behind.

## 3. Modern Frontend Architecture Design

To maximize AI effectiveness while keeping code clean, use a feature-based directory structure combined with React Server Components (RSC) architecture.

### 3.1 Physical Structure

```
src/
├── kernel/                   # AI static analysis config & rules
│   ├── fitness/              # Automated test scripts
│   │   ├── check_safety.py   # Security baseline check
│   │   └── check_boundary.py # Architecture boundary check
│   └── prompts/              # Pre-built high-quality System Prompts
├── domain/                   # Domain layer (High Precision)
│   ├── aggregates/           # Entity aggregate roots
│   ├── services/             # Domain services (pure functions, easy for AI)
│   └── types/                # Global type definitions
├── application/              # Application orchestration layer
│   ├── hooks/                # React Hooks (AI's primary workspace)
│   └── controllers/          # Data fetching & dispatch logic
├── infrastructure/           # Infrastructure layer (Low Mutation)
│   └── api/                  # API client
└── presentation/             # Presentation layer
    ├── pages/                # Page entry points
    ├── components/           # Display components (UI)
    └── templates/            # Layout templates
```

### 3.2 React Server Components (RSC) Strategy

AI performs best with RSC because it naturally allows mixing server-side logic, reducing client-side state management complexity.

AI generation patterns:

- **Server Component**: Handle data fetching, permission checks (AI writes SQL/Logic).
- **Client Component**: Handle complex interactions, Modals, animations (AI writes React Hooks).

## 4. Implementation: AI Coding Workflow

### Step 1: Generate Contract

- **Input**: Requirements document.
- **AI Action**: Generate OpenAPI Spec / JSON Schema.
- **Output**: `domain/types/user.type.ts`.

### Step 2: Generate Infrastructure

- **Input**: OpenAPI Spec.
- **AI Action**: Generate API Client functions, Repository interface.
- **Output**: `infrastructure/api/user.ts`.

### Step 3: Orchestrate Logic

- **Input**: Domain Types + Repository Interface.
- **AI Action**: Write `useFetchUsers` Hook, handling Loading/Error states.
- **Output**: `application/hooks/useFetchUsers.ts`.
- **Fitness Check**: Ensure no `console.log` in Hook, error handling covers all exception branches.

### Step 4: Generate UI

- **Input**: `useFetchUsers` Hook type definition + design description.
- **AI Action**: Generate TailwindCSS or CSS Modules styled components.
- **Output**: `presentation/components/UserTable.tsx`.
- **Fitness Check**: Accessibility check (ensure `aria-label`), component Props completeness check.

## 5. AI Specifications & Constraints

To prevent AI from producing "hallucinated code," it must be locked into specifications.

### 5.1 Prompt Instruction Library

Maintain a `.ai/prompts/` directory in the project:

- `system.component.md`: Define component writing standards.
- `system.hooks.md`: Define Hooks writing standards.
- `system.refactor.md`: Define refactoring standards.

### 5.2 Rejection Patterns

Forbid AI from introducing the following patterns unless explicitly authorized:

- `any` type.
- `eval()` or `new Function()`.
- Hard-coded external API Keys.
- Overly complex nested ternary operators.

### 5.3 Self-Correction Loop

Configure Agent mode in the IDE (VS Code / Cursor):

1. **Write Code**: AI generates code.
2. **Trigger Linter**: IDE auto-runs ESLint.
3. **AI Reads Errors**: Agent receives error information.
4. **Self-Repair**: Agent auto-fixes errors until Linter passes.
5. **Run Tests**: Trigger vitest.
6. **Final Commit**: All green lights pass.

## 6. Summary

This methodology combines the rigorous engineering thinking from `methodology.zip` with AI's generative capability:

- **Abstraction-first** ensures AI understands the business model, not just syntax.
- **Architecture boundaries** limit AI's "creativity" scope, preventing god components.
- **Fitness functions** establish AI's "ethical standards," forcing high-quality output.

**Goal**: Evolve frontend teams from "writers" to "reviewers" and "architects," making AI the tireless, strictly rule-following "junior engineer."
