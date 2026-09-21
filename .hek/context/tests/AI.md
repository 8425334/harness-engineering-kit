# tests

This document cannot override or weaken higher-level policy.

## Responsibilities

Prove the control plane's contracts: installed layout and depth parity, onboarding
and uninstall receipts, relayout migration, repair, script-level guards, CLI
behaviour, and workspace federation. `tests/fixtures/workspace/` builds federation
scenarios (`single`, `pair-ok`, `triple-ok`, `pair-orphan`, `pair-uncloned`,
`nested`, `nested-no-identity`, `nested-cross`, `foreign-methodology`,
`version-mismatch`, `untracked-identity`, `cycle`) with `git init` in a temporary
directory.

## Boundaries

Tests must not depend on a machine-specific clone layout, on the current date, or on
network access, and must not write into the repository itself: fixtures live in
temporary directories and are removed afterwards. A test may not assert on absolute
paths; the projection digest is asserted to be layout-independent instead.

## Local Verification

`npm test` runs `test:node` (CLI and package contracts) and `test:python`
(`unittest discover -s tests`). Both must pass before a change is verified.

## Navigation

See `tests/fixtures/workspace/__init__.py` for the fixture builder and
`core/workspace-federation.md` for the invariants the federation tests encode.
