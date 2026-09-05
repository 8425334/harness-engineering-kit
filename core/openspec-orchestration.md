# Harness and OpenSpec Parent-Child Orchestration

Harness Engineering is the parent lifecycle. OpenSpec is a child capability for
specification authoring guidance and validation; it is not a peer workflow.

## Ownership Contract

Every live `change.json` carries the exact machine-readable relationship:

- parent: `harness-engineering`;
- child: `openspec`;
- sole child entrypoint: `docs/methodology/scripts/dispatch_openspec.py`;
- child actions: `status`, `instructions`, `validate`, `show`, and `templates`;
- parent-only authority: change creation, lifecycle state, approval,
  implementation, Sync, and Archive.

`init_change.py` creates this relationship. `check_change_workspace.py` and every
phase gate reject a missing or altered relationship. Direct change-scoped
OpenSpec commands and the standalone `/opsx:*` lifecycle are not valid
entrypoints in an instrumented repository.

## Dispatch Protocol

The Engineering coordinator may invoke only fixed, JSON-returning operations:

```text
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> status
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> instructions --artifact proposal|specs|design|tasks|apply|archive
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> validate
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> show
python3 docs/methodology/scripts/dispatch_openspec.py <change-dir> templates
```

The dispatcher validates the canonical workspace, parent-child contract, and
current Harness state before constructing fixed OpenSpec arguments. It exposes
no raw argument passthrough and records output digests and exit status as a
Harness event. OpenSpec output is child input to the coordinator; it cannot
advance state or authorize source changes.

Proposal/spec instructions are restricted to early contract states,
design/tasks instructions to `CONTRACT_READY` or contract rework, Apply
instructions to approved implementation states, and Archive instructions to
verified/synced states. Apply and Archive instruction dispatches are read-only;
the parent still performs those operations.

## Task Progress Projection

`task-plan.json` is the approval-bound parent DAG. OpenSpec `tasks.md` is its
human-readable child projection and carries runtime checkboxes. The coordinator
must not edit a checkbox directly. After a worker finishes a task and all
focused verification passes, it runs:

```text
python3 docs/methodology/scripts/record_task_completion.py complete <change-dir> T1 --run <task-run.json>
```

That operation checks dependencies, scope, timestamps, isolation, and planned
verification; records the run in `execution-evidence.json`; emits
`task.completed`; and synchronizes `T1` to `- [x]`. Parallel completions are
serialized. `record_task_completion.py sync <change-dir>` repairs the projection
from evidence after an interrupted write. Review fails unless checked tasks and
successful task runs match exactly.

When Apply is interrupted, keep the change in `IMPLEMENTING` and resume through
the parent coordinator:

```text
python3 docs/methodology/scripts/record_task_completion.py resume <change-dir> --actor <agent> --json
```

Resume validates all recorded runs, repairs the checkbox projection, records an
`execution.resumed` event, and returns completed, pending, and ready task waves.
A source change without a validated run remains pending; rerun its focused
verification and submit a new `task-run.json` through `complete` before moving
to dependent tasks. Resume never changes the approved DAG or advances lifecycle
state.
