# Harness Versioning and Upgrades

Harness uses the Kit's `VERSION` as the release version and the target project's `.hek/VERSION` as the installed version. Versions follow Semantic Versioning (`MAJOR.MINOR.PATCH`). The onboarding plan compares these values before any write.

## Upgrade rules

- A lower installed version and a higher Kit version is an `upgrade`. Canonical resources are synchronized in one ordered plan.
- Equal versions are still checked for drift; a release number does not prove that files are byte-identical.
- A higher installed version is a `downgrade` and is blocked. Use the newer Kit or make a separately approved rollback plan.
- A missing version in a truly fresh repository is `fresh`; a missing version in a partial or legacy repository is `unversioned` and blocks automatic apply. A malformed version is `invalid` and also blocks apply.

For `unversioned` or `invalid`, the Agent must identify the actual installed release from repository evidence and obtain confirmation before recording a valid `.hek/VERSION`; it must never guess a baseline just to pass the gate.

The install tier is independent of the version relationship. Tier 1 and Tier 2 describe the desired scope of this run. A Tier 1 run still synchronizes all Tier 1 canonical resources; Tier 2 additionally installs Fitness and lesson-memory assets.

## 1.0.0

1.0.0 adds workspace federation: several independent Git units cooperate without a central repository, each owning its own `.hek/project/identity.yaml`, OpenSpec change and specs. Applying it to a project with engineering-level nesting (one unit repository inside another) is blocked until the units are split into siblings; the migration may use a one-off, time-boxed waiver at `.hek/state/waivers/nested-<id>.json`, but `hek workspace verify` keeps reporting blocked until the structure is compliant. Installation ownership is decided by evidence rather than directory names, so a tree that merely contains `docs/methodology` is treated as fresh with a `legacy.unverified` warning instead of being adopted and blocked by a downgrade.

## Version consistency identification

A release number states what a Kit is called, not what it contains. Every
checkout therefore also has a content identity: `source_fingerprint`, the
SHA-256 of a manifest over the shipped assets (`VERSION`, `bin/`, `core/`,
`migrations/`, `scripts/`, `templates/`). Development-only sources such as
`scripts/smoke_test_skills.py`, plus `docs/`, tests, and examples, are excluded
because they change no installed file.

Every successful apply records that identity in `.hek/state/kit-identity.json`
(version, algorithm, fingerprint, file count, timestamp). Plan, `hek check`, and
`hek doctor` then compare three things instead of trusting the version:

| `identity_relation` | Meaning |
|---|---|
| `match` | The recorded Kit content, the checkout being run, and the installed canonical resources agree. |
| `drift` | One of them differs: the Kit content changed under an unchanged version, or an installed resource was edited or lost. |
| `unknown` | `.hek/state/kit-identity.json` is missing, so the installation cannot prove which Kit it came from. The next apply records one. |

`content_drift` names the files: `missing`, `modified`, and `stale` for
resources the Kit no longer ships. A same-version difference raises the
`version.same-content-drift` warning in the plan and fails `hek check`, with the
remedy to re-run `hek init --apply` from the checkout the project is meant to
run. `hek repair` reports the same facts as `kit-identity-drift` and
`kit-identity-missing` findings and re-records the identity when it runs. Stale
files are reported but never deleted by an upgrade: only `hek uninstall`
removes Harness content.

## Release migrations

Normal upgrades are data-free resource synchronization and do not require a version-specific script. A release that needs manual review or a structural migration adds one entry to `migrations/releases.json` keyed by its target version. The onboarding plan reports matching release entries and their manual decisions; it never deletes legacy files or rewrites project-owned facts automatically.

Every release therefore follows the same rule without hardcoding a particular version pair:

```text
installed < kit → compare → plan canonical sync → report release migrations → confirm → apply → check
```

When a future release is published, ordinary resource changes work through the same comparison. Only exceptional migration decisions need a new entry keyed by that release.
