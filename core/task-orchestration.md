# Task Evidence

OpenSpec owns task decomposition and progress in `tasks.md`. Engineering does
not create a parallel task plan, infer a second task graph, or repair checkboxes.

Each task must use OpenSpec's numbered format:

```markdown
- [ ] 1.1 Implement the bounded behavior; verify with `pytest tests/test_api.py`.
```

During Apply, a coordinator records the completed run in
`execution-evidence.json` with the task id, actor, workspace, timestamps,
changed files, command evidence, and integration order. The OpenSpec Apply
workflow checks the task only after implementation and focused verification
actually succeed.

`check_execution.py` fails closed when evidence is missing, references an unknown
task, claims an unchecked task, has non-zero commands, escapes the project root,
or disagrees with Review file digests. Parallel execution is optional; if used,
declare the isolation mode and capacity in the evidence. Sequential execution
records a fallback reason.
