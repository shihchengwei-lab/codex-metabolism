from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from codex_metabolism.decide import decide
from codex_metabolism.lifecycle import LifecycleError, apply_decision, rollback_intervention
from codex_metabolism.observe import observe
from codex_metabolism.stage import stage_review

from tests.helpers import NOW, make_deploy_home, session_records, write_jsonl


class AgentsReviewTests(unittest.TestCase):
    def test_invalid_utf8_is_reported_as_incomplete_and_disables_managed_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            agents = root / "AGENTS.md"
            agents.write_bytes(
                b"# Guidance\n\xff\n"
                b"<!-- codex-metabolism:managed-start -->\n"
                b"- Duplicate.\n- Duplicate.\n"
                b"<!-- codex-metabolism:managed-end -->\n"
            )

            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
            )
            document = next(item for item in snapshot.agents_documents if item.scope == "project")
            review = next(
                item
                for item in decide(snapshot, now=NOW)
                if item.mechanism == "agents_review" and item.metadata["source_path"] == str(agents)
            )

            self.assertFalse(document.whole_document_evaluated)
            self.assertEqual(document.decode_errors, 1)
            self.assertFalse(review.metadata["whole_document_evaluated"])
            self.assertFalse(review.metadata["managed_region"]["applyable"])

    def test_entire_user_project_and_nested_agents_documents_are_inventoried_and_reviewed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            user_agents = codex_home / "AGENTS.md"
            project_agents = root / "AGENTS.md"
            nested_agents = root / "src" / "AGENTS.md"
            user_agents.write_text("# Personal defaults\n\n- Keep answers concise.\n", encoding="utf-8")
            project_text = "# Project guidance\n\n" + "\n".join(
                [
                    "- Always run tests.",
                    "- Always run tests.",
                    *[f"- Project rule {index}." for index in range(1, 11)],
                ]
            ) + "\n"
            project_agents.write_text(project_text, encoding="utf-8")
            nested_agents.parent.mkdir(parents=True)
            nested_agents.write_text("# Source rules\n\n- Preserve public APIs.\n", encoding="utf-8")
            before = hashlib.sha256(project_agents.read_bytes()).hexdigest()

            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
            )

            self.assertEqual({document.scope for document in snapshot.agents_documents}, {"user", "project", "nested"})
            project_document = next(
                document for document in snapshot.agents_documents if Path(document.path) == project_agents
            )
            self.assertTrue(project_document.whole_document_evaluated)
            self.assertEqual(project_document.byte_count, len(project_agents.read_bytes()))
            self.assertEqual(project_document.content_sha256, before)

            decisions = decide(snapshot, now=NOW)
            review = next(
                decision
                for decision in decisions
                if decision.target_kind == "RULE" and decision.metadata.get("source_path") == str(project_agents)
            )
            self.assertEqual(review.decision, "PATCH")
            self.assertEqual(review.mechanism, "agents_review")
            self.assertEqual(review.metadata["rule_budget"], 10)
            self.assertTrue(review.metadata["whole_document_evaluated"])
            self.assertLessEqual(len(review.metadata["recommendations"]), 10)
            self.assertTrue(
                any(item["action"] in {"MERGE", "CONSOLIDATE"} for item in review.metadata["recommendations"])
            )

            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)
            self.assertTrue((staging / "proposed-rules" / review.id / "review.md").is_file())
            self.assertEqual(hashlib.sha256(project_agents.read_bytes()).hexdigest(), before)
            with self.assertRaises(LifecycleError):
                apply_decision(staging, review.id, project_root=root, skill_root=skills_root)
            self.assertEqual(hashlib.sha256(project_agents.read_bytes()).hexdigest(), before)

    def test_existing_agents_rule_that_failed_is_suggested_for_supersession_not_silently_edited(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            agents = root / "AGENTS.md"
            agents.write_text(
                "# Deployment\n\n- Always run preflight before deploy production.\n",
                encoding="utf-8",
            )
            before = agents.read_text(encoding="utf-8")

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

            self.assertTrue(any(item.target_kind == "HARNESS" for item in decisions))
            rule_review = next(item for item in decisions if item.target_kind == "RULE")
            self.assertTrue(
                any(item["action"] == "SUPERSEDE" for item in rule_review.metadata["recommendations"])
            )
            self.assertEqual(agents.read_text(encoding="utf-8"), before)

    def test_approved_patch_rewrites_only_an_existing_managed_region(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            agents = root / "AGENTS.md"
            start = "<!-- codex-metabolism:managed-start -->"
            end = "<!-- codex-metabolism:managed-end -->"
            original = (
                "# Human-owned project guidance\r\n\r\n"
                "Keep this paragraph byte-for-byte.\r\n\r\n"
                f"{start}\r\n"
                "- Always run preflight before deploy production.\r\n"
                "- Always run preflight before deploy production.\r\n"
                f"{end}\r\n\r\n"
                "## Human-owned tail\r\n\r\n"
                "- Preserve public APIs.\r\n"
            ).encode("utf-8")
            agents.write_bytes(original)
            start_at = original.index(start.encode("ascii")) + len(start)
            end_at = original.index(end.encode("ascii"))
            original_prefix = original[:start_at]
            original_suffix = original[end_at:]

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
            review = next(
                item
                for item in decisions
                if item.mechanism == "agents_review"
                and item.metadata.get("source_path") == str(agents)
            )
            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)

            self.assertTrue(review.metadata["managed_region"]["applyable"])
            self.assertTrue(
                (staging / "proposed-rules" / review.id / "managed-block.proposed.txt").is_file()
            )
            self.assertTrue((staging / "proposed-rules" / review.id / "changes.diff").is_file())

            apply_decision(
                staging,
                review.id,
                project_root=root,
                skill_root=skills_root,
                changed_at=NOW,
            )

            updated = agents.read_bytes()
            updated_start = updated.index(start.encode("ascii")) + len(start)
            updated_end = updated.index(end.encode("ascii"))
            self.assertEqual(updated[:updated_start], original_prefix)
            self.assertEqual(updated[updated_end:], original_suffix)
            self.assertNotIn(b"Always run preflight before deploy production", updated)

            archived = rollback_intervention(
                staging,
                review.id,
                project_root=root,
                skill_root=skills_root,
            )
            self.assertEqual(agents.read_bytes(), original)
            self.assertTrue(archived.is_file())

    def test_repeated_rule_can_be_staged_into_managed_region_but_not_human_owned_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            agents = root / "AGENTS.md"
            human_prefix = "# Human-owned\n\nDo not rewrite this paragraph.\n\n"
            human_suffix = "\n## Human tail\n\nKeep this too.\n"
            agents.write_text(
                human_prefix
                + "<!-- codex-metabolism:managed-start -->\n"
                + "- Keep generated output reproducible.\n"
                + "<!-- codex-metabolism:managed-end -->"
                + human_suffix,
                encoding="utf-8",
            )
            for index in (1, 2):
                write_jsonl(
                    codex_home / "sessions" / "2026" / "07" / "20" / f"rollout-{index}.jsonl",
                    session_records(
                        f"rule-{index}",
                        failed_command="edit generated file",
                        prerequisite="use generator",
                        correction="No, never modify generated files directly; use the generator.",
                    ),
                )

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
            suggestion = next(
                item for item in decisions if item.mechanism == "agents_recommendation"
            )
            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)

            self.assertTrue(suggestion.metadata["managed_region"]["applyable"])
            apply_decision(
                staging,
                suggestion.id,
                project_root=root,
                skill_root=skills_root,
                changed_at=NOW,
            )

            updated = agents.read_text(encoding="utf-8")
            self.assertTrue(updated.startswith(human_prefix))
            self.assertTrue(updated.endswith(human_suffix))
            self.assertIn("never modify generated files directly", updated)

    def test_rule_like_repeated_correction_creates_a_bounded_suggestion_without_creating_agents_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            for index in (1, 2):
                write_jsonl(
                    codex_home / "sessions" / "2026" / "07" / "20" / f"rollout-{index}.jsonl",
                    session_records(
                        f"rule-{index}",
                        failed_command="edit generated file",
                        prerequisite="use generator",
                        correction="No, never modify generated files directly; use the generator.",
                    ),
                )

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
            suggestion = next(
                item
                for item in decisions
                if item.target_kind == "RULE" and item.mechanism == "agents_recommendation"
            )

            self.assertEqual(suggestion.decision, "CREATE")
            self.assertLessEqual(len(suggestion.metadata["recommendations"]), 3)
            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)
            self.assertTrue((staging / "proposed-rules" / suggestion.id / "review.md").is_file())
            self.assertFalse((root / "AGENTS.md").exists())


if __name__ == "__main__":
    unittest.main()
