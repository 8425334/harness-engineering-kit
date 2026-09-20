# Task 0.1 — governance prerequisite

## What was required

`governance.json` for this change had to be created in an environment that
already carries a valid `.hek/project/agent-policy.yaml`, and
`python scripts/check_change_workspace.py --root <project-root>` had to pass.
Hand-writing the record was forbidden.

## What was done

This repository now carries its own Harness project facts, authored from real
repository evidence and validated by the Kit's own checks:

| File | Role |
| --- | --- |
| `.hek/VERSION` | installed version `1.0.0` |
| `.hek/project/agent-policy.yaml` | commands, authority order, permissions (`npm test`, `npm run verify`, real paths) |
| `.hek/project/profile.yaml` | standard profile, medium risk, review dates |
| `.hek/project/production/policy.yaml` | production write policy referenced by the agent policy |
| `.hek/context/ai.json` + 3 × `AI.md` | context index over the root, `scripts/`, and `tests/` |

`init_governance.py` (not a hand-written file) then produced
`openspec/changes/workspace-federation-refactor/governance.json` with the canonical
orchestration contract, and appended the `skill.triggered` event.

## Verification

```
python scripts/check_agent_policy.py     → AGENT POLICY OK
python scripts/check_profile.py          → PROFILE OK
python scripts/check_context_docs.py .   → CONTEXT DOCS OK: ai.json -> 3 AI.md document(s)
python scripts/init_governance.py ...    → GOVERNANCE ATTACHED
python scripts/check_change_workspace.py --root .  → OPENSPEC GOVERNANCE PASS
openspec validate workspace-federation-refactor --strict → valid
```

## Decision: project facts installed, Kit not vendored

The technical proposal (§9) offers two distribution shapes: a vendored full Kit,
or project-owned facts plus a pinned Kit. This repository takes the second, because
it *is* the Kit source: vendoring `.hek/kit/{core,scripts,templates}` would place a
second copy of `core/`, `scripts/` and `templates/` in the same work tree, and the
copy would drift on every edit to the source it duplicates. The policy therefore
points `architecture_overview`, `dependency_rules` and `methodology.lifecycle` at
the source tree (`core/*.md`) instead of `.hek/kit/core/*.md`.

Consequences, stated explicitly:

- `hek workspace verify` runs in this repository and reports a single-repository,
  federation-disabled projection (no identity is claimed for the Kit source).
- `hek check` and `hek doctor` will report the un-vendored `.hek/kit`, the root
  adapters, and `.hek/fitness` as missing: this repository is not a full
  installation, and `repair`'s `--source-root` default (the checkout itself) is the
  supported way to materialize them if a full install is ever wanted.
