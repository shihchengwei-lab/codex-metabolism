from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from examples.run_detector_evaluation import run


class DetectorEvaluationTests(unittest.TestCase):
    def test_public_boundary_suite_reports_hits_misses_and_abstentions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "detector-evaluation"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                code = run(output)

            self.assertEqual(code, 0)
            result = json.loads(
                (output / "detector-evaluation.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result["summary"]["case_count"], 24)
            self.assertEqual(result["summary"]["labeled_positive_count"], 16)
            self.assertEqual(result["summary"]["labeled_negative_count"], 8)
            self.assertEqual(
                result["confusion_matrix"],
                {
                    "true_positive": 8,
                    "false_positive": 0,
                    "false_negative": 8,
                    "true_negative": 8,
                },
            )
            self.assertEqual(result["metrics"]["precision"], 1.0)
            self.assertEqual(result["metrics"]["recall"], 0.5)
            self.assertEqual(result["metrics"]["abstention_rate"], 2 / 3)
            self.assertTrue(result["methodology"]["synthetic"])
            self.assertIn("not a real-world quality benchmark", result["methodology"]["claim"])

            known_misses = {
                item["id"]
                for item in result["cases"]
                if item["expected_detected"] and not item["observed_detected"]
            }
            self.assertEqual(
                known_misses,
                {
                    "path-variation",
                    "argument-variation",
                    "command-alias",
                    "quoted-path-variation",
                    "unmarked-correction",
                    "equivalent-recovery-command",
                    "flag-order-variation",
                    "shell-variant",
                },
            )
            rendered = stdout.getvalue()
            self.assertIn("Detector boundary: 24 cases", rendered)
            self.assertIn("Precision: 1.000", rendered)
            self.assertIn("Recall: 0.500", rendered)
            self.assertIn("False positives: 0", rendered)


if __name__ == "__main__":
    unittest.main()
