# sdd-workflow.md — coil-backend-api Adaptation

## Toolchain

This project uses OpenSpec CLI for SDD lifecycle management, driven by Claude Code Skills:

```bash
# Create new change
openspec new change "<name>"

# Generate artifacts (proposal → specs → design → tasks)
/opsx:propose <description>

# Implement tasks
/opsx:apply

# Sync specs
/opsx:sync

# Archive
/opsx:archive
```

Change directory: `openspec/changes/<name>/`
Archive directory: `openspec/changes/archive/YYYY-MM-DD-<name>/`

## Project-Specific Task Grouping Order

```
1. Domain Contract (coil-common) — Entity, VO, BO, DTO
2. Support (coil-backend-service/service/support/) — complex orchestration logic
3. Service (coil-backend-service/service/) — business entry points
4. Controller (coil-backend-service/controller/) — API endpoints
5. Mapper (coil-dal) — data access
6. SQL Migration (script/sql/update/) — permissions/schema changes
7. Verification — compile + fitness gate + three-way consistency check
8. Frontend (coil-backend-ui) — Vue components + API files
```

## Mapping to RAMER

| SDD Phase | RAMER Phase |
|-----------|------------|
| Explore | Pre-RAMER |
| Propose | R → A → M |
| Apply | E |
| Sync + Archive | R (review) |

Every SDD phase internally follows RAMER discipline.
