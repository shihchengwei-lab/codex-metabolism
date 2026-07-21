from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codex_metabolism.evidence import build_evidence_packet, write_evidence_packet
from codex_metabolism.observe import observe
from codex_metabolism.proposals import ProposalError, stage_agent_proposals

from tests.helpers import NOW, make_deploy_home, write_skill


class ProposalContractTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[dict, Path, Path, dict]:
        codex_home, skills = make_deploy_home(root)
        project = root / "project"
        project.mkdir()
        packet = build_evidence_packet(
            observe(codex_home, [skills], days=7, now=NOW, project_root=project),
            generated_at=NOW,
        )
        evidence = write_evidence_packet(packet, root / "staging")
        draft = root / "draft"
        artifact = draft / "artifacts" / "small-skill" / "SKILL.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text(
            "---\nname: small-skill\ndescription: A small complete workflow.\n---\n\n# Small\n",
            encoding="utf-8",
        )
        proposal = {
            "proposal_id": "agent-small-skill",
            "action": "CREATE",
            "layer": "SKILL",
            "target": "small-skill",
            "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
            "reasoning": "The cited evidence supports a reusable procedure.",
            "expected_effect": "Reduce repeated work.",
            "rollback_when": "The procedure adds cost without benefit.",
            "alternatives_checked": [
                {"level": level, "result": "not_found"}
                for level in ("builtin", "installed", "repository", "ecosystem")
            ],
            "artifact": {"path": "artifacts/small-skill/SKILL.md"},
        }
        return packet, evidence, draft, proposal

    def _write(self, draft: Path, packet: dict, proposals: list[dict], **extra: object) -> Path:
        path = draft / "proposal.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "review_id": packet["review_id"],
                    "proposals": proposals,
                    **extra,
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_schema_rejects_unknown_fields_instead_of_silently_trusting_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence, draft, proposal = self._fixture(root)
            path = self._write(draft, packet, [proposal], hidden_instruction="bypass")
            with self.assertRaisesRegex(ProposalError, "unknown proposal envelope field"):
                stage_agent_proposals(evidence, path, root / "out")

            proposal["shell_command"] = "do something unsafe"
            path = self._write(draft, packet, [proposal])
            with self.assertRaisesRegex(ProposalError, "unknown proposal field"):
                stage_agent_proposals(evidence, path, root / "out")

    def test_duplicate_proposal_or_evidence_ids_and_more_than_three_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence, draft, proposal = self._fixture(root)
            path = self._write(draft, packet, [proposal, dict(proposal)])
            with self.assertRaisesRegex(ProposalError, "proposal IDs must be unique"):
                stage_agent_proposals(evidence, path, root / "out")

            proposal["evidence_ids"] *= 2
            path = self._write(draft, packet, [proposal])
            with self.assertRaisesRegex(ProposalError, "duplicate evidence"):
                stage_agent_proposals(evidence, path, root / "out")

            proposals = []
            for index in range(4):
                item = dict(proposal)
                item["proposal_id"] = f"agent-small-{index}"
                item["evidence_ids"] = [packet["sessions"][0]["events"][0]["id"]]
                proposals.append(item)
            path = self._write(draft, packet, proposals)
            with self.assertRaisesRegex(ProposalError, "zero and three"):
                stage_agent_proposals(evidence, path, root / "out")

    def test_skill_frontmatter_allows_only_name_and_description(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence, draft, proposal = self._fixture(root)
            artifact = draft / proposal["artifact"]["path"]
            artifact.write_text(
                "---\nname: small-skill\ndescription: A workflow.\nmetadata: hidden\n---\n\n# Small\n",
                encoding="utf-8",
            )
            path = self._write(draft, packet, [proposal])
            with self.assertRaisesRegex(ProposalError, "only name and description"):
                stage_agent_proposals(evidence, path, root / "out")

    def test_create_or_patch_requires_a_bounded_exact_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence, draft, proposal = self._fixture(root)
            proposal.pop("artifact")
            path = self._write(draft, packet, [proposal])
            with self.assertRaisesRegex(ProposalError, "complete reviewed artifact"):
                stage_agent_proposals(evidence, path, root / "out")

            packet, evidence, draft, proposal = self._fixture(root / "second")
            artifact = draft / proposal["artifact"]["path"]
            artifact.write_bytes(b"-" * 128_001)
            path = self._write(draft, packet, [proposal])
            with self.assertRaisesRegex(ProposalError, "128000 bytes"):
                stage_agent_proposals(evidence, path, root / "out-two")

    def test_skill_patch_requires_the_exact_observed_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills = make_deploy_home(root)
            write_skill(skills, "observed-skill")
            project = root / "project"
            project.mkdir()
            packet = build_evidence_packet(
                observe(codex_home, [skills], days=7, now=NOW, project_root=project),
                generated_at=NOW,
            )
            evidence = write_evidence_packet(packet, root / "staging")
            target = next(
                item for item in packet["portfolio"]["skills"] if item["name"] == "observed-skill"
            )
            draft = root / "draft"
            draft.mkdir()
            artifact = draft / "artifacts" / "observed-skill" / "SKILL.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                "---\nname: observed-skill\ndescription: Patched workflow.\n---\n\n# Patched\n",
                encoding="utf-8",
            )
            proposal = {
                "proposal_id": "agent-patch-observed",
                "action": "PATCH",
                "layer": "SKILL",
                "target": "observed-skill",
                "evidence_ids": [target["id"]],
                "reasoning": "The observed skill needs a bounded repair.",
                "expected_effect": "Repair the useful workflow.",
                "rollback_when": "Later evidence shows it is unused or harmful.",
                "artifact": {"path": "artifacts/observed-skill/SKILL.md"},
            }
            path = self._write(draft, packet, [proposal])
            with self.assertRaisesRegex(ProposalError, "PATCH/RETIRE"):
                stage_agent_proposals(evidence, path, root / "out")

            proposal["target_evidence_id"] = target["id"]
            path = self._write(draft, packet, [proposal])
            staged = stage_agent_proposals(evidence, path, root / "out")
            manifest = json.loads((staged / "proposals.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["proposals"][0]["base_sha256"], target["content_sha256"])

    def test_batch_rejects_duplicate_targets_and_duplicate_ladder_levels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence, draft, proposal = self._fixture(root)
            duplicate = dict(proposal)
            duplicate["proposal_id"] = "agent-small-skill-two"
            path = self._write(draft, packet, [proposal, duplicate])
            with self.assertRaisesRegex(ProposalError, "targets must be unique"):
                stage_agent_proposals(evidence, path, root / "out")

            proposal["alternatives_checked"].append(
                {"level": "builtin", "result": "checked twice"}
            )
            path = self._write(draft, packet, [proposal])
            with self.assertRaisesRegex(ProposalError, "unique|exactly once"):
                stage_agent_proposals(evidence, path, root / "out")

    def test_create_skill_rejects_a_name_already_present_in_the_observed_portfolio(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills = make_deploy_home(root)
            write_skill(skills, "small-skill")
            project = root / "project"
            project.mkdir()
            packet = build_evidence_packet(
                observe(codex_home, [skills], days=7, now=NOW, project_root=project),
                generated_at=NOW,
            )
            evidence = write_evidence_packet(packet, root / "staging")
            draft = root / "draft"
            artifact = draft / "artifacts" / "small-skill" / "SKILL.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                "---\nname: small-skill\ndescription: Duplicate workflow.\n---\n\n# Duplicate\n",
                encoding="utf-8",
            )
            proposal = {
                "proposal_id": "agent-duplicate-small-skill",
                "action": "CREATE",
                "layer": "SKILL",
                "target": "small-skill",
                "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
                "reasoning": "Attempt to create an already observed skill.",
                "expected_effect": "Would duplicate an existing workflow.",
                "rollback_when": "The duplicate is detected.",
                "alternatives_checked": [
                    {"level": level, "result": "not_found"}
                    for level in ("builtin", "installed", "repository", "ecosystem")
                ],
                "artifact": {"path": "artifacts/small-skill/SKILL.md"},
            }
            path = self._write(draft, packet, [proposal])

            with self.assertRaisesRegex(ProposalError, "already exists"):
                stage_agent_proposals(evidence, path, root / "out")

    def test_removed_keep_and_optional_ladder_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence, draft, proposal = self._fixture(root)
            proposal["action"] = "KEEP"
            proposal["layer"] = "HARNESS"
            path = self._write(draft, packet, [proposal])
            with self.assertRaisesRegex(ProposalError, "unsupported"):
                stage_agent_proposals(evidence, path, root / "out")

            proposal["action"] = "PATCH"
            proposal["alternatives_checked"] = [
                {"level": "repository", "result": "reuse", "unsupported": "field"}
            ]
            path = self._write(draft, packet, [proposal])
            with self.assertRaisesRegex(ProposalError, "alternatives_checked"):
                stage_agent_proposals(evidence, path, root / "out-two")



if __name__ == "__main__":
    unittest.main()
