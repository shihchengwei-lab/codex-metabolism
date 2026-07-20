from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_metabolism.observe import observe

from tests.helpers import NOW, make_deploy_home, session_records, write_jsonl, write_skill


class ObserveTests(unittest.TestCase):
    def test_observes_realistic_codex_jsonl_without_claiming_structured_skill_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            write_skill(skills_root, "healthy-skill")
            records = session_records("session-three", skill_name="healthy-skill")
            write_jsonl(
                codex_home / "sessions" / "2026" / "07" / "20" / "rollout-three.jsonl",
                records,
            )

            snapshot = observe(
                codex_home=codex_home,
                skill_roots=[skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
            )

            self.assertEqual(snapshot.coverage.files_selected, 3)
            self.assertEqual(snapshot.coverage.files_parsed, 3)
            self.assertEqual(snapshot.coverage.parse_errors, 0)
            self.assertEqual(snapshot.coverage.skill_invocation, "heuristic")
            self.assertEqual({session.model for session in snapshot.sessions}, {"gpt-5.6"})
            self.assertEqual({session.cli_version for session in snapshot.sessions}, {"0.144.5"})

            first = next(session for session in snapshot.sessions if session.session_id == "session-one")
            statuses = [(tool.command, tool.status) for tool in first.tool_executions]
            self.assertIn(("deploy production", "failure"), statuses)
            self.assertIn(("deploy production", "success"), statuses)
            self.assertTrue(any("Run `preflight`" in message.text for message in first.corrections))

            healthy = next(skill for skill in snapshot.skills if skill.name == "healthy-skill")
            self.assertEqual(healthy.usage_signals, 1)
            self.assertFalse(healthy.protected)

    def test_parse_errors_downgrade_coverage_instead_of_becoming_non_use(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root, malformed=True)
            write_skill(skills_root, "possibly-used")

            snapshot = observe(
                codex_home=codex_home,
                skill_roots=[skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
            )

            self.assertEqual(snapshot.coverage.parse_errors, 1)
            self.assertEqual(snapshot.coverage.skill_invocation, "partial")
            self.assertFalse(snapshot.coverage.retirement_safe)

    def test_nested_non_string_type_is_treated_as_unknown_data_not_a_parser_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            write_jsonl(
                codex_home / "sessions" / "2026" / "07" / "20" / "rollout-object-type.jsonl",
                [
                    {
                        "type": "session_meta",
                        "payload": {"id": "object-type", "timestamp": NOW.isoformat()},
                    },
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": {"schema": "new-shape"},
                                    "nested": {"type": "input_text", "text": "Still readable"},
                                }
                            ],
                        },
                    },
                ],
            )

            snapshot = observe(
                codex_home=codex_home,
                skill_roots=[skills_root],
                days=7,
                now=NOW,
                project_root=root,
            )

            self.assertEqual(snapshot.coverage.files_parsed, 1)
            self.assertEqual(snapshot.coverage.parse_errors, 0)
            self.assertEqual(snapshot.sessions[0].session_id, "object-type")
            self.assertEqual(snapshot.sessions[0].messages[0].text, "Still readable")


if __name__ == "__main__":
    unittest.main()
