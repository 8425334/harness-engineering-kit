from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import layout, onboard
from scripts.versioning import classify_versions, compare_versions, parse_version


# Layout-derived paths so these tests follow the active layout instead of
# restating it. The concrete values are pinned once, in test_layout.py.
METHODOLOGY = layout.relative("methodology")
CORE = layout.relative("core")
SCRIPTS = layout.relative("scripts")
LESSONS = layout.relative("lessons")
FITNESS = layout.relative("fitness")
COMPACTION = layout.relative("compaction")
VERSION_REL = layout.relative("version")
# Read from the kit so a version bump does not need matching edits here.
SOURCE_VERSION = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
# A version above any real release, for exercising the downgrade guard.
FUTURE_VERSION = "99.0.0"
CONTEXT_INDEX = layout.relative("context_index")
CONTEXT_DOC = layout.relative("context_doc", module_path=".")
RECEIPT_REL = layout.relative("onboarding_receipt")
UNINSTALL_REL = layout.relative("uninstall_receipt")
POLICY_REL = layout.policy_rel()
PROFILE_REL = layout.profile_rel()
PRODUCTION_CHANGES = layout.relative("production_changes")
PRODUCTION_POLICY = layout.relative("production_policy")
PRODUCTION_README = layout.relative("production_readme")
PRODUCTION_TEMPLATE = layout.relative("production_template")
FITNESS_LEDGER = layout.relative("fitness_ledger")
FITNESS_SCRIPT = layout.fitness_script_rel()


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
    "{{METHODOLOGY_VERSION}}": SOURCE_VERSION, "{{YYYY-MM-DD}}": "2027-01-01",
}


def fill_placeholders(root: Path) -> None:
    # Derived from layout so the fixture tracks the active layout. The concrete
    # values are pinned once, in test_layout.py.
    for relative in ("AGENTS.md", "CLAUDE.md", "GEMINI.md",
                     layout.relative("context_index"),
                     layout.relative("context_doc", module_path="."),
                     layout.policy_rel(), layout.profile_rel()):
        target = root / relative
        if not target.is_file():
            continue
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


