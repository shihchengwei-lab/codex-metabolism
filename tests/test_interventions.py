from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from codex_metabolism.decide import decide
from codex_metabolism.interventions import load_interventions
from codex_metabolism.lifecycle import (
    LifecycleError,
    activate_harness,
    activate_tool,
    apply_decision,
    retire_tool,
    rollback_intervention,
)
from codex_metabolism.observe import observe
from codex_metabolism.stage import stage_review

from tests.helpers import NOW, make_deploy_home, session_records, write_jsonl, write_skill


def success_only_records(session_id: str, timestamp: str) -> list[dict]:
    return [
        {
            "type": "session_meta",
            "payload": {
                "session_id": session_id,
                "timestamp": timestamp,
                "cwd": "C:/demo/repo",
                "cli_version": "0.144.5",
            },
        },
        {"type": "turn_context", "payload": {"model": "gpt-5.6", "cwd": "C:/demo/repo"}},
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "call_id": f"{session_id}-success",
                "name": "functions.exec",
                "input": json.dumps({"command": "preflight && deploy production"}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": f"{session_id}-success",
                "output": "Script completed\nExit code: 0\nOutput:\ndeployed",
            },
        },
    ]


def unrelated_records(session_id: str, timestamp: str) -> list[dict]:
    return [
        {
            "type": "session_meta",
            "payload": {
                "session_id": session_id,
                "timestamp": timestamp,
                "cwd": "C:/demo/repo",
                "cli_version": "0.144.5",
            },
        },
        {"type": "turn_context", "payload": {"model": "gpt-5.6", "cwd": "C:/demo/repo"}},
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "call_id": f"{session_id}-status",
                "name": "functions.exec",
                "input": json.dumps({"command": "git status --short"}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": f"{session_id}-status",
                "output": "Script completed\nExit code: 0\nOutput:\n",
            },
        },
    ]


