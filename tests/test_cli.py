from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from codex_metabolism.cli import _parser, main

from tests.helpers import NOW, make_deploy_home


class AgentFirstCliTests(unittest.TestCase):
    def test_rollback_requires_explicit_human_approval_flag(self) -> None:
        parser = _parser()
        without = parser.parse_args(["rollback", "proposal-one"])
        with_flag = parser.parse_args(["rollback", "proposal-one", "--human-approved"])

        self.assertFalse(without.human_approved)
        self.assertTrue(with_flag.human_approved)

    def test_observe_outputs_neutral_evidence_and_never_a_decision_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills = make_deploy_home(root)
            project = root / "project"
            project.mkdir()
            output = root / "review"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                code = main(
                    [
                        "observe",
                        "--days",
                        "7",
                        "--codex-home",
                        str(codex_home),
                        "--skill-root",
                        str(skills),
                        "--project-root",
                        str(project),
                        "--output-dir",
                        str(output),
                        "--now",
                        NOW.isoformat(),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertTrue((output / "evidence.json").is_file())
            self.assertFalse((output / "decisions.json").exists())
            self.assertIn("runtime made no decision", stdout.getvalue())

    def test_cli_stages_and_applies_only_after_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills = make_deploy_home(root)
            project = root / "project"
            project.mkdir()
            output = root / "review"
            self.assertEqual(
                main(
                    [
                        "observe",
                        "--codex-home",
                        str(codex_home),
                        "--skill-root",
                        str(skills),
                        "--project-root",
                        str(project),
                        "--output-dir",
                        str(output),
                        "--now",
                        NOW.isoformat(),
                    ]
                ),
                0,
            )
            packet = json.loads((output / "evidence.json").read_text(encoding="utf-8"))
            draft = root / "draft"
            artifact = draft / "artifacts" / "verified-workflow" / "SKILL.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text(
                "---\nname: verified-workflow\ndescription: Reuse a verified workflow.\n"
                "---\n\n# Verified workflow\n\n1. Execute.\n2. Verify.\n",
                encoding="utf-8",
            )
            proposal = draft / "proposal.json"
            proposal.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "review_id": packet["review_id"],
                        "proposals": [
                            {
                                "proposal_id": "agent-verified-workflow",
                                "action": "CREATE",
                                "layer": "SKILL",
                                "target": "verified-workflow",
                                "evidence_ids": [packet["sessions"][0]["events"][0]["id"]],
                                "reasoning": "Codex identified a reusable verified trajectory.",
                                "expected_effect": "Avoid reconstructing the workflow.",
                                "rollback_when": "It adds maintenance cost without reuse.",
                                "alternatives_checked": [
                                    {"level": level, "result": "not_found"}
                                    for level in ("builtin", "installed", "repository", "ecosystem")
                                ],
                                "artifact": {"path": "artifacts/verified-workflow/SKILL.md"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stage_stdout = io.StringIO()
            with redirect_stdout(stage_stdout):
                self.assertEqual(
                    main(
                        [
                            "stage",
                            str(proposal),
                            "--evidence",
                            str(output / "evidence.json"),
                            "--output-dir",
                            str(output),
                        ]
                    ),
                    0,
                )

            manifest = json.loads((output / "proposals.json").read_text(encoding="utf-8"))
            approved_digest = manifest["proposals"][0]["approval_digest"]
            self.assertIn(approved_digest, stage_stdout.getvalue())
            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit):
                main(
                    [
                        "apply",
                        "agent-verified-workflow",
                        "--output-dir",
                        str(output),
                        "--skill-root",
                        str(skills),
                    ]
                )
            self.assertIn("--approved-digest", stderr.getvalue())

            applied = main(
                [
                    "apply",
                    "agent-verified-workflow",
                    "--output-dir",
                    str(output),
                    "--skill-root",
                    str(skills),
                    "--approved-digest",
                    approved_digest,
                ]
            )
            self.assertEqual(applied, 0)
            self.assertTrue((skills / "verified-workflow" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
