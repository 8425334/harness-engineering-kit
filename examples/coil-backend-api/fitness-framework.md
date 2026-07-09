# fitness-framework.md — coil-backend-api Adaptation

## Invocation

```bash
# Fast gate (run after every agent change)
python3 docs/fitness/scripts/fitness.py --tier fast

# Normal gate (pre-commit)
python3 docs/fitness/scripts/fitness.py --tier normal

# Preview (dry-run)
python3 docs/fitness/scripts/fitness.py --dry-run
```

## 12 Quality Dimensions

| Dimension File | What It Checks |
|---------------|----------------|
| `architecture-boundary.md` | `org.dromara.coil` packages must not appear in `ruoyi-common`; Controllers must not be in `coil-app`; `docs/fitness` must have `AI.md`/`ai.json`/`README.md` |
| `backend-quality.md` | Java impl classes ≤ 800 effective logic lines; production classes/methods/fields/branches/state transitions must carry Javadoc or descriptive annotations |
| `ddd-compliance.md` | Domain layer (`/domain/`) Java classes must not import or use infrastructure annotations/classes (`@Service`/`@Component`/`@Mapper` etc.) |
| `debug-log-cleanup.md` | Changed files must not contain leftover `System.out`/`console.log`/`print()`/`printStackTrace`/`debugger`; framework-level `log.*` is allowed |
| `docs-quality.md` | Agent entry points (AGENTS.md / AI.md / ai.json) exist; `docs/fitness` has rule manual and verification ledger; AI.md and ai.json are in sync |
| `frontend-quality.md` | Frontend typecheck (normal tier) and build (deep tier) pass |
| `permission-management.md` | Changed Controller endpoints must declare Sa-Token access annotations; permission codes must be traceable in `script/sql/**/*.sql` |
| `sdd-quality.md` | `docs/sdd/` directory exists; `openspec/config.yaml` context and rules blocks are populated; active changes have proposal.md + tasks.md |
| `security.md` | Block `--dangerously-skip-permissions` / `bypassPermissions` dangerous agent configs from entering the repo |
| `sql-quality.md` | SQL migration scripts must land under `script/sql/update/` |
| `test-coverage.md` | Changed business logic classes must have matching `XxxTest.java` in same package; changed modules ≥ 65% JaCoCo line coverage |
| `wx-api-boundary.md` | wx-api Controller/Service/Domain changes must sync `docs/design/driver-task-flow`; API mapping matches design semantics |

## Executor Implementation

This project's `fitness.py` is a ~220-line Python script:
- Manual frontmatter parsing (zero dependencies)
- Supports `--tier` grading, `--dry-run` preview, `--verbose` output
- Hard Gate failure returns exit code 2
- Results grouped by dimension

The executor itself is portable — copy to any project, add corresponding `.md` rule files under `docs/fitness/`, and it works.
