from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import onboard
from scripts.versioning import classify_versions, compare_versions, parse_version


PLACEHOLDER_VALUES = {
    "{{PROJECT_NAME}}": "test-project", "{{TEAM_OR_OWNER}}": "team",
    "{{LANGUAGE_OR_FRAMEWORK}}": "python", "{{FAST_TEST_COMMAND}}": "pytest -x",
    "{{TEST_COMMAND}}": "pytest", "{{BUILD_COMMAND}}": "make build",
    "{{FITNESS_COMMAND}}": "pytest fitness", "{{READABLE_PATHS}}": ".",
    "{{WRITABLE_PATHS}}": "src", "{{DENIED_PATHS_OR_SECRETS}}": ".env",
    "{{ONE_SENTENCE_PROJECT_SUMMARY}}": "A test project.", "{{ROOT_MODULE_SUMMARY}}": "root",
    "{{ROUTING_KEYWORD}}": "root", "{{DIRECTORY_NAME}}": "Root", "{{SCOPE_DESCRIPTION}}": "repo",
    "{{RESPONSIBILITY_1}}": "demo", "{{RESPONSIBILITY_2}}": "demo",
    "{{ALLOWED_MODIFICATIONS}}": "src", "{{FORBIDDEN_MODIFICATIONS}}": ".env",
    "{{DEPENDENCY_RULE}}": "src", "{{LOCAL_TEST_COMMAND_OR_POLICY_REFERENCE}}": "pytest",
    "{{ENTRY_POINTS}}": "src", "{{RELATED_CONTRACTS}}": "none", "{{RULE_OWNER}}": "team",
    "{{METHODOLOGY_OWNER}}": "team", "{{PROJECT_SPECIFIC_DEFINITION_OR_DEFAULT}}": ">2 files",
    "{{FAST_NORMAL_OR_DEEP}}": "normal", "{{EXCEPTION_RECORD_PATH}}": "docs/methodology/exceptions.md",
    "{{METHODOLOGY_VERSION}}": "0.3.0", "{{YYYY-MM-DD}}": "2027-01-01",
}


def fill_placeholders(root: Path) -> None:
    for relative in ("AGENTS.md", "CLAUDE.md", "ai.json", "AI.md",
                     "docs/methodology/agent-policy.yaml", "docs/methodology/profile.yaml"):
        target = root / relative
        text = target.read_text(encoding="utf-8")
        for placeholder, value in PLACEHOLDER_VALUES.items():
            text = text.replace(placeholder, value)
        target.write_text(text, encoding="utf-8")


def run_onboard(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "onboard.py"), *arguments],
        capture_output=True,
        text=True,
    )


class OnboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Path(__file__).resolve().parents[1]

    def test_versioning_classifies_ordered_releases(self) -> None:
        self.assertEqual(classify_versions("0.2.0", "0.3.0"), "upgrade")
        self.assertEqual(classify_versions("0.3.0", "0.3.0"), "same")
        self.assertEqual(classify_versions("0.4.0", "0.3.0"), "downgrade")
        self.assertEqual(classify_versions("not-a-version", "0.3.0"), "invalid")
        self.assertEqual(classify_versions("", "0.3.0"), "invalid")
        self.assertEqual(classify_versions(None, "not-a-version"), "invalid")
        self.assertEqual(classify_versions("1.0.0-01", "1.0.0"), "invalid")
        self.assertLess(compare_versions(parse_version("1.0.0-rc.1"), parse_version("1.0.0")), 0)

    def test_plan_reports_version_transition_and_release_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            version_path = root / "docs/methodology/VERSION"
            version_path.parent.mkdir(parents=True)
            version_path.write_text("0.2.0\n", encoding="utf-8")
            plan = onboard.render_plan(
                root,
                self.source,
                1,
                "current",
                [],
            )
            self.assertEqual(plan["installed_version"], "0.2.0")
            self.assertEqual(plan["source_version"], "0.3.0")
            self.assertEqual(plan["version_relation"], "upgrade")
            self.assertEqual(plan["version_transition"]["from"], "0.2.0")
            self.assertEqual(plan["migration_manifest_errors"], [])
            self.assertTrue(plan["release_migrations"])

    def test_unversioned_legacy_project_is_not_treated_as_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".claude/skills/ramer").mkdir(parents=True)
            plan = onboard.render_plan(root, self.source, 1, "legacy", [])
            self.assertEqual(plan["version_relation"], "unversioned")

    def test_apply_blocks_unversioned_legacy_project_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            (root / ".claude/skills/ramer").mkdir(parents=True)
            result = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--tier", "1", "--apply", "--json",
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["version_relation"], "unversioned")
            self.assertFalse((root / "AGENTS.md").exists())

    def test_apply_blocks_downgrade_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            version_path = root / "docs/methodology/VERSION"
            version_path.parent.mkdir(parents=True)
            version_path.write_text("0.4.0\n", encoding="utf-8")
            result = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--tier", "1", "--apply", "--json",
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["version_relation"], "downgrade")
            self.assertFalse((root / "AGENTS.md").exists())

    def test_detects_all_repository_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(onboard.detect_status(root), "fresh")
            (root / "AI.md").write_text("partial\n", encoding="utf-8")
            self.assertEqual(onboard.detect_status(root), "partial")
            (root / ".claude/skills/ramer").mkdir(parents=True)
            self.assertEqual(onboard.detect_status(root), "legacy")
            (root / "docs/methodology").mkdir(parents=True)
            (root / "docs/methodology/VERSION").write_text("0.3.0\n", encoding="utf-8")
            (root / "docs/methodology/agent-policy.yaml").write_text("version: 1\n", encoding="utf-8")
            (root / ".agents/skills/engineering").mkdir(parents=True)
            (root / ".agents/skills/engineering/SKILL.md").write_text("skill\n", encoding="utf-8")
            self.assertEqual(onboard.detect_status(root), "legacy")
            (root / ".claude/skills/ramer").rmdir()
            self.assertEqual(onboard.detect_status(root), "current")

    def test_tier_two_plan_includes_java_scanner(self) -> None:
        actions = onboard.source_actions(self.source, self.source / "tests", 2, "fresh")
        scanner = [action for action in actions if action.target.endswith("JavaParameterScanner.java")]
        self.assertEqual(len(scanner), 1)
        self.assertEqual(scanner[0].source, "templates/fitness/JavaParameterScanner.java.template")
        self.assertTrue(any(action.target == "docs/fitness/verification-ledger.md" for action in actions))

    def test_tier_one_plan_installs_production_controls(self) -> None:
        """agent-policy.yaml references the production policy at every tier."""
        actions = onboard.source_actions(self.source, self.source / "tests", 1, "fresh")
        targets = {action.target for action in actions}
        self.assertIn("docs/methodology/production/policy.yaml", targets)
        self.assertIn("docs/methodology/production/README.md", targets)
        self.assertIn("docs/methodology/production/change-record.template.json", targets)
        self.assertNotIn("docs/fitness/scripts/fitness.py", targets)

    def test_tier_one_install_passes_agent_policy_check(self) -> None:
        """A Tier 1 install with filled placeholders must satisfy check_agent_policy."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            onboard.apply_actions(root, self.source, onboard.source_actions(self.source, root, 1, "fresh"))
            policy = root / "docs/methodology/agent-policy.yaml"
            text = policy.read_text(encoding="utf-8")
            for placeholder, value in {
                "{{PROJECT_NAME}}": "tier-one",
                "{{TEAM_OR_OWNER}}": "team-a",
                "{{LANGUAGE_OR_FRAMEWORK}}": "python",
                "{{FAST_TEST_COMMAND}}": "pytest -x",
                "{{TEST_COMMAND}}": "pytest",
                "{{BUILD_COMMAND}}": "make build",
                "{{FITNESS_COMMAND}}": "pytest fitness",
                "{{READABLE_PATHS}}": ".",
                "{{WRITABLE_PATHS}}": "src",
                "{{DENIED_PATHS_OR_SECRETS}}": ".env",
            }.items():
                text = text.replace(placeholder, value)
            policy.write_text(text, encoding="utf-8")
            from scripts.check_agent_policy import validate

            self.assertEqual(validate(policy), [])

    def test_apply_reports_created_and_unchanged_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            actions = onboard.source_actions(self.source, root, 1, "fresh")
            first = onboard.apply_actions(root, self.source, actions)
            created = {entry["target"] for entry in first if entry["result"] == "created"}
            self.assertIn("AGENTS.md", created)
            self.assertIn("docs/methodology/core/change-lifecycle.md", created)
            second = onboard.apply_actions(root, self.source, actions)
            unchanged = {entry["target"] for entry in second if entry["result"] == "unchanged"}
            self.assertIn("docs/methodology/VERSION", unchanged)
            preserved = {entry["target"] for entry in second if entry["result"] == "preserved"}
            self.assertIn("AGENTS.md", preserved)

    def test_apply_rolls_back_created_files_and_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actions = [
                onboard.Action("create", "VERSION", "docs/methodology/VERSION", "test"),
                onboard.Action("mkdir", None, "docs/methodology/production/changes", "test"),
                onboard.Action("sync", "VERSION", "docs/methodology/policy.yaml", "test"),
            ]
            original = onboard.copy_file
            calls = {"count": 0}

            def flaky(source, target, overwrite):
                calls["count"] += 1
                if calls["count"] == 1:
                    return original(source, target, overwrite)
                raise OSError("simulated failure")

            with patch.object(onboard, "copy_file", side_effect=flaky):
                with self.assertRaises(OSError):
                    onboard.apply_actions(root, self.source, actions)
            self.assertFalse((root / "docs").exists())

    def test_apply_is_idempotent_and_preserves_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            existing = root / "AI.md"
            existing.write_text("project-owned\n", encoding="utf-8")
            actions = onboard.source_actions(self.source, root, 1, "partial")
            onboard.apply_actions(root, self.source, actions)
            first = (root / "docs/methodology/VERSION").read_bytes()
            onboard.apply_actions(root, self.source, actions)
            self.assertEqual((root / "docs/methodology/VERSION").read_bytes(), first)
            self.assertEqual(existing.read_text(encoding="utf-8"), "project-owned\n")

    def test_apply_rolls_back_overwrite_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "VERSION"
            target.write_text("old\n", encoding="utf-8")
            actions = [onboard.Action("sync", "VERSION", "VERSION", "test")]
            with patch.object(onboard, "copy_file", side_effect=OSError("simulated failure")):
                with self.assertRaises(OSError):
                    onboard.apply_actions(root, self.source, actions)
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")

    def test_source_preflight_reports_missing_assets(self) -> None:
        action = onboard.Action("create", "missing.txt", "missing.txt", "test")
        errors = onboard.validate_action_sources(self.source, [action])
        self.assertTrue(any("missing.txt" in error for error in errors))

    def test_kit_dev_scripts_are_not_installed(self) -> None:
        """M6: smoke_test_skills.py only works inside a kit checkout."""
        actions = onboard.source_actions(self.source, self.source / "tests", 2, "fresh")
        targets = {action.target for action in actions}
        self.assertNotIn("docs/methodology/scripts/smoke_test_skills.py", targets)
        errors = onboard.validate_action_sources(self.source, actions)
        self.assertEqual(errors, [])

    def test_no_superpowers_directories_are_created(self) -> None:
        """L1: the installer must not inject unrelated workspace directories."""
        actions = onboard.source_actions(self.source, self.source / "tests", 2, "fresh")
        targets = {action.target for action in actions}
        self.assertNotIn("docs/superpowers/plans", targets)
        self.assertNotIn("docs/superpowers/specs", targets)

    def test_sync_tree_reports_created_then_unchanged(self) -> None:
        """L3: Skill sync receipts use the same verbs as file copies."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actions = onboard.source_actions(self.source, root, 1, "fresh")
            first = onboard.apply_actions(root, self.source, actions)
            verbs = {entry["target"]: entry["result"] for entry in first if entry["target"].endswith("skills/engineering")}
            self.assertEqual(sorted(verbs.values()), ["created", "created"])
            second = onboard.apply_actions(root, self.source, actions)
            verbs = {entry["target"]: entry["result"] for entry in second if entry["target"].endswith("skills/engineering")}
            self.assertEqual(sorted(verbs.values()), ["unchanged", "unchanged"])

    def test_json_apply_failure_still_prints_a_receipt(self) -> None:
        """M2: machine mode emits one JSON receipt even when apply rolls back."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            # docs/methodology/core as a regular file makes every core sync fail.
            (root / "docs/methodology").mkdir(parents=True)
            (root / "docs/methodology/core").write_text("blocked\n", encoding="utf-8")
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--tier", "1", "--apply", "--json",
            )
            self.assertEqual(completed.returncode, 2)
            receipt = json.loads(completed.stdout)
            self.assertTrue(receipt["errors"])
            self.assertTrue(any("rolled back" in error for error in receipt["errors"]))

    def test_check_output_reports_the_outcome_not_a_plan(self) -> None:
        """M1: `check` prints its result instead of a misleading read-only plan."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            onboard.apply_actions(root, self.source, onboard.source_actions(self.source, root, 1, "fresh"))
            blocked = run_onboard("--project-root", str(root), "--source-root", str(self.source), "--check")
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("ONBOARDING CHECK FAILED", blocked.stdout)
            self.assertNotIn("Read-only plan", blocked.stdout)
            fill_placeholders(root)
            passed = run_onboard("--project-root", str(root), "--source-root", str(self.source), "--check")
            self.assertEqual(passed.returncode, 0, passed.stdout)
            self.assertIn("ONBOARDING CHECK PASSED", passed.stdout)
            self.assertNotIn("Read-only plan", passed.stdout)


if __name__ == "__main__":
    unittest.main()
