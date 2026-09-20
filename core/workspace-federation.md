# Workspace Federation

Multiple independent Git units cooperate without a central repository. Every shared
fact lives next to the thing it describes, and the group view is projected on
demand instead of being stored as a second authority.

## Model

| Concept | Location | Committed | Lifecycle |
| --- | --- | --- | --- |
| Unit identity and contract edges | `.hek/project/identity.yaml` in each unit | yes | moves with the code in the same pull request |
| Commands, permissions, context | `.hek/project/agent-policy.yaml` in each unit | yes | unchanged |
| Unit spec and change | `openspec/changes/<change-id>/` in each unit | yes | proposed, approved, applied, archived by that unit |
| Federation change set reference | `governance.json.workspace` in each unit | yes | references only, never spec content |
| Contract artifact | wherever `identity.publishes[].artifact` points | yes | tagged with the release |
| Group projection | `.hek/state/workspace-projection.json` (cache) | no | invalidated by content digest |
| Verdict | CI result | no | recomputed on every run |

A `unit` is one Git repository that can be built, verified and delivered on its own.
A `federation change set` is the set of unit-local changes that implement one
cross-unit change; it only stores references.

## Invariants

1. Every participating unit owns its own OpenSpec change and at least one local
   `specs/**/*.md`. If A, B and C participate, three local specs must exist; a
   single merged workspace spec is forbidden.
2. The workspace root must never own `openspec/changes/`, `specs/` or
   `workspace-spec.md`. The projection may report spec diagnostics, never spec
   content.
3. Identity is validated mechanically: schema, id patterns, URL shape, artifact
   and snapshot paths, semver ranges, and Git tracking.
4. `harness_root` must equal the Git top level of the unit and must contain
   `.hek/VERSION` plus `agent-policy.yaml`.
5. No engineering-level nesting: the Git top level of one unit may not live
   inside the Git top level of another. A write target must belong to the
   repository that owns the session.
6. Every `consumes[].contract` is published by exactly one visible unit, whose
   `repo_url` matches the declared `provider_repo`; the contract graph must be
   acyclic.
7. All units in one `workspace_id` run the same Kit version.
8. A single repository without `identity.yaml` stays on the pre-federation path:
   federation checks are skipped, structural boundary checks are not.

## Commands

| Command | Purpose |
| --- | --- |
| `hek workspace discover [--root <dir>]... [--depth N] [--json]` | Aggregate the projection |
| `hek workspace verify [--root <dir>]... [--json]` | Validate the invariants; exit 2 when blocked |
| `hek workspace context <path> [--json]` | Answer path ownership, context to load and `input_bytes` |
| `hek workspace exec <unit> -- <cmd...>` | Run a command in a unit root with `HEK_UNIT`/`HEK_WORKSPACE` |
| `hek workspace guard --path <path> [--session-root <dir>] [--json]` | Pre-write boundary guard; exit 2 blocks coding |
| `hek workspace guard --stdin [--json]` | Same guard for host-agent hooks: read the tool payload from stdin |
| `hek workspace compat --contract <id> [--json]` | Consumer-side compatibility evidence |
| `hek workspace compat --all [--json]` | Check every consumed contract of the current unit |
| `hek workspace graph [--json]` | Contract adjacency list |
| `hek workspace run <unit>\|all <fast_test\|test\|build\|fitness>` | Checkout-local aggregated run |
| `hek workspace pin [--version X]` | Record and verify the Kit version pin |
| `hek workspace status [--root <dir>]... [--json]` | Report which unit is not onboarded and which consumer lags its provider |

Exit codes match the rest of the Kit: `0` pass, `2` blocked.

## Working Rules

- Start one agent session per unit root. Use `--add-dir` (or an equivalent read
  scope) for contracts you need to read, not for units you need to change.
- `exec` refuses to launch when the projection is blocked: a nested, mixed or
  version-mismatched workspace is not a place to start an agent session.
- The responsibility direction equals the dependency direction: the consumer
  verifies the provider contract it depends on, so no central repository and no
  registry are needed.
- Cross-unit contract, evidence and dispatch paths always use
  `{"unit": "<unit_id>", "path": "<unit-relative path>"}`. Paths inside
  `identity.yaml` are implicitly scoped to their own unit.
- A cross-unit task loads the coordinator's root context plus contract
  snapshots; never mount another unit's `AI.md` chain.
- Structural nesting is blocked before any write, at any depth: the check pairs
  every enumerated candidate, walks each candidate for nested work trees
  (accepting a `.git` pointer file as well as a directory), and consults the Git
  superproject of every candidate. The only exception is a
  one-off, externally approved waiver bound to a change digest and an expiry,
  stored at `.hek/state/waivers/nested-<id>.json`. A waiver lets the guard say
  `nesting.waived` so a migration can proceed; `verify` still reports blocked
  until the structure is actually split.
- Directory names (`docs/methodology`, `docs/sdd`) never prove ownership of an
  installation. Only `.hek/VERSION`, or a legacy tree carrying both
  `docs/methodology/scripts/` and `docs/methodology/core/` with a released
  version, counts as evidence.

## Diagnostics

`workspace.mixed`, `identity.missing`, `identity.schema`, `identity.duplicate`,
`identity.untracked`, `unit.nested`, `unit.no-harness`, `contract.orphan`
(`warning` when the provider is not cloned, `blocked` when it is visible but does
not publish), `contract.provider-mismatch`, `contract.duplicate-provider`,
`contract.cycle`, `kit.version-mismatch`, `spec.missing`, `spec.reference`,
`spec.duplicate`, plus two deliberate extensions beyond the proposal's list:
`workspace.root` (an explicitly named root does not exist, or holds no Git
repository — a bad path must never look like a passing empty workspace) and
`contract.version` (a declared range does not accept the published version; the
consumer `compat` command reports it as `blocked`, the aggregate `verify` reports
a recorded `to_version` drift as `warning`). The guard adds `nested.detected`,
`boundary.cross-repo`, `harness.mismatch`, `legacy.unverified` (warning) and
`nesting.waived` (info), and the `context` command uses the command-local codes
`context.budget` and `context.missing`.
