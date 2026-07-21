from __future__ import annotations

import csv
import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from codex_metabolism.cli import (
    _advisor_candidates,
    _collaboration_advisor_candidates,
    _plugin_catalog,
    main,
)
from codex_metabolism.observe import observe

from tests.helpers import NOW, make_deploy_home, write_skill


class CliTests(unittest.TestCase):
    def test_review_help_presents_model_assistance_as_recommended_and_offline_as_fallback(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as exit_status:
            main(["review", "--help"])

        self.assertEqual(exit_status.exception.code, 0)
        rendered = stdout.getvalue()
        self.assertIn("recommended model-assisted review", rendered)
        self.assertIn("deterministic fallback", rendered)
        self.assertIn("bounded", rendered)
        self.assertIn("OpenAI", rendered)

    def test_decision_advisor_skips_keep_only_inventory_items(self) -> None:
        def item(identifier: str, decision: str) -> SimpleNamespace:
            return SimpleNamespace(
                id=identifier,
                decision=decision,
                target_kind="SKILL",
                target="demo",
                mechanism="retain_used_skill",
                readiness="ready",
                confidence="medium",
                proposed_change="Keep it.",
                evidence=[],
                adoption_ladder=[],
            )

        candidates = _advisor_candidates([item("keep", "KEEP"), item("patch", "PATCH")])

        self.assertEqual([candidate["id"] for candidate in candidates], ["patch"])

    def test_collaboration_advisor_candidates_include_reusable_work_without_claiming_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            snapshot = observe(
                codex_home, [skills_root], days=7, now=NOW, project_root=root
            )
            snapshot.sessions[0].tool_executions.append(
                snapshot.sessions[0].tool_executions[-1]
            )

            candidates = _collaboration_advisor_candidates(snapshot, limit=8)

            self.assertLessEqual(len(candidates), 8)
            rendered = json.dumps(candidates, ensure_ascii=False)
            self.assertNotIn("session-one", rendered)
            self.assertNotIn(str(root), rendered)
            self.assertTrue(all(item["id"].startswith("signal-") for item in candidates))
            context = next(item for item in candidates if item["kind"] == "workflow_candidate")
            self.assertLessEqual(len(context["user_inputs_sample"]), 2)
            self.assertTrue(all(len(text) <= 200 for text in context["user_inputs_sample"]))
            self.assertRegex(context["project_key"], r"^[0-9a-f]{12}$")
            self.assertGreaterEqual(context["tool_activity"]["successful"], 2)
            self.assertTrue(context["tool_trace"])
            self.assertTrue(
                all(set(step) == {"tool_name", "status"} for step in context["tool_trace"])
            )
            self.assertFalse(context["completion_verified"])

    def test_collaboration_candidate_ids_remain_unique_when_session_ids_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            snapshot = observe(
                codex_home, [skills_root], days=7, now=NOW, project_root=root
            )
            snapshot.sessions[1].session_id = snapshot.sessions[0].session_id

            candidates = _collaboration_advisor_candidates(snapshot, limit=24)
            ids = [item["id"] for item in candidates]

            self.assertEqual(len(ids), len(set(ids)))

    def test_plugin_inventory_uses_shared_launcher_and_skips_not_installed_entries(self) -> None:
        output = """\
Marketplace `openai-curated`
PLUGIN                       STATUS              VERSION
browser@openai-bundled       installed, enabled  1.2.3
slack@openai-curated         not installed
"""
        resolved = [r"C:\Windows\System32\cmd.exe", "/d", "/s", "/c", "codex.cmd"]

        with (
            patch("codex_metabolism.cli.build_codex_command", return_value=resolved) as build,
            patch(
                "codex_metabolism.cli.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=output, stderr=""),
            ) as run,
        ):
            entries = _plugin_catalog()

        build.assert_called_once_with(["plugin", "list"])
        self.assertEqual(run.call_args.args[0], resolved)
        self.assertEqual([entry["name"] for entry in entries], ["browser@openai-bundled"])
        self.assertEqual(entries[0]["status"], "installed, enabled")

    def test_review_command_runs_observe_decide_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            output = root / "review-output"
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps([]), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
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
            self.assertIn("1 proposed change, 0 KEEP", stdout.getvalue())

    def test_review_can_export_privacy_safe_evidence_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            output = root / "review-output"
            export_path = root / "friction-evidence.csv"
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
                    "--export-evidence",
                    str(export_path),
                    "--now",
                    NOW.isoformat(),
                ]
            )

            self.assertEqual(code, 0)
            with export_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            staged = json.loads((output / "decisions.json").read_text(encoding="utf-8"))

            self.assertEqual(
                {row["record_id"] for row in rows},
                {item["id"] for item in staged["decisions"]},
            )
            self.assertTrue(all(row["record_type"] == "decision" for row in rows))
            rendered = export_path.read_text(encoding="utf-8")
            self.assertNotIn("session-one", rendered)
            self.assertNotIn("session-two", rendered)
            self.assertNotIn(str(root), rendered)

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
        advisor_models: list[str] = []

        class FakeAdvisor:
            def __init__(self, *, model: str) -> None:
                self.model = model
                advisor_models.append(model)

            def advise(self, candidates: list[dict], *, cwd: Path) -> list[dict]:
                self_test = unittest.TestCase()
                self_test.assertTrue(candidates)
                self_test.assertTrue(all(item["decision"] != "KEEP" for item in candidates))
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

            def advise_collaboration(self, candidates: list[dict], *, cwd: Path) -> list[dict]:
                return [
                    {
                        "suggestion_id": "semantic-1",
                        "opportunity_type": "workflow_friction",
                        "confidence": "medium",
                        "evidence_ids": [candidates[0]["id"]],
                        "suggested_layer": "HARNESS",
                        "recommendation": "Inspect the repeated preflight friction.",
                        "reasoning": "The feedback candidate identifies repeated workflow friction.",
                        "human_review_required": True,
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
            self.assertEqual(staged["semantic_advisor"][0]["suggestion_id"], "semantic-1")
            self.assertTrue(staged["semantic_advisor_meta"]["human_review_required"])
            self.assertGreater(staged["semantic_advisor_meta"]["candidate_count"], 0)
            report = (output / "report.md").read_text(encoding="utf-8")
            self.assertIn("Review mode: **model-assisted**", report)
            self.assertIn("GPT-5.6 interprets bounded collaboration evidence", report)
            self.assertIn("GPT-5.6 collaboration-layer review (non-authoritative)", report)
            self.assertIn("cannot mutate live state", report)
            self.assertEqual(staged["review_mode"], "model_assisted")
            self.assertEqual(advisor_models, ["gpt-5.6-sol"])

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

    def test_enable_command_is_opt_in_and_keeps_background_network_access_off(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / ".codex-metabolism"
            config_path = output / "automation" / "config.json"

            with patch(
                "codex_metabolism.cli.enable_automation",
                return_value=config_path,
            ) as enable:
                code = main(
                    [
                        "enable",
                        "--project-root",
                        str(root),
                        "--output-dir",
                        str(output),
                        "--codex-home",
                        str(root / ".codex"),
                        "--skill-root",
                        str(root / ".agents" / "skills"),
                        "--every-days",
                        "7",
                        "--after-sessions",
                        "10",
                        "--no-skillreaper",
                        "--now",
                        NOW.isoformat(),
                    ]
                )

            self.assertEqual(code, 0)
            config = enable.call_args.args[0]
            self.assertFalse(config["search_oss"])
            self.assertNotIn("--search-oss", config["review_argv"])
            self.assertEqual(config["after_sessions"], 10)
            self.assertEqual(config["every_days"], 7)

    def test_internal_scheduler_entrypoint_has_readable_help(self) -> None:
        stream = io.StringIO()

        with redirect_stdout(stream), self.assertRaises(SystemExit) as exit_status:
            main(["--help"])

        self.assertEqual(exit_status.exception.code, 0)
        rendered = stream.getvalue()
        self.assertNotIn("==SUPPRESS==", rendered)
        self.assertIn("Internal stage-only scheduler entrypoint", rendered)

    def test_status_command_prints_heartbeat_and_is_nonzero_when_unhealthy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / ".codex-metabolism"
            status = {
                "enabled": True,
                "registered": False,
                "health": "unregistered",
                "overdue": False,
                "pending_sessions": 4,
                "pending_decisions": 2,
                "last_check_at": None,
                "last_successful_review_at": None,
                "next_due_at": NOW.isoformat(),
                "last_error": None,
                "notice_path": str(output / "automation" / "NOTICE.md"),
                "scheduler_kind": "windows-task-scheduler",
            }
            stream = io.StringIO()

            with (
                patch("codex_metabolism.cli.get_automation_status", return_value=status),
                redirect_stdout(stream),
            ):
                code = main(["status", "--output-dir", str(output)])

            self.assertEqual(code, 1)
            rendered = stream.getvalue()
            self.assertIn("Health: unregistered", rendered)
            self.assertIn("Pending sessions: 4", rendered)
            self.assertIn("Pending decisions: 2", rendered)

    def test_scheduled_review_command_reuses_review_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.json"
            captured: list[list[str]] = []

            def fake_scheduled(config_path, *, now, review_runner, notifier=None):
                captured.append([str(config_path), now.isoformat()])
                self.assertEqual(review_runner(["review", "--days", "1"]), 17)
                return {"ran_review": True, "decisions": 0}

            with (
                patch("codex_metabolism.cli.run_scheduled_review", side_effect=fake_scheduled),
                patch("codex_metabolism.cli.main", return_value=17) as recursive_main,
            ):
                code = main(
                    [
                        "scheduled-review",
                        "--config",
                        str(config),
                        "--now",
                        NOW.isoformat(),
                    ]
                )

            self.assertEqual(code, 0)
            recursive_main.assert_called_once_with(["review", "--days", "1"])
            self.assertEqual(captured[0][0], str(config))

    def test_successful_manual_review_refreshes_automation_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            output = root / "review-output"
            catalog = root / "catalog.json"
            catalog.write_text(json.dumps([]), encoding="utf-8")

            with patch("codex_metabolism.cli.record_review_success") as record:
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
                        "--now",
                        NOW.isoformat(),
                    ]
                )

            self.assertEqual(code, 0)
            record.assert_called_once_with(output, reviewed_at=NOW, source="manual")


if __name__ == "__main__":
    unittest.main()
