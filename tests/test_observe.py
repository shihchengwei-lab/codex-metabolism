from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codex_metabolism.evidence import build_evidence_packet
from codex_metabolism.observe import observe

from tests.helpers import NOW, make_deploy_home, session_records, write_jsonl, write_skill


class ObserveTests(unittest.TestCase):
    def test_observation_preserves_neutral_ordered_events_without_semantic_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            records = session_records("interrupted-turn")
            records.insert(
                3,
                {
                    "type": "event_msg",
                    "payload": {"type": "turn_aborted", "reason": "interrupted"},
                },
            )
            write_jsonl(
                codex_home / "sessions" / "2026" / "07" / "20" / "rollout-neutral.jsonl",
                records,
            )

            snapshot = observe(codex_home, [skills_root], days=7, now=NOW, project_root=root)
            session = snapshot.sessions[0]
            packet = build_evidence_packet(snapshot, generated_at=NOW)
            serialized = json.dumps(packet, ensure_ascii=False)

            self.assertEqual(session.interrupted_turns, 1)
            self.assertFalse(hasattr(session, "corrections"))
            self.assertFalse(hasattr(session, "feedback_candidates"))
            self.assertNotIn('"correction"', serialized)
            self.assertNotIn('"friction"', serialized)
            self.assertNotIn('"workflow_candidate"', serialized)
            sequences = [
                event["sequence"]
                for event in packet["sessions"][0]["events"]
                if "sequence" in event
            ]
            self.assertEqual(sequences, sorted(sequences))

    def test_late_user_messages_remain_available_to_the_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            records = session_records("long-session")
            records[5:5] = [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": f"Follow-up {index}"}],
                    },
                }
                for index in range(35)
            ]
            write_jsonl(
                codex_home / "sessions" / "2026" / "07" / "20" / "rollout-long.jsonl",
                records,
            )

            snapshot = observe(codex_home, [skills_root], days=7, now=NOW, project_root=root)
            messages = [item.text for item in snapshot.sessions[0].messages]

            self.assertIn("Follow-up 34", messages)
            self.assertTrue(any(message.startswith("No. Run") for message in messages))

    def test_observes_jsonl_and_reports_skill_usage_as_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            write_skill(skills_root, "healthy-skill")
            write_jsonl(
                codex_home / "sessions" / "2026" / "07" / "20" / "rollout-three.jsonl",
                session_records("session-three", skill_name="healthy-skill"),
            )

            snapshot = observe(codex_home, [skills_root], days=7, now=NOW, project_root=root)

            self.assertEqual(snapshot.coverage.files_selected, 3)
            self.assertEqual(snapshot.coverage.files_parsed, 3)
            self.assertEqual(snapshot.coverage.parse_errors, 0)
            self.assertEqual(snapshot.coverage.skill_invocation, "heuristic")
            first = next(item for item in snapshot.sessions if item.session_id == "session-one")
            self.assertIn(("deploy production", "failure"), [(t.command, t.status) for t in first.tool_executions])
            healthy = next(skill for skill in snapshot.skills if skill.name == "healthy-skill")
            self.assertEqual(healthy.usage_signals, 1)

    def test_parse_gaps_stay_unknown_and_unfamiliar_nested_types_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root, malformed=True)
            write_jsonl(
                codex_home / "sessions" / "2026" / "07" / "20" / "rollout-object.jsonl",
                [
                    {"type": "session_meta", "payload": {"id": "object", "timestamp": NOW.isoformat()}},
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

            snapshot = observe(codex_home, [skills_root], days=7, now=NOW, project_root=root)

            self.assertEqual(snapshot.coverage.parse_errors, 1)
            self.assertEqual(snapshot.coverage.skill_invocation, "partial")
            object_session = next(item for item in snapshot.sessions if item.session_id == "object")
            self.assertEqual(object_session.messages[0].text, "Still readable")

    def test_model_facing_packet_redacts_known_paths_and_secret_like_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            records = session_records("private")
            records[2]["payload"]["content"][0]["text"] = (
                f"Inspect {root / 'private.txt'} with token=sk-secretvalue123"
            )
            write_jsonl(
                codex_home / "sessions" / "2026" / "07" / "20" / "rollout-private.jsonl",
                records,
            )

            snapshot = observe(codex_home, [skills_root], days=7, now=NOW, project_root=root)
            serialized = json.dumps(build_evidence_packet(snapshot, generated_at=NOW), ensure_ascii=False)

            self.assertNotIn(str(root), serialized)
            self.assertNotIn("sk-secretvalue123", serialized)
            self.assertIn("<PATH>", serialized)
            self.assertIn("<REDACTED>", serialized)

    def test_agents_documents_are_inventoried_as_available_not_claimed_evaluated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            (root / "AGENTS.md").write_text("# Human-owned instructions\n", encoding="utf-8")

            snapshot = observe(codex_home, [skills_root], days=7, now=NOW, project_root=root)
            packet = build_evidence_packet(snapshot, generated_at=NOW)

            self.assertEqual(len(snapshot.agents_documents), 1)
            self.assertTrue(snapshot.agents_documents[0].whole_document_available)
            self.assertFalse(hasattr(snapshot.agents_documents[0], "whole_document_evaluated"))
            self.assertFalse(hasattr(snapshot.agents_documents[0], "content"))
            self.assertFalse(hasattr(snapshot.agents_documents[0], "codex_context_limit"))
            self.assertFalse(hasattr(snapshot.agents_documents[0], "decode_errors"))
            self.assertTrue(packet["portfolio"]["agents_documents"][0]["whole_document_available"])
            self.assertNotIn("Human-owned instructions", json.dumps(packet))


if __name__ == "__main__":
    unittest.main()