def apply_with_receipt(root: Path, source: Path, actions: list[onboard.Action], tier: int = 1) -> None:
    plan = onboard.render_plan(root, source, tier, "fresh", actions)
    plan["read_only"] = False
    plan["confirmed_at"] = "2026-09-08T00:00:00+00:00"
    plan["results"] = onboard.apply_actions(root, source, actions)
    receipt = layout.receipt_path(root)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
            version_path = root / VERSION_REL
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
            self.assertEqual(plan["source_version"], SOURCE_VERSION)
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
            version_path = root / VERSION_REL
            version_path.parent.mkdir(parents=True)
            version_path.write_text(f"{FUTURE_VERSION}\n", encoding="utf-8")
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
            context_doc = root / layout.relative("context_doc", module_path=".")
            context_doc.parent.mkdir(parents=True, exist_ok=True)
            context_doc.write_text("partial\n", encoding="utf-8")
            self.assertEqual(onboard.detect_status(root), "partial")
            (root / ".claude/skills/ramer").mkdir(parents=True)
            self.assertEqual(onboard.detect_status(root), "legacy")
            for relative in (VERSION_REL, POLICY_REL):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("0.3.0\n" if relative == VERSION_REL else "version: 1\n", encoding="utf-8")
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
        self.assertTrue(any(action.target == FITNESS_LEDGER for action in actions))

    def test_tier_one_plan_installs_production_controls(self) -> None:
        """agent-policy.yaml references the production policy at every tier."""
        actions = onboard.source_actions(self.source, self.source / "tests", 1, "fresh")
        targets = {action.target for action in actions}
        self.assertIn(PRODUCTION_POLICY, targets)
        self.assertIn(PRODUCTION_README, targets)
        self.assertIn(PRODUCTION_TEMPLATE, targets)
        self.assertIn(FITNESS_SCRIPT, targets)
        self.assertIn(f"{FITNESS}/scripts/check_sdd_quality.py", targets)
        self.assertIn(f"{FITNESS}/sdd-quality.md", targets)
        self.assertNotIn(f"{FITNESS}/scripts/check_security_baseline.py", targets)

    def test_install_plan_includes_opencode_skill(self) -> None:
        actions = onboard.source_actions(self.source, self.source / "tests", 1, "fresh")
        targets = {action.target for action in actions}
        self.assertIn(".opencode/skills/engineering", targets)
        self.assertIn(".cursor/skills/engineering", targets)
        self.assertIn(".gemini/skills/engineering", targets)
        self.assertIn(".trae/skills/engineering", targets)

    def test_native_workflow_contract_includes_verify(self) -> None:
        self.assertIn("openspec-verify-change", onboard.REQUIRED_OPENSPEC_SKILLS)
        self.assertEqual(onboard.OPENSPEC_WORKFLOWS[-1], "verify")

    def test_selected_agent_gets_only_its_native_context_and_skill(self) -> None:
        claude_targets = {action.target for action in onboard.source_actions(self.source, self.source / "tests", 1, "fresh", "claude")}
        self.assertIn("CLAUDE.md", claude_targets)
        self.assertNotIn("AGENTS.md", claude_targets)
        self.assertIn(".claude/skills/engineering", claude_targets)
        self.assertNotIn(".agents/skills/engineering", claude_targets)
        self.assertNotIn(".opencode/skills/engineering", claude_targets)

        codex_targets = {action.target for action in onboard.source_actions(self.source, self.source / "tests", 1, "fresh", "codex")}
        self.assertIn("AGENTS.md", codex_targets)
        self.assertNotIn("CLAUDE.md", codex_targets)
        self.assertNotIn("GEMINI.md", codex_targets)
        self.assertIn(".agents/skills/engineering", codex_targets)
        self.assertNotIn(".claude/skills/engineering", codex_targets)
        self.assertNotIn(".opencode/skills/engineering", codex_targets)

        cursor_targets = {action.target for action in onboard.source_actions(self.source, self.source / "tests", 1, "fresh", "cursor")}
        self.assertIn(".cursor/skills/engineering", cursor_targets)
        self.assertNotIn(".agents/skills/engineering", cursor_targets)

        gemini_targets = {action.target for action in onboard.source_actions(self.source, self.source / "tests", 1, "fresh", "gemini")}
        self.assertIn(".gemini/skills/engineering", gemini_targets)
        self.assertIn("GEMINI.md", gemini_targets)
        self.assertNotIn("AGENTS.md", gemini_targets)

        trae_targets = {action.target for action in onboard.source_actions(self.source, self.source / "tests", 1, "fresh", "trae-work")}
        self.assertIn(".trae/skills/engineering", trae_targets)

    def test_install_plan_includes_requirement_reflection_core(self) -> None:
        actions = onboard.source_actions(self.source, self.source / "tests", 1, "fresh")
        targets = {action.target for action in actions}
        self.assertIn(f"{CORE}/requirement-reflection.md", targets)
        skill = (self.source / "templates/engineering/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Requirement Reflection", skill)
        self.assertIn(f"{CORE}/requirement-reflection.md", skill)

    def test_install_plan_includes_cache_protocol_and_portable_compaction(self) -> None:
        actions = onboard.source_actions(self.source, self.source / "tests", 1, "fresh")
        targets = {action.target for action in actions}
        self.assertIn(f"{SCRIPTS}/context_cache.py", targets)
        self.assertIn(f"{COMPACTION}/README.md", targets)
        self.assertIn(f"{COMPACTION}/codex-save-state.sh", targets)
        self.assertNotIn(".claude/hooks/save-state.sh", targets)

    def test_tier_one_install_passes_agent_policy_check(self) -> None:
        """A Tier 1 install with filled placeholders must satisfy check_agent_policy."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            actions = onboard.source_actions(self.source, root, 1, "fresh")
            apply_with_receipt(root, self.source, actions)
            policy = root / POLICY_REL
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
            # Control scripts are executed from one flat directory and import
            # their siblings by bare name, so match that mode here too.
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
            try:
                from check_agent_policy import validate
            finally:
                sys.path.pop(0)

            self.assertEqual(validate(policy), [])

    def test_apply_reports_created_and_unchanged_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            actions = onboard.source_actions(self.source, root, 1, "fresh")
            first = onboard.apply_actions(root, self.source, actions)
            created = {entry["target"] for entry in first if entry["result"] == "created"}
            self.assertIn("AGENTS.md", created)
            self.assertIn(f"{CORE}/change-lifecycle.md", created)
            second = onboard.apply_actions(root, self.source, actions)
            unchanged = {entry["target"] for entry in second if entry["result"] == "unchanged"}
            self.assertIn(VERSION_REL, unchanged)
            preserved = {entry["target"] for entry in second if entry["result"] == "preserved"}
            self.assertIn("AGENTS.md", preserved)

    def test_apply_rolls_back_created_files_and_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actions = [
                onboard.Action("create", "VERSION", VERSION_REL, "test"),
                onboard.Action("mkdir", None, PRODUCTION_CHANGES, "test"),
                onboard.Action("sync", "VERSION", POLICY_REL, "test"),
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
            first = (root / VERSION_REL).read_bytes()
            onboard.apply_actions(root, self.source, actions)
            self.assertEqual((root / VERSION_REL).read_bytes(), first)
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

    def test_apply_rejects_symlinked_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            # Symlink the directory holding the target, so the write must cross a
            # symlinked path component. Derive it from the target rather than
            # naming a directory, which differs between layouts.
            (root / Path(VERSION_REL).parent).symlink_to(outside, target_is_directory=True)
            sentinel = outside / "sentinel.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            actions = [onboard.Action("create", "VERSION", VERSION_REL, "test")]

            with self.assertRaises(OSError):
                onboard.apply_actions(root, self.source, actions)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertFalse((outside / "VERSION").exists())

    def test_source_preflight_reports_missing_assets(self) -> None:
        action = onboard.Action("create", "missing.txt", "missing.txt", "test")
        errors = onboard.validate_action_sources(self.source, [action])
        self.assertTrue(any("missing.txt" in error for error in errors))

    def test_kit_dev_scripts_are_not_installed(self) -> None:
        """M6: smoke_test_skills.py only works inside a kit checkout."""
        actions = onboard.source_actions(self.source, self.source / "tests", 2, "fresh")
        targets = {action.target for action in actions}
        self.assertNotIn(f"{SCRIPTS}/smoke_test_skills.py", targets)
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
            self.assertEqual(sorted(verbs.values()), ["created"] * 6)
            second = onboard.apply_actions(root, self.source, actions)
            verbs = {entry["target"]: entry["result"] for entry in second if entry["target"].endswith("skills/engineering")}
            self.assertEqual(sorted(verbs.values()), ["unchanged"] * 6)

    def test_json_apply_failure_still_prints_a_receipt(self) -> None:
        """M2: machine mode emits one JSON receipt even when apply rolls back."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            # The core directory as a regular file makes every core sync fail.
            (root / METHODOLOGY).mkdir(parents=True)
            (root / CORE).write_text("blocked\n", encoding="utf-8")
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
            actions = onboard.source_actions(self.source, root, 1, "fresh")
            apply_with_receipt(root, self.source, actions)
            blocked = run_onboard("--project-root", str(root), "--source-root", str(self.source), "--check")
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("ONBOARDING CHECK FAILED", blocked.stdout)
            self.assertNotIn("Read-only plan", blocked.stdout)
            fill_placeholders(root)
            passed = run_onboard("--project-root", str(root), "--source-root", str(self.source), "--check")
            self.assertEqual(passed.returncode, 0, passed.stdout)
            self.assertIn("ONBOARDING CHECK PASSED", passed.stdout)
            self.assertNotIn("Read-only plan", passed.stdout)

    def test_selected_agent_check_does_not_require_other_native_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "claude")
            apply_with_receipt(root, self.source, actions)
            fill_placeholders(root)
            self.assertFalse((root / "AGENTS.md").exists())
            checked = run_onboard("--project-root", str(root), "--source-root", str(self.source), "--agent", "claude", "--check")
            self.assertEqual(checked.returncode, 0, checked.stdout)

    def test_uninstall_plan_is_receipt_driven_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            (root / "AGENTS.md").write_text("project-owned\n", encoding="utf-8")
            actions = onboard.source_actions(self.source, root, 1, "partial")
            apply_with_receipt(root, self.source, actions)
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--plan", "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            plan = json.loads(completed.stdout)
            self.assertEqual(plan["mode"], "uninstall")
            self.assertTrue(plan["read_only"])
            self.assertEqual(plan["receipt_source"], RECEIPT_REL)
            targets = {removal["target"] for removal in plan["removals"]}
            self.assertIn(f"{CORE}/change-lifecycle.md", targets)
            self.assertIn(RECEIPT_REL, targets)
            # A file the install preserved is project-owned and never planned for removal.
            self.assertNotIn("AGENTS.md", targets)
            self.assertTrue((root / f"{CORE}/change-lifecycle.md").is_file())

    def test_uninstall_apply_removes_installed_assets_and_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "codex")
            apply_with_receipt(root, self.source, actions)
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--apply", "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            receipt = json.loads(completed.stdout)
            self.assertFalse(receipt["read_only"])
            counts: dict[str, int] = {}
            for entry in receipt["results"]:
                counts[entry["result"]] = counts.get(entry["result"], 0) + 1
            self.assertGreater(counts.get("removed", 0), 0)
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / ".agents/skills/engineering").exists())
            self.assertFalse((root / CORE).exists())
            self.assertFalse((root / RECEIPT_REL).exists())
            self.assertTrue((root / UNINSTALL_REL).is_file())

    def test_uninstall_preserves_modified_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "codex")
            apply_with_receipt(root, self.source, actions)
            edited = root / f"{CORE}/change-lifecycle.md"
            edited.write_text(edited.read_text(encoding="utf-8") + "\nproject edit\n", encoding="utf-8")
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--apply", "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            receipt = json.loads(completed.stdout)
            kept = {entry["target"]: entry["result"] for entry in receipt["results"]}
            self.assertEqual(kept.get(f"{CORE}/change-lifecycle.md"), "kept-modified")
            self.assertTrue(edited.is_file())

    def test_uninstall_keep_project_facts_retains_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "codex")
            apply_with_receipt(root, self.source, actions)
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--apply", "--json", "--keep-project-facts",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            receipt = json.loads(completed.stdout)
            self.assertTrue(receipt["keep_project_facts"])
            for relative in ("AGENTS.md", CONTEXT_INDEX, POLICY_REL, "openspec/config.yaml"):
                self.assertTrue((root / relative).is_file(), relative)
            self.assertFalse((root / CORE).exists())

    def test_uninstall_without_receipt_falls_back_to_source_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "codex")
            apply_with_receipt(root, self.source, actions)
            (root / RECEIPT_REL).unlink()
            planned = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--tier", "1", "--plan", "--json",
            )
            self.assertEqual(planned.returncode, 0, planned.stdout)
            plan = json.loads(planned.stdout)
            self.assertEqual(plan["receipt_source"], "source-analysis")
            self.assertTrue(any(removal["target"] == VERSION_REL for removal in plan["removals"]))
            applied = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--tier", "1", "--apply", "--json",
            )
            self.assertEqual(applied.returncode, 0, applied.stdout)
            self.assertFalse((root / VERSION_REL).exists())

    def test_uninstall_does_not_follow_symlinked_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "codex")
            apply_with_receipt(root, self.source, actions)
            sentinel = outside / "keep.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            (root / ".agents/skills/engineering/link").symlink_to(outside, target_is_directory=True)
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--apply", "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue((root / ".agents/skills/engineering/link").is_symlink())

    def test_uninstall_without_receipt_preserves_edited_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "codex")
            apply_with_receipt(root, self.source, actions)
            edited = root / "AGENTS.md"
            edited.write_text(edited.read_text(encoding="utf-8") + "\nproject edit\n", encoding="utf-8")
            (root / RECEIPT_REL).unlink()
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--tier", "1", "--apply", "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            receipt = json.loads(completed.stdout)
            results = {entry["target"]: entry["result"] for entry in receipt["results"]}
            self.assertEqual(results.get("AGENTS.md"), "kept-modified")
            self.assertTrue(edited.is_file())
            # An unmodified canonical asset is still byte-identical to the Kit and goes away.
            self.assertFalse((root / VERSION_REL).exists())

    def test_uninstall_without_receipt_leaves_foreign_project_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            agents = root / "AGENTS.md"
            agents.write_text("# Project rules nobody else wrote\n", encoding="utf-8")
            ai = root / "ai.json"
            ai.write_text('{"name": "my-project"}\n', encoding="utf-8")
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--tier", "1", "--apply", "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertTrue(agents.is_file())
            self.assertTrue(ai.is_file())
            receipt = json.loads(completed.stdout)
            removed = [entry for entry in receipt["results"] if entry["result"] == "removed"]
            self.assertEqual(removed, [])

    def test_uninstall_keeps_openspec_skills_without_recorded_digests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "codex")
            apply_with_receipt(root, self.source, actions)
            edited = root / ".agents/skills/openspec-explore/SKILL.md"
            edited.write_text(edited.read_text(encoding="utf-8") + "\nuser edit\n", encoding="utf-8")
            receipt_path = root / RECEIPT_REL
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            # Older Kit releases wrote OpenSpec entries without per-file digests.
            for entry in receipt["results"]:
                if isinstance(entry, dict):
                    entry.pop("trees", None)
            receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--apply", "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertTrue(edited.is_file())
            results = {entry["target"]: entry["result"] for entry in json.loads(completed.stdout)["results"]}
            self.assertEqual(results.get(".agents/skills/openspec-explore"), "kept")
            # The Engineering Skill still has a receipt digest and is removed.
            self.assertFalse((root / ".agents/skills/engineering").exists())

    def test_uninstall_keeps_symlinked_targets_without_aborting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = Path(directory) / "shared-agent-skills"
            outside.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "codex")
            apply_with_receipt(root, self.source, actions)
            (root / ".agents").rename(root / ".agents.installed")
            (root / ".agents").symlink_to(outside, target_is_directory=True)
            sentinel = outside / "keep.txt"
            sentinel.write_text("keep\n", encoding="utf-8")
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--apply", "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue((root / ".agents").is_symlink())
            self.assertTrue((root / ".agents.installed/skills/engineering/SKILL.md").is_file())
            self.assertFalse((root / CORE).exists())

    def test_uninstall_prunes_nested_empty_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            actions = onboard.source_actions(self.source, root, 1, "fresh", "codex")
            apply_with_receipt(root, self.source, actions)
            leftover = root / f"{LESSONS}/2026-01-01"
            leftover.mkdir(parents=True)
            completed = run_onboard(
                "--project-root", str(root), "--source-root", str(self.source),
                "--uninstall", "--apply", "--json",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            receipt = json.loads(completed.stdout)
            self.assertNotIn("errors", receipt)
            self.assertFalse((root / LESSONS).exists())
            self.assertFalse((root / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
