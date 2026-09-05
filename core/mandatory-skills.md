# Supporting Capabilities

The only lifecycle Skill in this kit is `engineering`. Other tools are supporting capabilities selected by task and project policy:

| Capability | Purpose | Fallback |
|---|---|---|
| OpenSpec child | Specification authoring guidance and validation, dispatched only by the Harness parent through `dispatch_openspec.py` | Maintain the same artifacts without the CLI; never let `/opsx:*` or direct change-scoped OpenSpec calls own creation, state, approval, implementation, Sync, or Archive |
| Code navigation/index | Find symbols, callers, and dependencies | Targeted repository search |
| Test/build/Fitness runners | Produce verification evidence | Project commands from policy |
| Browser or API tooling | Verify user-visible/integration behavior | Focused manual evidence |
| Multi-agent execution | Reduce wall time after approval | Sequential execution with identical gates |

Tool availability must be checked when used. Missing support produces explicit fallback evidence; it never changes authority, artifact, approval, or review requirements.
