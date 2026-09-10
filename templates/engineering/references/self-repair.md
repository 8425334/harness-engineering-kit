# Harness Self-Repair

Use this playbook when the Harness control plane, its runtime, or the `engineering` Skill itself is not in a working state during a user conversation. Repair is a bounded, evidence-first loop: diagnose, restore canonical assets, re-check, and report. It is not a second onboarding and it never invents project facts.

## Triggers

Repair is in scope when any of these is observed, including when the user reports it without naming it precisely:

1. **Engineering Skill not loaded** — the project-local Skill is missing, stale, or undiscoverable for the active Agent, the Agent cannot find or select `engineering`, or a required Skill reference is absent.
2. **Python environment or dependency problem** — no usable Python 3 on `PATH`, an interpreter below the supported minimum, an installed control script that no longer compiles, or a canonical script whose sibling module was removed.
3. **Harness incomplete** — the installed control plane is missing canonical core documents, control scripts, workflow templates, OpenSpec schema files, workspace directories, or the installed `docs/methodology/VERSION`; or the installed version drifted from the Kit.

Do not use repair for an unimplemented feature, a design dispute, or a clean install. A project with no control plane at all is onboarding, not repair.

## Diagnose

Diagnosis is read-only and safe to run at any point:

```bash
python3 <kit>/scripts/repair.py --project-root . --source-root <kit> --json
# Windows: py -3
```

Pass `--agent <id>` when the active Agent is known and its project-local Skill must be restored. Without it the engine repairs the Agent recorded in `docs/methodology/onboarding.json`, and otherwise only refreshes Skill trees that already exist. When `--source-root` is omitted the engine uses the Kit path recorded by onboarding; if that fails, ask the user for the Kit checkout and never download a remote installer.

Read the findings, not just the exit code:

- `repairable` — the engine can restore it from the Kit with `--apply`.
- `manual` — the engine will not act, for example a missing interpreter or a downgrade. Report the stated remedy and stop that path.
- `informational` — context only; it never blocks.

Every finding carries a stable `id` (`skill-missing`, `skill-stale`, `control-plane-missing`, `control-plane-drift`, `control-script-broken`, `python-unusable`, `openspec-skills-missing`, `fitness-change-requires-approval`, `version-downgrade`, `not-installed`, ...), an `area`, a `severity`, at most a dozen examples, and a `remedy` for anything the engine will not fix alone.

## Repair

Report the findings and the planned restores, then apply:

```bash
python3 <kit>/scripts/repair.py --project-root . --source-root <kit> --agent <id> --apply --json
```

`--apply` is idempotent and per-operation: it restores only canonical Kit resources, recreates missing control-plane directories, re-syncs stale `engineering` Skill trees, and regenerates missing OpenSpec lifecycle Skills when the OpenSpec CLI is available. It writes `docs/methodology/repair.json` as the audit receipt.

## Boundaries

- Repair never rewrites a project-owned fact that already exists: `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`, `ai.json`, `AI.md`, `agent-policy.yaml`, `profile.yaml`, and `openspec/config.yaml` are preserved. A missing fact file is restored from the canonical scaffold and reported so its placeholders are filled from repository evidence.
- Repair never installs interpreters, runtimes, or packages and never writes outside the project root. It never rewrites an existing `docs/fitness/**` baseline; a missing protected file is reported as a `manual` finding, and the canonical Fitness scaffold is installed only when no baseline exists. A user-level Skill directory is reported as information only; installing there requires the user's separate approval.
- Repair never downgrades an installation. When the installed version is newer than the Kit, it reports the mismatch and stops.
- If the Kit source cannot be located, stop and ask for the absolute path. Never substitute a guessed or downloaded source.
- A `manual` finding is not silently bypassed. Report it with its remedy and let the user decide.

## Re-check and report

`--apply` re-diagnoses automatically and stores the result under `verification`. A run is only complete when `status` is `repaired` or `healthy` and no `repairable` or `manual` finding remains; otherwise report the residual findings with their remedies.

Return the observed trigger, the finding ids and severities, the restored files or Skill trees, the environment versions, the verification result, any `manual` item still open, and the next valid action. Do not report a repair as successful before the re-check passes.

If repair cannot make the environment healthy — for example no supported Python on the host, or a missing Kit checkout — report the blocker and the exact command the user must run. Do not recreate the Harness lifecycle, the OpenSpec Skills, or the fitness control plane by hand.
