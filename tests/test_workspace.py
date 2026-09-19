"""Contract tests for workspace federation (identity, projection, guard)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))

import workspace  # noqa: E402
import workspace_guard  # noqa: E402
import onboard  # noqa: E402
from check_change_workspace import check_workspace  # noqa: E402
from check_identity import validate as validate_identity_file  # noqa: E402
from fixtures.workspace import build, fixture  # noqa: E402
from openspec_common import orchestration_contract  # noqa: E402


GIT = shutil.which("git")


@unittest.skipUnless(GIT, "git is required to materialize workspace fixtures")
class WorkspaceFixtureTests(unittest.TestCase):
    """Fixtures are built in a temp directory; nothing is committed to the Kit."""

    def test_discover_single_unit_skips_federation(self) -> None:
        with fixture("single") as root:
            projection = workspace.discover([root])
        self.assertEqual(projection.units, [])
        self.assertEqual(projection.contracts, [])
        self.assertEqual(projection.diagnostics, [])
        self.assertIsNone(projection.workspace_id)

    def test_pair_ok_discovers_two_units_and_one_contract(self) -> None:
        with fixture("pair-ok") as root:
            projection = workspace.discover([root])
        self.assertEqual([unit.unit_id for unit in projection.units], ["backend-api", "backend-ui"])
        self.assertEqual([item["contract"] for item in projection.contracts], ["backend-api-http", "backend-ui-static"])
        self.assertEqual(projection.diagnostics, [])
        self.assertEqual(projection.workspace_id, "coil-platform")

    def test_three_units_have_three_local_specs(self) -> None:
        with fixture("triple-ok") as root:
            projection = workspace.discover([root])
            self.assertEqual(projection.diagnostics, [])
            self.assertEqual(len(projection.units), 3)
            for unit in projection.units:
                change_dirs = workspace.change_dirs(unit.root)
                self.assertEqual(len(change_dirs), 1)
                self.assertTrue(workspace.spec_files(change_dirs[0]))
            self.assertFalse((root / "workspace-spec.md").exists())
            self.assertFalse((root / "specs").exists())
            self.assertFalse((root / "openspec").exists())

    def test_verify_nested_blocked(self) -> None:
        with fixture("nested") as root:
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "unit.nested" for item in projection.diagnostics))

    def test_verify_nested_without_identity_blocked(self) -> None:
        with fixture("nested-no-identity") as root:
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "unit.nested" for item in projection.diagnostics))

    def test_verify_orphan_contract(self) -> None:
        with fixture("pair-orphan") as root:
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        orphan = [item for item in projection.diagnostics if item.code == "contract.orphan"]
        self.assertTrue(orphan)
        self.assertTrue(all(item.level == "blocked" for item in orphan))

    def test_verify_uncloned_provider_warning(self) -> None:
        with fixture("pair-uncloned") as root:
            code, projection = workspace.verify([root])
        self.assertEqual(code, 0, [item.as_dict() for item in projection.diagnostics])
        orphan = [item for item in projection.diagnostics if item.code == "contract.orphan"]
        self.assertTrue(orphan)
        self.assertTrue(all(item.level == "warning" for item in orphan))

    def test_verify_cycle_blocked(self) -> None:
        with fixture("cycle") as root:
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "contract.cycle" for item in projection.diagnostics))

    def test_verify_version_mismatch(self) -> None:
        with fixture("version-mismatch") as root:
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "kit.version-mismatch" for item in projection.diagnostics))

    def test_verify_untracked_identity(self) -> None:
        with fixture("untracked-identity") as root:
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "identity.untracked" for item in projection.diagnostics))

    def test_foreign_methodology_not_legacy(self) -> None:
        with fixture("foreign-methodology") as product:
            sys.path.insert(0, str(REPO / "scripts"))
            import onboard  # noqa: PLC0415

            self.assertEqual(onboard.detect_status(product), "fresh")
            self.assertIsNone(onboard.relayout_source(product))
            self.assertIsNone(onboard.installed_version_path(product).read_text(encoding="utf-8") if onboard.installed_version_path(product).is_file() else None)
            plan = onboard.render_plan(product, REPO, 2, "fresh", [])
            self.assertEqual(plan["version_relation"], "fresh")
            self.assertEqual([warning["code"] for warning in plan["warnings"]], ["legacy.unverified"])
            # A genuine legacy install still migrates.
            (product / "docs/methodology/scripts").mkdir(exist_ok=True)
            (product / "docs/methodology/core").mkdir(exist_ok=True)
            (product / "docs/methodology/VERSION").write_text("0.5.1\n", encoding="utf-8")
            self.assertEqual(onboard.detect_status(product), "relayout")


@unittest.skipUnless(GIT, "git is required to materialize workspace fixtures")
class ProjectionTests(unittest.TestCase):
    def test_digest_is_layout_independent(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            build("pair-ok", Path(first))
            build("pair-ok", Path(second))
            projection_a = workspace.discover([Path(first)])
            projection_b = workspace.discover([Path(second)])
        self.assertEqual(projection_a.digest, projection_b.digest)
        self.assertNotEqual(projection_a.roots, projection_b.roots)

    def test_digest_changes_on_kit_version_or_tracking(self) -> None:
        with fixture("pair-ok") as root:
            baseline = workspace.discover([root]).digest
            version_file = root / "backend-api/.hek/VERSION"
            version_file.write_text("9.9.9\n", encoding="utf-8")
            changed = workspace.discover([root]).digest
            self.assertNotEqual(baseline, changed)

    def test_mixed_workspace_roots_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            build("pair-ok", base / "one")
            build("triple-ok", base / "two")
            # Rewrite one unit's workspace_id so the aggregated call sees two groups.
            identity = base / "two/backend-api/.hek/project/identity.yaml"
            identity.write_text(
                identity.read_text(encoding="utf-8").replace("coil-platform", "other-platform"),
                encoding="utf-8",
            )
            code, projection = workspace.verify([base / "one", base / "two"])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "workspace.mixed" for item in projection.diagnostics))

    def test_central_spec_is_rejected(self) -> None:
        with fixture("pair-ok") as root:
            (root / "workspace-spec.md").write_text("# central\n", encoding="utf-8")
            code, projection = workspace.verify([root])
            self.assertEqual(code, 2)
            self.assertTrue(any(item.code == "spec.reference" and "central" in item.message for item in projection.diagnostics))
            (root / "workspace-spec.md").unlink()
            (root / "specs").mkdir()
            code, _ = workspace.verify([root])
            self.assertEqual(code, 2)
            shutil.rmtree(root / "specs")
            (root / "openspec/changes").mkdir(parents=True)
            code, _ = workspace.verify([root])
            self.assertEqual(code, 2)

    def test_duplicate_unit_id_is_rejected(self) -> None:
        with fixture("pair-ok") as root:
            identity = root / "backend-ui/.hek/project/identity.yaml"
            identity.write_text(
                identity.read_text(encoding="utf-8").replace("unit_id: backend-ui", "unit_id: backend-api"),
                encoding="utf-8",
            )
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "identity.duplicate" for item in projection.diagnostics))

    def test_spec_reference_must_match_local_change(self) -> None:
        with fixture("pair-ok") as root:
            governance = root / "backend-ui/openspec/changes/backend-ui-update-export/governance.json"
            record = json.loads(governance.read_text(encoding="utf-8"))
            record["workspace"]["related_changes"][0]["change_id"] = "backend-api-missing"
            governance.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "spec.missing" for item in projection.diagnostics))

    def test_missing_external_spec_blocked(self) -> None:
        with fixture("pair-ok") as root:
            (root / "backend-api/openspec/changes/backend-api-add-export/specs/export.md").unlink()
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "spec.missing" for item in projection.diagnostics))

    def test_spec_path_outside_change_is_reference_error(self) -> None:
        with fixture("pair-ok") as root:
            governance = root / "backend-ui/openspec/changes/backend-ui-update-export/governance.json"
            record = json.loads(governance.read_text(encoding="utf-8"))
            record["workspace"]["related_changes"][0]["specs"][0]["path"] = "README.md"
            (root / "backend-api/README.md").write_text("# readme\n", encoding="utf-8")
            governance.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            code, projection = workspace.verify([root])
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "spec.reference" for item in projection.diagnostics))


class IdentityValidationTests(unittest.TestCase):
    def _payload(self) -> dict:
        return {
            "schema_version": 1,
            "kind": "harness-unit",
            "workspace_id": "coil-platform",
            "unit_id": "backend-ui",
            "unit_kind": "frontend",
            "repo_url": "ssh://git@example.com/coil/backend-ui.git",
            "publishes": [],
            "consumes": [],
        }

    def test_valid_identity_has_no_errors(self) -> None:
        self.assertEqual(workspace.validate_identity(self._payload()), [])

    def test_unknown_top_level_key_is_rejected(self) -> None:
        payload = self._payload()
        payload["extra"] = "x"
        self.assertTrue(any("unknown top-level keys" in error for error in workspace.validate_identity(payload)))

    def test_artifact_cannot_escape_the_unit(self) -> None:
        payload = self._payload()
        payload["publishes"] = [
            {"contract": "backend-ui-static", "artifact": "../x", "format": "static-manifest", "version_source": "file:V"}
        ]
        self.assertTrue(any("artifact" in error for error in workspace.validate_identity(payload)))

    def test_publishes_require_repo_url(self) -> None:
        payload = self._payload()
        payload.pop("repo_url")
        payload["publishes"] = [
            {"contract": "backend-ui-static", "artifact": "dist/x", "format": "static-manifest", "version_source": "file:V"}
        ]
        self.assertTrue(any("repo_url is required" in error for error in workspace.validate_identity(payload)))

    def test_semver_range_validation(self) -> None:
        self.assertTrue(workspace.is_semver_range("^1.4.0"))
        self.assertTrue(workspace.is_semver_range(">=1.0 <=2.0"))
        self.assertTrue(workspace.is_semver_range("1.x"))
        self.assertFalse(workspace.is_semver_range("latest"))

    def test_unit_scoped_path_rejects_bare_relative(self) -> None:
        self.assertEqual(workspace.unit_scoped_path({"unit": "backend-ui", "path": "a/b.md"}), ("backend-ui", "a/b.md"))
        for invalid in ("/abs/x.md", "a/../b.md", "a/", "a\\b.md", "../x"):
            with self.subTest(path=invalid):
                with self.assertRaises(ValueError):
                    workspace.unit_scoped_path({"unit": "backend-ui", "path": invalid})
        with self.assertRaises(ValueError):
            workspace.unit_scoped_path("openspec/changes/x/specs/y.md")

    def test_identity_file_validation_reports_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(any("missing identity" in error for error in validate_identity_file(directory)))


@unittest.skipUnless(GIT, "git is required to materialize workspace fixtures")
class GuardTests(unittest.TestCase):
    def test_guard_allows_own_repo(self) -> None:
        with fixture("pair-ok") as root:
            target = root / "backend-api/src/x.java"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("class X {}\n", encoding="utf-8")
            diagnostics = workspace_guard.guard(target, root / "backend-api")
        self.assertEqual(diagnostics, [])

    def test_guard_blocks_nested_write(self) -> None:
        with fixture("nested") as root:
            target = root / "backend-api/backend-ui/src/x.ts"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("export {}\n", encoding="utf-8")
            diagnostics = workspace_guard.guard(target, root / "backend-api")
        self.assertEqual([item.code for item in diagnostics], ["nested.detected"])
        self.assertTrue(workspace_guard.has_blocked(diagnostics))

    def test_guard_blocks_cross_repo_write(self) -> None:
        with fixture("pair-ok") as root:
            target = root / "backend-ui/src/x.ts"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("export {}\n", encoding="utf-8")
            diagnostics = workspace_guard.guard(target, root / "backend-api")
        self.assertEqual([item.code for item in diagnostics], ["boundary.cross-repo"])

    def test_nesting_waiver_is_scoped(self) -> None:
        with fixture("nested") as root:
            waivers = root / "backend-api/.hek/state/waivers"
            waivers.mkdir(parents=True, exist_ok=True)
            (waivers / "nested-split.json").write_text(
                json.dumps({"id": "split", "approved_by": "reviewer", "expires_at": "2999-01-01T00:00:00Z"}),
                encoding="utf-8",
            )
            target = root / "backend-api/backend-ui/src/x.ts"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("export {}\n", encoding="utf-8")
            guarded = workspace_guard.guard(target, root / "backend-api")
            code, projection = workspace.verify([root])
        self.assertEqual([item.code for item in guarded], ["nesting.waived"])
        self.assertFalse(workspace_guard.has_blocked(guarded))
        self.assertEqual(code, 2)
        self.assertTrue(any(item.code == "unit.nested" for item in projection.diagnostics))


class GovernanceWorkspaceTests(unittest.TestCase):
    """Unit-local half of I15, enforced by check_change_workspace.py."""

    def _change(self, root: Path, change_id: str, workspace: dict | None) -> Path:
        change_dir = root / "openspec/changes" / change_id
        (change_dir / "specs").mkdir(parents=True, exist_ok=True)
        (change_dir / ".openspec.yaml").write_text("schema: harness-engineering\n", encoding="utf-8")
        (change_dir / "specs/cap.md").write_text("## Purpose\n\nx\n", encoding="utf-8")
        record = {
            "schema_version": 1,
            "change_id": change_id,
            "title": change_id,
            "profile": "standard",
            "risk": "medium",
            "skill": "engineering",
            "mode": "backend",
            "delivery_scope": "technical",
            "project_root": str(root),
            "owner": "owner",
            "orchestration": orchestration_contract(change_id),
            "events": [],
        }
        if workspace is not None:
            record["workspace"] = workspace
        (change_dir / "governance.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return change_dir

    def _section(self, change_id: str, **overrides) -> dict:
        section = {
            "workspace_id": "coil-platform",
            "unit_id": "backend-ui",
            "role": "consumer",
            "change_id": change_id,
            "related_changes": [
                {
                    "unit": "backend-ui",
                    "change_id": change_id,
                    "specs": [{"unit": "backend-ui", "path": f"openspec/changes/{change_id}/specs/cap.md"}],
                }
            ],
        }
        section.update(overrides)
        return section

    def test_workspace_section_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._change(root, "demo-1", None)
            self.assertEqual(check_workspace(root), [])

    def test_unknown_workspace_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._change(root, "demo-1", self._section("demo-1", extra="x"))
            errors = check_workspace(root)
        self.assertTrue(any("unknown keys" in error for error in errors))

    def test_bad_role_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._change(root, "demo-1", self._section("demo-1", role="owner"))
            errors = check_workspace(root)
        self.assertTrue(any("role must be" in error for error in errors))

    def test_local_spec_must_exist_and_live_inside_the_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            section = self._section("demo-1")
            section["related_changes"][0]["specs"][0]["path"] = "README.md"
            (root / "README.md").write_text("# readme\n", encoding="utf-8")
            self._change(root, "demo-1", section)
            errors = check_workspace(root)
            self.assertTrue(any("must live inside" in error for error in errors))
            (root / "README.md").unlink()
            errors = check_workspace(root)
            self.assertTrue(any("does not exist in this unit" in error for error in errors))

    def test_foreign_members_are_only_format_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            section = self._section("demo-1")
            section["related_changes"].append(
                {
                    "unit": "backend-api",
                    "change_id": "backend-api-add-export",
                    "specs": [{"unit": "backend-api", "path": "openspec/changes/backend-api-add-export/specs/x.md"}],
                }
            )
            self._change(root, "demo-1", section)
            self.assertEqual(check_workspace(root), [])

    def test_breaking_change_requires_window_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            section = self._section("demo-1", contracts=[
                {
                    "contract": "backend-api-http",
                    "provider": "backend-api",
                    "from_version": "1.4.0",
                    "to_version": "2.0.0",
                    "breaking": True,
                }
            ])
            self._change(root, "demo-1", section)
            errors = check_workspace(root)
        self.assertTrue(any("deprecated_until" in error for error in errors))
        self.assertTrue(any("verification is required" in error for error in errors))
        self.assertTrue(any("derived_from is required" in error for error in errors))

    def test_local_verification_evidence_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            section = self._section("demo-1", contracts=[
                {
                    "contract": "backend-api-http",
                    "provider": "backend-api",
                    "from_version": "1.4.0",
                    "to_version": "1.5.0",
                    "breaking": False,
                    "verification": {"unit": "backend-ui", "path": ".hek/state/compat-backend-api-http.json"},
                }
            ])
            self._change(root, "demo-1", section)
            errors = check_workspace(root)
            self.assertTrue(any("verification.path does not exist" in error for error in errors))
            evidence = root / ".hek/state/compat-backend-api-http.json"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text("{}\n", encoding="utf-8")
            self.assertEqual(check_workspace(root), [])


class OnboardIdentityTests(unittest.TestCase):
    def test_identity_check_is_skipped_without_an_identity_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(onboard.identity_check_required(root))
            identity = root / ".hek/project/identity.yaml"
            identity.parent.mkdir(parents=True, exist_ok=True)
            identity.write_text("schema_version: 1\n", encoding="utf-8")
            self.assertTrue(onboard.identity_check_required(root))

    def test_unit_id_apply_writes_an_identity_draft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            action = onboard.Action(
                "create-identity",
                "templates/identity.yaml.template",
                "identity.yaml.draft",
                "unit identity draft",
            )
            onboard.apply_actions(
                root,
                REPO,
                [action],
                identity={
                    "unit_id": "backend-api",
                    "workspace_id": "coil-platform",
                    "unit_kind": "backend",
                    "repo_url": "ssh://git@example.com/coil/backend-api.git",
                },
            )
            text = (root / "identity.yaml.draft").read_text(encoding="utf-8")
        self.assertIn('unit_id: "backend-api"', text)
        self.assertIn('workspace_id: "coil-platform"', text)
        # The draft is valid input to the identity validator once written.
        payload = workspace.parse_identity(text)
        self.assertEqual(workspace.validate_identity(payload), [])

    def test_workspace_root_is_not_treated_as_a_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("unit-a", "unit-b"):
                unit = root / name
                (unit / ".git").mkdir(parents=True)
            self.assertTrue(onboard.looks_like_workspace_root(root))
            self.assertFalse(onboard.looks_like_workspace_root(root / "unit-a"))


if __name__ == "__main__":
    unittest.main()
