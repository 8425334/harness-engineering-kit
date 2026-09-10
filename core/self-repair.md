# Self-Repair and Runtime Integrity

Self-Repair keeps the Harness control plane usable *during* a user conversation. It is the bounded recovery path for three failure classes, not a second installer and not a way to weaken a gate.

| Failure class | Typical symptom | Owner of the fix |
|---|---|---|
| `engineering` Skill not loaded | The Agent cannot find or select the Skill, or its files are missing or stale | Canonical Skill tree re-sync from the Kit |
| Python environment or dependency problem | No usable Python 3, interpreter below the supported minimum, or an installed control script that no longer compiles | Host action for the interpreter; canonical re-sync for scripts |
| Harness incomplete | Canonical core documents, control scripts, workflow templates, OpenSpec schema files, workspace directories, or `docs/methodology/VERSION` are missing; the installed version drifted | Canonical resource sync from the Kit |

Repair is implemented once, in `scripts/repair.py`, and reached through `hek repair` (apply) and `hek doctor` (read-only). The installed copy is `docs/methodology/scripts/repair.py`.

## Invariants

- **Read-only by default.** Diagnosis never writes. Only `--apply` restores files, and it is idempotent and per-operation, so one failing resource cannot roll back the rest.
- **Canonical only.** Repair writes the canonical methodology, control scripts, workflow templates, OpenSpec schema, and the project-local `engineering` Skill. It never rewrites a project-owned fact that already exists.
- **No host mutation.** Repair never installs an interpreter, runtime, or package and never writes outside the project root. It never rewrites an existing `docs/fitness/**` baseline — a missing protected file becomes a `manual` finding — and installs the canonical Fitness scaffold only when no baseline exists. Missing host prerequisites are reported as `manual` findings with the exact remedy.
- **No downgrade.** When the installed version is newer than the Kit, repair reports the mismatch and stops.
- **No guessed source.** When the Kit checkout cannot be located — recorded by onboarding or given by the user — repair stops and asks. It never downloads or invents a source.
- **Evidence.** Every apply writes `docs/methodology/repair.json` with the environment, findings, planned restores, per-operation results, and the post-apply verification.

## Finding model

Each finding has a stable `id`, an `area`, a `severity`, a bounded example list, and an optional `remedy`.

| Severity | Meaning | Agent action |
|---|---|---|
| `repairable` | The Kit can restore it with `--apply` | Show the plan, apply, and re-check |
| `manual` | The engine will not act automatically | Report the remedy and stop that path |
| `informational` | Context only | Mention only if relevant; it never blocks |

Representative ids include `skill-missing`, `skill-stale`, `skill-scope-unknown`, `skill-user-root-stale`, `control-plane-missing`, `control-plane-drift`, `control-script-broken`, `project-fact-missing`, `workspace-dir-missing`, `fitness-ledger-missing`, `fitness-change-requires-approval`, `openspec-skills-missing`, `python-unusable`, `version-downgrade`, `version-invalid`, and `not-installed`.

## Scope selection

The Agent scope is explicit or derived, never guessed:

1. An explicit `--agent` wins.
2. Otherwise the Agent recorded in `docs/methodology/onboarding.json` is used.
3. Otherwise repair refreshes only Skill trees that already exist. If none exist, it reports `skill-scope-unknown` and asks for the Agent instead of creating six platform installs.

The installed tier defaults to the recorded tier, so a Tier 1 installation is repaired as Tier 1.

## Relationship to Onboarding

A project with no control plane is *onboarding*: use the onboarding playbook. Repair assumes Harness was installed and drifted, and it reuses the same canonical action model. Onboarding, upgrade, repair, and uninstall therefore share one definition of what Harness owns, while uninstall remains the only path that deletes it.
