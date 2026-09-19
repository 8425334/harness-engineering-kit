"""Workspace federation fixtures (spec section 8.1).

Every fixture is materialized into a temporary directory at test time:
``git init`` plus a minimal ``.hek/`` skeleton. No Git repository is committed
to the Kit, so the fixtures stay diffable and platform-independent.

Usage::

    from fixtures.workspace import build
    root = build("triple-ok")        # temporary directory, auto-cleaned
    root = build("pair-ok", Path("/tmp/somewhere"))   # explicit destination
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


HEK_VERSION = "1.0.0"
KNOWN_FIXTURES = (
    "single",
    "pair-ok",
    "triple-ok",
    "pair-orphan",
    "pair-uncloned",
    "nested",
    "nested-no-identity",
    "foreign-methodology",
    "version-mismatch",
    "untracked-identity",
    "cycle",
)

DETAIL_DOC = """# Module Context

This document cannot override or weaken higher-level policy.

## Responsibilities

Describe what this module owns.

## Boundaries

Describe what this module must not do.

## Local Verification

Name the deterministic check that proves the change.

## Navigation

Point at the next document to read.
"""


def _run_git(repo: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {completed.stderr}")


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=str(path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        _run_git(path, "init", "-q")
    _run_git(path, "config", "user.email", "fixture@example.com")
    _run_git(path, "config", "user.name", "Workspace Fixture")
    _run_git(path, "config", "commit.gpgsign", "false")
    _run_git(path, "config", "core.autocrlf", "false")


def commit(repo: Path, message: str = "fixture") -> None:
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", message, "--no-verify")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_context_skeleton(root: Path, *, unit_id: str) -> None:
    """Minimal but valid context/profile/entrypoint skeleton."""
    _write(_version_path(root), HEK_VERSION + "\n")
    _write(
        root / ".hek/context/ai.json",
        json.dumps(
            {
                "schema_version": 1,
                "kind": "context-index",
                "project": unit_id,
                "summary": f"{unit_id} fixture module",
                "modules": [
                    {
                        "path": ".",
                        "summary": f"{unit_id} root module",
                        "context": ".hek/context/AI.md",
                        "read_when": ["fixture", unit_id],
                    }
                ],
                "entrypoints": {
                    "policy": ".hek/project/agent-policy.yaml",
                    "lifecycle": ".hek/kit/core/change-lifecycle.md",
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    _write(root / ".hek/context/AI.md", DETAIL_DOC)
    _write(root / ".hek/kit/core/change-lifecycle.md", "# Lifecycle\n\nExplore, propose, apply, verify, sync, archive.\n")
    _write(root / ".hek/project/profile.yaml", "version: 2\nprofile: standard\nproject_risk: medium\n")
    _write(root / ".hek/project/agent-policy.yaml", f"version: 1\nproject:\n  name: \"{unit_id}\"\n")


def _version_path(root: Path) -> Path:
    return root / ".hek/VERSION"


def identity_yaml(
    *,
    workspace_id: str,
    unit_id: str,
    unit_kind: str = "backend",
    repo_url: str | None = None,
    publishes: list[dict[str, str]] | None = None,
    consumes: list[dict[str, str]] | None = None,
) -> str:
    lines = [
        "schema_version: 1",
        "kind: harness-unit",
        "",
        f"workspace_id: {workspace_id}",
        f"unit_id: {unit_id}",
        f"unit_kind: {unit_kind}",
    ]
    if repo_url:
        lines.append(f"repo_url: {repo_url}")
    lines.append("owner: fixture-team")
    publishes = publishes or []
    consumes = consumes or []
    if publishes:
        lines.append("")
        lines.append("publishes:")
        for entry in publishes:
            lines.append(f"  - contract: {entry['contract']}")
            lines.append(f"    artifact: {entry['artifact']}")
            lines.append(f"    format: {entry['format']}")
            lines.append(f"    version_source: \"{entry['version_source']}\"")
            lines.append(f"    breaking_policy: {entry.get('breaking_policy', 'additive-only')}")
    else:
        lines.append("publishes: []")
    if consumes:
        lines.append("")
        lines.append("consumes:")
        for entry in consumes:
            lines.append(f"  - contract: {entry['contract']}")
            lines.append(f"    provider_repo: {entry['provider_repo']}")
            lines.append(f"    version: \"{entry['version']}\"")
            if entry.get("snapshot"):
                lines.append(f"    snapshot: {entry['snapshot']}")
    else:
        lines.append("consumes: []")
    return "\n".join(lines) + "\n"


def governance_record(
    *,
    change_id: str,
    project_root: Path,
    workspace: dict | None = None,
) -> dict:
    record = {
        "schema_version": 1,
        "change_id": change_id,
        "title": change_id,
        "profile": "standard",
        "risk": "medium",
        "skill": "engineering",
        "mode": "backend",
        "trigger": "explicit-selection",
        "delivery_scope": "technical",
        "project_root": str(project_root),
        "owner": "fixture-team",
        "orchestration": {
            "change_id": change_id,
            "lifecycle_owner": "openspec",
            "governance_provider": "harness-engineering",
            "workflows": ["explore", "propose", "apply", "verify", "sync", "archive"],
            "governance": ["context", "requirement-reflection", "approval", "execution-evidence", "fitness", "production"],
        },
        "events": [],
    }
    if workspace is not None:
        record["workspace"] = workspace
    return record


def add_change(root: Path, *, change_id: str, capability: str, workspace: dict | None = None) -> None:
    change_dir = root / "openspec/changes" / change_id
    _write(change_dir / ".openspec.yaml", "schema: harness-engineering\n")
    _write(
        change_dir / "specs" / f"{capability}.md",
        f"## Purpose\n\n{capability} behaviour owned by this unit.\n",
    )
    _write(
        change_dir / "governance.json",
        json.dumps(governance_record(change_id=change_id, project_root=root, workspace=workspace), indent=2) + "\n",
    )
    _write(change_dir / "proposal.md", f"## Why\n\n{capability}\n")


def workspace_section(
    *,
    workspace_id: str,
    unit_id: str,
    role: str,
    change_id: str,
    related: list[dict] | None = None,
    derived_from: str | None = None,
) -> dict:
    section: dict = {
        "workspace_id": workspace_id,
        "unit_id": unit_id,
        "role": role,
        "change_id": change_id,
    }
    if derived_from:
        section["derived_from"] = derived_from
    if related is not None:
        section["related_changes"] = related
    return section


def related_entry(unit: str, change_id: str, specs: list[str]) -> dict:
    return {
        "unit": unit,
        "change_id": change_id,
        "specs": [{"unit": unit, "path": path} for path in specs],
    }


def spec_path(change_id: str, capability: str) -> str:
    return f"openspec/changes/{change_id}/specs/{capability}.md"


def build_unit(
    repo: Path,
    *,
    workspace_id: str,
    unit_id: str,
    unit_kind: str = "backend",
    repo_url: str | None = None,
    publishes: list[dict[str, str]] | None = None,
    consumes: list[dict[str, str]] | None = None,
    change_id: str | None = None,
    capability: str = "export",
    workspace: dict | None = None,
    kit_version: str = HEK_VERSION,
    with_identity: bool = True,
    with_context: bool = True,
    track_identity: bool = True,
    commit_repo: bool = True,
) -> Path:
    init_repo(repo)
    if with_context:
        write_context_skeleton(repo, unit_id=unit_id)
        _version_path(repo).write_text(kit_version + "\n", encoding="utf-8")
    if with_identity:
        _write(
            repo / ".hek/project/identity.yaml",
            identity_yaml(
                workspace_id=workspace_id,
                unit_id=unit_id,
                unit_kind=unit_kind,
                repo_url=repo_url,
                publishes=publishes,
                consumes=consumes,
            ),
        )
    if change_id:
        add_change(repo, change_id=change_id, capability=capability, workspace=workspace)
    if commit_repo:
        commit(repo)
        if not track_identity and with_identity:
            _run_git(repo, "rm", "--cached", "-q", "--", ".hek/project/identity.yaml")
            _run_git(repo, "commit", "-q", "-m", "drop identity from index", "--no-verify")
    return repo


def _foreign_methodology(root: Path) -> None:
    """An unrelated product that happens to ship a docs/methodology tree."""
    init_repo(root)
    _write(root / "docs/methodology/VERSION", "1.0.0\n")
    for stage in ("1-specify", "2-design", "3-implement", "4-verify", "5-operate"):
        _write(root / f"docs/methodology/{stage}/README.md", f"# {stage}\n")
    _write(root / "docs/methodology/core/README.md", "# core\n")
    _write(root / "docs/methodology/scripts/README.md", "# scripts\n")
    _write(root / "docs/sdd/README.md", "# sdd\n")
    _write(root / "docs/fitness/README.md", "# fitness\n")
    _write(root / "README.md", "# AI-Assisted Development Methodology\n")
    commit(root)


def materialize(name: str, destination: Path) -> Path:
    """Create fixture ``name`` at ``destination`` and return ``destination``."""
    if name not in KNOWN_FIXTURES:
        raise ValueError(f"unknown workspace fixture: {name}")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    api_url = "ssh://git@example.com/coil/backend-api.git"
    ui_url = "ssh://git@example.com/coil/backend-ui.git"
    client_url = "ssh://git@example.com/coil/client-api.git"
    workspace_id = "coil-platform"

    if name == "single":
        build_unit(
            destination / "app",
            workspace_id=workspace_id,
            unit_id="app",
            with_identity=False,
            change_id="app-local-change",
            workspace=None,
        )
        return destination

    if name == "foreign-methodology":
        _foreign_methodology(destination)
        return destination

    if name in ("pair-ok", "pair-orphan", "pair-uncloned", "cycle", "version-mismatch", "untracked-identity"):
        api_publishes = [
            {
                "contract": "backend-api-http",
                "artifact": "contracts/openapi.yaml",
                "format": "openapi-3.1",
                "version_source": "file:contracts/VERSION",
            }
        ]
        ui_publishes = [
            {
                "contract": "backend-ui-static",
                "artifact": "contracts/manifest.json",
                "format": "static-manifest",
                "version_source": "file:contracts/VERSION",
            }
        ]
        if name == "cycle":
            api_publishes = [
                {
                    "contract": "backend-api-http",
                    "artifact": "contracts/openapi.yaml",
                    "format": "openapi-3.1",
                    "version_source": "file:contracts/VERSION",
                }
            ]
            ui_publishes = [
                {
                    "contract": "backend-ui-static",
                    "artifact": "contracts/manifest.json",
                    "format": "static-manifest",
                    "version_source": "file:contracts/VERSION",
                }
            ]

        api_change = "backend-api-add-export"
        ui_change = "backend-ui-update-export"

        if name == "pair-orphan":
            api_publishes = []
        if name == "pair-uncloned":
            # Only the consumer is present; its provider repository is not cloned.
            build_unit(
                destination / "backend-ui",
                workspace_id=workspace_id,
                unit_id="backend-ui",
                unit_kind="frontend",
                repo_url=ui_url,
                publishes=ui_publishes if name != "pair-orphan" else None,
                consumes=[
                    {
                        "contract": "backend-api-http",
                        "provider_repo": api_url,
                        "version": "^1.5.0",
                        "snapshot": ".hek/project/contracts/backend-api-http.snapshot.json",
                    }
                ],
                change_id=ui_change,
                workspace=workspace_section(
                    workspace_id=workspace_id,
                    unit_id="backend-ui",
                    role="consumer",
                    change_id=ui_change,
                    related=[related_entry("backend-ui", ui_change, [spec_path(ui_change, "export")])],
                ),
            )
            return destination

        if name == "cycle":
            api_consumes = [
                {"contract": "backend-ui-static", "provider_repo": ui_url, "version": "^1.0.0"}
            ]
            ui_consumes = [
                {"contract": "backend-api-http", "provider_repo": api_url, "version": "^1.5.0"}
            ]
        elif name == "pair-orphan":
            api_consumes = []
            ui_consumes = [
                {"contract": "backend-api-http", "provider_repo": api_url, "version": "^1.5.0"}
            ]
        else:
            api_consumes = []
            ui_consumes = [
                {
                    "contract": "backend-api-http",
                    "provider_repo": api_url,
                    "version": "^1.5.0",
                    "snapshot": ".hek/project/contracts/backend-api-http.snapshot.json",
                }
            ]

        related = [
            related_entry("backend-api", api_change, [spec_path(api_change, "export")]),
            related_entry("backend-ui", ui_change, [spec_path(ui_change, "export")]),
        ]
        api_kit = "0.6.0" if name == "version-mismatch" else HEK_VERSION
        ui_kit = HEK_VERSION

        build_unit(
            destination / "backend-api",
            workspace_id=workspace_id,
            unit_id="backend-api",
            repo_url=api_url,
            publishes=api_publishes or None,
            consumes=api_consumes or None,
            change_id=api_change,
            workspace=workspace_section(
                workspace_id=workspace_id,
                unit_id="backend-api",
                role="provider",
                change_id=api_change,
                related=related,
            ),
            kit_version=api_kit,
        )
        build_unit(
            destination / "backend-ui",
            workspace_id=workspace_id,
            unit_id="backend-ui",
            unit_kind="frontend",
            repo_url=ui_url,
            publishes=ui_publishes,
            consumes=ui_consumes,
            change_id=ui_change,
            workspace=workspace_section(
                workspace_id=workspace_id,
                unit_id="backend-ui",
                role="consumer",
                change_id=ui_change,
                related=related,
            ),
            kit_version=ui_kit,
            track_identity=name != "untracked-identity",
        )

        contract_content = '{"openapi":"3.1.0","info":{"version":"1.5.0"}}\n'
        _write(destination / "backend-api/contracts/openapi.yaml", contract_content)
        _write(destination / "backend-api/contracts/VERSION", "1.5.0\n")
        _write(
            destination / "backend-ui/contracts/manifest.json",
            '{"name":"backend-ui-static","version":"1.0.0"}\n',
        )
        _write(destination / "backend-ui/contracts/VERSION", "1.0.0\n")
        _write(destination / "backend-api/contracts/openapi.yaml", contract_content)
        _write(
            destination / "backend-ui/.hek/project/contracts/backend-api-http.snapshot.json",
            contract_content,
        )
        commit(destination / "backend-api")
        commit(destination / "backend-ui")
        if name == "untracked-identity":
            # The final commit above would otherwise re-add every fixture file.
            _run_git(destination / "backend-ui", "rm", "--cached", "-q", "--", ".hek/project/identity.yaml")
            _run_git(destination / "backend-ui", "commit", "-q", "-m", "keep identity untracked", "--no-verify")
        return destination

    if name == "triple-ok":
        api_change = "backend-api-add-export"
        ui_change = "backend-ui-update-export"
        client_change = "client-api-adapt-export"
        related = [
            related_entry("backend-api", api_change, [spec_path(api_change, "export")]),
            related_entry("backend-ui", ui_change, [spec_path(ui_change, "export")]),
            related_entry("client-api", client_change, [spec_path(client_change, "export")]),
        ]
        build_unit(
            destination / "backend-api",
            workspace_id=workspace_id,
            unit_id="backend-api",
            repo_url=api_url,
            publishes=[
                {
                    "contract": "backend-api-http",
                    "artifact": "contracts/openapi.yaml",
                    "format": "openapi-3.1",
                    "version_source": "file:contracts/VERSION",
                }
            ],
            change_id=api_change,
            workspace=workspace_section(
                workspace_id=workspace_id,
                unit_id="backend-api",
                role="provider",
                change_id=api_change,
                related=related,
            ),
        )
        build_unit(
            destination / "backend-ui",
            workspace_id=workspace_id,
            unit_id="backend-ui",
            unit_kind="frontend",
            repo_url=ui_url,
            publishes=[
                {
                    "contract": "backend-ui-static",
                    "artifact": "contracts/manifest.json",
                    "format": "static-manifest",
                    "version_source": "file:contracts/VERSION",
                }
            ],
            consumes=[
                {"contract": "backend-api-http", "provider_repo": api_url, "version": "^1.5.0"}
            ],
            change_id=ui_change,
            workspace=workspace_section(
                workspace_id=workspace_id,
                unit_id="backend-ui",
                role="consumer",
                change_id=ui_change,
                derived_from=api_change,
                related=related,
            ),
        )
        build_unit(
            destination / "client-api",
            workspace_id=workspace_id,
            unit_id="client-api",
            repo_url=client_url,
            publishes=[
                {
                    "contract": "client-api-http",
                    "artifact": "contracts/openapi.yaml",
                    "format": "openapi-3.1",
                    "version_source": "file:contracts/VERSION",
                }
            ],
            consumes=[
                {"contract": "backend-api-http", "provider_repo": api_url, "version": "^1.5.0"}
            ],
            change_id=client_change,
            workspace=workspace_section(
                workspace_id=workspace_id,
                unit_id="client-api",
                role="consumer",
                change_id=client_change,
                derived_from=api_change,
                related=related,
            ),
        )
        _write(destination / "backend-api/contracts/openapi.yaml", '{"openapi":"3.1.0"}\n')
        _write(destination / "backend-api/contracts/VERSION", "1.5.0\n")
        _write(destination / "backend-ui/contracts/manifest.json", '{"name":"backend-ui-static"}\n')
        _write(destination / "backend-ui/contracts/VERSION", "1.0.0\n")
        _write(destination / "client-api/contracts/openapi.yaml", '{"openapi":"3.1.0"}\n')
        _write(destination / "client-api/contracts/VERSION", "1.0.0\n")
        for unit in ("backend-api", "backend-ui", "client-api"):
            commit(destination / unit)
        return destination

    if name in ("nested", "nested-no-identity"):
        api_change = "backend-api-add-export"
        ui_change = "backend-ui-update-export"
        with_identity = name == "nested"
        related = [
            related_entry("backend-api", api_change, [spec_path(api_change, "export")])
        ]
        build_unit(
            destination / "backend-api",
            workspace_id=workspace_id,
            unit_id="backend-api",
            repo_url=api_url,
            with_identity=with_identity,
            change_id=api_change,
            workspace=workspace_section(
                workspace_id=workspace_id,
                unit_id="backend-api",
                role="independent",
                change_id=api_change,
                related=related,
            )
            if with_identity
            else None,
        )
        # The nested repository is created after the parent commit so the parent
        # stays a normal work tree that happens to contain another Git root.
        build_unit(
            destination / "backend-api/backend-ui",
            workspace_id=workspace_id,
            unit_id="backend-ui",
            unit_kind="frontend",
            repo_url=ui_url,
            with_identity=True,
            change_id=ui_change,
            workspace=workspace_section(
                workspace_id=workspace_id,
                unit_id="backend-ui",
                role="independent",
                change_id=ui_change,
                related=[related_entry("backend-ui", ui_change, [spec_path(ui_change, "export")])],
            ),
        )
        return destination

    raise ValueError(f"unhandled workspace fixture: {name}")


@contextmanager
def fixture(name: str) -> Iterator[Path]:
    """Materialize ``name`` under a temporary directory and clean it up."""
    directory = tempfile.mkdtemp(prefix=f"hek-ws-{name}-")
    try:
        yield materialize(name, Path(directory))
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def build(name: str, destination: Path | None = None) -> Path:
    """Materialize ``name``; without ``destination`` the caller must clean up."""
    if destination is None:
        destination = Path(tempfile.mkdtemp(prefix=f"hek-ws-{name}-"))
    return materialize(name, Path(destination))
