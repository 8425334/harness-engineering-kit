# scripts

This document cannot override or weaken higher-level policy.

## Responsibilities

Hold the deterministic control scripts that every lifecycle gate calls: onboarding
and layout migration (`onboard.py`, `layout.py`), OpenSpec governance
(`openspec_common.py`, `check_change_workspace.py`, `init_governance.py`), context
resolution and caching, Fitness protection, lesson memory, repair, and workspace
federation (`workspace.py`, `workspace_guard.py`, `workspace_ctl.py`,
`check_identity.py`).

## Boundaries

Scripts never invent project facts and never rewrite project-owned files.
Federation commands read every fact from the unit that owns it and fail closed with
exit code 2 when a required file is missing; they must not create a workspace-level
spec or treat a directory name as proof of installation ownership.

## Local Verification

`python -m unittest discover -s tests -p "test_*.py"` covers every script contract.
For a single entry point, run it directly, for example
`python scripts/workspace_ctl.py verify --root <dir> --json`, which exits 0 on pass
and 2 when blocked.

## Navigation

Read `docs/versioning.md` before changing upgrade behaviour, `core/openspec-orchestration.md`
before changing change-lifecycle contracts, and `core/workspace-federation.md`
before changing federation.
