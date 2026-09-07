#!/usr/bin/env python3
"""Smoke-test the native OpenSpec integration and Engineering governance shell."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from check_change_workspace import check_workspace
from check_execution import validate_execution
from openspec_common import orchestration_contract
from verify_skill import verify


NATIVE_SKILLS = (
    "openspec-explore",
    "openspec-propose",
    "openspec-apply-change",
    "openspec-sync-specs",
    "openspec-archive-change",
    "openspec-update-change",
    "openspec-verify-change",
)


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def smoke() -> None:
    repository = Path(__file__).resolve().parent.parent
    if not (repository / "templates" / "openspec-schema").is_dir() or not (repository / "core").is_dir():
        raise RuntimeError("run from a kit checkout")

    with tempfile.TemporaryDirectory(prefix="openspec-native-smoke-") as temp:
        root = Path(temp)
        home = root / "home"
        project = root / "project"
        project.mkdir()
        for platform, directory in (("claude", ".claude/skills"), ("codex", ".agents/skills"), ("opencode", ".opencode/skills")):
            target = project / directory / "engineering"
            shutil.copytree(repository / "templates/engineering", target)
            result = verify("engineering", project, platform, source_root=repository)
            if result.get("status") != "PASS":
                raise RuntimeError(f"engineering Skill verification failed for {platform}: {result}")
        environment = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "OPENSPEC_TELEMETRY": "0"}
        configured = (
            run(["openspec", "config", "set", "profile", "custom"], repository, environment),
            run([
                "openspec", "config", "set", "workflows",
                '["propose","explore","apply","update","sync","archive","verify"]',
            ], repository, environment),
        )
        if any(result.returncode != 0 for result in configured):
            raise RuntimeError("could not configure isolated OpenSpec workflow profile")
        initialized = run(
            ["openspec", "init", str(project), "--tools", "codex", "--profile", "custom", "--no-animation"],
            repository,
            environment,
        )
        if initialized.returncode != 0:
            raise RuntimeError(initialized.stderr or initialized.stdout)
        for skill in NATIVE_SKILLS:
            path = project / ".agents/skills" / skill / "SKILL.md"
            if not path.is_file():
                raise RuntimeError(f"missing native OpenSpec Skill: {path}")

        schema_target = project / "openspec/schemas/harness-engineering"
        shutil.copytree(repository / "templates/openspec-schema", schema_target)
        validated = run(["openspec", "schema", "validate", "harness-engineering", "--json"], project, environment)
        if validated.returncode != 0 or '"valid": true' not in validated.stdout:
            raise RuntimeError(f"schema validation failed: {validated.stdout or validated.stderr}")

        created = run(["openspec", "new", "change", "demo-change", "--schema", "harness-engineering"], project, environment)
        if created.returncode != 0:
            raise RuntimeError(created.stderr or created.stdout)
        change = project / "openspec/changes/demo-change"
        write_json(change / "governance.json", {
            "schema_version": 1,
            "change_id": "demo-change",
            "project_root": str(project),
            "orchestration": orchestration_contract("demo-change"),
        })
        if check_workspace(project):
            raise RuntimeError("new OpenSpec change did not satisfy governance workspace checks")

        (change / "tasks.md").write_text("# Tasks\n\n- [x] 1.1 Smoke task\n", encoding="utf-8")
        write_json(change / "execution-evidence.json", {
            "schema_version": 1,
            "strategy": "sequential",
            "fallback_reason": "smoke uses one coordinator",
            "coordinator": "smoke",
            "capability": {"agent_parallelism": False, "isolation": "single-workspace", "max_concurrency": 1},
            "started_at": "2026-09-07T00:00:00+00:00",
            "completed_at": "2026-09-07T00:01:00+00:00",
            "task_runs": [{
                "task_id": "1.1", "actor": "smoke", "status": "completed", "isolation": "single-workspace",
                "workspace": "project", "result_ref": "smoke-run", "started_at": "2026-09-07T00:00:00+00:00",
                "completed_at": "2026-09-07T00:00:30+00:00", "changed_files": ["README.md"],
                "commands": [{"command": "true", "exit_code": 0, "evidence": "smoke.log"}],
            }],
            "integration": {
                "actor": "smoke", "status": "passed", "order": ["1.1"], "changed_files": [],
                "commands": [{"command": "true", "exit_code": 0, "evidence": "integration.log"}],
            },
        })
        record = json.loads((change / "governance.json").read_text(encoding="utf-8"))
        if validate_execution(change, record):
            raise RuntimeError("execution evidence did not cover the checked OpenSpec task")

    print("SKILL SMOKE PASS: OpenSpec 1.12 native Skills, custom schema, governance sidecar, execution evidence")


if __name__ == "__main__":
    try:
        smoke()
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"SKILL SMOKE FAIL: {exc}")
        raise SystemExit(2)
