from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codex_metabolism.decide import decide
from codex_metabolism.observe import observe
from codex_metabolism.stage import stage_review

from tests.helpers import NOW, make_deploy_home, session_records, write_jsonl


class StageTests(unittest.TestCase):
    def test_report_exposes_friction_funnel_when_no_pattern_qualifies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            records = [
                record
                for record in session_records("retry-without-correction")
                if not (
                    record.get("payload", {}).get("type") == "message"
                    and str(
                        (record.get("payload", {}).get("content") or [{}])[0].get(
                            "text", ""
                        )
                    ).startswith("No. Run `")
                )
            ]
            records.insert(
                3,
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "turn_aborted",
                        "turn_id": "turn-1",
                        "reason": "interrupted",
                    },
                },
            )
            write_jsonl(
                codex_home / "sessions" / "2026" / "07" / "20" / "rollout-retry.jsonl",
                records,
            )
            snapshot = observe(
                codex_home, [skills_root], days=7, now=NOW, project_root=root
            )
            output = root / ".codex-metabolism"

            stage_review(snapshot, [], output, generated_at=NOW)

            report = (output / "report.md").read_text(encoding="utf-8")
            self.assertIn("Review mode: **deterministic fallback**", report)
            self.assertIn("Semantic interpretation was not run", report)
            self.assertIn("`--advisor codex`", report)
            self.assertIn("## Friction detection funnel", report)
            self.assertIn("Observed user feedback candidates: 0", report)
            self.assertIn("Structured interrupted turns: 1", report)
            self.assertIn("Tool failures with a command: 1", report)
            self.assertIn("Same-command recoveries: 1", report)
            self.assertIn("Recoveries with a recognized user correction: 0", report)
            self.assertIn("Recurring patterns meeting the decision threshold: 0", report)
            self.assertIn(
                "Zero qualifying patterns does not mean zero collaboration friction.",
                report,
            )
            self.assertIn("## Review guidance", report)
            self.assertIn("Guidance is non-authoritative", report)
            self.assertIn("Inspect interruption context before staging an intervention", report)
            self.assertIn("Do not lower the correction gate based on recovery alone", report)
            payload = json.loads((output / "decisions.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["review_mode"], "deterministic_fallback")
            self.assertEqual(
                payload["observation"]["friction_detection_funnel"]["interrupted_turns"],
                1,
            )
            guidance = payload["review_guidance"]
            self.assertEqual({item["signal"] for item in guidance}, {"interruption", "recovery_gap"})
            self.assertTrue(all(item["authority"] == "advisory" for item in guidance))

    def test_stage_reports_configured_plugins_separately_from_session_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[
                    {
                        "kind": "plugin",
                        "name": "browser@openai-bundled",
                        "status": "installed, enabled",
                        "source": "codex-plugin-list",
                    }
                ],
                catalog_checked=True,
            )
            output = root / ".codex-metabolism"

            stage_review(snapshot, [], output, generated_at=NOW)

            report = (output / "report.md").read_text(encoding="utf-8")
            payload = json.loads((output / "decisions.json").read_text(encoding="utf-8"))
            self.assertIn(
                "session-observed PATH tools=0 · configured plugins=1",
                report,
            )
            self.assertEqual(payload["observation"]["configured_plugin_count"], 1)

    def test_stage_writes_review_artifacts_without_touching_live_codex_files(self) -> None:
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
            output = root / ".codex-metabolism"

            result = stage_review(snapshot, decisions, output, generated_at=NOW)

            self.assertEqual(result, output)
            self.assertTrue((output / "report.md").is_file())
            self.assertTrue((output / "decisions.json").is_file())
            harness = next(d for d in decisions if d.target_kind == "HARNESS")
            proposal = output / "proposed-harness" / harness.id
            self.assertTrue((proposal / "guard.py").is_file())
            self.assertTrue((proposal / "rule.json").is_file())
            self.assertTrue((proposal / "hooks.fragment.json").is_file())
            self.assertFalse((root / ".codex" / "hooks.json").exists())

            payload = json.loads((output / "decisions.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            staged = next(item for item in payload["decisions"] if item["id"] == harness.id)
            self.assertEqual(staged["status"], "proposed")
            self.assertEqual(staged["readiness"], "ready")
            self.assertEqual(len(staged["adoption_ladder"]), 5)
            self.assertIn("coverage", staged)
            self.assertGreaterEqual(len(staged["evidence"]), 2)


if __name__ == "__main__":
    unittest.main()
