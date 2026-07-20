from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from examples.run_friction_cases_demo import run


class FrictionCasesDemoTests(unittest.TestCase):
    def test_public_demo_replays_two_non_command_order_friction_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "friction-cases"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                code = run(output)

            self.assertEqual(code, 0)
            payload = json.loads(
                (output / ".codex-metabolism" / "decisions.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["observation"]["configured_plugin_count"], 0)
            by_signature = {
                item.get("metadata", {}).get("signature"): item
                for item in payload["decisions"]
            }

            existing_tool = by_signature["explore codex logs"]
            self.assertEqual(existing_tool["decision"], "PATCH")
            self.assertEqual(existing_tool["target_kind"], "TOOL")
            self.assertEqual(existing_tool["mechanism"], "adopt_external")
            self.assertEqual(existing_tool["target"], "tobitege/codlogs")
            self.assertNotIn("required_command", existing_tool["metadata"])

            visual_proof = by_signature["review dashboard completion"]
            self.assertEqual(visual_proof["decision"], "PATCH")
            self.assertEqual(visual_proof["target_kind"], "SKILL")
            self.assertEqual(visual_proof["mechanism"], "workflow_instruction")
            self.assertEqual(visual_proof["target"], "ui-verification")
            self.assertNotIn("required_command", visual_proof["metadata"])

            rendered = stdout.getvalue()
            self.assertIn("Existing-tool friction: PATCH TOOL -> tobitege/codlogs", rendered)
            self.assertIn("Visual-proof friction: PATCH SKILL -> ui-verification", rendered)


if __name__ == "__main__":
    unittest.main()
