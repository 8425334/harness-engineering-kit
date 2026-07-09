# coil-backend-api — Methodology Adaptation Example

This directory contains the project-specific adaptation examples extracted from the core methodology documents. These serve as a reference for how a real-world Java Spring Boot + Vue 3 monorepo adapted the AI-Assisted Development Methodology.

## Project Profile

| Property | Value |
|----------|-------|
| **Stack** | Java 8/17 (Spring Boot 5.6.0), Vue 3 + Soybean Admin |
| **Build** | Maven (multi-module), pnpm workspace |
| **Architecture** | Monolith with orchestrated services (RuoYi-Vue-Plus fork) |
| **Modules** | `ruoyi-admin` → `coil-backend-service` → `coil-wms/wx/ocr/ipes-service` + `coil-common` + `coil-dal` |
| **Frontend** | `coil-backend-ui/` (Vue 3 SFC + TypeScript) |

## Adaptation Files

Each file below corresponds to a core methodology document and shows how it was adapted to this specific project:

| Core Document | Adaptation File | Key Customizations |
|---------------|----------------|-------------------|
| `abstraction-first.md` | [abstraction-first.md](abstraction-first.md) | ACL mapped to package structure, Entity Quartet pattern |
| `fitness-framework.md` | [fitness-framework.md](fitness-framework.md) | 12 quality dimensions with Java-specific checks |
| `frontend-architecture.md` | [frontend-architecture.md](frontend-architecture.md) | Vue 3 + VibeCoding complement |
| `harness-engineering.md` | [harness-engineering.md](harness-engineering.md) | 100+ path documents, full Skill catalog |
| `ramer-agent.md` | [ramer-agent.md](ramer-agent.md) | Hexagonal DDD + Layered hybrid, wx login reference |
| `ramer-cycle.md` | [ramer-cycle.md](ramer-cycle.md) | Path-document loader, Entity Quartet contracts, Sa-Token permissions |
| `sdd-workflow.md` | [sdd-workflow.md](sdd-workflow.md) | OpenSpec toolchain, task ordering by module dependency |

## How to Use This Example

When adapting the methodology to your own project:

1. Read the core document first (e.g., `core/ramer-cycle.md`)
2. Then read this project's adaptation to see how abstract principles became concrete rules
3. Pattern-match: find the analogous module/package in your codebase
4. Create your own adaptation following the same structure
