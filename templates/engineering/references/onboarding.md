# Harness Onboarding

Use this playbook when a repository is not integrated, contains the previous architecture, or has drifted from the current Harness release.

## Conversation Contract

1. Confirm the target repository and whether the user wants a fresh install, an upgrade, or both. Do not infer permission to overwrite project configuration.
2. Locate the kit checkout. Prefer the path containing this Skill; otherwise ask for the absolute kit path. Do not download or execute an untrusted remote installer.
3. Inspect only the repository root and known markers. Run the read-only plan (`py -3` instead of `python3` on Windows):

   ```bash
   python3 <kit>/scripts/onboard.py --project-root . --source-root <kit> --plan --json
   ```

4. Explain the detected state (`fresh`, `partial`, `legacy`, or `current`), the files to create/sync/preserve, the selected tier, and any legacy files that remain untouched. For `legacy`, explicitly state that old `ramer`, `fe-engineering`, `multi-agent`, Cursor, and Codex entries are not silently deleted.
5. After the user confirms the displayed plan, apply it:

   ```bash
   python3 <kit>/scripts/onboard.py --project-root . --source-root <kit> --tier <1|2> --apply --json
   ```

6. Replace placeholders in the preserved project configuration using facts discovered from the repository. Never invent commands, owners, paths, or security settings. Keep native `AGENTS.md`/`CLAUDE.md` instructions authoritative.
7. Run the post-apply check and stop on failure:

   ```bash
   python3 <kit>/scripts/onboard.py --project-root . --source-root <kit> --check --json
   ```

8. Report the onboarding state, changed files, preserved legacy files, check output, unresolved placeholders or manual decisions, and the next valid action. Save the machine-readable receipt at `docs/methodology/onboarding.json`.

## State Rules

| State | Meaning | Agent action |
|---|---|---|
| `fresh` | No Harness entrypoint is present | Create the canonical control plane and local Skills |
| `partial` | Some current files exist | Preserve project configuration; fill missing controls |
| `legacy` | Previous Skill or methodology markers are present | Add current controls and provide a migration report; do not delete legacy files |
| `current` | Version, policy, and Engineering Skill are present | Sync canonical resources and run drift checks |

Tier 1 installs the core controls together with the production policy scaffold that `agent-policy.yaml` references. Tier 2 additionally installs Fitness gate scripts, Fitness rules, and lesson-memory templates. Choose Tier 2 for a complete integration unless the user explicitly requests a minimal bootstrap.

## Safety Boundaries

- `--plan` is read-only and is the default mode; `--apply` writes project controls. A later `--check` may update the onboarding receipt with its result, but never changes project controls.
- Root adapters, `ai.json`, policy, profile, OpenSpec configuration, and `AI.md` are preserved when present. Their edits require explicit user approval in the conversation.
- Canonical methodology scripts, core documents, workflow templates, and the project-local Engineering Skill may be synchronized on upgrade.
- No command performs `git reset`, deletes legacy entries, changes `docs/fitness/**` after bootstrap, installs dependencies, or accesses production systems.
- If the kit source cannot be located, stop and ask for its path; never guess a remote source.
