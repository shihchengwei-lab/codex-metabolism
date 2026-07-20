from __future__ import annotations

import unittest

from codex_metabolism.integrations.skillreaper import parse_skillreaper_report


class SkillReaperImportTests(unittest.TestCase):
    def test_imports_only_codex_skill_rows_and_preserves_verdict_evidence(self) -> None:
        report = {
            "GeneratedAt": "2026-07-20T10:00:00Z",
            "Sessions": 14,
            "MalformedLines": 0,
            "Warnings": [],
            "Rows": [
                {
                    "Category": "skill",
                    "Name": "old-unused",
                    "Platform": "codex",
                    "Path": "C:/demo/.agents/skills/old-unused",
                    "Removable": True,
                    "Uses": 0,
                    "Verdict": "REAP",
                    "Reason": "unused",
                },
                {
                    "Category": "skill",
                    "Name": "healthy-skill",
                    "Platform": "codex",
                    "Path": "C:/demo/.agents/skills/healthy-skill",
                    "Removable": True,
                    "Uses": 4,
                    "Verdict": "KEEP",
                    "Reason": "used",
                },
                {
                    "Category": "skill",
                    "Name": "not-ours",
                    "Platform": "claude-code",
                    "Path": "C:/demo/.claude/skills/not-ours",
                    "Removable": True,
                    "Uses": 0,
                    "Verdict": "REAP",
                    "Reason": "unused",
                },
            ],
        }

        imported = parse_skillreaper_report(report)

        self.assertTrue(imported.complete)
        self.assertEqual(imported.sessions, 14)
        self.assertEqual([row.skill_name for row in imported.evidence], ["old-unused", "healthy-skill"])
        self.assertEqual(imported.evidence[0].verdict, "REAP")
        self.assertTrue(imported.evidence[0].removable)

    def test_malformed_or_warned_report_is_not_retirement_complete(self) -> None:
        report = {
            "Sessions": 14,
            "MalformedLines": 1,
            "Warnings": [{"Path": "~/.codex/sessions", "Msg": "incomplete evidence"}],
            "Rows": [
                {
                    "Category": "skill",
                    "Name": "old-unused",
                    "Platform": "codex",
                    "Path": "C:/demo/.agents/skills/old-unused",
                    "Removable": True,
                    "Uses": 0,
                    "Verdict": "REAP",
                    "Reason": "unused",
                }
            ],
        }

        imported = parse_skillreaper_report(report)

        self.assertFalse(imported.complete)
        self.assertFalse(imported.evidence[0].complete)


if __name__ == "__main__":
    unittest.main()
