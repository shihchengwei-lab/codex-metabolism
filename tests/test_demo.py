from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from codex_metabolism.cli import main


class DemoFixtureTests(unittest.TestCase):
    def test_public_demo_replays_the_four_cross_layer_outcomes(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        agents = repo / "examples" / "demo-project" / "AGENTS.md"
        before = hashlib.sha256(agents.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "review"
            code = main(
                [
                    "review",
                    "--days",
                    "7",
                    "--codex-home",
                    str(repo / "examples" / "demo-home" / ".codex"),
                    "--skill-root",
                    str(repo / "examples" / "demo-home" / ".agents" / "skills"),
                    "--project-root",
                    str(repo / "examples" / "demo-project"),
                    "--catalog-file",
                    str(repo / "examples" / "reviewed-catalog.json"),
                    "--skillreaper-report",
                    str(repo / "examples" / "skillreaper-report.json"),
                    "--output-dir",
                    str(output),
                    "--now",
                    "2026-07-20T12:00:00+00:00",
                ]
            )

            self.assertEqual(code, 0)
            payload = json.loads((output / "decisions.json").read_text(encoding="utf-8"))
            outcomes = {(item["decision"], item["target_kind"], item["target"]) for item in payload["decisions"]}
            self.assertTrue(any(decision == "CREATE" and kind == "HARNESS" for decision, kind, _ in outcomes))
            self.assertIn(("KEEP", "SKILL", "healthy-skill"), outcomes)
            self.assertIn(("RETIRE_CANDIDATE", "SKILL", "old-unused"), outcomes)
            self.assertTrue(any(decision == "PATCH" and kind == "RULE" for decision, kind, _ in outcomes))
            self.assertEqual(len(payload["decisions"]), 4)
            rule = next(item for item in payload["decisions"] if item["target_kind"] == "RULE")
            self.assertTrue(rule["metadata"]["whole_document_evaluated"])
            self.assertTrue(rule["metadata"]["managed_region"]["applyable"])
            self.assertTrue((output / "proposed-rules" / rule["id"] / "changes.diff").is_file())
            self.assertEqual(hashlib.sha256(agents.read_bytes()).hexdigest(), before)
            harness = next(item for item in payload["decisions"] if item["target_kind"] == "HARNESS")
            installed_rung = next(
                rung for rung in harness["adoption_ladder"] if rung["name"] == "installed"
            )
            self.assertEqual(installed_rung["result"], "none")


if __name__ == "__main__":
    unittest.main()
