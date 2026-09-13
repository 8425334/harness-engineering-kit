"""Contract tests for the installed-layout single source of truth."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import layout  # noqa: E402


#: Fields whose value is a plain project-relative path. ``context_root`` is the
#: walk root rather than an artifact, ``root`` describes the layout itself, and
#: ``control_plane`` is a directory whose depth carries no self-location meaning,
#: so all three are excluded from the parity checks below.
EXCLUDED_FIELDS = {"root", "context_root", "control_plane"}
PATH_FIELDS = tuple(
    name for name in layout.Layout.__dataclass_fields__ if name not in EXCLUDED_FIELDS
)


class LegacyLayoutTests(unittest.TestCase):
    """Legacy values must reproduce the literals the control scripts used."""

    def test_accessors_match_the_pre_0_6_literals(self) -> None:
        root = REPO
        self.assertEqual(layout.relative("methodology", layout=layout.LEGACY), "docs/methodology")
        self.assertEqual(layout.relative("fitness", layout=layout.LEGACY), "docs/fitness")
        self.assertEqual(layout.relative("context_index", layout=layout.LEGACY), "ai.json")
        self.assertEqual(layout.relative("version", layout=layout.LEGACY), "docs/methodology/VERSION")
        self.assertEqual(
            layout.relative("onboarding_receipt", layout=layout.LEGACY),
            "docs/methodology/onboarding.json",
        )
        self.assertEqual(layout.relative("lessons", layout=layout.LEGACY), "docs/methodology/lessons")
        self.assertEqual(
            layout.relative("production_changes", layout=layout.LEGACY),
            "docs/methodology/production/changes",
        )
        self.assertEqual(
            layout.policy_path(root, layout=layout.LEGACY),
            root / "docs/methodology/agent-policy.yaml",
        )
        self.assertEqual(
            layout.profile_path(root, layout=layout.LEGACY),
            root / "docs/methodology/profile.yaml",
        )
        self.assertEqual(layout.protected_prefix(layout=layout.LEGACY), "docs/fitness/")

    def test_context_documents_sit_beside_the_code(self) -> None:
        root = REPO
        self.assertEqual(
            layout.context_doc_path(root, "ruoyi-modules/system", layout=layout.LEGACY),
            root / "ruoyi-modules/system/AI.md",
        )
        self.assertEqual(layout.context_doc_path(root, ".", layout=layout.LEGACY), root / "AI.md")
        self.assertEqual(layout.context_doc_path(root, None, layout=layout.LEGACY), root / "AI.md")
        # ai.json stores this as a string and the validator compares it verbatim,
        # so a stray "./" prefix would be a breaking change even though Path
        # comparison normalises it away.
        self.assertEqual(layout.relative("context_doc", module_path=".", layout=layout.LEGACY), "AI.md")
        self.assertEqual(layout.relative("context_doc", layout=layout.LEGACY), "AI.md")
        self.assertEqual(
            layout.relative("context_doc", module_path="ruoyi-modules/system", layout=layout.LEGACY),
            "ruoyi-modules/system/AI.md",
        )


class HekLayoutTests(unittest.TestCase):
    """The single-directory layout keeps everything Harness owns under .hek/."""

    def test_every_artifact_lives_under_the_hek_root(self) -> None:
        for name in PATH_FIELDS:
            with self.subTest(field=name):
                self.assertTrue(
                    layout.relative(name, layout=layout.HEK).startswith(".hek/"),
                    f"{name} must live under .hek/",
                )

    def test_openspec_stays_at_the_repository_root(self) -> None:
        # OpenSpec resolves its own root by walking up from the cwd, and its
        # generated Skills hardcode root-relative paths, so no Harness layout may
        # claim it.
        for target in (layout.LEGACY, layout.HEK):
            for name in PATH_FIELDS:
                with self.subTest(layout=target.root, field=name):
                    self.assertNotIn("openspec/", layout.relative(name, layout=target))

    def test_context_documents_mirror_the_module_tree(self) -> None:
        root = REPO
        self.assertEqual(
            layout.context_doc_path(root, "ruoyi-modules/system", layout=layout.HEK),
            root / ".hek/context/ruoyi-modules/system/AI.md",
        )
        self.assertEqual(
            layout.context_doc_path(root, ".", layout=layout.HEK),
            root / ".hek/context/AI.md",
        )


class NamedAccessorTests(unittest.TestCase):
    """The named accessors must agree with the layout table they derive from."""

    def test_legacy_accessors_reproduce_the_original_literals(self) -> None:
        target = layout.LEGACY
        self.assertEqual(layout.policy_rel(layout=target), "docs/methodology/agent-policy.yaml")
        self.assertEqual(layout.profile_rel(layout=target), "docs/methodology/profile.yaml")
        self.assertEqual(layout.protected_prefix(layout=target), "docs/fitness/")
        self.assertEqual(layout.fitness_script_rel(layout=target), "docs/fitness/scripts/fitness.py")

    def test_hek_accessors_follow_the_single_directory_layout(self) -> None:
        target = layout.HEK
        self.assertEqual(layout.policy_rel(layout=target), ".hek/project/agent-policy.yaml")
        self.assertEqual(layout.profile_rel(layout=target), ".hek/project/profile.yaml")
        self.assertEqual(layout.protected_prefix(layout=target), ".hek/fitness/")
        self.assertEqual(layout.fitness_script_rel(layout=target), ".hek/fitness/scripts/fitness.py")

    def test_fitness_script_lives_under_the_fitness_root(self) -> None:
        # The phase gate matches the command string recorded in evidence, so the
        # runner path must be derived from the same place the installer uses.
        for target in (layout.LEGACY, layout.HEK):
            with self.subTest(layout=target.root):
                self.assertTrue(
                    layout.fitness_script_rel(layout=target).startswith(
                        layout.protected_prefix(layout=target)
                    )
                )

    def test_accessors_default_to_the_active_layout(self) -> None:
        self.assertEqual(layout.policy_rel(), layout.policy_rel(layout=layout.ACTIVE))
        self.assertEqual(layout.protected_prefix(), layout.protected_prefix(layout=layout.ACTIVE))


class DepthParityTests(unittest.TestCase):
    """New and old locations must sit at the same depth below the project root.

    Control scripts and the Fitness runner derive the project root from
    ``Path(__file__).parents[N]``. Keeping the depths equal is what lets
    ``fitness.py`` (``parents[3]``) and ``verify_skill.py`` survive the move
    unchanged, so it is asserted rather than assumed.
    """

    #: Depth intentionally differs. Both are only ever read through an explicit
    #: ``layout.path(...)`` call, never through parent arithmetic, so the change
    #: cannot break self-location.
    DEPTH_EXCEPTIONS = {
        "version": "versioning.read_version() always receives an explicit path",
        "context_index": "context scripts join the literal path onto the project root",
    }

    def test_artifact_depth_is_preserved(self) -> None:
        for name in PATH_FIELDS:
            if name in self.DEPTH_EXCEPTIONS:
                continue
            legacy = layout.relative(name, layout=layout.LEGACY)
            target = layout.relative(name, layout=layout.HEK)
            with self.subTest(field=name):
                self.assertEqual(
                    len(Path(legacy).parts),
                    len(Path(target).parts),
                    f"{name}: {legacy} -> {target} changes nesting depth",
                )

    def test_depth_exceptions_are_still_accurate(self) -> None:
        """Guard the exception list itself, so it cannot rot into an excuse."""
        for name, reason in self.DEPTH_EXCEPTIONS.items():
            with self.subTest(field=name):
                self.assertNotEqual(
                    len(Path(layout.relative(name, layout=layout.LEGACY)).parts),
                    len(Path(layout.relative(name, layout=layout.HEK)).parts),
                    f"{name} no longer differs in depth; drop it from DEPTH_EXCEPTIONS ({reason})",
                )

    def test_the_installed_script_depth_matches_the_runner_expectation(self) -> None:
        # fitness.py resolves its rules directory as parents[1] and the project
        # root as parents[3] from its own file. Both layouts must agree.
        for target in (layout.LEGACY, layout.HEK):
            scripts = Path(layout.relative("fitness", layout=target)) / "scripts/fitness.py"
            with self.subTest(layout=target.root):
                self.assertEqual(scripts.parents[1].as_posix(), layout.relative("fitness", layout=target))
                self.assertEqual(len(scripts.parts) - 1, 3)


class RootResolutionTests(unittest.TestCase):
    def test_project_root_self_locates_in_the_kit_checkout(self) -> None:
        self.assertTrue(layout.is_kit_checkout(REPO))
        self.assertEqual(layout.project_root(), REPO)

    def test_project_root_self_locates_in_an_installation(self) -> None:
        """Both install layouts must resolve to the same project root.

        The checkout test above cannot catch a wrong parent index, because the
        scripts sit at a different depth there. Copy the module into a simulated
        installation so the installed depth is exercised directly.
        """
        source = REPO / "scripts/layout.py"
        for install_dir in ("docs/methodology/scripts", ".hek/kit/scripts"):
            with self.subTest(install=install_dir):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory).resolve()
                    target = root / install_dir
                    target.mkdir(parents=True)
                    shutil.copy2(source, target / "layout.py")
                    probe = subprocess.run(
                        [sys.executable, "-c",
                         "import layout; print(layout.project_root()); print(layout.is_kit_checkout(layout.project_root()))"],
                        cwd=target, capture_output=True, text=True, encoding="utf-8",
                    )
                    self.assertEqual(probe.returncode, 0, probe.stderr)
                    resolved, looks_like_kit = probe.stdout.split()
                    self.assertEqual(Path(resolved), root)
                    self.assertEqual(looks_like_kit, "False")

    def test_explicit_root_wins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(layout.project_root(directory), Path(directory).resolve())


if __name__ == "__main__":
    unittest.main()
