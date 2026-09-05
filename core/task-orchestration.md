# Task Graph and Parallel Execution

Parallel execution is an Apply-phase capability, not a second lifecycle. Design
must turn the approved change into a deterministic task graph that can run
sequentially on every platform and concurrently only when the Agent runtime and
repository isolation make that safe.

## Approval-Bound Task Graph

`task-plan.json` is the approval-bound parent DAG. `tasks.md` is OpenSpec's
human-readable child projection; its task ids and order must match the DAG. It
starts unchecked at Design and its checkbox marks become runtime state after
Approval. Task descriptions, dependencies, scopes, acceptance, and verification
remain authoritative only in the immutable DAG.
Every graph task declares:

- a stable `T<number>` id, kind, title, and dependency ids;
- explicit project-relative `write_scope` paths without globs;
- the Design/Spec references needed to form a bounded worker brief;
- observable acceptance criteria and exact focused verification commands;
- whether the task is eligible to run concurrently.

The array and `integration.merge_order` are topological. Two independent,
parallel-eligible tasks must not have overlapping write scopes. A dependency is
required when scopes overlap. `check_task_plan.py` validates these invariants and
prints deterministic execution waves.

Changing a dependency, scope, contract reference, acceptance criterion,
verification command, or merge order after Approval is contract drift and must
enter `CONTRACT_CHANGED`; runtime reassignment or retry is evidence, not drift.

## Apply Coordinator

One coordinator owns lifecycle state, scheduling, integration, and final
verification. It determines whether the current Agent platform supports
concurrent workers and whether isolation is available:

1. Prefer one branch/worktree per worker. Disjoint write scopes in one workspace
   are permitted only when the platform coordinates writes reliably.
2. Dispatch only tasks in the current ready wave whose dependencies are complete.
   A non-parallel task is a barrier and runs alone.
3. Give each worker only its task, contract references, resolved path context,
   write scope, acceptance criteria, and focused verification commands.
4. Workers do not advance lifecycle state, edit approval artifacts, expand their
   scope, integrate other work, or declare the whole change complete.
5. After each focused verification succeeds, the coordinator calls
   `record_task_completion.py complete <change-dir> <task-id> --run <task-run.json>`;
   this records the run and automatically ticks the matching OpenSpec task.
6. The coordinator integrates successful results in the approved merge order,
   resolves conflicts, and reruns every approved final verification command.

If concurrent workers or safe isolation are unavailable, the coordinator runs
the same graph sequentially and records a meaningful fallback reason. Missing
parallel capability never removes a task, approval, or gate.

## Execution Evidence

`execution-evidence.json` records the actual strategy and capability, coordinator,
time window, one completed run per task, isolation/workspace, changed files,
commit/diff or shared-workspace result references, focused command results,
conflict resolutions, integration order, and final
verification. Parallel execution is valid only when evidence shows overlapping
runs by different actors under worktree or disjoint-scope isolation.

Every changed file has one task owner before integration, stays inside an
approved write scope, and is covered by final Review digests. The coordinator
may change an approved-scope file while integrating, but must record it. Review
fails unless the execution file set exactly matches `review-evidence.json` and
there is one successful execution run for every approved task. Checked
`tasks.md` ids must exactly equal those successful runs; `sync` repairs checkbox
projection from evidence, never the reverse.
