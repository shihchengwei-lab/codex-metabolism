from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from codex_metabolism.evidence_export import CSV_FIELDS, export_evidence_csv
from codex_metabolism.models import Coverage, Decision, Observation


class EvidenceExportTests(unittest.TestCase):
    def test_export_is_deterministic_structured_and_excludes_private_source_text(self) -> None:
        coverage = Coverage(
            files_selected=3,
            files_parsed=2,
            parse_errors=1,
            skill_invocation="partial",
            skill_lifecycle_source="local-positive-only",
            skill_lifecycle_complete=False,
        )
        observation = Observation(
            codex_home=r"C:\Users\alice\.codex",
            project_root=r"C:\Users\alice\private-project",
            days=7,
            sessions=[],
            skills=[],
            repo_assets=[],
            catalog_entries=[],
            coverage=coverage,
        )
        decision = Decision(
            id="met-safe-reference",
            decision="PATCH",
            target_kind="TOOL",
            target=r"C:\Users\alice\private-tool",
            mechanism="configure_installed",
            evidence=[
                {
                    "id": "ev-safe-two",
                    "session_id": "private-session-two",
                    "kind": "user_correction",
                    "summary": "raw correction with SECRET",
                    "source": r"C:\Users\alice\.codex\sessions\two.jsonl",
                    "hard": False,
                },
                {
                    "id": "ev-safe-one",
                    "session_id": "private-session-one",
                    "kind": "verified_recovery",
                    "summary": "private command recovered",
                    "source": "/home/alice/session.jsonl",
                    "hard": True,
                },
            ],
            confidence="medium",
            proposed_change="Run SECRET from C:\\Users\\alice before retrying.",
            coverage=coverage.to_dict(),
            adoption_ladder=[],
            metadata={
                "signature": r"C:\Users\alice\deploy --token SECRET",
                "session_ids": ["private-session-two", "private-session-one"],
            },
        )
        abstentions = [
            {
                "signature": "/home/alice/private-task",
                "reason": "no_verified_recovery_path",
                "failure_sessions": 2,
                "verified_recovery_sessions": 0,
                "success_only_sessions": 1,
            }
        ]

        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first.csv"
            second = Path(temp) / "second.csv"

            export_evidence_csv(observation, [decision], first, abstentions=abstentions)
            export_evidence_csv(observation, [decision], second, abstentions=abstentions)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            rendered = first.read_text(encoding="utf-8")
            for private_value in (
                "private-session",
                "alice",
                "SECRET",
                "raw correction",
                "private command",
            ):
                self.assertNotIn(private_value, rendered)

            with first.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)

            self.assertEqual(tuple(reader.fieldnames or ()), CSV_FIELDS)
            self.assertEqual([row["record_type"] for row in rows], ["decision", "abstention"])

            action = rows[0]
            self.assertEqual(action["record_id"], "met-safe-reference")
            self.assertRegex(action["task_ref"], r"^task-\d{3}$")
            self.assertEqual(action["session_refs"], "session-001;session-002")
            self.assertEqual(
                action["observed_signals"], "user_correction;verified_recovery"
            )
            self.assertEqual(
                action["session_counts"],
                "failure=1;recovery=1;success_only=unknown",
            )
            self.assertEqual(action["evidence_refs"], "ev-safe-one;ev-safe-two")
            self.assertEqual(action["decision"], "PATCH")
            self.assertRegex(
                action["intervention"],
                r"^TOOL:configure_installed:target-\d{3}$",
            )
            self.assertEqual(action["confidence"], "medium")
            self.assertEqual(action["result"], "proposed")
            self.assertEqual(
                action["coverage"],
                "parsed=2/3;errors=1;skill_usage=partial;"
                "lifecycle=local-positive-only;retirement_safe=false",
            )

            abstention = rows[1]
            self.assertEqual(abstention["record_id"], "abstention-001")
            self.assertEqual(abstention["decision"], "")
            self.assertEqual(
                abstention["result"], "abstained:no_verified_recovery_path"
            )
            self.assertEqual(
                abstention["session_counts"],
                "failure=2;recovery=0;success_only=1",
            )


if __name__ == "__main__":
    unittest.main()
