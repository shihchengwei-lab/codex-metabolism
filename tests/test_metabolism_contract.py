from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_metabolism.evidence import build_evidence_packet, write_evidence_packet
from codex_metabolism.interventions import latest_interventions, load_interventions
from codex_metabolism.lifecycle import (
    LifecycleError,
    apply_agent_proposal,
    record_agent_intervention,
)
from codex_metabolism.models import InterventionReceipt
from codex_metabolism.observe import observe
from codex_metabolism.proposals import ProposalError, stage_agent_proposals

from tests.helpers import NOW, make_deploy_home


class MetabolismContractTests(unittest.TestCase):
    def _evidence(self, root: Path) -> tuple[dict, Path]:
        codex_home, skills = make_deploy_home(root)
        project = root / "project"
        project.mkdir()
        packet = build_evidence_packet(
            observe(codex_home, [skills], days=7, now=NOW, project_root=project),
            generated_at=NOW,
        )
        return packet, write_evidence_packet(packet, root / "state")

    def _stage_skill_create(self, root: Path) -> tuple[Path, str]:
        packet, evidence = self._evidence(root)
        draft = root / "draft"
        artifact = draft / "artifacts" / "approved-skill" / "SKILL.md"
        artifact.parent.mkdir(parents=True)
        artifact.write_text(
            "---\nname: approved-skill\ndescription: Use the reviewed workflow.\n"
            "---\n\n# Approved workflow\n",
            encoding="utf-8",
        )
        proposal = {
            "schema_version": 1,
            "review_id": packet["review_id"],
            "proposals": [
                {
                    "proposal_id": "create-approved-skill",
                    "action": "CREATE",
                    "layer": "SKILL",
                    "target": "approved-skill",
                    "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
                    "reasoning": "The cited sessions contain a reusable path.",
                    "expected_effect": "Reduce repeated recovery work.",
                    "rollback_when": "Later evidence shows extra cost without benefit.",
                    "alternatives_checked": [
                        {"level": level, "result": "not_found"}
                        for level in ("builtin", "installed", "repository", "ecosystem")
                    ],
                    "artifact": {"path": "artifacts/approved-skill/SKILL.md"},
                }
            ],
        }
        proposal_path = draft / "proposal.json"
        proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
        staging = stage_agent_proposals(evidence, proposal_path, root / "state")
        manifest = json.loads((staging / "proposals.json").read_text(encoding="utf-8"))
        return staging, manifest["proposals"][0]["approval_digest"]

    def test_approval_digest_binds_the_reviewed_proposal_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging, approved_digest = self._stage_skill_create(root)
            sealed = staging / "proposed-skills" / "approved-skill" / "SKILL.md"
            swapped = (
                "---\nname: swapped-skill\ndescription: This was not reviewed.\n"
                "---\n\n# Swapped\n"
            )
            sealed.write_text(swapped, encoding="utf-8")
            manifest_path = staging / "proposals.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            item = manifest["proposals"][0]
            item["target"] = "swapped-skill"
            item["artifact_sha256"] = hashlib.sha256(swapped.encode("utf-8")).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(LifecycleError, "approved digest"):
                apply_agent_proposal(
                    staging,
                    "create-approved-skill",
                    root / "skills",
                    approved_digest=approved_digest,
                )

    def test_zero_proposals_is_valid_and_keep_is_not_a_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence = self._evidence(root)
            draft = root / "draft"
            draft.mkdir()
            proposal_path = draft / "proposal.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [],
                    }
                ),
                encoding="utf-8",
            )

            staging = stage_agent_proposals(evidence, proposal_path, root / "state")
            manifest = json.loads((staging / "proposals.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "no_change")
            self.assertEqual(manifest["proposals"], [])
            self.assertIn("No changes proposed", (staging / "report.md").read_text(encoding="utf-8"))

            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [
                            {
                                "proposal_id": "keep-old-hook",
                                "action": "KEEP",
                                "layer": "HARNESS",
                                "target": "old-hook",
                                "evidence_ids": [packet["sessions"][0]["id"]],
                                "reasoning": "No change is necessary.",
                                "expected_effect": "No change.",
                                "rollback_when": "Not applicable.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProposalError, "unsupported"):
                stage_agent_proposals(evidence, proposal_path, root / "invalid")

    def test_non_skill_retirement_records_the_real_layer_action_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence = self._evidence(root)
            draft = root / "draft"
            proposed_diff = draft / "artifacts" / "disable-old-hook.patch"
            proposed_diff.parent.mkdir(parents=True)
            proposed_diff.write_text("reviewed diff that disables the hook\n", encoding="utf-8")
            proposal_path = draft / "proposal.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [
                            {
                                "proposal_id": "retire-old-hook",
                                "action": "RETIRE_CANDIDATE",
                                "layer": "HARNESS",
                                "target": "old-hook",
                                "evidence_ids": [packet["sessions"][0]["id"]],
                                "reasoning": "The repository hook duplicates a built-in check.",
                                "expected_effect": "Remove redundant maintenance.",
                                "rollback_when": "The built-in check does not cover the repository.",
                                "artifact": {"path": "artifacts/disable-old-hook.patch"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            staging = stage_agent_proposals(evidence, proposal_path, root / "state")
            manifest = json.loads((staging / "proposals.json").read_text(encoding="utf-8"))
            approved_digest = manifest["proposals"][0]["approval_digest"]
            implementation_evidence = root / "project" / "retirement.diff"
            implementation_evidence.write_text(
                "actual git diff and verification output\n",
                encoding="utf-8",
            )

            durable = record_agent_intervention(
                staging,
                "retire-old-hook",
                implementation_evidence,
                approved_digest=approved_digest,
            )
            implementation_evidence.unlink()
            receipt = load_interventions(staging / "interventions.jsonl")[-1]

            self.assertTrue(durable.is_file())
            self.assertTrue(durable.is_relative_to(staging.resolve()))
            self.assertEqual(receipt.target_kind, "HARNESS")
            self.assertEqual(receipt.status, "RETIRED")
            self.assertEqual(receipt.metadata["action"], "RETIRE_CANDIDATE")
            self.assertEqual(receipt.metadata["execution_mode"], "existing_mechanism")
            self.assertRegex(receipt.metadata["implementation_evidence_sha256"], r"^[0-9a-f]{64}$")

    def test_rule_harness_and_tool_keep_their_layer_but_use_existing_mechanisms(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence = self._evidence(root)
            draft = root / "draft"
            artifacts = draft / "artifacts"
            artifacts.mkdir(parents=True)
            proposals = []
            cases = [
                ("create-bounded-rule", "CREATE", "RULE", "bounded-rule", "ACTIVE"),
                ("patch-installed-tool", "PATCH", "TOOL", "installed-tool", "ACTIVE"),
                ("retire-old-hook", "RETIRE_CANDIDATE", "HARNESS", "old-hook", "RETIRED"),
            ]
            for proposal_id, action, layer, target, _ in cases:
                artifact = artifacts / f"{proposal_id}.patch"
                artifact.write_text(f"reviewed {layer} {action}\n", encoding="utf-8")
                proposal = {
                    "proposal_id": proposal_id,
                    "action": action,
                    "layer": layer,
                    "target": target,
                    "evidence_ids": [packet["sessions"][0]["id"]],
                    "reasoning": f"Evidence supports {action} for this {layer}.",
                    "expected_effect": "Reduce recurring collaboration cost.",
                    "rollback_when": "Later evidence contradicts the change.",
                    "artifact": {"path": f"artifacts/{proposal_id}.patch"},
                }
                if action == "CREATE":
                    proposal["alternatives_checked"] = [
                        {"level": level, "result": "not_found"}
                        for level in ("builtin", "installed", "repository", "ecosystem")
                    ]
                proposals.append(proposal)
            proposal_path = draft / "proposal.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": proposals,
                    }
                ),
                encoding="utf-8",
            )
            staging = stage_agent_proposals(evidence, proposal_path, root / "state")
            manifest = json.loads((staging / "proposals.json").read_text(encoding="utf-8"))
            digests = {
                item["proposal_id"]: item["approval_digest"]
                for item in manifest["proposals"]
            }

            for proposal_id, _, layer, _, expected_status in cases:
                implementation = root / "project" / f"{proposal_id}.evidence"
                implementation.write_text(
                    f"verified through existing mechanism for {layer}\n",
                    encoding="utf-8",
                )
                record_agent_intervention(
                    staging,
                    proposal_id,
                    implementation,
                    approved_digest=digests[proposal_id],
                )

            receipts = load_interventions(staging / "interventions.jsonl")
            self.assertEqual(
                [(item.target_kind, item.status) for item in receipts],
                [(case[2], case[4]) for case in cases],
            )
            self.assertTrue(
                all(item.metadata["execution_mode"] == "existing_mechanism" for item in receipts)
            )

    def test_target_history_and_rollback_contract_return_to_the_next_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills = make_deploy_home(root)
            project = root / "project"
            project.mkdir()
            first = InterventionReceipt(
                intervention_id="legacy-create-id",
                proposal_id="create-preflight",
                target_kind="HARNESS",
                target="preflight",
                mechanism="existing",
                scope="project",
                status="ACTIVE",
                activated_at="2026-07-18T08:00:00+00:00",
                artifact_path="first.patch",
                reasoning="Repeated sessions skipped preflight.",
                expected_effect="Preflight runs before deployment.",
                rollback_when="Valid deployments are blocked.",
                evidence_ids=["evidence-original"],
                metadata={
                    "action": "CREATE",
                    "review_id": "review-create",
                    "execution_mode": "existing_mechanism",
                    "approved_artifact_sha256": "a" * 64,
                    "implementation_evidence_sha256": "b" * 64,
                },
            )
            second = InterventionReceipt(
                intervention_id="legacy-retire-id",
                proposal_id="retire-preflight",
                target_kind="HARNESS",
                target="preflight",
                mechanism="existing",
                scope="project",
                status="RETIRED",
                activated_at="2026-07-20T08:00:00+00:00",
                artifact_path="retire.patch",
                reasoning="The platform now provides the same preflight.",
                expected_effect="Remove duplicate maintenance.",
                rollback_when="The platform check misses repository-specific failures.",
                evidence_ids=["evidence-retirement"],
                metadata={
                    "action": "RETIRE_CANDIDATE",
                    "review_id": "review-retire",
                    "execution_mode": "existing_mechanism",
                    "approved_artifact_sha256": "c" * 64,
                    "implementation_evidence_sha256": "d" * 64,
                },
            )

            self.assertEqual(latest_interventions([first, second]), [second])
            packet = build_evidence_packet(
                observe(
                    codex_home,
                    [skills],
                    days=7,
                    now=NOW,
                    project_root=project,
                    intervention_records=[first, second],
                ),
                generated_at=NOW,
            )
            item = packet["portfolio"]["interventions"][0]

            self.assertEqual(item["reasoning"], second.reasoning)
            self.assertEqual(item["expected_effect"], second.expected_effect)
            self.assertEqual(item["rollback_when"], second.rollback_when)
            self.assertEqual(item["evidence_ids"], second.evidence_ids)
            self.assertEqual(item["review_id"], "review-retire")
            self.assertEqual(item["execution_mode"], "existing_mechanism")
            self.assertEqual(item["approved_artifact_sha256"], "c" * 64)
            self.assertEqual(item["implementation_evidence_sha256"], "d" * 64)
            self.assertEqual([entry["status"] for entry in item["history"]], ["ACTIVE", "RETIRED"])
            self.assertEqual(item["history"][0]["proposal_id"], "create-preflight")
            self.assertEqual(item["history"][0]["review_id"], "review-create")


if __name__ == "__main__":
    unittest.main()
