from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ClosedLoopDemoTests(unittest.TestCase):
    def test_demo_runs_two_review_generations_and_validates_the_harness(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "closed-loop-demo"
            result = subprocess.run(
                [
                    sys.executable,
                    str(repo / "examples" / "run_closed_loop_demo.py"),
                    "--output-root",
                    str(workspace),
                ],
                cwd=repo,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("First review: CREATE HARNESS + PATCH RULE", result.stdout)
            self.assertIn("Second review: KEEP HARNESS (VALIDATED)", result.stdout)
            self.assertTrue((workspace / ".codex-metabolism" / "interventions.jsonl").is_file())
            self.assertTrue((workspace / ".codex-metabolism" / "report.md").is_file())


if __name__ == "__main__":
    unittest.main()
