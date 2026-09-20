"""CLI contract tests for ``scripts/workspace_ctl.py``."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

from fixtures.workspace import build, fixture  # noqa: E402


GIT = shutil.which("git")
SCRIPT = REPO / "scripts/workspace_ctl.py"


def run_workspace(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_workspace_stdin(args: list[str], cwd: Path, payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


@unittest.skipUnless(GIT, "git is required to materialize workspace fixtures")
class WorkspaceCliTests(unittest.TestCase):
    def test_discover_json_reports_units_and_contracts(self) -> None:
        with fixture("pair-ok") as root:
            completed = run_workspace(["discover", "--root", str(root), "--json"], root)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["kind"], "workspace-projection")
        self.assertEqual([unit["unit_id"] for unit in payload["units"]], ["backend-api", "backend-ui"])
        self.assertEqual(len(payload["contracts"]), 2)
        self.assertEqual(payload["diagnostics"], [])

    def test_verify_nested_exits_two(self) -> None:
        with fixture("nested") as root:
            completed = run_workspace(["verify", "--root", str(root), "--json"], root)
        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any(item["code"] == "unit.nested" for item in payload["diagnostics"]))

    def test_verify_triple_ok_passes_with_three_local_specs(self) -> None:
        with fixture("triple-ok") as root:
            completed = run_workspace(["verify", "--root", str(root), "--json"], root)
        self.assertEqual(completed.returncode, 0, completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(len(payload["units"]), 3)
        self.assertEqual(payload["diagnostics"], [])
        self.assertFalse((root / "workspace-spec.md").exists())

    def test_verify_orphan_and_cycle_and_version_exit_two(self) -> None:
        for name in ("pair-orphan", "cycle", "version-mismatch"):
            with self.subTest(fixture=name):
                with fixture(name) as root:
                    completed = run_workspace(["verify", "--root", str(root)], root)
                self.assertEqual(completed.returncode, 2)
                self.assertIn("BLOCKED", completed.stdout)

    def test_context_reports_unit_and_cross_unit(self) -> None:
        with fixture("pair-ok") as root:
            unit = root / "backend-api"
            target = unit / "src/x.java"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("class X {}\n", encoding="utf-8")
            completed = run_workspace(["context", str(target), "--json"], unit)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["unit_id"], "backend-api")
            self.assertFalse(payload["cross_unit"])
            self.assertGreater(payload["input_bytes"], 0)
            self.assertIn(".hek/context/AI.md", payload["load_order"])
            # A target owned by another unit fails closed rather than loading it.
            foreign = run_workspace(["context", str(root / "backend-ui/openspec"), "--json"], unit)
            self.assertEqual(foreign.returncode, 2)

    def test_exec_sets_env_and_cwd(self) -> None:
        with fixture("pair-ok") as root:
            completed = run_workspace(
                [
                    "exec", "--root", str(root), "backend-api", "--",
                    sys.executable, "-c",
                    "import os;print(os.getcwd());print(os.environ.get('HEK_UNIT'));print(os.environ.get('HEK_WORKSPACE'))",
                ],
                root,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            lines = completed.stdout.strip().splitlines()
            self.assertEqual(Path(lines[0]).resolve(), (root / "backend-api").resolve())
            self.assertEqual(lines[1], "backend-api")
            self.assertEqual(lines[2], "coil-platform")

    def test_guard_blocks_nested_and_allows_own_repo(self) -> None:
        with fixture("nested") as root:
            nested_target = root / "backend-api/backend-ui/src/x.ts"
            nested_target.parent.mkdir(parents=True, exist_ok=True)
            nested_target.write_text("export {}\n", encoding="utf-8")
            blocked = run_workspace(
                ["guard", "--path", str(nested_target), "--session-root", str(root / "backend-api"), "--json"],
                root,
            )
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(json.loads(blocked.stdout)["diagnostics"][0]["code"], "nested.detected")
        with fixture("pair-ok") as root:
            own = root / "backend-api/src/x.java"
            own.parent.mkdir(parents=True, exist_ok=True)
            own.write_text("class X {}\n", encoding="utf-8")
            allowed = run_workspace(
                ["guard", "--path", str(own), "--session-root", str(root / "backend-api"), "--json"],
                root,
            )
            self.assertEqual(allowed.returncode, 0, allowed.stdout)

    def test_guard_blocks_cross_repo_write(self) -> None:
        with fixture("pair-ok") as root:
            foreign = root / "backend-ui/src/x.ts"
            foreign.parent.mkdir(parents=True, exist_ok=True)
            foreign.write_text("export {}\n", encoding="utf-8")
            completed = run_workspace(
                ["guard", "--path", str(foreign), "--session-root", str(root / "backend-api"), "--json"],
                root,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stdout)["diagnostics"][0]["code"], "boundary.cross-repo")

    def test_compat_tracks_provider_artifact_changes(self) -> None:
        with fixture("pair-ok") as root:
            consumer = root / "backend-ui"
            passing = run_workspace(["compat", "--root", str(root), "--contract", "backend-api-http", "--json"], consumer)
            self.assertEqual(passing.returncode, 0, passing.stdout + passing.stderr)
            self.assertEqual(json.loads(passing.stdout)["verdict"], "pass")
            self.assertTrue((consumer / ".hek/state/compat-backend-api-http.json").is_file())

            artifact = root / "backend-api/contracts/openapi.yaml"
            artifact.write_text('{"openapi":"3.1.0","info":{"version":"2.0.0"}}\n', encoding="utf-8")
            failing = run_workspace(["compat", "--root", str(root), "--contract", "backend-api-http", "--json"], consumer)
            self.assertEqual(failing.returncode, 2)
            self.assertEqual(json.loads(failing.stdout)["verdict"], "fail")

            snapshot = consumer / ".hek/project/contracts/backend-api-http.snapshot.json"
            snapshot.write_text(artifact.read_text(encoding="utf-8"), encoding="utf-8")
            updated = run_workspace(["compat", "--root", str(root), "--contract", "backend-api-http", "--json"], consumer)
            self.assertEqual(updated.returncode, 0, updated.stdout)
            self.assertEqual(json.loads(updated.stdout)["verdict"], "pass")

    def test_graph_and_pin(self) -> None:
        with fixture("triple-ok") as root:
            graph = run_workspace(["graph", "--root", str(root), "--json"], root)
            self.assertEqual(graph.returncode, 0, graph.stderr)
            adjacency = json.loads(graph.stdout)
            self.assertEqual(adjacency["backend-ui"], ["backend-api"])
            self.assertEqual(adjacency["backend-api"], [])
            pinned = run_workspace(["pin", "--root", str(root), "--json"], root)
            self.assertEqual(pinned.returncode, 0, pinned.stderr)
            self.assertEqual(json.loads(pinned.stdout)["version"], "1.0.0")
        with fixture("version-mismatch") as root:
            self.assertEqual(run_workspace(["pin", "--root", str(root)], root).returncode, 2)

    def test_unknown_unit_exec_is_blocked(self) -> None:
        with fixture("pair-ok") as root:
            completed = run_workspace(["exec", "--root", str(root), "nope", "--", sys.executable, "-c", "pass"], root)
        self.assertEqual(completed.returncode, 2)

    def test_status_reports_consumer_lag(self) -> None:
        with fixture("pair-ok") as root:
            aligned = run_workspace(["status", "--root", str(root), "--json"], root)
            self.assertEqual(aligned.returncode, 0, aligned.stderr)
            payload = json.loads(aligned.stdout)
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(len(payload["units"]), 2)
            self.assertEqual(payload["not_onboarded"], [])
            self.assertEqual([item["state"] for item in payload["consumers"]], ["ok"])

            (root / "backend-api/contracts/VERSION").write_text("2.0.0\n", encoding="utf-8")
            lagging = run_workspace(["status", "--root", str(root), "--json"], root)
            self.assertEqual(lagging.returncode, 0, lagging.stderr)
            entry = json.loads(lagging.stdout)["consumers"][0]
            self.assertEqual(entry["state"], "behind")
            self.assertEqual(entry["published"], "2.0.0")
            self.assertEqual(entry["unit_id"], "backend-ui")

    def test_status_lists_units_without_identity(self) -> None:
        with fixture("pair-ok") as root:
            (root / "backend-ui/.hek/project/identity.yaml").unlink()
            completed = run_workspace(["status", "--root", str(root), "--json"], root)
        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertTrue(any(item["code"] == "identity.missing" for item in payload["not_onboarded"]))

    def test_compat_fails_when_range_excludes_the_published_version(self) -> None:
        """I13: a matching snapshot must not hide an incompatible version."""
        with fixture("pair-ok") as root:
            consumer = root / "backend-ui"
            artifact = (root / "backend-api/contracts/openapi.yaml").read_text(encoding="utf-8")
            (root / "backend-api/contracts/VERSION").write_text("2.0.0\n", encoding="utf-8")
            (consumer / ".hek/project/contracts/backend-api-http.snapshot.json").write_text(
                artifact, encoding="utf-8"
            )
            completed = run_workspace(
                ["compat", "--root", str(root), "--contract", "backend-api-http", "--json"], consumer
            )
        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["verdict"], "fail")
        codes = [finding["code"] for finding in payload["contracts"][0]["findings"]]
        self.assertIn("contract.version", codes)

    def test_compat_all_covers_every_consumed_contract(self) -> None:
        with fixture("triple-ok") as root:
            consumer = root / "client-api"
            passing = run_workspace(["compat", "--root", str(root), "--all", "--json"], consumer)
            self.assertEqual(passing.returncode, 0, passing.stdout)
            payload = json.loads(passing.stdout)
            self.assertEqual([entry["contract"] for entry in payload["contracts"]], ["backend-api-http"])
            self.assertTrue((consumer / ".hek/state/compat-backend-api-http.json").is_file())

            (root / "backend-api/contracts/VERSION").write_text("2.0.0\n", encoding="utf-8")
            failing = run_workspace(["compat", "--root", str(root), "--all", "--json"], consumer)
        self.assertEqual(failing.returncode, 2)
        self.assertEqual(json.loads(failing.stdout)["verdict"], "fail")

    def test_compat_requires_a_target(self) -> None:
        with fixture("pair-ok") as root:
            completed = run_workspace(["compat", "--root", str(root), "--json"], root / "backend-ui")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("--contract", completed.stderr)

    def test_exec_is_blocked_by_a_blocked_projection(self) -> None:
        with fixture("nested") as root:
            completed = run_workspace(
                ["exec", "--root", str(root), "backend-api", "--", sys.executable, "-c", "print('ran')"],
                root,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("unit.nested", completed.stderr)
        self.assertNotIn("ran", completed.stdout)

    def test_verify_nonexistent_root_is_blocked(self) -> None:
        with fixture("pair-ok") as root:
            missing = root / "not-cloned"
            completed = run_workspace(["verify", "--root", str(missing), "--json"], root)
        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertEqual([item["code"] for item in payload["diagnostics"]], ["workspace.root"])

    def test_guard_stdin_hook_payload(self) -> None:
        """The hook layer: a host payload on stdin decides the verdict."""
        with fixture("nested") as root:
            target = root / "backend-api/backend-ui/src/x.ts"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("export {}\n", encoding="utf-8")
            blocked = run_workspace_stdin(
                ["guard", "--stdin", "--json"],
                root / "backend-api",
                json.dumps({"tool_input": {"file_path": str(target)}}),
            )
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(json.loads(blocked.stdout)["diagnostics"][0]["code"], "nested.detected")
            # Without a usable session root the hook fails closed, not open.
            unknown = run_workspace_stdin(
                ["guard", "--stdin", "--json"],
                root,
                json.dumps({"tool_input": {"file_path": str(target)}}),
            )
            self.assertEqual(unknown.returncode, 2)
            self.assertEqual(json.loads(unknown.stdout)["diagnostics"][0]["code"], "harness.mismatch")
        with fixture("pair-ok") as root:
            own = root / "backend-api/src/x.java"
            own.parent.mkdir(parents=True, exist_ok=True)
            own.write_text("class X {}\n", encoding="utf-8")
            allowed = run_workspace_stdin(
                ["guard", "--stdin", "--json"],
                root / "backend-api",
                json.dumps({"tool_input": {"file_path": str(own)}}),
            )
            self.assertEqual(allowed.returncode, 0, allowed.stdout)
            unparseable = run_workspace_stdin(["guard", "--stdin", "--json"], root, "")
            self.assertEqual(unparseable.returncode, 0)
            self.assertEqual(json.loads(unparseable.stdout)["diagnostics"][0]["level"], "info")

    def test_contract_pin_template_checks_the_declared_range(self) -> None:
        import shutil as shutil_module

        repo = Path(__file__).resolve().parents[1]
        template = repo / "templates/fitness/check_contract_pin.py.template"
        with fixture("pair-ok") as root:
            unit = root / "backend-ui"
            script = unit / ".hek/fitness/scripts/check_contract_pin.py"
            script.parent.mkdir(parents=True, exist_ok=True)
            shutil_module.copyfile(template, script)
            matching = subprocess.run(
                [sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            self.assertEqual(matching.returncode, 0, matching.stdout + matching.stderr)
            identity = unit / ".hek/project/identity.yaml"
            identity.write_text(
                identity.read_text(encoding="utf-8").replace('version: "^1.5.0"', 'version: "^2.0.0"'),
                encoding="utf-8",
            )
            mismatched = subprocess.run(
                [sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
        self.assertEqual(mismatched.returncode, 2)
        self.assertIn("does not satisfy", mismatched.stdout)

    def test_context_budget_exceeded_is_blocked(self) -> None:
        with fixture("pair-ok") as root:
            unit = root / "backend-api"
            modules = ["."] + [f"mod{index}" for index in range(1, 5)]
            for module in modules:
                directory = unit if module == "." else unit / module
                directory.mkdir(parents=True, exist_ok=True)
                context = unit / ".hek/context" / ("" if module == "." else module) / "AI.md"
                context.parent.mkdir(parents=True, exist_ok=True)
                padding = "\n".join("x" * 80 for _ in range(700))
                context.write_text(
                    "# Module Context\n\ncannot override or weaken higher-level policy.\n\n"
                    "## Responsibilities\n\n## Boundaries\n\n## Local Verification\n\n## Navigation\n\n"
                    f"{padding}\n",
                    encoding="utf-8",
                )
            index = unit / ".hek/context/ai.json"
            index.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "context-index",
                        "project": "backend-api",
                        "summary": "budget fixture",
                        "modules": [
                            {
                                "path": module,
                                "summary": f"{module} module",
                                "context": f".hek/context/{'' if module == '.' else module + '/'}AI.md",
                                "read_when": [module if module != "." else "root"],
                            }
                            for module in modules
                        ],
                        "entrypoints": {
                            "policy": ".hek/project/agent-policy.yaml",
                            "lifecycle": ".hek/kit/core/change-lifecycle.md",
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            target = unit / "mod1/x.ts"
            completed = run_workspace(
                [
                    "context", str(target), "--json",
                    *[item for index in range(1, 5) for item in ("--keyword", f"mod{index}")],
                ],
                unit,
            )
        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertGreater(payload["input_bytes"], 262144)
        self.assertTrue(any(item["code"] == "context.budget" for item in payload["diagnostics"]))


if __name__ == "__main__":
    unittest.main()
