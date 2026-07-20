from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codex_metabolism.decide import decide
from codex_metabolism.observe import observe
from codex_metabolism.stage import stage_review

from tests.helpers import NOW, make_deploy_home


class StageTests(unittest.TestCase):
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
