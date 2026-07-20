from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _seconds(timestamp: str) -> float:
    hours, minutes, remainder = timestamp.split(":")
    seconds, milliseconds = remainder.split(",")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000
    )


class SubmissionDocsTests(unittest.TestCase):
    def test_readme_opens_with_the_metabolism_distinction(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        quick_start = readme.index("## Judge quick start")
        for required in (
            "Everyone is building agent memory. We built agent metabolism.",
            "not another memory store, skill generator, or session dashboard",
            "lifecycle manager for the persistent interventions around Codex",
            "does not fine-tune or update model weights",
            "Same Codex, different metabolism.",
        ):
            self.assertIn(required, readme)
            self.assertLess(readme.index(required), quick_start)

    def test_readme_puts_a_concrete_metabolized_failure_before_quick_start(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        heading = "## One failure, metabolized"
        self.assertIn(heading, readme)
        self.assertLess(readme.index(heading), readme.index("## Judge quick start"))
        for required in (
            "two sessions repeated the same failed `deploy production` command",
            "stage a `PreToolUse` guard",
            "`old-unused`",
            "never auto-delete",
        ):
            self.assertIn(required, readme)

    def test_readme_puts_a_zero_install_judge_path_before_the_architecture(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        heading = "## Judge quick start — under 60 seconds"
        self.assertIn(heading, readme)
        self.assertLess(readme.index(heading), readme.index("## The metabolic loop"))
        for required in (
            "python examples/run_closed_loop_demo.py",
            "No installation, API key, Codex login, or personal session data is required.",
            "First review: CREATE HARNESS + PATCH RULE",
            "Second review: KEEP HARNESS (VALIDATED)",
            "docs/assets/judge-demo.png",
        ):
            self.assertIn(required, readme)

    def test_readme_exposes_build_evidence_and_supported_platforms(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for required in (
            "## Who it is for",
            "## How Codex and GPT-5.6 built this",
            "### Codex and GPT-5.6 contributions",
            "### Human product decisions",
            "The deterministic judge demo intentionally makes no model call.",
            "## Supported platforms",
            "Linux, Python 3.12:** independently verified from a clean clone",
            "macOS, Python 3.11+:** designed for standard-library portability, not yet verified",
        ):
            self.assertIn(required, readme)

    def test_readme_shows_the_verified_live_advisor_result(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for required in (
            "## Optional live GPT-5.6 advisor",
            "--advisor codex --advisor-model gpt-5.6-sol",
            "`CREATE HARNESS`",
            "`KEEP RULE`",
            "non-authoritative",
            "48.5 seconds",
        ):
            self.assertIn(required, readme)

    def test_video_pack_is_timed_under_three_minutes_and_covers_required_topics(self) -> None:
        production_guide = ROOT / "docs" / "DEMO_VIDEO.md"
        subtitles = ROOT / "docs" / "demo-voiceover.en.srt"
        self.assertTrue(production_guide.is_file())
        self.assertTrue(subtitles.is_file())

        guide_text = production_guide.read_text(encoding="utf-8")
        subtitle_text = subtitles.read_text(encoding="utf-8")
        cues = re.findall(
            r"(?m)^(\d{2}:\d{2}:\d{2},\d{3}) --> "
            r"(\d{2}:\d{2}:\d{2},\d{3})$",
            subtitle_text,
        )

        self.assertGreaterEqual(len(cues), 8)
        self.assertLessEqual(_seconds(cues[-1][1]), 180)
        for required in (
            "Codex Metabolism",
            "Codex",
            "GPT-5.6",
            "gpt-5.6-sol",
            "CREATE HARNESS",
            "KEEP RULE",
            "KEEP HARNESS",
            "synthetic",
        ):
            self.assertIn(required, subtitle_text)
        self.assertIn("privacy", guide_text.lower())
        for required in (
            "YouTube",
            "Shot",
            "English voiceover",
            "live synthetic advisor run",
            "--advisor codex --advisor-model gpt-5.6-sol",
        ):
            self.assertIn(required, guide_text)

    def test_devpost_checklist_records_the_public_repository_but_not_user_actions(self) -> None:
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")

        self.assertIn(
            "- [x] Publish repository: https://github.com/shihchengwei-lab/codex-metabolism",
            devpost,
        )
        self.assertIn("- [ ] Record and upload a public YouTube video", devpost)
        self.assertIn("- [ ] Obtain and enter the `/feedback` Codex Session ID", devpost)

    def test_source_distribution_includes_submission_assets(self) -> None:
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

        self.assertIn("recursive-include docs *.md *.srt *.svg *.png", manifest)


if __name__ == "__main__":
    unittest.main()
