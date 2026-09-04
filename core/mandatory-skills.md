# Supporting Capabilities

The only lifecycle Skill in this kit is `engineering`. Other tools are supporting capabilities selected by task and project policy:

| Capability | Purpose | Fallback |
|---|---|---|
| OpenSpec workspace | Canonical active change and specification storage | Maintain the same `openspec/changes` artifact layout without the CLI |
| Code navigation/index | Find symbols, callers, and dependencies | Targeted repository search |
| Test/build/Fitness runners | Produce verification evidence | Project commands from policy |
| Browser or API tooling | Verify user-visible/integration behavior | Focused manual evidence |
| Multi-agent execution | Reduce wall time after approval | Sequential execution with identical gates |

Tool availability must be checked when used. Missing support produces explicit fallback evidence; it never changes authority, artifact, approval, or review requirements.
