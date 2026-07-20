from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from examples.run_messy_evidence_demo import run


class MessyEvidenceDemoTests(unittest.TestCase):
    def test_noisy_fixture_actions_once_and_abstains_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "messy-evidence"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                code = run(output)

            self.assertEqual(code, 0)
            staged = json.loads(
                (output / ".codex-metabolism" / "decisions.json").read_text(
                    encoding="utf-8"
                )
            )
            challenge = json.loads(
                (output / "challenge-results.json").read_text(encoding="utf-8")
            )
            with (output / "friction-evidence.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                exported = list(csv.DictReader(handle))

            self.assertEqual(len(staged["decisions"]), 1)
            action = staged["decisions"][0]
            self.assertEqual(action["decision"], "PATCH")
            self.assertEqual(action["target_kind"], "TOOL")
            self.assertEqual(action["target"], "tobitege/codlogs")
            self.assertEqual(
                action["metadata"]["signature"], "explore codex logs safely"
            )

            self.assertEqual(
                challenge["summary"],
                {
                    "decision_count": 1,
                    "abstention_count": 2,
                    "coverage_warning_count": 1,
                    "unsafe_retirement_decision_count": 0,
                },
            )
            self.assertEqual(challenge["fixture"]["session_count"], 6)
            self.assertEqual(challenge["fixture"]["catalog_candidate_count"], 2)
            self.assertEqual(
                {item["reason"] for item in challenge["abstentions"]},
                {
                    "only_one_verified_recovery_session",
                    "no_verified_recovery_path",
                },
            )
            no_recovery = next(
                item
                for item in challenge["abstentions"]
                if item["reason"] == "no_verified_recovery_path"
            )
            self.assertEqual(no_recovery["failure_sessions"], 2)
            self.assertEqual(no_recovery["verified_recovery_sessions"], 0)
            self.assertEqual(no_recovery["success_only_sessions"], 1)

            coverage = challenge["coverage"]
            self.assertEqual(coverage["files_selected"], 6)
            self.assertEqual(coverage["files_parsed"], 6)
            self.assertEqual(coverage["parse_errors"], 1)
            self.assertEqual(coverage["skill_invocation"], "partial")
            self.assertEqual(coverage["skill_lifecycle_source"], "skillreaper")
            self.assertFalse(coverage["skill_lifecycle_complete"])
            self.assertFalse(coverage["retirement_safe"])
            self.assertFalse(
                any(
                    item["decision"] == "RETIRE_CANDIDATE"
                    for item in staged["decisions"]
                )
            )

            self.assertEqual(
                [row["record_type"] for row in exported],
                ["decision", "abstention", "abstention"],
            )
            self.assertEqual(exported[0]["decision"], "PATCH")
            self.assertRegex(
                exported[0]["intervention"],
                r"^TOOL:adopt_external:target-\d{3}$",
            )
            self.assertEqual(
                exported[0]["session_counts"],
                "failure=2;recovery=2;success_only=unknown",
            )
            self.assertEqual(
                {row["result"] for row in exported[1:]},
                {
                    "abstained:only_one_verified_recovery_session",
                    "abstained:no_verified_recovery_path",
                },
            )
            self.assertTrue(all(row["decision"] == "" for row in exported[1:]))
            exported_text = (output / "friction-evidence.csv").read_text(
                encoding="utf-8"
            )
            for private_value in (
                "action-one",
                "action-two",
                "single-recovery",
                "no-recovery-one",
                "C:/demo/noisy-repo",
            ):
                self.assertNotIn(private_value, exported_text)

            rendered = stdout.getvalue()
            self.assertIn("Messy evidence: 1 decision, 2 abstentions", rendered)
            self.assertIn("Actioned: PATCH TOOL -> tobitege/codlogs", rendered)
            self.assertIn(
                "Abstained: publish package -> only 1 verified recovery session",
                rendered,
            )
            self.assertIn(
                "Abstained: review flaky tests -> repeated failures but no verified recovery path",
                rendered,
            )
            self.assertIn("Coverage warning: 1 malformed JSONL line", rendered)
            self.assertIn("Unsafe retirement decisions: 0", rendered)


if __name__ == "__main__":
    unittest.main()
