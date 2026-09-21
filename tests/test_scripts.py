"""Regression tests for the strict-review fixes in the control scripts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))

from check_agent_policy import validate as validate_agent_policy  # noqa: E402
from check_context_docs import validate_context_impact  # noqa: E402
from check_phase import check, is_exit_code, validate_context_updates  # noqa: E402
from check_production_readiness import rollout_cycles, validate as validate_production  # noqa: E402
from fixtures.workspace import write_context_skeleton  # noqa: E402
from lessons_common import load_lessons, validate_lesson  # noqa: E402
from methodology_common import meaningful, write_json  # noqa: E402
from check_change_workspace import check_workspace  # noqa: E402
from layout import policy_rel, relative as layout_relative  # noqa: E402
from openspec_common import orchestration_contract  # noqa: E402


# Layout-derived paths; the concrete values are pinned in test_layout.py.
LESSONS = layout_relative("lessons")
PRODUCTION_CHANGES = layout_relative("production_changes")
PRODUCTION_AUDIT = layout_relative("production_audit")
POLICY_REL = policy_rel()
CONTEXT_INDEX = layout_relative("context_index")
CONTEXT_DETAIL = layout_relative("context_doc", module_path=".")


def impact_decision(required: bool, paths: list[str]) -> dict[str, object]:
    return {"required": required, "paths": paths, "reason": "Declared during design confirmation"}


def run_script(name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / name), *arguments],
        capture_output=True,
        text=True,
    )


def base_lesson(**overrides: object) -> dict[str, object]:
    lesson = {
        "schema_version": 1, "lesson_id": "sample-lesson", "title": "t", "pattern": "p",
        "root_cause": "rc", "prevention": "pv", "verification": "v", "scope": "project",
        "status": "active", "keywords": ["k"], "paths": [], "rules": [],
        "source_changes": [], "source_events": [],
    }
    lesson.update(overrides)
    return lesson


def base_production_record(**overrides: object) -> dict[str, object]:
    record = {
        "schema_version": 1, "change_id": "demo-1", "title": "t", "environment": "production",
        "profile": "standard", "risk": "medium", "owner": "o", "service": "svc", "state": "INTAKE",
        "technical_done": False, "operational_done": False,
        "evidence": {"spec": "s", "tests": ["t"], "gates": ["g"], "review": "r"},
        "observability": {"dashboard": "d", "alerts": ["a"], "baseline": "b", "correlation": "c"},
        "rollout": {"strategy": "canary", "stages": ["1%", "25%", "100%"], "stop_conditions": ["sc"], "operator": "op"},
        "rollback": {"strategy": "st", "runbook": "rb", "owner": "o", "tested_at": "2026-01-01", "data_plan": "dp"},
        "approvals": {"reviewer": "rev", "approved_at": "2026-01-01"},
        "audit_log": f"{PRODUCTION_AUDIT}/demo-1.jsonl",
    }
    record.update(overrides)
    return record


class LessonMemoryTests(unittest.TestCase):
    def test_retired_lessons_are_skipped_not_errors(self) -> None:
        """S1: retiring a lesson must not brick retrieval or the Explore gate."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lessons = root / LESSONS
            lessons.mkdir(parents=True)
            write_json(lessons / "active-one.json", base_lesson(lesson_id="active-one"))
            write_json(lessons / "retired-one.json", base_lesson(lesson_id="retired-one", status="retired"))
            loaded, errors = load_lessons(root, active_only=True)
            self.assertEqual(errors, [])
            self.assertEqual([lesson["lesson_id"] for lesson in loaded], ["active-one"])

    def test_invalid_lesson_status_is_still_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lessons = root / LESSONS
            lessons.mkdir(parents=True)
            write_json(lessons / "weird.json", base_lesson(lesson_id="weird", status="frozen"))
            _, errors = load_lessons(root, active_only=True)
            self.assertTrue(any("status" in error for error in errors))

    def test_malformed_lesson_fields_are_blocked(self) -> None:
        """M7/L10: type checks keep broken lessons out of the active set."""
        for field, value in (("source_events", None), ("rules", "phase-review"), ("paths", "src/x"), ("keywords", [])):
            with self.subTest(field=field):
                errors = validate_lesson(base_lesson(**{field: value}))
                self.assertTrue(errors, f"{field}={value!r} must not validate")

    def test_event_id_uses_a_single_normalized_timestamp(self) -> None:
        """L9: the failure id ends in Z and matches the recorded `at`."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            (change_dir / "evidence").mkdir(parents=True)
            write_json(change_dir / "governance.json", {
                "schema_version": 1, "change_id": "demo-1", "title": "t", "profile": "standard",
                "risk": "medium", "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "delivery_scope": "technical", "project_root": str(Path(directory)), "state": "INTAKE",
                "owner": "o", "orchestration": orchestration_contract("demo-1"), "events": [],
            })
            completed = run_script(
                "record_failure.py", str(change_dir), "--source", "fitness", "--category", "fitness",
                "--rule", "demo-rule", "--message", "m", "--actor", "tester",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            event = json.loads((change_dir / "evidence/failure-events.jsonl").read_text().splitlines()[0])
            self.assertNotIn("+0000", event["event_id"])
            self.assertIn("Z-", event["event_id"], "the normalized timestamp must carry a Z suffix inside the id")
            stamp = event["event_id"].removeprefix("failure-").removesuffix("-demo-rule")
            self.assertTrue(event["at"].replace("+00:00", "Z").replace(":", "").startswith(stamp))


class ProductionRecordTests(unittest.TestCase):
    def test_malformed_records_fail_closed(self) -> None:
        """M9: previously passing gaps now block the readiness gate."""
        cases = {
            "audit_log none": base_production_record(audit_log=None),
            "audit_log empty": base_production_record(audit_log=""),
            "audit_log absolute": base_production_record(audit_log="/var/log/audit.jsonl"),
            "stages as string": base_production_record(rollout={"strategy": "canary", "stages": "1% 25% 100%", "stop_conditions": ["sc"], "operator": "op"}),
            "stages empty": base_production_record(rollout={"strategy": "canary", "stages": [], "stop_conditions": ["sc"], "operator": "op"}),
            "stages duplicated": base_production_record(rollout={"strategy": "canary", "stages": ["1%", "1%"], "stop_conditions": ["sc"], "operator": "op"}),
            "wrong schema": base_production_record(schema_version=99),
            "unknown state": base_production_record(state="WHATEVER"),
            "done as string": base_production_record(technical_done="false", operational_done="false"),
            "placeholder window": base_production_record(
                state="DEPLOYED", technical_done=True, operational_done=True,
                observability={"dashboard": "d", "alerts": ["a"], "baseline": "b", "correlation": "c", "observation_window_minutes": "{{WINDOW}}"},
            ),
        }
        for name, record in cases.items():
            with self.subTest(case=name):
                self.assertTrue(validate_production(record), f"{name} must not pass")

    def test_valid_record_passes(self) -> None:
        self.assertEqual(validate_production(base_production_record()), [])

    def test_rollout_cycles_reset_on_rollback(self) -> None:
        """M10: a rollback restarts the rollout sequence from the first stage."""
        events = [
            {"to": "DEPLOYED", "rollout_stage": "1%"},
            {"to": "ROLLED_BACK", "evidence": ["rollback-done"]},
            {"to": "REMEDIATING"},
        ]
        self.assertEqual(rollout_cycles(events)[-1], [])
        events.extend([
            {"to": "DEPLOYED", "rollout_stage": "1%"},
            {"to": "DEPLOYED", "rollout_stage": "25%"},
            {"to": "DEPLOYED", "rollout_stage": "100%"},
        ])
        self.assertEqual(rollout_cycles(events)[-1], ["1%", "25%", "100%"])
        self.assertEqual(len(rollout_cycles(events)), 2)

    def test_non_dict_record_is_rejected_cleanly(self) -> None:
        """M13: a JSON array record exits 2 with a message, not a traceback."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changes = root / PRODUCTION_CHANGES
            changes.mkdir(parents=True)
            record_path = changes / "demo-1.json"
            record_path.write_text("[1, 2, 3]\n", encoding="utf-8")
            completed = run_script("change_state.py", str(record_path), "CLASSIFIED", "--actor", "t")
            self.assertEqual(completed.returncode, 2)
            self.assertIn("JSON object", completed.stdout + completed.stderr)
            self.assertNotIn("Traceback", completed.stdout + completed.stderr)

    def test_record_outside_canonical_location_is_blocked(self) -> None:
        """L15: location checking matches the canonical directory layout."""
        with tempfile.TemporaryDirectory() as directory:
            record_path = Path(directory) / "somewhere/production/changes/demo-1.json"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(json.dumps(base_production_record()), encoding="utf-8")
            completed = run_script("change_state.py", str(record_path), "CLASSIFIED", "--actor", "t")
            self.assertEqual(completed.returncode, 2)
            self.assertIn(PRODUCTION_CHANGES, completed.stdout + completed.stderr)


