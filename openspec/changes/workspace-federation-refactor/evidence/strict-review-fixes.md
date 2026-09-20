# Strict review of the federation gate — findings and fixes

Recorded on 2026-09-21. A strict review of the delivered implementation, run by
reproducing each suspected failure with a probe before touching any code, found
three fail-open defects plus several partial implementations. Everything below is
fixed and covered by a regression test that fails against the previous behaviour.

## Fail-open defects

| # | Finding | Reproduction before the fix | Fix |
| --- | --- | --- | --- |
| H1 | `compat` ignored the declared version range (I13 half implemented) | provider `2.0.0`, consumer `^1.5.0`, snapshot bytes equal → `compat` exit 0 / `pass`, while `status` said `behind` | `compat` evaluates `version_satisfies(published, declared)` and reports a blocked `contract.version` finding; `--all` checks every consumed contract in one run |
| H2 | Nesting detection failed open beyond three levels and never compared enumerated candidates | a unit four levels below another → `verify` exit 0, no diagnostics; with `--depth 6` both units enumerated → still exit 0 | `discover` now pairs every enumerated candidate, walks each candidate for nested work trees with a documented 64-level safety bound (accepting a `.git` pointer file), and consults `git rev-parse --show-superproject-working-tree` |
| H3 | A nonexistent or repository-less `--root` produced a passing empty projection | `verify --root H:\no\such\dir` → `status: pass`, exit 0 | blocked `workspace.root` diagnostic with exit 2 |

## Partial implementations

| # | Finding | Fix |
| --- | --- | --- |
| M1 | `governance.workspace.contracts` was effectively unvalidated: an unconsumed contract with a non-publishing provider and fabricated versions passed both layers | unit-local: the contract must appear in the unit's `identity.yaml` and a consumer's `to_version` must satisfy its declared range; aggregate: `contract.orphan` / `contract.provider-mismatch` for unknown or misattributed providers, warning `contract.version` for recorded drift |
| M2 | The `--show-superproject-working-tree` rule from §5.10 was required but never called (`git_superproject()` was dead code) | wired into `discover`; covered by a test that stubs the Git fact, because `git submodule add` cannot run in this sandbox (`basename: command not found` in git-submodule) |
| M3 | `exec` launched a session even when the projection was blocked | `exec` refuses blocked projections with exit 2, like `run` |
| M4 | Several gates had no test: policy writable-path boundary, `project_root()` workspace refusal, digest tracking, deep nesting | each now has a regression test (see `tests/test_workspace.py`, `tests/test_workspace_ctl.py`) |

## Smaller consistency fixes

- `is_semver_range` rejects leading zeros (`01.2.3`); `version_satisfies` normalises
  `>= 1.0` to `>=1.0` so the validator and the evaluator agree.
- `unit_scoped_path` rejects non-normalized input (`a//b`, `./a/b`, `a/./b`) instead
  of silently normalising it, and it is now actually used by the aggregate spec
  reference check rather than being dead code.
- A unit consuming a contract it publishes is reported as `contract.cycle`.
- A unit declaring a workspace section in more than one change is reported as
  `spec.duplicate`.
- `workspace context` no longer loads a foreign unit's module chain: a cross-unit
  target stops after reporting ownership and the blocked boundary finding.
- `aggregation_findings()` (dead code) was removed; `detect_nesting()` and
  `git_superproject()` now have callers.
- New diagnostic codes `workspace.root` and `contract.version` extend the proposal's
  §3.2 list; they are documented in `core/workspace-federation.md` as deliberate
  extensions, together with the command-local `context.budget` / `context.missing`.

## Verification after the fixes

```
python -m unittest discover -s tests -p "test_*.py"   # 198 tests, OK
node --test tests/test_cli.js tests/test_package.js tests/test_workspace_cli.js  # 48, pass
python scripts/check_change_workspace.py --root .      # OPENSPEC GOVERNANCE PASS
openspec validate workspace-federation-refactor --strict  # valid
```

The saved projection in `verify-triple-ok.json` was re-generated with the current
code; the digest for the same three fixtures is unchanged, which confirms the
fixes did not alter the projection contract.
