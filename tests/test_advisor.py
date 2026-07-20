from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from codex_metabolism.advisor import ADVISOR_SCHEMA, AdvisorError, CodexAdvisor


class AdvisorTests(unittest.TestCase):
    def test_codex_advisor_is_ephemeral_read_only_and_defaults_to_verified_gpt_5_6(self) -> None:
        advisor = CodexAdvisor()
        command = advisor.build_command(schema_path="schema.json", output_path="result.json")

        self.assertEqual(command[:2], ["codex", "exec"])
        self.assertIn("--ephemeral", command)
        self.assertIn("--sandbox", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertEqual(command[command.index("-m") + 1], "gpt-5.6-sol")
        self.assertIn("--output-schema", command)

    def test_windows_runtime_uses_the_executable_resolved_by_path_order(self) -> None:
        native = r"C:\Program Files\OpenAI Codex\codex.exe"

        def fake_which(command: str) -> str | None:
            return {"codex": native, "codex.exe": native}.get(command)

        advisor = CodexAdvisor(os_name="nt", which=fake_which)
        command = advisor.build_runtime_command(
            schema_path="schema.json",
            output_path="result.json",
        )

        self.assertEqual(command[:2], [native, "exec"])

    def test_windows_runtime_wraps_path_order_cmd_shim_before_packaged_exe(self) -> None:
        shim = r"C:\demo\npm\codex.CMD"
        packaged = r"C:\Program Files\WindowsApps\OpenAI.Codex\codex.exe"
        command_processor = r"C:\Windows\System32\cmd.exe"

        def fake_which(command: str) -> str | None:
            return {"codex.exe": packaged, "codex": shim}.get(command)

        advisor = CodexAdvisor(
            os_name="nt",
            which=fake_which,
            comspec=command_processor,
        )
        command = advisor.build_runtime_command(
            schema_path="schema.json",
            output_path="result.json",
        )

        self.assertEqual(
            command[:6],
            [command_processor, "/d", "/s", "/c", shim, "exec"],
        )

    def test_non_windows_runtime_keeps_the_portable_codex_command(self) -> None:
        advisor = CodexAdvisor(os_name="posix", which=lambda _: None)
        command = advisor.build_runtime_command(
            schema_path="schema.json",
            output_path="result.json",
        )

        self.assertEqual(command[:2], ["codex", "exec"])

    def test_advisor_schema_uses_the_codex_structured_output_subset(self) -> None:
        evidence_ids = ADVISOR_SCHEMA["properties"]["suggestions"]["items"]["properties"][
            "evidence_ids"
        ]

        self.assertNotIn("uniqueItems", evidence_ids)

    def test_advisor_rejects_duplicate_evidence_ids_locally(self) -> None:
        advisor = CodexAdvisor(model="gpt-5.6-sol")
        candidates = [
            {
                "id": "candidate-1",
                "mechanical": False,
                "readiness": "ready",
                "evidence_ids": ["evidence-1"],
            }
        ]

        with self.assertRaisesRegex(AdvisorError, "duplicate evidence IDs"):
            advisor.validate_suggestions(
                candidates,
                [
                    {
                        "candidate_id": "candidate-1",
                        "decision": "KEEP",
                        "target_kind": "SKILL",
                        "confidence": "high",
                        "evidence_ids": ["evidence-1", "evidence-1"],
                    }
                ],
            )

    def test_advisor_rejects_invented_evidence_and_rule_when_harness_is_possible(self) -> None:
        advisor = CodexAdvisor(model="gpt-5.6")
        candidates = [
            {
                "id": "candidate-1",
                "mechanical": True,
                "evidence_ids": ["evidence-1", "evidence-2"],
            }
        ]

        with self.assertRaises(AdvisorError):
            advisor.validate_suggestions(
                candidates,
                [
                    {
                        "candidate_id": "candidate-1",
                        "decision": "CREATE",
                        "target_kind": "RULE",
                        "target": "deploy-rule",
                        "confidence": "high",
                        "evidence_ids": ["invented"],
                        "proposed_change": "Remember to run preflight.",
                    }
                ],
            )

    def test_advisor_runs_with_evidence_on_stdin_and_validates_structured_output(self) -> None:
        captured: dict[str, object] = {}

        def fake_runner(command: list[str], **kwargs: object) -> SimpleNamespace:
            captured["command"] = command
            captured["input"] = kwargs["input"]
            output = Path(command[command.index("-o") + 1])
            output.write_text(
                json.dumps(
                    {
                        "suggestions": [
                            {
                                "candidate_id": "candidate-1",
                                "decision": "CREATE",
                                "target_kind": "HARNESS",
                                "target": "preflight-guard",
                                "confidence": "high",
                                "evidence_ids": ["evidence-1"],
                                "proposed_change": "Use a pre-tool guard.",
                                "reasoning": "The correction is mechanically enforceable.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        advisor = CodexAdvisor(runner=fake_runner)
        candidates = [
            {
                "id": "candidate-1",
                "mechanical": True,
                "readiness": "ready",
                "evidence_ids": ["evidence-1"],
            }
        ]

        with tempfile.TemporaryDirectory() as temp:
            suggestions = advisor.advise(candidates, cwd=Path(temp))

        supplied = json.loads(str(captured["input"]))
        self.assertEqual(supplied["candidates"], candidates)
        self.assertEqual(suggestions[0]["candidate_id"], "candidate-1")
        self.assertEqual(suggestions[0]["target_kind"], "HARNESS")

    def test_advisor_accepts_external_tool_adoption_as_a_supported_target(self) -> None:
        advisor = CodexAdvisor(model="gpt-5.6")
        candidates = [
            {
                "id": "candidate-tool",
                "mechanical": True,
                "readiness": "ready",
                "evidence_ids": ["evidence-tool"],
            }
        ]

        suggestions = advisor.validate_suggestions(
            candidates,
            [
                {
                    "candidate_id": "candidate-tool",
                    "decision": "PATCH",
                    "target_kind": "TOOL",
                    "target": "acme/existing-tool",
                    "confidence": "medium",
                    "evidence_ids": ["evidence-tool"],
                    "proposed_change": "Adopt the reviewed external tool.",
                    "reasoning": "The ecosystem rung found an existing implementation.",
                }
            ],
        )

        self.assertEqual(suggestions[0]["target_kind"], "TOOL")


if __name__ == "__main__":
    unittest.main()
