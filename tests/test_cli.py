from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_metabolism.cli import main

from tests.helpers import NOW, make_deploy_home, write_skill


class CliTests(unittest.TestCase):
    def test_review_command_runs_observe_decide_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            output = root / "review-output"
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps([]), encoding="utf-8")

            code = main(
                [
                    "review",
                    "--days",
                    "7",
                    "--codex-home",
                    str(codex_home),
                    "--skill-root",
                    str(skills_root),
                    "--project-root",
                    str(root),
                    "--output-dir",
                    str(output),
                    "--catalog-file",
                    str(catalog),
                    "--no-skillreaper",
                    "--now",
                    NOW.isoformat(),
                ]
            )

            self.assertEqual(code, 0)
            self.assertTrue((output / "report.md").is_file())
            self.assertTrue((output / "decisions.json").is_file())

    def test_review_imports_a_read_only_skillreaper_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            write_skill(skills_root, "old-unused", age_days=60)
            output = root / "review-output"
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps([]), encoding="utf-8")
            skillreaper = root / "skillreaper.json"
            skillreaper.write_text(
                json.dumps(
                    {
                        "GeneratedAt": NOW.isoformat(),
                        "Sessions": 12,
                        "MalformedLines": 0,
                        "Warnings": [],
                        "Rows": [
                            {
                                "Category": "skill",
                                "Name": "old-unused",
                                "Platform": "codex",
                                "Path": str(skills_root / "old-unused"),
                                "Removable": True,
                                "Uses": 0,
                                "Verdict": "REAP",
                                "Reason": "unused",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            code = main(
                [
                    "review",
                    "--codex-home",
                    str(codex_home),
                    "--skill-root",
                    str(skills_root),
                    "--project-root",
                    str(root),
                    "--output-dir",
                    str(output),
                    "--catalog-file",
                    str(catalog),
                    "--skillreaper-report",
                    str(skillreaper),
                    "--now",
                    NOW.isoformat(),
                ]
            )

            self.assertEqual(code, 0)
            staged = json.loads((output / "decisions.json").read_text(encoding="utf-8"))
            self.assertEqual(staged["observation"]["coverage"]["skill_lifecycle_source"], "skillreaper")
            self.assertTrue(
                any(
                    decision["target"] == "old-unused"
                    and decision["decision"] == "RETIRE_CANDIDATE"
                    for decision in staged["decisions"]
                )
            )

    def test_codex_advisor_is_opt_in_and_attached_as_non_authoritative_metadata(self) -> None:
        class FakeAdvisor:
            def __init__(self, *, model: str) -> None:
                self.model = model

            def advise(self, candidates: list[dict], *, cwd: Path) -> list[dict]:
                candidate = candidates[0]
                return [
                    {
                        "candidate_id": candidate["id"],
                        "decision": candidate["decision"],
                        "target_kind": candidate["target_kind"],
                        "target": candidate["target"],
                        "confidence": "high",
                        "evidence_ids": candidate["evidence_ids"],
                        "proposed_change": candidate["proposed_change"],
                        "reasoning": "Mechanical enforcement matches the evidence.",
                    }
                ]

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            output = root / "review-output"
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps([]), encoding="utf-8")

            with patch("codex_metabolism.cli.CodexAdvisor", FakeAdvisor):
                code = main(
                    [
                        "review",
                        "--codex-home",
                        str(codex_home),
                        "--skill-root",
                        str(skills_root),
                        "--project-root",
                        str(root),
                        "--output-dir",
                        str(output),
                        "--catalog-file",
                        str(catalog),
                        "--no-skillreaper",
                        "--advisor",
                        "codex",
                        "--now",
                        NOW.isoformat(),
                    ]
                )

            self.assertEqual(code, 0)
            staged = json.loads((output / "decisions.json").read_text(encoding="utf-8"))
            advised = next(
                decision for decision in staged["decisions"] if "codex_advisor" in decision["metadata"]
            )
            self.assertEqual(advised["metadata"]["codex_advisor"]["confidence"], "high")
            self.assertEqual(advised["metadata"]["advisor_role"], "non_authoritative")

    def test_activate_tool_command_records_existing_artifact_without_installing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            output = root / "review-output"
            catalog = root / "catalog.json"
            catalog.write_text(
                json.dumps(
                    [
                        {
                            "kind": "oss",
                            "name": "acme/codex-deploy-preflight-guard",
                            "description": "A Codex hook that requires preflight before deploy commands",
                            "url": "https://github.com/acme/codex-deploy-preflight-guard",
                            "license": "MIT",
                            "stars": 42,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "review",
                        "--codex-home",
                        str(codex_home),
                        "--skill-root",
                        str(skills_root),
                        "--project-root",
                        str(root),
                        "--output-dir",
                        str(output),
                        "--catalog-file",
                        str(catalog),
                        "--no-skillreaper",
                        "--now",
                        NOW.isoformat(),
                    ]
                ),
                0,
            )
            payload = json.loads((output / "decisions.json").read_text(encoding="utf-8"))
            decision = next(item for item in payload["decisions"] if item["target_kind"] == "TOOL")
            artifact = root / "bin" / "reviewed-tool.exe"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("already installed", encoding="utf-8")

            code = main(
                [
                    "activate-tool",
                    decision["id"],
                    "--artifact",
                    str(artifact),
                    "--staging",
                    str(output),
                ]
            )

            self.assertEqual(code, 0)
            self.assertEqual(artifact.read_text(encoding="utf-8"), "already installed")
            self.assertTrue((output / "interventions.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