class GateAndLifecycleTests(unittest.TestCase):
    def test_change_id_must_match_directory_name(self) -> None:
        """L17: a hand-edited governance.json cannot carry a foreign change_id."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            change_dir.mkdir(parents=True)
            write_json(change_dir / "governance.json", {
                "schema_version": 1, "change_id": "other-id", "title": "t", "profile": "standard",
                "risk": "medium", "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "delivery_scope": "technical", "project_root": "/nonexistent", "state": "INTAKE",
                "owner": "o", "orchestration": orchestration_contract("other-id"), "events": [],
            })
            errors = check(change_dir, "EXPLORE")
            self.assertTrue(any("must match the change directory name" in error for error in errors))

    def test_review_exit_code_must_be_an_integer(self) -> None:
        """L18: JSON false is not a zero exit code."""
        self.assertTrue(is_exit_code(0))
        self.assertFalse(is_exit_code(False))
        self.assertFalse(is_exit_code("0"))
        self.assertFalse(is_exit_code(None))

    def test_binary_artifact_is_not_meaningful(self) -> None:
        """M12: non-UTF-8 artifacts fail the gate instead of crashing it."""
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "spec.md"
            binary.write_bytes(b"# spec\n\n\xff\xfe binary")
            self.assertFalse(meaningful(binary))

    def test_policy_location_is_enforced(self) -> None:
        """M4: a policy outside the canonical location fails with a clear error."""
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "agent-policy.yaml"
            policy.write_text("version: 1\n", encoding="utf-8")
            errors = validate_agent_policy(policy)
            self.assertTrue(any(POLICY_REL in error for error in errors))

    def test_approve_design_refuses_to_rebind(self) -> None:
        """M11: an existing approval blocks silent digest rebinding."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            change_dir.mkdir(parents=True)
            write_json(change_dir / "governance.json", {
                "schema_version": 1, "change_id": "demo-1", "title": "t", "profile": "standard",
                "risk": "medium", "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "delivery_scope": "technical", "project_root": "/nonexistent", "state": "DESIGN_READY",
                "owner": "o", "orchestration": orchestration_contract("demo-1"), "events": [],
            })
            write_json(change_dir / "approval.json", {"schema_version": 1, "status": "approved"})
            completed = run_script(
                "approve_design.py", str(change_dir), "--actor", "reviewer",
                "--source", "test", "--approval-id", "AP-2",
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("already exists", completed.stdout + completed.stderr)

    def test_preflight_requires_project_root(self) -> None:
        """L14: a change record without project_root fails loudly, not via CWD."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            change_dir.mkdir(parents=True)
            write_json(change_dir / "governance.json", {"schema_version": 1, "change_id": "demo-1", "state": "INTAKE", "orchestration": orchestration_contract("demo-1")})
            completed = run_script("preflight_lessons.py", str(change_dir), "--actor", "tester")
            self.assertEqual(completed.returncode, 2)
            self.assertIn("project_root", completed.stdout + completed.stderr)

    def test_approve_lesson_validates_before_writing(self) -> None:
        """L13: a change workspace outside project_root is blocked before any write."""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            elsewhere = Path(directory) / "elsewhere/changes/demo-1"
            (project / LESSONS).mkdir(parents=True)
            (elsewhere / "evidence").mkdir(parents=True)
            write_json(elsewhere / "governance.json", {
                "schema_version": 1, "change_id": "demo-1", "state": "VERIFYING",
                "orchestration": orchestration_contract("demo-1"),
                "project_root": str(project), "events": [],
            })
            write_json(elsewhere / "lesson-candidate.json", base_lesson(lesson_id="demo-lesson", status="candidate"))
            (elsewhere / "evidence/failure-events.jsonl").write_text("", encoding="utf-8")
            completed = run_script(
                "approve_lesson.py", str(elsewhere / "lesson-candidate.json"),
                "--actor", "reviewer", "--source", "test", "--approval-id", "AP-1",
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("does not contain", completed.stdout + completed.stderr)
            self.assertFalse((project / f"{LESSONS}/demo-lesson.json").exists())


class ContextImpactGateTests(unittest.TestCase):
    """Review must reject a context file that changed without a declared decision.

    ``validate_context_updates`` is the function ``check_phase.check`` calls for
    REVIEW, so these cases pin the exact gate rather than a copy of its logic.
    """

    def project(self, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        write_context_skeleton(root, unit_id="demo")
        return root

    def change(self, root: Path) -> Path:
        change_dir = root / "openspec/changes/demo-1"
        change_dir.mkdir(parents=True, exist_ok=True)
        return change_dir

    def run_gate(self, change_dir: Path, root: Path, impact: dict[str, object], reviewed: list[str]) -> list[str]:
        write_json(change_dir / "context-impact.json", impact)
        errors: list[str] = []
        _, impact_errors = validate_context_impact(change_dir / "context-impact.json", root)
        errors.extend(impact_errors)
        if impact_errors:
            return errors
        review = {"files": {path: "0" * 64 for path in reviewed}}
        validate_context_updates(change_dir, {"project_root": str(root)}, review, errors)
        return errors

    def test_edited_index_needs_a_declared_decision(self) -> None:
        """Regression: the guard compared a bare ``ai.json`` and never fired."""
        with tempfile.TemporaryDirectory() as directory:
            root = self.project(Path(directory) / "project")
            change_dir = self.change(root)
            impact = {
                "schema_version": 1,
                "analyzed_paths": ["src/app.py", CONTEXT_INDEX],
                "signals": ["none"],
                "ai_json": impact_decision(False, []),
                "ai_md": impact_decision(False, []),
            }
            errors = self.run_gate(change_dir, root, impact, ["src/app.py", CONTEXT_INDEX])
            self.assertIn("ai.json changed without an approved context impact decision", errors)

    def test_edited_detail_needs_a_declared_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.project(Path(directory) / "project")
            change_dir = self.change(root)
            impact = {
                "schema_version": 1,
                "analyzed_paths": ["src/app.py", CONTEXT_DETAIL],
                "signals": ["none"],
                "ai_json": impact_decision(False, []),
                "ai_md": impact_decision(False, []),
            }
            errors = self.run_gate(change_dir, root, impact, ["src/app.py", CONTEXT_DETAIL])
            self.assertIn("AI.md changed without an approved context impact decision", errors)

    def test_declared_index_update_must_be_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.project(Path(directory) / "project")
            change_dir = self.change(root)
            impact = {
                "schema_version": 1,
                "analyzed_paths": ["src/app.py", CONTEXT_INDEX],
                "signals": ["module-topology"],
                "ai_json": impact_decision(True, [CONTEXT_INDEX]),
                "ai_md": impact_decision(False, []),
            }
            errors = self.run_gate(change_dir, root, impact, ["src/app.py"])
            self.assertIn("required ai_json updates are missing from review file digests", errors)
            self.assertEqual(self.run_gate(change_dir, root, impact, ["src/app.py", CONTEXT_INDEX]), [])

    def test_signal_without_its_document_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.project(Path(directory) / "project")
            change_dir = self.change(root)
            impact = {
                "schema_version": 1,
                "analyzed_paths": ["src/app.py"],
                "signals": ["responsibility"],
                "ai_json": impact_decision(False, []),
                "ai_md": impact_decision(False, []),
            }
            errors = self.run_gate(change_dir, root, impact, ["src/app.py"])
            self.assertIn("context-impact.json signals require ai_md update", errors)

    def test_code_only_change_declared_none_passes(self) -> None:
        """The gate audits the declaration, it never infers context impact."""
        with tempfile.TemporaryDirectory() as directory:
            root = self.project(Path(directory) / "project")
            change_dir = self.change(root)
            impact = {
                "schema_version": 1,
                "analyzed_paths": ["src/app.py"],
                "signals": ["none"],
                "ai_json": impact_decision(False, []),
                "ai_md": impact_decision(False, []),
            }
            self.assertEqual(self.run_gate(change_dir, root, impact, ["src/app.py"]), [])


class MetricsTests(unittest.TestCase):
    def test_archived_changes_still_count(self) -> None:
        """M5: metrics must include the documented archive destination."""
        with tempfile.TemporaryDirectory() as directory:
            changes = Path(directory)
            # Documented layout: openspec/changes/archive/<date>-<change-id>/.
            archived = changes / "archive/2026-09-05-demo-1/evidence"
            archived.mkdir(parents=True)
            (archived / "events.jsonl").write_text(
                '{"event": "skill.triggered", "change_id": "demo-1", "at": "2026-01-01T00:00:00Z", "mode": "backend"}\n'
                '{"event": "methodology.transition", "change_id": "demo-1", "at": "2026-01-01T00:00:01Z", "to": "ARCHIVED"}\n',
                encoding="utf-8",
            )
            (changes / "archive/2026-09-05-demo-1/lesson-candidate.json").write_text("{}", encoding="utf-8")
            write_json(changes / "archive/2026-09-05-demo-1/execution-evidence.json", {
                "schema_version": 1,
                "strategy": "parallel",
                "capability": {"agent_parallelism": True, "isolation": "worktree", "max_concurrency": 2},
                "task_runs": [
                    {"task_id": "T1", "actor": "worker-1", "status": "completed"},
                    {"task_id": "T2", "actor": "worker-2", "status": "completed"},
                ],
            })
            completed = run_script("skill_metrics.py", str(changes))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            metrics = json.loads(completed.stdout)
            self.assertEqual(metrics["triggered"], 1)
            self.assertEqual(metrics["archived"], 1)
            self.assertEqual(metrics["completion_rate"], 1.0)
            self.assertEqual(metrics["lesson_candidates"], 1)
            self.assertEqual(metrics["execution_by_strategy"], {"parallel": 1})
            self.assertEqual(metrics["parallel_adoption_rate"], 1.0)
            self.assertEqual(metrics["task_runs"], 2)
            self.assertEqual(metrics["max_declared_concurrency"], 2)

    def test_missing_changes_root_fails_closed(self) -> None:
        """L12: a nonexistent root reports an error instead of silent zeros."""
        completed = run_script("skill_metrics.py", "/nonexistent/changes-root")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("CHANGES ROOT MISSING", completed.stdout + completed.stderr)


class AtomicityTests(unittest.TestCase):
    def test_write_json_replaces_atomically_and_cleans_up(self) -> None:
        """M8: no .tmp remnants and the payload round-trips."""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested/record.json"
            payload = {"schema_version": 1, "items": ["a"]}
            write_json(target, payload)
            write_json(target, {**payload, "items": ["a", "b"]})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["items"], ["a", "b"])
            self.assertEqual(list(Path(directory, "nested").glob("*.tmp")), [])


class ChangeWorkspaceGuardTests(unittest.TestCase):
    """Workspace-ownership guard (check_change_workspace.py)."""

    def _registered(self, change_dir: Path, project_root: Path, change_id: str | None = None) -> None:
        name = change_id or change_dir.name
        (change_dir / ".openspec.yaml").write_text("schema: harness-engineering\n", encoding="utf-8")
        write_json(change_dir / "governance.json", {
            "schema_version": 1, "change_id": name, "title": "t",
            "profile": "standard", "risk": "medium", "skill": "engineering", "mode": "backend",
            "delivery_scope": "technical", "project_root": str(project_root), "owner": "o",
            "orchestration": orchestration_contract(name), "events": [],
        })

    def test_missing_or_empty_changes_root_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(check_workspace(root), [])
            (root / "openspec/changes").mkdir(parents=True)
            self.assertEqual(check_workspace(root), [])

    def test_all_registered_changes_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change_dir = root / "openspec/changes/demo-1"
            change_dir.mkdir(parents=True)
            self._registered(change_dir, root)
            self.assertEqual(check_workspace(root), [])

    def test_unmanaged_directory_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            orphan = root / "openspec/changes/realtime-3d-explosion"
            orphan.mkdir(parents=True)
            (orphan / "proposal.md").write_text("# proposal\n", encoding="utf-8")
            errors = check_workspace(root)
            self.assertTrue(errors)
            self.assertTrue(all("openspec/changes/realtime-3d-explosion" in error for error in errors))
            self.assertTrue(any("missing OpenSpec change marker .openspec.yaml" in error for error in errors))

    def test_unmanaged_directories_are_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changes = root / "openspec/changes"
            for name in ("zz-orphan", "aa-orphan"):
                (changes / name).mkdir(parents=True)
            errors = check_workspace(root)
            # An unmanaged directory reports both missing markers, so collapse to the
            # reported directories before asserting the ordering this test is about.
            reported = list(dict.fromkeys(error.split(":")[0] for error in errors))
            self.assertEqual(reported, [
                "openspec/changes/aa-orphan",
                "openspec/changes/zz-orphan",
            ])

    def test_archive_dot_entries_and_files_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changes = root / "openspec/changes"
            (changes / "archive/2026-09-05-open-a").mkdir(parents=True)
            (changes / ".hidden-draft").mkdir(parents=True)
            (changes / "notes.md").write_text("x", encoding="utf-8")
            (changes / "orphan").mkdir(parents=True)
            errors = check_workspace(root)
            self.assertEqual({error.split(":")[0] for error in errors}, {"openspec/changes/orphan"})

    def test_bad_schema_and_foreign_change_id_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad_schema = root / "openspec/changes/bad-schema"
            bad_schema.mkdir(parents=True)
            self._registered(bad_schema, root)
            (bad_schema / ".openspec.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
            wrong_id = root / "openspec/changes/wrong-id"
            wrong_id.mkdir(parents=True)
            self._registered(wrong_id, root, change_id="other-id")
            errors = check_workspace(root)
            self.assertTrue(any("bad-schema" in error and "schema must be" in error for error in errors))
            self.assertTrue(any("wrong-id" in error and "must match" in error for error in errors))

    def test_phase_gate_fails_closed_on_unmanaged_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registered = root / "openspec/changes/registered"
            orphan = root / "openspec/changes/orphan"
            registered.mkdir(parents=True)
            orphan.mkdir(parents=True)
            (orphan / "proposal.md").write_text("# x\n", encoding="utf-8")
            self._registered(registered, root)
            errors = check(registered, "EXPLORE")
            self.assertTrue(any(error.startswith("workspace:") and "orphan" in error for error in errors))
            self._registered(orphan, root)
            errors = check(registered, "EXPLORE")
            self.assertFalse(any(error.startswith("workspace:") for error in errors))

    def test_orchestration_contract_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            change_dir = root / "openspec/changes/demo-1"
            change_dir.mkdir(parents=True)
            self._registered(change_dir, root)
            record = json.loads((change_dir / "governance.json").read_text(encoding="utf-8"))
            record.pop("orchestration")
            write_json(change_dir / "governance.json", record)
            self.assertTrue(any("orchestration" in error for error in check_workspace(root)))

    def test_cli_scan_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "openspec/changes/orphan").mkdir(parents=True)
            completed = run_script("check_change_workspace.py", "--root", str(root))
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertIn("BLOCKED", completed.stdout + completed.stderr)
            self.assertIn("orphan", completed.stdout + completed.stderr)
            (root / "openspec/changes").joinpath("orphan").rmdir()
            completed = run_script("check_change_workspace.py", "--root", str(root))
            self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
