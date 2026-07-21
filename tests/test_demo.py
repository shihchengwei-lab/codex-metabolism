from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentFirstDemoTests(unittest.TestCase):
    def test_prepare_only_creates_neutral_input_for_a_live_codex_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "live-review"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "examples" / "run_agent_first_demo.py"),
                    "--output-root",
                    str(output),
                    "--prepare-only",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Synthetic evidence is ready for a live Codex review", result.stdout)
            self.assertIn("Use $codex-metabolism", result.stdout)
            self.assertIn("Target project (inspect read-only before approval)", result.stdout)
            self.assertTrue((output / ".codex-metabolism" / "evidence.json").is_file())
            self.assertTrue((output / "project" / "tools" / "preflight.py").is_file())
            self.assertTrue((output / "project" / "tools" / "release.py").is_file())
            self.assertTrue((output / "project" / "release.ps1").is_file())
            self.assertFalse((output / ".codex-metabolism" / "proposals.json").exists())

    def test_demo_separates_agent_judgment_from_runtime_safety(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "demo-output"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "examples" / "run_agent_first_demo.py"),
                    "--output-root",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Runtime interpretation: 0 semantic decisions", result.stdout)
            self.assertIn("Recorded Codex fixture: CREATE SKILL deploy-safely", result.stdout)
            self.assertIn("the exact displayed digest was approved", result.stdout)
            self.assertIn("Receipt visible to the next review: ACTIVE", result.stdout)
            self.assertIn("Rollback: live skill archived, not deleted", result.stdout)

            evidence = json.loads((output / ".codex-metabolism" / "evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["authority"], "evidence_only")
            self.assertNotIn("decisions", evidence)
            self.assertFalse((output / "skills" / "deploy-safely" / "SKILL.md").exists())
            self.assertTrue(
                (
                    output
                    / ".codex-metabolism"
                    / "archive"
                    / "agent-deploy-safely"
                    / "deploy-safely"
                    / "SKILL.md"
                ).is_file()
            )


if __name__ == "__main__":
    unittest.main()
