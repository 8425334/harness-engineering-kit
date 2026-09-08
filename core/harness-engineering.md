# Harness Engineering Architecture

Harness Engineering makes an AI coding environment predictable through explicit
authority, minimal context loading, executable governance gates, and durable
evidence.

## Responsibility boundaries

| Component | Responsibility |
|---|---|
| Native root adapter | Authority, safety, required reads, and Skill routing |
| `agent-policy.yaml` | Canonical project commands, paths, permissions, and delivery references |
| Root `ai.json` / path `AI.md` | Compact project map and local context |
| `engineering` Skill | Governance wrapper around OpenSpec and repository controls |
| Deterministic scripts | Context, approval, execution/review, Fitness, lessons, and production gates |

OpenSpec is the lifecycle owner. Its native Skills and CLI create changes,
progress artifacts, validate, verify, sync specs, and archive. Engineering never
keeps a competing state machine, dispatcher, task plan, or checkbox projection.

## Governance loop

After `openspec new change <id> --schema harness-engineering`, attach `governance.json` with
`init_governance.py`. Engineering then validates context, reflects requirements,
reviews design, binds approval, records execution evidence, checks review and
Fitness, and closes production or lessons. OpenSpec's `.openspec.yaml`, schema,
artifact graph, and `tasks.md` remain authoritative.

## Context loading

Load native instructions, `resolve_context.py` output, the selected Engineering
profile, then task code, contracts, and tests. The index routes; Markdown
explains. Neither can override native instructions or policy.

## Platform boundary

Claude uses `.claude/skills/engineering`; Codex uses `.agents/skills/engineering`;
OpenCode uses `.opencode/skills/engineering`; Cursor uses `.cursor/skills/engineering`;
Gemini uses `.gemini/skills/engineering`; Trae uses `.trae/skills/engineering`.
The Skill frontmatter and native root adapter both require implicit selection for
non-trivial changes, so users do not need to type `/engineering`. OpenSpec 1.12.0
generates its seven native workflow Skills in the same agent-specific roots,
including Verify.
