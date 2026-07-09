# ramer-cycle.md — coil-backend-api Adaptation

## R — Path-Document Loading

```bash
python3 "$HOME/.codex/skills/coil-project-guide/scripts/find_ai_context.py" <target-path>
```

100+ `ai.json`/`AI.md` pairs in the repo. Priority: nearest `ai.json` > nearest `AI.md` > parent → root `AI.md` > `AGENTS.md`.

## A — Module Boundary Analysis

Key constraints:
- `coil-app/coil-common` is the domain layer — no Controllers or business orchestration
- `coil-app/coil-dal` is for Mapper and XML only — no business rules
- `coil-service/coil-backend-service` is the orchestration layer — can depend on all coil services
- Never push business logic into `ruoyi-common` (framework-level common layer)

## M — Entity Quartet Contract

Each domain object needs 5 coordinated artifacts:
- Entity + VO + BO in `coil-app/coil-common`
- Mapper + XML in `coil-app/coil-dal`
- MapStruct-Plus `@AutoMapper` for auto-generated bidirectional conversion

## E — Implementation Conventions

- Complex logic (>60 lines) extracted to `support/` directory
- Cross-service coordination via Domain Events (`ApplicationEvent`)
- Every Controller endpoint must declare Sa-Token permission annotation

## R — Fitness Gate

```bash
python3 docs/fitness/scripts/fitness.py --tier fast
```

Check dimensions: architecture boundary, code size, permission annotations, AI.md/ai.json sync, SQL migration location, SDD infrastructure.
