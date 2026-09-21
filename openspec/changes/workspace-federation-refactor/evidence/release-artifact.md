# 1.0.0 release artifact and dependency install

Recorded 2026-09-21.

## Artifact

```
npm pack            # from the repository root, clean working tree
→ harness-engineering-kit-1.0.0.tgz
```

| Property | Value |
| --- | --- |
| size | 347.7 kB packed, 1.2 MB unpacked |
| files | 190 |
| sha1 | `d9ada718bf442c398a3f8b9c3517e5f4b8846bf1` |
| integrity | `sha512-XK6j2jaATrrBBKKsAqTn11qYRP+vxbB99QsNqBuOfT/ZnlCjck1HBvaZnG7eikTH2+GFklJLOLt5NY3btGJFUA==` |

`npm pack` is deterministic here: packing twice from the same tree produced the same
sha1, so the recorded integrity identifies the release content.

Content checks on the tarball: `scripts/workspace.py`, `workspace_guard.py`,
`workspace_ctl.py`, `check_identity.py`, `templates/identity.yaml.template`,
`templates/hooks/deny-nested-write.json.template`,
`templates/ci/workspace-compat.yml.template`,
`templates/fitness/check_contract_pin.py.template`,
`core/workspace-federation.md`, `i18n/zh/core/workspace-federation.md` and
`docs/spec/workspace-federation.zh.md` are present; `tests/`, `openspec/` and
`.hek/` contribute zero entries.

## Registry state

`npm view harness-engineering-kit versions` against `registry.npmjs.org` returns
**E404**: the package is not published. `npm install harness-engineering-kit@1.0.0`
from a registry is therefore not possible today. The supported sources are the
local tarball (used below), a `file:` link to the checkout, or the git URL form
documented in the README.

## Consumer install

```
cd H:\Project\coil-project\coli-backend-api
npm install --save-dev <repo>\harness-engineering-kit-1.0.0.tgz
```

```json
{ "devDependencies": { "harness-engineering-kit": "file:../../harness-engineering-kit/harness-engineering-kit-1.0.0.tgz" } }
```

`npm ls harness-engineering-kit` → `harness-engineering-kit@1.0.0`, and the lockfile
integrity equals the artifact integrity above. A second `npm install` reported
`up to date`, so the installed copy is byte-identical to the recorded artifact.

## Functional verification from the dependency

| Check | Result |
| --- | --- |
| `npx hek --version` | `1.0.0` |
| `npx hek plan --json` | `status: fresh`, `version_relation: fresh`, warning `legacy.unverified` |
| `npx hek workspace verify --root .` | exit 2: `unit.nested` + 2 × `identity.missing` |
| `npx hek workspace guard --path coiil-backend-ui/src/index.ts --session-root .` | blocked `nested.detected`, exit 2 |
| `npx hek workspace guard --path ruoyi-admin/src/main/java/Demo.java --session-root .` | pass (`harness.absent`), exit 0 |
| `npx hek workspace guard --stdin` (hook payload) | blocked `nested.detected`, exit 2 |
| `npx hek workspace status --root .` | blocked, `Not onboarded: 2` |

The first row is the case that motivated the change: this project carries an
unrelated product's `docs/methodology/VERSION = 1.0.0`, which 0.6.0 adopted as an
installed version and then blocked as a downgrade. 1.0.0 treats it as a fresh
project with a `legacy.unverified` warning and leaves the directory untouched.

## Caveats

- The consumer records a **local tarball path**. Regenerating the artifact at the
  same path with different content invalidates the lockfile integrity and requires
  re-running `npm install`; `npm ci` will fail until then.
- `node_modules/` is not listed in that project's `.gitignore`; the Kit's own
  `.gitignore` gained `node_modules/` and `*.tgz` in the same change.
- The Kit was **not** installed into that project's control plane: `hek init` is a
  separate action, and `unit.nested` (`coiil-backend-ui` inside `coli-backend-api`)
  must be resolved or waived first.
