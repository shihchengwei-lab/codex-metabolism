from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_metabolism.decide import decide
from codex_metabolism.integrations.skillreaper import parse_skillreaper_report
from codex_metabolism.observe import observe

from tests.helpers import NOW, make_deploy_home, session_records, write_jsonl, write_skill


class DecideTests(unittest.TestCase):
    def test_mechanical_harness_wins_over_skill_or_rule_for_preflight_friction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
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
            friction = [d for d in decisions if d.metadata.get("signature") == "deploy production"]

            self.assertEqual(len(friction), 1)
            self.assertEqual(friction[0].decision, "CREATE")
            self.assertEqual(friction[0].target_kind, "HARNESS")
            self.assertEqual(friction[0].mechanism, "pretool_guard")
            self.assertEqual(friction[0].metadata["required_command"], "preflight")
            self.assertGreaterEqual(len(friction[0].evidence), 2)
            self.assertEqual(friction[0].readiness, "ready")
            self.assertEqual(
                [rung["name"] for rung in friction[0].adoption_ladder],
                ["necessity", "builtin", "installed", "repo", "ecosystem"],
            )
            self.assertFalse(any(d.target_kind == "RULE" for d in friction))
            self.assertFalse(any(d.target_kind == "SKILL" for d in friction))

    def test_contextual_repeated_workflow_patches_the_skill_when_no_mechanical_fix_is_known(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            write_skill(skills_root, "release-workflow", description="Guide a contextual release review")
            correction = "Use $release-workflow and verify the contextual checklist."
            for index in (1, 2):
                write_jsonl(
                    codex_home / "sessions" / "2026" / "07" / "20" / f"rollout-{index}.jsonl",
                    session_records(
                        f"release-{index}",
                        failed_command="release project",
                        prerequisite="review context",
                        correction=correction,
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
            release = [d for d in decisions if d.target == "release-workflow" and d.decision == "PATCH"]

            self.assertEqual(len(release), 1)
            self.assertEqual(release[0].target_kind, "SKILL")
            self.assertEqual(release[0].mechanism, "workflow_instruction")

    def test_skillreaper_reap_becomes_candidate_and_keep_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            write_skill(skills_root, "old-unused", age_days=60)
            write_skill(skills_root, "healthy-skill", age_days=60)
            write_jsonl(
                codex_home / "sessions" / "2026" / "07" / "20" / "rollout-healthy.jsonl",
                session_records("healthy", skill_name="healthy-skill"),
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
            imported = parse_skillreaper_report(
                {
                    "GeneratedAt": NOW.isoformat(),
                    "Sessions": 12,
                    "MalformedLines": 0,
                    "Warnings": [],
                    "Rows": [
                        {
                            "Category": "skill",
                            "Name": "old-unused",
                            "Platform": "codex",
                            "Path": str(skills_root / "old-unused"),
                            "Removable": True,
                            "Uses": 0,
                            "Verdict": "REAP",
                            "Reason": "unused",
                        },
                        {
                            "Category": "skill",
                            "Name": "healthy-skill",
                            "Platform": "codex",
                            "Path": str(skills_root / "healthy-skill"),
                            "Removable": True,
                            "Uses": 3,
                            "Verdict": "KEEP",
                            "Reason": "used",
                        },
                    ],
                }
            )
            snapshot.lifecycle_evidence = imported.evidence
            snapshot.coverage.skill_lifecycle_source = "skillreaper"
            snapshot.coverage.skill_lifecycle_complete = imported.complete
            decisions = decide(snapshot, now=NOW, grace_days=28)

            self.assertTrue(
                any(
                    d.target == "old-unused"
                    and d.decision == "RETIRE_CANDIDATE"
                    and d.confidence == "high"
                    and d.metadata["lifecycle_analyzer"] == "skillreaper"
                    for d in decisions
                )
            )
            self.assertTrue(any(d.target == "healthy-skill" and d.decision == "KEEP" for d in decisions))

    def test_without_external_lifecycle_evidence_non_use_is_not_a_retirement_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            write_skill(skills_root, "old-unused", age_days=60)
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
            )

            decisions = decide(snapshot, now=NOW, grace_days=28)

            self.assertFalse(any(d.target == "old-unused" and d.decision == "RETIRE_CANDIDATE" for d in decisions))

    def test_incomplete_skillreaper_report_blocks_retirement_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            write_skill(skills_root, "old-unused", age_days=60)
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
            )
            imported = parse_skillreaper_report(
                {
                    "Sessions": 12,
                    "MalformedLines": 1,
                    "Warnings": [{"Path": "~/.codex", "Msg": "incomplete"}],
                    "Rows": [
                        {
                            "Category": "skill",
                            "Name": "old-unused",
                            "Platform": "codex",
                            "Path": str(skills_root / "old-unused"),
                            "Removable": True,
                            "Uses": 0,
                            "Verdict": "REAP",
                            "Reason": "unused",
                        }
                    ],
                }
            )
            snapshot.lifecycle_evidence = imported.evidence
            snapshot.coverage.skill_lifecycle_source = "skillreaper"
            snapshot.coverage.skill_lifecycle_complete = imported.complete

            decisions = decide(snapshot, now=NOW, grace_days=28)

            self.assertFalse(any(d.target == "old-unused" and d.decision == "RETIRE_CANDIDATE" for d in decisions))


if __name__ == "__main__":
    unittest.main()
