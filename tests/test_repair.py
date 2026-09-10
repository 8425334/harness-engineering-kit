"""Regression tests for the conversation-time self-repair engine."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import onboard, repair


REPO = Path(__file__).resolve().parents[1]
HEALTHY_OPENSPEC = {"command": "openspec", "version": "1.12.0", "ok": True}


def install(root: Path, agent: str = "codex", tier: int = 1) -> None:
    """Build a complete install without shelling out to the OpenSpec CLI."""

    actions = [
        action
        for action in onboard.source_actions(REPO, root, tier, "fresh", agent)
        if action.kind != "openspec-init"
    ]
    onboard.apply_actions(root, REPO, actions)
    receipt = {
        "schema_version": 1,
        "status": "fresh",
        "project_root": str(root),
        "source_root": str(REPO),
        "source_version": "0.5.1",
        "installed_version": "0.5.1",
        "version_relation": "fresh",
        "tier": tier,
        "agent": agent,
        "read_only": False,
    }
    (root / "docs/methodology").mkdir(parents=True, exist_ok=True)
    (root / "docs/methodology/onboarding.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tool = onboard.OPENSPEC_TOOLS.get(agent)
    if tool:
        for skill in onboard.REQUIRED_OPENSPEC_SKILLS:
            path = root / onboard.OPENSPEC_SKILL_ROOTS[tool] / skill / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"---\nname: {skill}\n---\n", encoding="utf-8")


def finding_ids(payload: dict[str, object]) -> set[str]:
    return {str(finding["id"]) for finding in payload.get("findings") or []}  # type: ignore[union-attr]


def blocking_findings(payload: dict[str, object]) -> list[dict[str, object]]:
    return [
        finding
        for finding in payload.get("findings") or []  # type: ignore[union-attr]
        if str(finding.get("severity")) in ("repairable", "manual")
    ]


class RepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hek-repair-")
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        openspec = patch.object(repair, "probe_openspec", return_value=dict(HEALTHY_OPENSPEC))
        openspec.start()
        self.addCleanup(openspec.stop)

    def options(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "project_root": self.root,
            "source_root": REPO,
            "agent": None,
            "tier": None,
            "apply": False,
            "diagnose": True,
            "as_json": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    # -- diagnosis ---------------------------------------------------------

    def test_healthy_install_has_no_blocking_findings(self) -> None:
        install(self.root)
        code, payload = repair.run(self.options())
        self.assertEqual(code, 0)
        self.assertEqual(blocking_findings(payload), [])
        self.assertIn(payload["status"], ("healthy", "healthy-with-notes"))
        self.assertEqual(payload["agent"], "codex")
        self.assertEqual(payload["read_only"], True)

    def test_not_installed_points_at_onboarding(self) -> None:
        code, payload = repair.run(self.options())
        self.assertEqual(code, 2)
        self.assertIn("not-installed", finding_ids(payload))
        self.assertEqual(payload["repairs"], [])

    def test_diagnose_is_read_only(self) -> None:
        install(self.root)
        shutil.rmtree(self.root / ".agents/skills/engineering")
        before = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        code, payload = repair.run(self.options())
        self.assertEqual(code, 2)
        self.assertIn("skill-missing", finding_ids(payload))
        after = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        self.assertEqual(before, after)
        self.assertFalse((self.root / "docs/methodology/repair.json").exists())

    # -- repair ------------------------------------------------------------

    def test_repairs_missing_engineering_skill(self) -> None:
        install(self.root)
        skill = self.root / ".agents/skills/engineering"
        shutil.rmtree(skill)
        code, payload = repair.run(self.options(apply=True))
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "repaired")
        self.assertEqual(blocking_findings(payload), [])
        self.assertTrue((skill / "SKILL.md").is_file())
        self.assertTrue((skill / "references/self-repair.md").is_file())
        receipt = json.loads((self.root / "docs/methodology/repair.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["mode"], "apply")
        self.assertEqual(receipt["verification"]["status"], "passed")

    def test_repairs_missing_canonical_resources_and_broken_script(self) -> None:
        install(self.root)
        (self.root / "docs/methodology/core/change-lifecycle.md").unlink()
        (self.root / "docs/methodology/scripts/versioning.py").unlink()
        broken = self.root / "docs/methodology/scripts/check_profile.py"
        broken.write_text("def broken(:\n", encoding="utf-8")

        code, payload = repair.run(self.options())
        self.assertEqual(code, 2)
        ids = finding_ids(payload)
        self.assertIn("control-plane-missing", ids)
        self.assertIn("control-plane-drift", ids)
        self.assertIn("control-script-broken", ids)

        code, payload = repair.run(self.options(apply=True))
        self.assertEqual(code, 0, payload)
        self.assertTrue((self.root / "docs/methodology/core/change-lifecycle.md").is_file())
        self.assertTrue((self.root / "docs/methodology/scripts/versioning.py").is_file())
        self.assertEqual(
            broken.read_text(encoding="utf-8"),
            (REPO / "scripts/check_profile.py").read_text(encoding="utf-8"),
        )

    def test_repairs_unversioned_install(self) -> None:
        install(self.root)
        (self.root / "docs/methodology/VERSION").unlink()
        code, payload = repair.run(self.options())
        self.assertEqual(payload["version_relation"], "unversioned")
        self.assertIn("control-plane-missing", finding_ids(payload))
        code, payload = repair.run(self.options(apply=True))
        self.assertEqual(code, 0, payload)
        self.assertEqual(
            (self.root / "docs/methodology/VERSION").read_text(encoding="utf-8").strip(),
            (REPO / "VERSION").read_text(encoding="utf-8").strip(),
        )

    def test_repair_preserves_project_owned_facts(self) -> None:
        install(self.root)
        agents = self.root / "AGENTS.md"
        policy = self.root / "docs/methodology/agent-policy.yaml"
        agents.write_text("# project rules\n", encoding="utf-8")
        policy.write_text("project: mine\n", encoding="utf-8")
        code, payload = repair.run(self.options(apply=True))
        self.assertEqual(code, 0, payload)
        self.assertEqual(agents.read_text(encoding="utf-8"), "# project rules\n")
        self.assertEqual(policy.read_text(encoding="utf-8"), "project: mine\n")

    def test_repair_restores_missing_project_fact_with_placeholder_notice(self) -> None:
        install(self.root)
        (self.root / "ai.json").unlink()
        code, payload = repair.run(self.options())
        self.assertIn("project-fact-missing", finding_ids(payload))
        code, payload = repair.run(self.options(apply=True))
        self.assertEqual(code, 0, payload)
        self.assertTrue((self.root / "ai.json").is_file())

    def test_protected_fitness_baseline_is_never_rewritten(self) -> None:
        install(self.root)
        fitness_rule = self.root / "docs/fitness/sdd-quality.md"
        self.assertTrue(fitness_rule.is_file())
        fitness_rule.unlink()
        code, payload = repair.run(self.options())
        self.assertEqual(code, 2)
        finding = next(f for f in payload["findings"] if f["id"] == "fitness-change-requires-approval")
        self.assertEqual(finding["severity"], "manual")
        self.assertEqual([entry for entry in payload["repairs"] if entry["target"].startswith("docs/fitness/")], [])
        code, payload = repair.run(self.options(apply=True))
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "needs-attention")
        self.assertFalse(fitness_rule.exists())

    def test_downgrade_blocks_repair(self) -> None:
        install(self.root)
        (self.root / "docs/methodology/VERSION").write_text("99.0.0\n", encoding="utf-8")
        code, payload = repair.run(self.options())
        self.assertEqual(code, 2)
        self.assertIn("version-downgrade", finding_ids(payload))
        self.assertEqual(payload["repairs"], [])
        code, payload = repair.run(self.options(apply=True))
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "needs-attention")
        self.assertFalse((self.root / "docs/methodology/repair.json").exists())

    # -- scope and environment --------------------------------------------

    def test_explicit_agent_scopes_the_skill_repair(self) -> None:
        install(self.root, agent="codex")
        code, payload = repair.run(self.options(agent="claude"))
        self.assertIn("skill-missing", finding_ids(payload))
        targets = [(entry["kind"], entry["target"]) for entry in payload["repairs"]]
        self.assertIn(("sync-tree", ".claude/skills/engineering"), targets)
        self.assertNotIn(("sync-tree", ".agents/skills/engineering"), targets)
        actions = [repair.deserialize(entry) for entry in payload["repairs"] if entry["kind"] == "sync-tree"]
        repair.apply_repairs(self.root, REPO, actions)
        self.assertTrue((self.root / ".claude/skills/engineering/SKILL.md").is_file())

    def test_unknown_agent_scope_is_reported_not_guessed(self) -> None:
        install(self.root)
        receipt = json.loads((self.root / "docs/methodology/onboarding.json").read_text(encoding="utf-8"))
        receipt["agent"] = "all"
        (self.root / "docs/methodology/onboarding.json").write_text(json.dumps(receipt), encoding="utf-8")
        shutil.rmtree(self.root / ".agents/skills/engineering")
        code, payload = repair.run(self.options())
        self.assertIn("skill-scope-unknown", finding_ids(payload))
        self.assertEqual([entry for entry in payload["repairs"] if entry["kind"] == "sync-tree"], [])

    def test_missing_openspec_cli_is_reported_with_a_remedy(self) -> None:
        install(self.root)
        (self.root / ".agents/skills/openspec-explore/SKILL.md").unlink()
        with patch.object(repair, "probe_openspec", return_value={"command": None, "version": None, "ok": False}):
            code, payload = repair.run(self.options())
        self.assertEqual(code, 2)
        openspec = next(f for f in payload["findings"] if f["id"] == "openspec-skills-missing")
        self.assertEqual(openspec["severity"], "manual")
        self.assertIn("openspec", openspec["remedy"])
        self.assertEqual([entry for entry in payload["repairs"] if entry["kind"] == "openspec-init"], [])

    def test_stale_user_level_skill_is_reported_informationally(self) -> None:
        install(self.root)
        user_root = Path(self.temporary.name) / "user-skills"
        (user_root / "engineering").mkdir(parents=True)
        (user_root / "engineering" / "SKILL.md").write_text("stale shadow\n", encoding="utf-8")
        with patch.dict(repair.USER_SKILL_ROOTS, {"codex": user_root}):
            code, payload = repair.run(self.options())
        self.assertEqual(code, 0, payload)
        finding = next(f for f in payload["findings"] if f["id"] == "skill-user-root-stale")
        self.assertEqual(finding["severity"], "informational")
        self.assertIn("project-locally", finding["remedy"])
        self.assertEqual(payload["repairs"], [])

    def test_source_root_defaults_to_the_onboarding_receipt(self) -> None:
        install(self.root)
        code, payload = repair.run(self.options(source_root=None))
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["source_root"], str(REPO))

    def test_missing_source_is_reported(self) -> None:
        install(self.root)
        code, payload = repair.run(self.options(source_root=Path("/nonexistent-kit")))
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "error")
        self.assertIn("Not a Harness kit checkout", payload["errors"][0])


if __name__ == "__main__":
    unittest.main()
