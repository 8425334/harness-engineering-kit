# Harness Engineering Kit

This document cannot override or weaken higher-level policy.

## Responsibilities

Own the repository-native control plane that other projects install: the installed
layout, the OpenSpec governance sidecar, the deterministic checks, the Fitness and
lesson-memory resources, and the workspace federation model. The Kit source tree is
the single authority for this content; an installation copies it, it is not edited
in place.

## Boundaries

Do not add a second lifecycle, a central workspace repository, or a workspace-level
spec. Shared facts live next to what they describe: project facts in
`.hek/project/`, unit identity in each unit's `.hek/project/identity.yaml`, specs in
each unit's `openspec/changes/<change-id>/`. Do not edit an installed copy from here
to fix a project; change the source template and let the upgrade path deliver it.

## Local Verification

`npm run verify` runs the Node and Python suites plus the Skill contract checks.
`python scripts/check_agent_policy.py`, `check_profile.py`, `check_context_docs.py`,
and `check_change_workspace.py` validate this repository's own control plane, and
`openspec validate <change> --strict` validates a governed change.

## Navigation

Start at `README.md` for the installed layout and CLI, `core/harness-engineering.md`
for the methodology, `core/workspace-federation.md` for multi-unit work, and
`docs/versioning.md` for upgrade rules.
