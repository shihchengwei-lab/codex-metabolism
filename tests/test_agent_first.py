from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from codex_metabolism.cli import _parser
from codex_metabolism.evidence import build_evidence_packet, write_evidence_packet
from codex_metabolism.interventions import load_interventions, write_interventions
from codex_metabolism.lifecycle import (
    LifecycleError,
    apply_agent_proposal,
    record_agent_intervention,
    rollback_agent_intervention,
    restore_retired_skill,
)
from codex_metabolism.models import InterventionReceipt
from codex_metabolism.observe import observe
from codex_metabolism.proposals import ProposalError, stage_agent_proposals

from tests.helpers import NOW, make_deploy_home, write_skill


ROOT = Path(__file__).resolve().parents[1]


class AgentFirstEvidenceTests(unittest.TestCase):
    def test_receipt_ledger_uses_intervention_id_but_reads_the_legacy_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ledger = Path(temp) / "interventions.jsonl"
            receipt = InterventionReceipt(
                intervention_id="agent-one",
                target_kind="SKILL",
                target="small-skill",
                mechanism="agent_authored_skill",
                scope="user",
                status="ACTIVE",
                activated_at=NOW.isoformat(),
                artifact_path="small-skill/SKILL.md",
            )
            write_interventions(ledger, [receipt])
            serialized = ledger.read_text(encoding="utf-8")
            self.assertIn('"intervention_id": "agent-one"', serialized)
            self.assertNotIn("decision_id", serialized)

            ledger.write_text(
                serialized.replace('"intervention_id"', '"decision_id"'),
                encoding="utf-8",
            )
            self.assertEqual(load_interventions(ledger)[0].intervention_id, "agent-one")

    def _packet(self, root: Path) -> tuple[dict, Path]:
        codex_home, skill_root = make_deploy_home(root)
        project = root / "project"
        project.mkdir()
        observation = observe(
            codex_home,
            [skill_root],
            days=7,
            now=NOW,
            project_root=project,
        )
        packet = build_evidence_packet(observation, generated_at=NOW)
        path = write_evidence_packet(packet, root / "review")
        return packet, path

    def _approval_digest(self, staging: Path, proposal_id: str) -> str:
        manifest = json.loads((staging / "proposals.json").read_text(encoding="utf-8"))
        return next(
            item["approval_digest"]
            for item in manifest["proposals"]
            if item["proposal_id"] == proposal_id
        )

    def test_evidence_packet_prepares_context_without_making_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, path = self._packet(root)

            self.assertEqual(packet["schema_version"], 2)
            self.assertEqual(packet["authority"], "evidence_only")
            self.assertTrue(packet["review_id"].startswith("review-"))
            self.assertGreaterEqual(len(packet["sessions"]), 2)
            self.assertEqual({item["kind"] for item in packet["sessions"]}, {"session_capsule"})
            self.assertEqual(
                len({item["id"] for item in packet["sessions"]}),
                len(packet["sessions"]),
            )
            event_kinds = {
                event["kind"]
                for session in packet["sessions"]
                for event in session["events"]
            }
            self.assertIn("user_message", event_kinds)
            self.assertIn("tool_execution", event_kinds)
            self.assertEqual(packet["constraints"]["max_proposals"], 3)
            self.assertTrue(packet["constraints"]["human_review_required"])

            serialized = json.dumps(packet, ensure_ascii=False)
            self.assertNotIn('"decision"', serialized)
            self.assertNotIn('"suggestion"', serialized)
            self.assertNotIn('"friction"', serialized)
            self.assertNotIn('"workflow_candidate"', serialized)
            self.assertNotIn('"correction"', serialized)
            self.assertNotIn("session-one", serialized)
            self.assertNotIn(str(root), serialized)
            self.assertEqual(path, root / "review" / "evidence.json")

    def test_agent_authored_skill_is_sealed_exactly_and_must_cite_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence_path = self._packet(root)
            draft = root / "draft"
            artifact = draft / "artifacts" / "deploy-safely" / "SKILL.md"
            artifact.parent.mkdir(parents=True)
            authored = (
                "---\n"
                "name: deploy-safely\n"
                "description: Verify the target and run repository preflight before deployment.\n"
                "---\n\n"
                "# Deploy safely\n\n"
                "1. Resolve the target environment.\n"
                "2. Run the repository preflight.\n"
                "3. Deploy only after verification succeeds.\n"
            )
            artifact.write_text(authored, encoding="utf-8")
            proposal_path = draft / "proposal.json"
            proposal = {
                "schema_version": 1,
                "review_id": packet["review_id"],
                "proposals": [
                    {
                        "proposal_id": "agent-deploy-safely",
                        "action": "CREATE",
                        "layer": "SKILL",
                        "target": "deploy-safely",
                        "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
                        "reasoning": "The same deployment correction appears in recent evidence.",
                        "expected_effect": "Reduce repeated deployment recovery work.",
                        "rollback_when": "The workflow adds cost without preventing the friction.",
                        "alternatives_checked": [
                            {"level": "builtin", "result": "not_found"},
                            {"level": "installed", "result": "not_found"},
                            {"level": "repository", "result": "not_found"},
                            {"level": "ecosystem", "result": "not_found"},
                        ],
                        "artifact": {"path": "artifacts/deploy-safely/SKILL.md"},
                    }
                ],
            }
            proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

            staged = stage_agent_proposals(
                evidence_path,
                proposal_path,
                root / "staging",
            )

            sealed = staged / "proposed-skills" / "deploy-safely" / "SKILL.md"
            self.assertEqual(sealed.read_text(encoding="utf-8"), authored)
            manifest = json.loads((staged / "proposals.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["source"], "codex_agent")
            self.assertEqual(manifest["proposals"][0]["status"], "awaiting_human_approval")
            self.assertRegex(manifest["proposals"][0]["artifact_sha256"], r"^[0-9a-f]{64}$")

            proposal["proposals"][0]["evidence_ids"] = ["evidence-invented"]
            proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
            with self.assertRaisesRegex(ProposalError, "unknown evidence"):
                stage_agent_proposals(evidence_path, proposal_path, root / "invalid")

    def test_stage_rejects_missing_human_gate_and_artifact_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence_path = self._packet(root)
            draft = root / "draft"
            draft.mkdir()
            proposal_path = draft / "proposal.json"
            base = {
                "proposal_id": "agent-unsafe",
                "action": "CREATE",
                "layer": "SKILL",
                "target": "unsafe",
                "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
                "reasoning": "Evidence-backed reason.",
                "expected_effect": "Expected effect.",
                "rollback_when": "Rollback condition.",
                "alternatives_checked": [
                    {"level": level, "result": "not_found"}
                    for level in ("builtin", "installed", "repository", "ecosystem")
                ],
                "artifact": {"path": "../outside/SKILL.md"},
            }
            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [base],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProposalError, "inside the draft directory"):
                stage_agent_proposals(evidence_path, proposal_path, root / "staging")

    def test_approved_skill_create_writes_receipt_and_rolls_back_to_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence_path = self._packet(root)
            draft = root / "draft"
            artifact = draft / "artifacts" / "deploy-safely" / "SKILL.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                "---\nname: deploy-safely\ndescription: Run a verified deployment workflow.\n"
                "---\n\n# Deploy safely\n\n1. Verify.\n2. Deploy.\n",
                encoding="utf-8",
            )
            proposal_path = draft / "proposal.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [
                            {
                                "proposal_id": "agent-deploy-safely",
                                "action": "CREATE",
                                "layer": "SKILL",
                                "target": "deploy-safely",
                                "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
                                "reasoning": "A reusable sequence is visible in the cited session.",
                                "expected_effect": "Reduce repeated deployment setup.",
                                "rollback_when": "The workflow adds cost without preventing errors.",
                                "alternatives_checked": [
                                    {"level": level, "result": "not_found"}
                                    for level in ("builtin", "installed", "repository", "ecosystem")
                                ],
                                "artifact": {"path": "artifacts/deploy-safely/SKILL.md"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            staging = stage_agent_proposals(evidence_path, proposal_path, root / "staging")
            skills = root / "skills"

            with self.assertRaisesRegex(LifecycleError, "approval"):
                apply_agent_proposal(
                    staging,
                    "agent-deploy-safely",
                    skills,
                    approved_digest=None,
                )

            apply_agent_proposal(
                staging,
                "agent-deploy-safely",
                skills,
                approved_digest=self._approval_digest(staging, "agent-deploy-safely"),
            )
            live = skills / "deploy-safely" / "SKILL.md"
            self.assertTrue(live.is_file())
            receipts = load_interventions(staging / "interventions.jsonl")
            self.assertEqual(receipts[-1].status, "ACTIVE")
            self.assertEqual(receipts[-1].metadata["source"], "codex_agent")

            with patch(
                "codex_metabolism.lifecycle.append_intervention",
                side_effect=OSError("ledger unavailable"),
            ):
                with self.assertRaisesRegex(OSError, "ledger unavailable"):
                    rollback_agent_intervention(
                        staging,
                        "agent-deploy-safely",
                        skills,
                        human_approved=True,
                    )
            self.assertTrue(live.is_file())
            self.assertFalse(
                (staging / "archive" / "agent-deploy-safely" / "deploy-safely").exists()
            )

            with self.assertRaisesRegex(LifecycleError, "explicit human approval"):
                rollback_agent_intervention(
                    staging,
                    "agent-deploy-safely",
                    skills,
                    human_approved=False,
                )
            rollback_agent_intervention(
                staging,
                "agent-deploy-safely",
                skills,
                human_approved=True,
            )
            self.assertFalse(live.exists())
            archived = staging / "archive" / "agent-deploy-safely" / "deploy-safely" / "SKILL.md"
            self.assertTrue(archived.is_file())
            self.assertEqual(
                load_interventions(staging / "interventions.jsonl")[-1].status,
                "ROLLED_BACK",
            )

    def test_apply_rejects_an_artifact_changed_after_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence_path = self._packet(root)
            draft = root / "draft"
            artifact = draft / "artifacts" / "small-skill" / "SKILL.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                "---\nname: small-skill\ndescription: A complete small workflow.\n---\n\n# Small\n",
                encoding="utf-8",
            )
            proposal_path = draft / "proposal.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [
                            {
                                "proposal_id": "agent-small-skill",
                                "action": "CREATE",
                                "layer": "SKILL",
                                "target": "small-skill",
                                "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
                                "reasoning": "Cited evidence supports a reusable procedure.",
                                "expected_effect": "Reuse the procedure.",
                                "rollback_when": "It does not help.",
                                "alternatives_checked": [
                                    {"level": level, "result": "not_found"}
                                    for level in ("builtin", "installed", "repository", "ecosystem")
                                ],
                                "artifact": {"path": "artifacts/small-skill/SKILL.md"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            staging = stage_agent_proposals(evidence_path, proposal_path, root / "staging")
            approved_digest = self._approval_digest(staging, "agent-small-skill")
            sealed = staging / "proposed-skills" / "small-skill" / "SKILL.md"
            sealed.write_text(sealed.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

            with self.assertRaisesRegex(LifecycleError, "changed after staging"):
                apply_agent_proposal(
                    staging,
                    "agent-small-skill",
                    root / "skills",
                    approved_digest=approved_digest,
                )

    def test_agent_authored_patch_is_hash_gated_and_rolls_back_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills = make_deploy_home(root)
            live = write_skill(skills, "existing-skill", description="Original workflow")
            original = live.read_bytes()
            project = root / "project"
            project.mkdir()
            snapshot = observe(codex_home, [skills], days=7, now=NOW, project_root=project)
            packet = build_evidence_packet(snapshot, generated_at=NOW)
            evidence_path = write_evidence_packet(packet, root / "staging")
            target_evidence = next(
                item for item in packet["portfolio"]["skills"] if item["name"] == "existing-skill"
            )
            draft = root / "draft"
            artifact = draft / "artifacts" / "existing-skill" / "SKILL.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                "---\nname: existing-skill\ndescription: Original workflow with verification.\n"
                "---\n\n# Existing\n\n1. Run the workflow.\n2. Verify its result.\n",
                encoding="utf-8",
            )
            proposal_path = draft / "proposal.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [
                            {
                                "proposal_id": "agent-patch-existing",
                                "action": "PATCH",
                                "layer": "SKILL",
                                "target": "existing-skill",
                                "target_evidence_id": target_evidence["id"],
                                "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
                                "reasoning": "The existing workflow omits observed verification.",
                                "expected_effect": "Make verification part of future use.",
                                "rollback_when": "The added verification is irrelevant or harmful.",
                                "artifact": {"path": "artifacts/existing-skill/SKILL.md"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            staging = stage_agent_proposals(evidence_path, proposal_path, root / "staging")
            manifest = json.loads((staging / "proposals.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["proposals"][0]["base_sha256"], target_evidence["content_sha256"])
            approved_digest = self._approval_digest(staging, "agent-patch-existing")

            live.write_text(live.read_text(encoding="utf-8") + "human edit\n", encoding="utf-8")
            with self.assertRaisesRegex(LifecycleError, "changed after observation"):
                apply_agent_proposal(
                    staging,
                    "agent-patch-existing",
                    skills,
                    approved_digest=approved_digest,
                )

            live.write_bytes(original)
            apply_agent_proposal(
                staging,
                "agent-patch-existing",
                skills,
                approved_digest=approved_digest,
            )
            self.assertNotEqual(live.read_bytes(), original)
            patched = live.read_bytes()
            with patch(
                "codex_metabolism.lifecycle.append_intervention",
                side_effect=OSError("ledger unavailable"),
            ):
                with self.assertRaisesRegex(OSError, "ledger unavailable"):
                    rollback_agent_intervention(
                        staging,
                        "agent-patch-existing",
                        skills,
                        human_approved=True,
                    )
            self.assertEqual(live.read_bytes(), patched)
            rollback_agent_intervention(
                staging,
                "agent-patch-existing",
                skills,
                human_approved=True,
            )
            self.assertEqual(live.read_bytes(), original)

    def test_retirement_requires_observed_skill_and_remains_restorable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills = make_deploy_home(root)
            live = write_skill(skills, "idle-skill", description="Candidate for human-reviewed retirement")
            project = root / "project"
            project.mkdir()
            snapshot = observe(codex_home, [skills], days=7, now=NOW, project_root=project)
            packet = build_evidence_packet(snapshot, generated_at=NOW)
            evidence_path = write_evidence_packet(packet, root / "staging")
            target_evidence = next(
                item for item in packet["portfolio"]["skills"] if item["name"] == "idle-skill"
            )
            draft = root / "draft"
            draft.mkdir()
            proposal_path = draft / "proposal.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [
                            {
                                "proposal_id": "agent-retire-idle",
                                "action": "RETIRE_CANDIDATE",
                                "layer": "SKILL",
                                "target": "idle-skill",
                                "target_evidence_id": target_evidence["id"],
                                "evidence_ids": [target_evidence["id"]],
                                "reasoning": "The Agent found enough portfolio evidence to ask for retirement review.",
                                "expected_effect": "Reduce unused collaboration surface.",
                                "rollback_when": "A future task needs the archived workflow.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            staging = stage_agent_proposals(evidence_path, proposal_path, root / "staging")
            approved_digest = self._approval_digest(staging, "agent-retire-idle")

            archived = apply_agent_proposal(
                staging,
                "agent-retire-idle",
                skills,
                approved_digest=approved_digest,
            )
            self.assertFalse(live.exists())
            self.assertTrue(archived.is_file())
            with patch(
                "codex_metabolism.lifecycle.append_intervention",
                side_effect=OSError("ledger unavailable"),
            ):
                with self.assertRaisesRegex(OSError, "ledger unavailable"):
                    restore_retired_skill(
                        staging,
                        "agent-retire-idle",
                        skills,
                        human_approved=True,
                    )
            self.assertFalse(live.exists())
            self.assertTrue(archived.is_file())
            restored = restore_retired_skill(
                staging,
                "agent-retire-idle",
                skills,
                human_approved=True,
            )
            self.assertTrue(restored.is_file())

    def test_non_skill_fix_is_implemented_by_codex_then_only_recorded_by_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet, evidence_path = self._packet(root)
            draft = root / "draft"
            plan = draft / "artifacts" / "preflight.patch"
            plan.parent.mkdir(parents=True)
            plan.write_text("Agent-authored repository patch for human review.\n", encoding="utf-8")
            proposal_path = draft / "proposal.json"
            proposal_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [
                            {
                                "proposal_id": "agent-preflight-harness",
                                "action": "PATCH",
                                "layer": "HARNESS",
                                "target": "preflight-harness",
                                "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
                                "reasoning": "A mechanical repository check is smaller than a durable rule.",
                                "expected_effect": "Prevent the repeated unsafe operation.",
                                "rollback_when": "The guard blocks valid work or does not prevent the failure.",
                                "artifact": {"path": "artifacts/preflight.patch"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            staging = stage_agent_proposals(evidence_path, proposal_path, root / "staging")
            approved_digest = self._approval_digest(staging, "agent-preflight-harness")
            implemented = root / "project" / "preflight.py"
            implemented.parent.mkdir(exist_ok=True)
            implemented.write_text("print('verified')\n", encoding="utf-8")

            with self.assertRaisesRegex(LifecycleError, "approval"):
                record_agent_intervention(
                    staging,
                    "agent-preflight-harness",
                    implemented,
                    approved_digest=None,
                )
            recorded = record_agent_intervention(
                staging,
                "agent-preflight-harness",
                implemented,
                approved_digest=approved_digest,
            )

            self.assertNotEqual(recorded, implemented.resolve())
            self.assertEqual(recorded.read_bytes(), implemented.read_bytes())
            self.assertTrue(recorded.is_relative_to(staging.resolve()))
            receipt = load_interventions(staging / "interventions.jsonl")[-1]
            self.assertEqual(receipt.target_kind, "HARNESS")
            self.assertEqual(receipt.status, "ACTIVE")
            self.assertEqual(receipt.metadata["source"], "codex_agent")


class AgentFirstCliTests(unittest.TestCase):
    def test_cli_exposes_agent_first_surface_without_nested_advisor_or_scheduler(self) -> None:
        output = io.StringIO()
        with self.assertRaises(SystemExit), redirect_stdout(output):
            _parser().parse_args(["--help"])
        help_text = output.getvalue()
        for command in ("observe", "stage", "apply", "reject", "rollback"):
            self.assertIn(command, help_text)
        for removed in ("advisor", "enable", "scheduled-review", "search-oss"):
            self.assertNotIn(removed, help_text)


class AgentFirstSkillContractTests(unittest.TestCase):
    def test_skill_is_the_product_surface_and_runtime_is_only_the_substrate(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn("name: codex-metabolism", skill)
        self.assertIn("Codex owns semantic interpretation and artifact design", skill)
        self.assertIn("runtime owns evidence boundaries, persistence, and safe mutation", skill)
        self.assertIn("codex-metabolism observe", skill)
        self.assertIn("codex-metabolism stage", skill)
        self.assertIn("Search existing capabilities before proposing anything new", skill)
        self.assertIn("Show the exact diff and wait for explicit human approval", skill)
        self.assertNotIn("--advisor", skill)
        self.assertIn('$codex-metabolism', metadata)


if __name__ == "__main__":
    unittest.main()
