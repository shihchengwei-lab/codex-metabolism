from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from codex_metabolism.decide import decide
from codex_metabolism.integrations.skillreaper import parse_skillreaper_report
from codex_metabolism.interventions import load_interventions
from codex_metabolism.lifecycle import (
    apply_decision,
    archive_decision,
    reject_decision,
    restore_archived_skill,
)
from codex_metabolism.observe import observe
from codex_metabolism.stage import stage_review

from tests.helpers import NOW, make_deploy_home, session_records, write_jsonl, write_skill


class LifecycleTests(unittest.TestCase):
    def test_harness_apply_is_explicit_and_installs_a_working_guard(self) -> None:
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
            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)
            harness = next(d for d in decisions if d.target_kind == "HARNESS")

            apply_decision(staging, harness.id, project_root=root, skill_root=skills_root)

            hooks = json.loads((root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
            installed = root / ".codex" / "hooks" / f"codex-metabolism-{harness.id}" / "guard.py"
            self.assertTrue(installed.is_file())
            self.assertEqual(len(hooks["hooks"]["PreToolUse"]), 1)

            denied = subprocess.run(
                [sys.executable, str(installed)],
                input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "deploy production"}}),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(denied.returncode, 0)
            self.assertEqual(
                json.loads(denied.stdout)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

            allowed = subprocess.run(
                [sys.executable, str(installed)],
                input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "preflight && deploy production"}}),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(allowed.returncode, 0)
            self.assertEqual(allowed.stdout, "")

    def test_retirement_archives_instead_of_deleting_and_reject_only_changes_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            live = write_skill(skills_root, "old-unused", age_days=60).parent
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
                    "MalformedLines": 0,
                    "Warnings": [],
                    "Rows": [
                        {
                            "Category": "skill",
                            "Name": "old-unused",
                            "Platform": "codex",
                            "Path": str(live),
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
            decisions = decide(snapshot, now=NOW)
            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)
            retire = next(d for d in decisions if d.target == "old-unused")

            archived = archive_decision(staging, retire.id, skill_root=skills_root, archived_at=NOW)

            self.assertFalse(live.exists())
            self.assertTrue((archived / "SKILL.md").is_file())
            self.assertTrue(str(archived.resolve()).startswith(str((skills_root / ".codex-metabolism-archive").resolve())))
            after_archive = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
            )
            self.assertFalse(any(skill.name == "old-unused" for skill in after_archive.skills))

            restored = restore_archived_skill(
                staging,
                retire.id,
                skill_root=skills_root,
                restored_at=NOW + timedelta(hours=1),
            )
            self.assertEqual(restored, live.resolve())
            self.assertTrue((restored / "SKILL.md").is_file())
            self.assertFalse(archived.exists())
            latest = load_interventions(staging / "interventions.jsonl")[-1]
            self.assertEqual(latest.status, "ACTIVE")
            self.assertEqual(latest.metadata["lifecycle_event"], "RESTORED")

            harness = next(d for d in decisions if d.target_kind == "HARNESS")
            reject_decision(staging, harness.id)
            self.assertFalse((root / ".codex" / "hooks.json").exists())
            payload = json.loads((staging / "decisions.json").read_text(encoding="utf-8"))
            rejected = next(item for item in payload["decisions"] if item["id"] == harness.id)
            self.assertEqual(rejected["status"], "rejected")

    def test_skill_patch_uses_the_same_safe_staging_name_as_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            skill_file = write_skill(skills_root, "release-workflow")
            skill_file.write_text(
                "---\nname: release:workflow\ndescription: Contextual release guidance\n---\n\n# Release\n",
                encoding="utf-8",
            )
            for index in (1, 2):
                write_jsonl(
                    codex_home / "sessions" / "2026" / "07" / "20" / f"rollout-release-{index}.jsonl",
                    session_records(
                        f"release-{index}",
                        failed_command="release project",
                        correction="Use $release:workflow and verify the contextual checklist.",
                        skill_name="release:workflow",
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
            patch = next(d for d in decisions if d.target == "release:workflow" and d.decision == "PATCH")
            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)

            apply_decision(staging, patch.id, project_root=root, skill_root=skills_root)

            self.assertIn("Evidence-backed update", skill_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