class InterventionLifecycleTests(unittest.TestCase):
    def _apply_demo_harness(
        self,
        root: Path,
        *,
        confirm_trust: bool = True,
    ) -> tuple[Path, Path, Path, object]:
        codex_home, skills_root = make_deploy_home(root)
        snapshot = observe(
            codex_home,
            [skills_root],
            days=7,
            now=NOW,
            project_root=root,
            catalog_entries=[],
            catalog_checked=True,
        )
        decisions = decide(snapshot, now=NOW)
        harness = next(item for item in decisions if item.target_kind == "HARNESS")
        staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)
        apply_decision(
            staging,
            harness.id,
            project_root=root,
            skill_root=skills_root,
            changed_at=NOW,
        )
        if confirm_trust:
            activate_harness(
                staging,
                harness.id,
                confirmed_trusted=True,
                activated_at=NOW,
            )
        return codex_home, skills_root, staging, harness

    def test_harness_apply_waits_for_explicit_codex_hook_trust_before_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, _, staging, harness = self._apply_demo_harness(root, confirm_trust=False)

            records = load_interventions(staging / "interventions.jsonl")

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].decision_id, harness.id)
            self.assertEqual(records[0].status, "PENDING_TRUST")
            self.assertEqual(records[0].target_kind, "HARNESS")
            self.assertEqual(records[0].signature, "deploy production")
            self.assertTrue(Path(records[0].artifact_path).is_dir())

            with self.assertRaises(LifecycleError):
                activate_harness(
                    staging,
                    harness.id,
                    confirmed_trusted=False,
                )
            active = activate_harness(
                staging,
                harness.id,
                confirmed_trusted=True,
                activated_at=NOW,
            )
            self.assertEqual(active.status, "ACTIVE")
            self.assertTrue(active.metadata["user_confirmed_codex_hook_trust"])

    def test_active_intervention_suppresses_duplicate_creation_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root, staging, harness = self._apply_demo_harness(root)
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW + timedelta(hours=1),
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
                intervention_records=load_interventions(staging / "interventions.jsonl"),
            )

            decisions = decide(snapshot, now=NOW + timedelta(hours=1))

            self.assertFalse(
                any(
                    item.metadata.get("signature") == harness.metadata.get("signature")
                    and item.mechanism != "intervention_reevaluation"
                    for item in decisions
                )
            )

    def test_pending_trust_harness_is_reported_without_duplicate_or_outcome_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root, staging, harness = self._apply_demo_harness(
                root,
                confirm_trust=False,
            )
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW + timedelta(hours=1),
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
                intervention_records=load_interventions(staging / "interventions.jsonl"),
            )

            decisions = decide(snapshot, now=NOW + timedelta(hours=1))

            self.assertFalse(
                any(
                    item.metadata.get("signature") == harness.metadata.get("signature")
                    and item.mechanism not in {
                        "intervention_reevaluation",
                        "intervention_pending_trust",
                    }
                    for item in decisions
                )
            )
            pending = next(
                item
                for item in decisions
                if item.metadata.get("intervention_id") == harness.id
            )
            self.assertEqual(pending.decision, "KEEP")
            self.assertEqual(pending.metadata["lifecycle_verdict"], "PENDING_TRUST")
            self.assertEqual(pending.metadata["post_session_count"], 0)

    def test_future_failures_mark_an_active_intervention_ineffective(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root, staging, harness = self._apply_demo_harness(root)
            for index in (1, 2):
                records = session_records(f"future-failure-{index}")
                records[0]["payload"]["timestamp"] = (NOW + timedelta(hours=index)).isoformat()
                write_jsonl(
                    codex_home / "sessions" / "2026" / "07" / "20" / f"rollout-future-failure-{index}.jsonl",
                    records,
                )
            receipts = load_interventions(staging / "interventions.jsonl")
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW + timedelta(days=1),
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
                intervention_records=receipts,
            )

            decisions = decide(snapshot, now=NOW + timedelta(days=1))
            evaluation = next(
                item
                for item in decisions
                if item.metadata.get("intervention_id") == harness.id
                and item.metadata.get("lifecycle_verdict") == "INEFFECTIVE"
            )

            self.assertEqual(evaluation.decision, "PATCH")
            self.assertEqual(evaluation.target_kind, "HARNESS")

    def test_future_successes_validate_an_active_intervention(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root, staging, harness = self._apply_demo_harness(root)
            for index in (1, 2):
                write_jsonl(
                    codex_home / "sessions" / "2026" / "07" / "20" / f"rollout-future-success-{index}.jsonl",
                    success_only_records(
                        f"future-success-{index}",
                        (NOW + timedelta(hours=index)).isoformat(),
                    ),
                )
            receipts = load_interventions(staging / "interventions.jsonl")
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW + timedelta(days=1),
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
                intervention_records=receipts,
            )

            decisions = decide(snapshot, now=NOW + timedelta(days=1))
            evaluation = next(
                item
                for item in decisions
                if item.metadata.get("intervention_id") == harness.id
                and item.metadata.get("lifecycle_verdict") == "VALIDATED"
            )

            self.assertEqual(evaluation.decision, "KEEP")

    def test_long_idle_period_only_nominates_active_intervention_for_retirement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root, staging, harness = self._apply_demo_harness(root)
            for index in range(10):
                write_jsonl(
                    codex_home / "sessions" / "2026" / "08" / "19" / f"rollout-idle-{index}.jsonl",
                    unrelated_records(
                        f"idle-{index}",
                        (NOW + timedelta(days=29, minutes=index)).isoformat(),
                    ),
                )
            snapshot = observe(
                codex_home,
                [skills_root],
                days=60,
                now=NOW + timedelta(days=30),
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
                intervention_records=load_interventions(staging / "interventions.jsonl"),
            )

            evaluation = next(
                item
                for item in decide(snapshot, now=NOW + timedelta(days=30))
                if item.metadata.get("intervention_id") == harness.id
            )

            self.assertEqual(evaluation.decision, "RETIRE_CANDIDATE")
            self.assertEqual(evaluation.metadata["lifecycle_verdict"], "IDLE_CANDIDATE")
            self.assertEqual(evaluation.confidence, "low")

    def test_external_tool_is_only_activated_after_a_real_artifact_is_supplied(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            catalog = [
                {
                    "kind": "oss",
                    "name": "acme/codex-deploy-preflight-guard",
                    "description": "A Codex hook that requires preflight before deploy commands",
                    "url": "https://github.com/acme/codex-deploy-preflight-guard",
                    "license": "MIT",
                    "updated_at": "2026-07-18T00:00:00Z",
                    "stars": 42,
                }
            ]
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=catalog,
                catalog_checked=True,
            )
            decisions = decide(snapshot, now=NOW)
            tool = next(item for item in decisions if item.target_kind == "TOOL")
            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)
            installed = root / "bin" / "deploy-preflight.exe"
            installed.parent.mkdir(parents=True)
            installed.write_text("reviewed external tool", encoding="utf-8")

            with self.assertRaises(LifecycleError):
                activate_tool(staging, tool.id, artifact=root / "bin" / "missing.exe")
            receipt = activate_tool(
                staging,
                tool.id,
                artifact=installed,
                activated_at=NOW,
            )

            self.assertEqual(receipt.status, "ACTIVE")
            self.assertEqual(receipt.target_kind, "TOOL")
            self.assertEqual(Path(receipt.artifact_path), installed.resolve())
            self.assertEqual(installed.read_text(encoding="utf-8"), "reviewed external tool")
            payload = json.loads((staging / "decisions.json").read_text(encoding="utf-8"))
            activated = next(item for item in payload["decisions"] if item["id"] == tool.id)
            self.assertEqual(activated["status"], "activated")

    def test_idle_external_tool_can_only_be_recorded_retired_after_user_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            catalog = [
                {
                    "kind": "oss",
                    "name": "acme/codex-deploy-preflight-guard",
                    "description": "A Codex hook that requires preflight before deploy commands",
                    "url": "https://github.com/acme/codex-deploy-preflight-guard",
                    "license": "MIT",
                    "updated_at": "2026-07-18T00:00:00Z",
                    "stars": 42,
                }
            ]
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=catalog,
                catalog_checked=True,
            )
            initial = decide(snapshot, now=NOW)
            tool = next(item for item in initial if item.target_kind == "TOOL")
            staging = stage_review(snapshot, initial, root / ".codex-metabolism", generated_at=NOW)
            installed = root / "bin" / "deploy-preflight.exe"
            installed.parent.mkdir(parents=True)
            installed.write_text("reviewed external tool", encoding="utf-8")
            activate_tool(staging, tool.id, artifact=installed, activated_at=NOW)
            for index in range(10):
                write_jsonl(
                    codex_home / "sessions" / "2026" / "08" / "19" / f"rollout-tool-idle-{index}.jsonl",
                    unrelated_records(
                        f"tool-idle-{index}",
                        (NOW + timedelta(days=29, minutes=index)).isoformat(),
                    ),
                )
            later = observe(
                codex_home,
                [skills_root],
                days=60,
                now=NOW + timedelta(days=30),
                project_root=root,
                catalog_entries=catalog,
                catalog_checked=True,
                intervention_records=load_interventions(staging / "interventions.jsonl"),
            )
            reevaluated = decide(later, now=NOW + timedelta(days=30))
            retirement = next(
                item
                for item in reevaluated
                if item.target_kind == "TOOL" and item.decision == "RETIRE_CANDIDATE"
            )
            stage_review(later, reevaluated, staging, generated_at=NOW + timedelta(days=30))

            with self.assertRaises(LifecycleError):
                retire_tool(staging, retirement.id, confirmed_inactive=False)
            receipt = retire_tool(
                staging,
                retirement.id,
                confirmed_inactive=True,
                retired_at=NOW + timedelta(days=30),
            )

            self.assertEqual(receipt.decision_id, tool.id)
            self.assertEqual(receipt.status, "RETIRED")
            self.assertTrue(installed.exists(), "recording retirement must not delete external files")

    def test_harness_rollback_removes_only_its_hook_and_archives_the_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, skills_root, staging, harness = self._apply_demo_harness(root)

            archived = rollback_intervention(
                staging,
                harness.id,
                project_root=root,
                skill_root=skills_root,
                rolled_back_at=NOW + timedelta(days=1),
            )

            hooks = json.loads((root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
            self.assertFalse(
                any(
                    hook.get("codexMetabolismDecision") == harness.id
                    for group in hooks["hooks"].get("PreToolUse", [])
                    for hook in group.get("hooks", [])
                )
            )
            self.assertTrue((archived / "guard.py").is_file())
            latest = load_interventions(staging / "interventions.jsonl")[-1]
            self.assertEqual(latest.status, "ROLLED_BACK")

    def test_skill_patch_rollback_restores_the_reviewed_original(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            skill_file = write_skill(
                skills_root,
                "release-workflow",
                description="Guide a contextual release review",
            )
            original = skill_file.read_text(encoding="utf-8")
            for index in (1, 2):
                write_jsonl(
                    codex_home / "sessions" / "2026" / "07" / "20" / f"rollout-release-{index}.jsonl",
                    session_records(
                        f"release-{index}",
                        failed_command="release project",
                        correction="No, use $release-workflow and verify the contextual checklist.",
                        skill_name="release-workflow",
                    ),
                )
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
            )
            decisions = decide(snapshot, now=NOW)
            patch = next(
                item for item in decisions if item.target == "release-workflow" and item.decision == "PATCH"
            )
            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)
            apply_decision(
                staging,
                patch.id,
                project_root=root,
                skill_root=skills_root,
                changed_at=NOW,
            )
            self.assertNotEqual(skill_file.read_text(encoding="utf-8"), original)

            archived = rollback_intervention(
                staging,
                patch.id,
                project_root=root,
                skill_root=skills_root,
                rolled_back_at=NOW + timedelta(days=1),
            )

            self.assertEqual(skill_file.read_text(encoding="utf-8"), original)
            self.assertTrue((archived / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
