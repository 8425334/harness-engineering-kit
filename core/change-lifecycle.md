# OpenSpec Change Lifecycle

OpenSpec is the lifecycle owner for every governed change:

```text
Explore → Propose → Apply → Verify → Sync → Archive
```

Use native OpenSpec Skills and CLI for change creation, artifact ordering, task
progress, validation, spec synchronization, and archiving. Engineering adds
governance evidence around those actions; it does not introduce another state
machine or task projection.

| OpenSpec action | Native entrypoint | Engineering governance |
|---|---|---|
| Explore | `openspec-explore` | context resolution, requirement reflection, lesson preflight |
| Propose | `openspec-propose` / `openspec new change` | design review, approval, context impact |
| Apply | `openspec-apply-change` | execution evidence, focused verification, Fitness |
| Verify | `openspec-verify-change` | strict artifact validation, review evidence, drift and production gates |
| Sync | `openspec-sync-specs` | sync evidence and canonical digest |
| Archive | `openspec-archive-change` / `openspec archive` | archive evidence, lessons, production closure |

## Governance sidecar

After OpenSpec creates `openspec/changes/<id>/`, attach `governance.json` with
`init_governance.py`. The sidecar records ownership, profile, risk, context,
approval, execution, review, Fitness, lessons, and production evidence. The
OpenSpec `.openspec.yaml` marker and native artifact graph remain authoritative.

`tasks.md` is the only task definition and checkbox progress source. Engineering
records `execution-evidence.json` and verifies that each checked task has one
successful run; it never rewrites task checkboxes or maintains a parallel DAG.

## Gates

Use `check_change_workspace.py` for workspace registration, `check_phase.py` for
governance gates, and OpenSpec for lifecycle validation:

```bash
openspec status --change <id> --json
openspec validate <id> --type change --strict --no-interactive
python3 docs/methodology/scripts/check_phase.py <change-dir> DESIGN
```

Approval binds normalized contract artifacts. Apply evidence binds checked
OpenSpec tasks to actors, workspaces, commands, changed files, and integration.
Review requires current digests; Sync requires source and canonical spec digests;
Archive requires OpenSpec validation plus governance and any production closure.
