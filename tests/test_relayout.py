"""Tests for the pre-0.6 -> .hek/ migration."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from scripts import layout, onboard  # noqa: E402


#: Minimal path document that satisfies the context-document contract, so the
#: migration can be checked end to end rather than only structurally.
PATH_DOCUMENT = (
    "# Path Context\n\n"
    "This detail cannot override or weaken higher-level policy.\n\n"
    "## Responsibilities\n\n- demo\n\n"
    "## Boundaries\n\n- demo\n\n"
    "## Local Verification\n\n- pytest\n\n"
    "## Navigation\n\n- src\n"
)


POLICY_BODY = """version: 1
project:
  name: "demo"

context:
  architecture_overview: docs/methodology/core/harness-engineering.md
  dependency_rules: docs/methodology/core/ddd-modeling.md

permissions:
  readable_paths: ["."]
  writable_paths: ["src", "docs", "openspec"]
  protected_paths: [.hek/fitness]

delivery:
  production_policy: docs/methodology/production/policy.yaml

methodology:
  lifecycle: docs/methodology/core/change-lifecycle.md
"""

INDEX_BODY = {
    "schema_version": 1,
    "kind": "context-index",
    "project": "demo",
    "summary": "A demo project.",
    "modules": [
        {"path": ".", "summary": "root", "context": "AI.md", "read_when": ["root"]},
        {"path": "src/api", "summary": "api", "context": "src/api/AI.md", "read_when": ["api"]},
    ],
    "entrypoints": {
        "policy": "docs/methodology/agent-policy.yaml",
        "lifecycle": "docs/methodology/core/change-lifecycle.md",
    },
}


def build_legacy_install(root: Path) -> None:
    """Lay out a project exactly as the pre-0.6 installer left it."""
    (root / ".git").mkdir()
    (root / "docs/methodology/core").mkdir(parents=True)
    (root / "docs/methodology/scripts").mkdir()
    (root / "docs/methodology/production").mkdir()
    (root / "docs/methodology/lessons").mkdir()
    (root / "docs/fitness/scripts").mkdir(parents=True)
    (root / "src/api").mkdir(parents=True)

    (root / "docs/methodology/VERSION").write_text("0.5.1\n", encoding="utf-8")
    (root / "docs/methodology/agent-policy.yaml").write_text(POLICY_BODY, encoding="utf-8")
    (root / "docs/methodology/profile.yaml").write_text("version: 2\n", encoding="utf-8")
    (root / "docs/methodology/core/change-lifecycle.md").write_text("# lifecycle\n", encoding="utf-8")
    (root / "docs/methodology/scripts/versioning.py").write_text("# kit script\n", encoding="utf-8")
    (root / "docs/methodology/production/policy.yaml").write_text("writable: [src]\n", encoding="utf-8")
    (root / "docs/methodology/lessons/README.md").write_text("# lessons\n", encoding="utf-8")
    (root / "docs/methodology/onboarding.json").write_text('{"schema_version": 1}\n', encoding="utf-8")
    # Retired before 0.5.0: nothing can verify it, so the migration only deletes
    # it because the plan lists it explicitly.
    (root / "docs/methodology/templates").mkdir()
    (root / "docs/methodology/templates/ramer").mkdir()
    (root / "docs/methodology/templates/ramer/SKILL.md").write_text("old\n", encoding="utf-8")

    # Project-added Fitness checks must survive a wholesale tree move.
    (root / "docs/fitness/scripts/fitness.py").write_text("# runner\n", encoding="utf-8")
    (root / "docs/fitness/scripts/check_vega_boundary.py").write_text("# project check\n", encoding="utf-8")
    (root / "docs/fitness/vega-contract-freeze.md").write_text("# project rule\n", encoding="utf-8")

    (root / "ai.json").write_text(json.dumps(INDEX_BODY, indent=2) + "\n", encoding="utf-8")
    (root / "AI.md").write_text(PATH_DOCUMENT, encoding="utf-8")
    (root / "src/api/AI.md").write_text(PATH_DOCUMENT, encoding="utf-8")
    (root / "AGENTS.md").write_text("# entry\n", encoding="utf-8")


def relayout_actions(root: Path) -> list[onboard.Action]:
    return onboard.source_actions(REPO, root, 2, "relayout", "codex")


class DetectionTests(unittest.TestCase):
    def test_legacy_install_is_detected_as_relayout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_legacy_install(root)
            self.assertEqual(onboard.detect_status(root), "relayout")

    def test_a_migrated_project_is_not_detected_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_legacy_install(root)
            onboard.apply_actions(root, REPO, relayout_actions(root))
            self.assertNotEqual(onboard.detect_status(root), "relayout")

    def test_a_fresh_project_is_not_treated_as_relayout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(onboard.detect_status(Path(directory)), "fresh")


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        build_legacy_install(self.root)
        self.actions = relayout_actions(self.root)

    def kinds(self, kind: str) -> list[onboard.Action]:
        return [action for action in self.actions if action.kind == kind]

    def test_project_content_is_moved_not_reinstalled(self) -> None:
        moved = {action.target: action.from_target for action in self.kinds("move")}
        self.assertEqual(moved.get(layout.policy_rel()), "docs/methodology/agent-policy.yaml")
        self.assertEqual(moved.get(layout.profile_rel()), "docs/methodology/profile.yaml")
        self.assertEqual(moved.get(layout.relative("context_index")), "ai.json")
        self.assertEqual(moved.get(layout.relative("context_doc", module_path=".")), "AI.md")
        self.assertEqual(
            moved.get(layout.relative("context_doc", module_path="src/api")),
            "src/api/AI.md",
        )

    def test_moved_targets_are_not_also_created(self) -> None:
        moved_targets = {action.target for action in self.kinds("move")}
        created = {action.target for action in self.actions if action.kind in {"create", "preserve"}}
        self.assertEqual(moved_targets & created, set())

    def test_project_fitness_survives_a_wholesale_tree_move(self) -> None:
        trees = {action.from_target: action.target for action in self.kinds("move-tree")}
        self.assertIn("docs/fitness", trees)
        self.assertEqual(trees["docs/fitness"], layout.relative("fitness"))

    def test_moves_run_before_the_install_actions(self) -> None:
        kinds = [action.kind for action in self.actions]
        self.assertLess(kinds.index("move"), kinds.index("create"))
        self.assertLess(kinds.index("move-tree"), kinds.index("create"))

    def test_superseded_tree_is_listed_for_deletion(self) -> None:
        removed = {action.target for action in self.kinds("remove")}
        self.assertIn("docs/methodology/VERSION", removed)
        self.assertIn("docs/methodology/core/change-lifecycle.md", removed)
        self.assertIn("docs/methodology/templates/ramer/SKILL.md", removed)
        # Moved content must never also be scheduled for deletion.
        moved_from = {str(action.from_target) for action in self.kinds("move")}
        self.assertEqual(removed & moved_from, set())

    def test_policy_is_rewritten_after_it_moves(self) -> None:
        rewrites = self.kinds("rewrite-policy")
        self.assertEqual(len(rewrites), 1)
        self.assertEqual(rewrites[0].target, layout.policy_rel())
        kinds = [action.kind for action in self.actions]
        self.assertLess(kinds.index("move"), kinds.index("rewrite-policy"))

    def test_legacy_directories_are_pruned(self) -> None:
        pruned = {action.target for action in self.kinds("prune-empty")}
        self.assertIn("docs/methodology", pruned)
        self.assertIn("docs/fitness", pruned)


class ApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        build_legacy_install(self.root)
        self.actions = relayout_actions(self.root)
        onboard.apply_actions(self.root, REPO, self.actions)

    def test_project_content_lands_under_hek(self) -> None:
        self.assertTrue((self.root / layout.policy_rel()).is_file())
        self.assertTrue((self.root / layout.profile_rel()).is_file())
        self.assertTrue((self.root / layout.relative("context_index")).is_file())
        self.assertTrue((self.root / layout.relative("context_doc", module_path=".")).is_file())
        self.assertTrue(
            (self.root / layout.relative("context_doc", module_path="src/api")).is_file()
        )

    def test_project_added_fitness_checks_survive(self) -> None:
        fitness = self.root / layout.relative("fitness")
        self.assertTrue((fitness / "scripts/check_vega_boundary.py").is_file())
        self.assertTrue((fitness / "vega-contract-freeze.md").is_file())

    def test_superseded_tree_is_removed(self) -> None:
        self.assertFalse((self.root / "docs/methodology").exists())
        self.assertFalse((self.root / "docs/fitness").exists())

    def test_policy_is_repointed_at_the_new_layout(self) -> None:
        policy = (self.root / layout.policy_rel()).read_text(encoding="utf-8")
        self.assertIn(layout.relative("core"), policy)
        self.assertIn(layout.relative("production_policy"), policy)
        self.assertNotIn("docs/methodology", policy)

    def test_context_index_is_repointed_at_the_new_layout(self) -> None:
        index = json.loads(
            (self.root / layout.relative("context_index")).read_text(encoding="utf-8")
        )
        contexts = [module["context"] for module in index["modules"]]
        self.assertEqual(
            contexts,
            [
                layout.relative("context_doc", module_path="."),
                layout.relative("context_doc", module_path="src/api"),
            ],
        )
        # Moving the file is not enough: every route it carries must resolve.
        for relative in contexts:
            self.assertTrue((self.root / relative).is_file(), relative)
        self.assertEqual(index["entrypoints"]["policy"], layout.policy_rel())
        self.assertTrue((self.root / index["entrypoints"]["lifecycle"]).is_file())

    def test_policy_grants_write_access_to_the_control_plane(self) -> None:
        policy = (self.root / layout.policy_rel()).read_text(encoding="utf-8")
        writable = next(
            line for line in policy.splitlines() if line.strip().startswith("writable_paths:")
        )
        self.assertIn(layout.HEK.root, writable)
        # Pre-existing entries must be preserved, not replaced.
        self.assertIn("src", writable)

    def test_migration_is_idempotent(self) -> None:
        results = onboard.apply_actions(self.root, REPO, self.actions)
        by_kind: dict[str, list[str]] = {}
        for action, result in zip(self.actions, results):
            by_kind.setdefault(action.kind, []).append(result["result"])
        # The origins are gone, so a second run reports them missing instead of
        # relocating anything twice.
        self.assertEqual(set(by_kind["move"]), {"missing"})
        self.assertEqual(set(by_kind["move-tree"]), {"missing"})
        self.assertTrue((self.root / layout.policy_rel()).is_file())
        self.assertFalse((self.root / "docs/methodology").exists())


class ContextResolutionTests(unittest.TestCase):
    """The end-to-end proof that the migration produced a working control plane."""

    def test_resolve_context_succeeds_after_migrating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_legacy_install(root)
            onboard.apply_actions(root, REPO, relayout_actions(root))

            sys.path.insert(0, str(REPO / "scripts"))
            from resolve_context import resolve_context

            resolved = resolve_context(root, ["src/api"])
            self.assertEqual(resolved["targets"], ["src/api"])
            # Root context first, then the deepest matching module.
            self.assertEqual(
                resolved["load_order"],
                [
                    layout.policy_rel(),
                    layout.profile_rel(),
                    layout.relative("context_index"),
                    layout.relative("context_doc", module_path="."),
                    layout.relative("context_doc", module_path="src/api"),
                ],
            )
            for relative in resolved["load_order"]:
                self.assertTrue((root / relative).is_file(), relative)


class DriftProtectionTests(unittest.TestCase):
    def test_a_file_edited_after_planning_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_legacy_install(root)
            actions = relayout_actions(root)
            # Edit a file the plan scheduled for deletion, after the plan exists.
            victim = root / "docs/methodology/core/change-lifecycle.md"
            victim.write_text("# hand-edited after planning\n", encoding="utf-8")

            results = onboard.apply_actions(root, REPO, actions)
            kept = [
                entry for entry in results
                if entry["target"] == "docs/methodology/core/change-lifecycle.md"
            ]
            self.assertEqual([entry["result"] for entry in kept], ["kept-modified"])
            self.assertTrue(victim.is_file(), "an edited file must not be deleted")

    def test_an_existing_destination_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_legacy_install(root)
            actions = relayout_actions(root)
            destination = root / layout.policy_rel()
            destination.parent.mkdir(parents=True)
            destination.write_text("# written by hand\n", encoding="utf-8")

            results = onboard.apply_actions(root, REPO, actions)
            entry = next(item for item in results if item["target"] == layout.policy_rel())
            self.assertEqual(entry["result"], "preserved")
            self.assertEqual(destination.read_text(encoding="utf-8"), "# written by hand\n")


if __name__ == "__main__":
    unittest.main()
