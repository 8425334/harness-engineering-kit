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

from check_agent_policy import validate as validate_agent_policy  # noqa: E402
from check_phase import check, is_exit_code  # noqa: E402
from check_production_readiness import rollout_cycles, validate as validate_production  # noqa: E402
from lessons_common import load_lessons, validate_lesson  # noqa: E402
from methodology_common import meaningful, write_json  # noqa: E402


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
        "audit_log": "docs/methodology/production/audit/demo-1.jsonl",
    }
    record.update(overrides)
    return record


class LessonMemoryTests(unittest.TestCase):
    def test_retired_lessons_are_skipped_not_errors(self) -> None:
        """S1: retiring a lesson must not brick retrieval or the Explore gate."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lessons = root / "docs/methodology/lessons"
            lessons.mkdir(parents=True)
            write_json(lessons / "active-one.json", base_lesson(lesson_id="active-one"))
            write_json(lessons / "retired-one.json", base_lesson(lesson_id="retired-one", status="retired"))
            loaded, errors = load_lessons(root, active_only=True)
            self.assertEqual(errors, [])
            self.assertEqual([lesson["lesson_id"] for lesson in loaded], ["active-one"])

    def test_invalid_lesson_status_is_still_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lessons = root / "docs/methodology/lessons"
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
            write_json(change_dir / "change.json", {
                "schema_version": 2, "change_id": "demo-1", "title": "t", "profile": "standard",
                "risk": "medium", "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "delivery_scope": "technical", "project_root": str(Path(directory)), "state": "INTAKE",
                "owner": "o", "events": [],
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
            changes = root / "docs/methodology/production/changes"
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
            self.assertIn("docs/methodology/production/changes", completed.stdout + completed.stderr)


class GateAndLifecycleTests(unittest.TestCase):
    def test_change_id_must_match_directory_name(self) -> None:
        """L17: a hand-edited change.json cannot carry a foreign change_id."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            change_dir.mkdir(parents=True)
            write_json(change_dir / "change.json", {
                "schema_version": 2, "change_id": "other-id", "title": "t", "profile": "standard",
                "risk": "medium", "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "delivery_scope": "technical", "project_root": "/nonexistent", "state": "INTAKE",
                "owner": "o", "events": [],
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
        """M4: a policy outside docs/methodology fails with a clear error."""
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "agent-policy.yaml"
            policy.write_text("version: 1\n", encoding="utf-8")
            errors = validate_agent_policy(policy)
            self.assertTrue(any("docs/methodology/agent-policy.yaml" in error for error in errors))

    def test_init_change_rejects_non_canonical_policy_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "profile.yaml").write_text("version: 2\n", encoding="utf-8")
            (root / "agent-policy.yaml").write_text("version: 1\n", encoding="utf-8")
            completed = run_script(
                "init_change.py", "demo-1", "--title", "T", "--mode", "backend", "--owner", "o",
                "--trigger", "native-selection",
                "--profile-path", str(root / "profile.yaml"),
                "--policy-path", str(root / "agent-policy.yaml"),
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("docs/methodology/agent-policy.yaml", completed.stdout + completed.stderr)
            self.assertNotIn("Traceback", completed.stdout + completed.stderr)

    def test_approve_design_refuses_to_rebind(self) -> None:
        """M11: an existing approval blocks silent digest rebinding."""
        with tempfile.TemporaryDirectory() as directory:
            change_dir = Path(directory) / "changes/demo-1"
            change_dir.mkdir(parents=True)
            write_json(change_dir / "change.json", {
                "schema_version": 2, "change_id": "demo-1", "title": "t", "profile": "standard",
                "risk": "medium", "skill": "engineering", "mode": "backend", "trigger": "native-selection",
                "delivery_scope": "technical", "project_root": "/nonexistent", "state": "DESIGN_READY",
                "owner": "o", "events": [],
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
            write_json(change_dir / "change.json", {"schema_version": 2, "change_id": "demo-1", "state": "INTAKE"})
            completed = run_script("preflight_lessons.py", str(change_dir), "--actor", "tester")
            self.assertEqual(completed.returncode, 2)
            self.assertIn("project_root", completed.stdout + completed.stderr)

    def test_approve_lesson_validates_before_writing(self) -> None:
        """L13: a change workspace outside project_root is blocked before any write."""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            elsewhere = Path(directory) / "elsewhere/changes/demo-1"
            (project / "docs/methodology/lessons").mkdir(parents=True)
            (elsewhere / "evidence").mkdir(parents=True)
            write_json(elsewhere / "change.json", {
                "schema_version": 2, "change_id": "demo-1", "state": "VERIFYING",
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
            self.assertFalse((project / "docs/methodology/lessons/demo-lesson.json").exists())


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
            completed = run_script("skill_metrics.py", str(changes))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            metrics = json.loads(completed.stdout)
            self.assertEqual(metrics["triggered"], 1)
            self.assertEqual(metrics["archived"], 1)
            self.assertEqual(metrics["completion_rate"], 1.0)
            self.assertEqual(metrics["lesson_candidates"], 1)

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


if __name__ == "__main__":
    unittest.main()
