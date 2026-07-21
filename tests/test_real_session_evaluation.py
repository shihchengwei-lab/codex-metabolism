from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "anonymized-real-session-evaluation.json"


class RealSessionEvaluationTests(unittest.TestCase):
    def test_public_fixture_is_real_bounded_and_anonymized(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["provenance"]["source"], "real_codex_sessions")
        self.assertFalse(payload["provenance"]["raw_logs_committed"])
        self.assertEqual(payload["coverage"]["files_selected"], 14)
        self.assertEqual(payload["coverage"]["files_parsed"], 14)
        self.assertEqual(payload["coverage"]["unique_sessions"], 6)
        self.assertEqual(payload["coverage"]["duplicate_session_files"], 8)
        self.assertEqual(payload["coverage"]["parse_errors"], 0)
        self.assertGreaterEqual(len(payload["cases"]), 2)
        self.assertTrue(all(case["evidence"] for case in payload["cases"]))
        self.assertTrue(all(case["agent_judgment"] for case in payload["cases"]))
        self.assertTrue(all(case["recommended_outcome"] for case in payload["cases"]))

        for forbidden in ("kk789", "shihchengwei", "C:\\\\Users", "/Users/", "github.com/"):
            self.assertNotIn(forbidden, serialized)
        self.assertIsNone(
            re.search(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                serialized,
                re.IGNORECASE,
            )
        )

    def test_real_session_runner_validates_and_summarizes_the_fixture(self) -> None:
        result = subprocess.run(
            [sys.executable, "examples/run_real_session_evaluation.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("REAL SESSION EVALUATION", result.stdout)
        self.assertIn("14/14 files parsed", result.stdout)
        self.assertIn("6 unique sessions", result.stdout)
        self.assertIn("raw logs committed: no", result.stdout.casefold())


if __name__ == "__main__":
    unittest.main()
