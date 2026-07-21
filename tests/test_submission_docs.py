from __future__ import annotations

import unittest
from pathlib import Path

import codex_metabolism


ROOT = Path(__file__).resolve().parents[1]


class PublicSurfaceContractTests(unittest.TestCase):
    def test_readme_explains_the_agent_first_boundary_and_current_entrypoint(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Agent thinks; the runtime remembers and constrains", readme)
        self.assertIn("Codex owns semantic interpretation and artifact design", readme)
        self.assertIn("runtime owns evidence boundaries, persistence, and safe mutation", readme)
        self.assertIn("$codex-metabolism", readme)
        self.assertIn("python examples/run_agent_first_demo.py", readme)
        self.assertIn("python examples/run_real_session_evaluation.py", readme)
        self.assertIn("real Codex sessions", readme)
        self.assertIn("weekly usage reset", readme)
        self.assertIn("native Scheduled task", readme)
        self.assertIn("zero to three", readme)
        self.assertIn("approval digest", readme)
        self.assertIn("existing Git/repository mechanism", readme)
        for stale in (
            "--advisor",
            "run_closed_loop_demo.py",
            "run_detector_evaluation.py",
            "codex-metabolism enable",
            "CREATE HARNESS + PATCH RULE",
            "precision `1.000`",
        ):
            self.assertNotIn(stale, readme)

    def test_chinese_readme_has_the_same_architecture_without_mojibake(self) -> None:
        readme = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")

        self.assertIn("Agent 負責思考；runtime 負責記住與約束", readme)
        self.assertIn("Codex 負責語義理解與產物設計", readme)
        self.assertIn("python examples/run_agent_first_demo.py", readme)
        self.assertIn("零到三個", readme)
        self.assertIn("approval digest", readme)
        self.assertNotIn("�", readme)
        self.assertNotIn("--advisor", readme)

    def test_distribution_and_ci_ship_only_the_agent_first_surface(self) -> None:
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        for packaged in (
            "SKILL.md",
            "agents/openai.yaml",
            "references/*.md",
            "examples/run_real_session_evaluation.py",
            "examples/anonymized-real-session-evaluation.json",
        ):
            self.assertIn(packaged, manifest)
        self.assertIn('version = "0.2.1"', project)
        self.assertEqual(codex_metabolism.__version__, "0.2.1")
        self.assertIn("run_agent_first_demo.py", workflow)
        self.assertIn("run_real_session_evaluation.py", workflow)
        for stale in (
            "run_closed_loop_demo.py",
            "run_friction_cases_demo.py",
            "run_messy_evidence_demo.py",
            "run_detector_evaluation.py",
        ):
            self.assertNotIn(stale, workflow)

    def test_current_docs_do_not_present_removed_v01_detectors_as_the_product(self) -> None:
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")
        video = (ROOT / "docs" / "DEMO_VIDEO.md").read_text(encoding="utf-8")

        for document in (devpost, video):
            self.assertIn("Agent-first", document)
            self.assertNotIn("--advisor", document)
            self.assertNotIn("run_closed_loop_demo.py", document)
            self.assertNotIn("27 synthetic", document)
        self.assertFalse((ROOT / "docs" / "EVALUATION.md").exists())
        self.assertFalse((ROOT / "docs" / "REAL_SESSION_REVIEW.md").exists())
        self.assertTrue((ROOT / "docs" / "assets" / "agent-first-loop.svg").is_file())

        schema = (ROOT / "references" / "proposal-schema.md").read_text(encoding="utf-8")
        self.assertIn("zero to three proposals", schema)
        self.assertNotIn("CREATE | PATCH | KEEP", schema)
        self.assertNotIn("human_review_required", schema)

    def test_forward_test_records_the_agent_contribution_without_claiming_impact(self) -> None:
        report = (ROOT / "docs" / "FORWARD_TEST.md").read_text(encoding="utf-8")

        self.assertIn("fresh Codex Agent", report)
        self.assertIn("PATCH / HARNESS", report)
        self.assertIn("git apply --check", report)
        self.assertIn("The target repository remained unchanged", report)
        self.assertIn("not an impact study", report)

    def test_skill_offers_native_scheduling_without_weakening_the_human_gate(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        schedule = (ROOT / "references" / "scheduled-review.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")

        self.assertIn("weekly usage reset", skill)
        self.assertIn("native Codex Scheduled task", skill)
        self.assertIn("first user-initiated review", skill)
        self.assertIn("never run `apply`, `record`, `rollback`, or `restore`", skill)
        self.assertIn("$codex-metabolism", schedule)
        self.assertIn("STAGE ONLY", schedule)
        self.assertIn("Do not apply, record, rollback, restore", schedule)
        self.assertIn("每週用量重置", chinese)
        self.assertIn("Scheduled task", chinese)


if __name__ == "__main__":
    unittest.main()
