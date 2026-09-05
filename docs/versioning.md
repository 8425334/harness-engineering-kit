# Harness Versioning and Upgrades

Harness uses the Kit's `VERSION` as the release version and the target project's `docs/methodology/VERSION` as the installed version. Versions follow Semantic Versioning (`MAJOR.MINOR.PATCH`). The onboarding plan compares these values before any write.

## Upgrade rules

- A lower installed version and a higher Kit version is an `upgrade`. Canonical resources are synchronized in one ordered plan.
- Equal versions are still checked for drift; a release number does not prove that files are byte-identical.
- A higher installed version is a `downgrade` and is blocked. Use the newer Kit or make a separately approved rollback plan.
- A missing version in a truly fresh repository is `fresh`; a missing version in a partial or legacy repository is `unversioned` and blocks automatic apply. A malformed version is `invalid` and also blocks apply.

For `unversioned` or `invalid`, the Agent must identify the actual installed release from repository evidence and obtain confirmation before recording a valid `docs/methodology/VERSION`; it must never guess a baseline just to pass the gate.

The install tier is independent of the version relationship. Tier 1 and Tier 2 describe the desired scope of this run. A Tier 1 run still synchronizes all Tier 1 canonical resources; Tier 2 additionally installs Fitness and lesson-memory assets.

## Release migrations

Normal upgrades are data-free resource synchronization and do not require a version-specific script. A release that needs manual review or a structural migration adds one entry to `migrations/releases.json` keyed by its target version. The onboarding plan reports matching release entries and their manual decisions; it never deletes legacy files or rewrites project-owned facts automatically.

Every release therefore follows the same rule without hardcoding a particular version pair:

```text
installed < kit → compare → plan canonical sync → report release migrations → confirm → apply → check
```

When a future release is published, ordinary resource changes work through the same comparison. Only exceptional migration decisions need a new entry keyed by that release.
