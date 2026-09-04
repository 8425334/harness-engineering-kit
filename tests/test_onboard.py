from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import onboard


class OnboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Path(__file__).resolve().parents[1]

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


if __name__ == "__main__":
    unittest.main()
