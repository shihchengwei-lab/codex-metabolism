from __future__ import annotations

import re
import struct
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
    def test_devpost_project_story_is_bounded_and_scannable(self) -> None:
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")
        story = devpost.split("## Inspiration", 1)[1].split("## Submission checklist", 1)[0]

        self.assertLessEqual(len(re.findall(r"\b[\w'-]+\b", story)), 900)
        for heading in (
            "## Inspiration",
            "## What it does",
            "## How we built it",
            "## Challenges",
            "## Accomplishments",
            "## What we learned",
            "## Demo video",
            "## What's next",
        ):
            self.assertEqual(devpost.count(heading), 1)
        for required in (
            "literal goblin problem",
            "Hermes Agent",
            "Claude Code Insights",
            "session-analytics",
            "GPT-5.6 is the semantic interpreter",
            "deterministic code is the evidence and safety envelope",
            "human is the mutation gate",
            "**Parse gaps must remain unknown.**",
            "**Silence is not success.**",
            "**Trust was the product boundary.**",
            "collaboration layer",
            "long-term goal",
        ):
            self.assertIn(required, story)

    def test_public_docs_present_gpt_as_interpreter_and_deterministic_code_as_gate(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        traditional = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")

        for required in (
            "## Model-assisted review (recommended)",
            "codex-metabolism review --days 7 --advisor codex",
            "## Deterministic fallback",
            "GPT-5.6 interprets collaboration opportunities",
            "deterministic code constrains the evidence and safety boundary",
        ):
            self.assertIn(required, readme)
        self.assertIn("## 模型協作 review（建議主路徑）", traditional)
        self.assertIn("## Deterministic fallback（離線備援）", traditional)
        self.assertIn("GPT-5.6 is the semantic interpreter", devpost)
        self.assertIn("deterministic code is the evidence and safety envelope", devpost)

    def test_public_story_is_a_human_ai_collaboration_growth_loop(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        traditional = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")
        video = (ROOT / "docs" / "demo-voiceover.en.srt").read_text(encoding="utf-8")

        for required in (
            "Human and AI improve the collaboration layer together",
            "reusable workflow",
            "future sessions",
            "human approval",
        ):
            self.assertIn(required, readme)
        self.assertIn("人與 AI 共同改善協作層", traditional)
        self.assertIn("reusable workflow", devpost)
        self.assertIn("human and AI improve the layer between them", video)

    def test_real_session_review_states_the_current_mvp_boundary(self) -> None:
        review_path = ROOT / "docs" / "REAL_SESSION_REVIEW.md"
        self.assertTrue(review_path.is_file())
        review = review_path.read_text(encoding="utf-8")
        for required in (
            "213/213",
            "9",
            "20",
            "1,286",
            "352",
            "0 proposed changes",
            "observability evidence",
            "not causal improvement evidence",
            "24 pseudonymous candidates",
            "24 unique pseudonymous candidates with 37 bounded user excerpts",
            "zero skill captures",
            "reject duplicates before analysis",
            "human_review_required=true",
        ):
            self.assertIn(required, review)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        traditional = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")
        self.assertIn("[Real-session review](docs/REAL_SESSION_REVIEW.md)", readme)
        self.assertIn("[真實 session review](docs/REAL_SESSION_REVIEW.md)", traditional)
        self.assertIn("Current MVP boundary", devpost)
        self.assertIn("long-term goal", devpost)

    def test_devpost_loop_visual_is_cover_ready(self) -> None:
        svg_path = ROOT / "docs" / "assets" / "metabolism-loop.svg"
        png_path = ROOT / "docs" / "assets" / "metabolism-loop.png"
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")

        self.assertTrue(svg_path.is_file())
        self.assertTrue(png_path.is_file())
        svg = svg_path.read_text(encoding="utf-8")
        for required in (
            'width="1600" height="900" viewBox="0 0 1600 900"',
            "WORK + SIGNALS",
            "workflow → skill candidate",
            "friction → smallest fix",
            "HUMAN APPROVAL",
            "LATER SESSIONS VALIDATE",
            "KEEP · REPAIR ·",
            "ROLLBACK · ARCHIVE",
            "FUTURE HUMAN + CODEX SESSIONS",
        ):
            self.assertIn(required, svg)
        self.assertNotIn("Legacy Cleanup", svg)
        self.assertIn("assets/metabolism-loop.png", devpost)

        header = png_path.read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", header[16:24]), (1600, 900))

    def test_readmes_keep_the_judge_path_bounded_and_nonduplicative(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        traditional = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")

        self.assertLessEqual(len(readme.splitlines()), 260)
        self.assertLessEqual(len(traditional.splitlines()), 190)
        self.assertEqual(readme.count("python examples/run_closed_loop_demo.py"), 1)
        self.assertEqual(traditional.count("python examples/run_closed_loop_demo.py"), 1)
        self.assertIn("## Evidence at a glance", readme)
        self.assertIn("## 證據一覽", traditional)

    def test_ci_exposes_the_supported_windows_linux_python_matrix(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(workflow.is_file())
        content = workflow.read_text(encoding="utf-8")

        for required in (
            "pull_request:",
            "push:",
            "workflow_dispatch:",
            "contents: read",
            "ubuntu-latest",
            "windows-latest",
            '"3.11"',
            '"3.12"',
            "actions/checkout@v7",
            "actions/setup-python@v7",
            "python -m unittest discover -s tests -v",
            "python examples/run_closed_loop_demo.py",
            "python examples/run_friction_cases_demo.py",
            "python examples/run_messy_evidence_demo.py",
            "python examples/run_detector_evaluation.py",
            "python -m build",
        ):
            self.assertIn(required, content)
        self.assertNotIn("macos-latest", content)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("actions/workflows/ci.yml/badge.svg", readme)

    def test_detector_evaluation_is_public_bounded_and_reproducible(self) -> None:
        evaluation = ROOT / "docs" / "EVALUATION.md"
        self.assertTrue(evaluation.is_file())
        content = evaluation.read_text(encoding="utf-8")

        for required in (
            "python examples/run_detector_evaluation.py",
            "27",
            "11",
            "8",
            "0",
            "1.000",
            "0.500",
            "0.704",
            "path variation",
            "argument variation",
            "command aliases",
            "unmarked corrections",
            "synthetic",
            "not a real-world quality benchmark",
            "failure → correction → same-command success",
            "two different sessions",
            "normal retry",
            "linguistic negatives",
            "sentence-initial `No`",
            "false allow",
        ):
            self.assertIn(required, content)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        traditional = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")
        self.assertIn("[Detector boundary evaluation](docs/EVALUATION.md)", readme)
        self.assertIn("[Detector 邊界評估](docs/EVALUATION.md)", traditional)
        self.assertIn("27-case detector boundary evaluation", devpost)
        self.assertIn("public video shows the current 27-case suite", devpost)

    def test_readme_opens_with_the_metabolism_distinction(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        quick_start = readme.index("## Judge quick start")
        for required in (
            "Everyone is building agent memory. We built agent metabolism.",
            "not another memory store, skill generator, or session dashboard",
            "A shared improvement loop for humans and coding agents",
            "does not fine-tune model weights",
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
        self.assertLess(readme.index(heading), readme.index("## The human–AI metabolic loop"))
        for required in (
            "python examples/run_closed_loop_demo.py",
            "No installation, API key, Codex login, or personal session data is required.",
            "First review: CREATE HARNESS + PATCH RULE",
            "Second review: KEEP HARNESS (VALIDATED)",
            "docs/assets/judge-demo.png",
        ):
            self.assertIn(required, readme)

    def test_readme_exposes_two_non_command_order_friction_cases(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for required in (
            "## Two more real-world friction patterns",
            "python examples/run_friction_cases_demo.py",
            "Existing-tool friction: PATCH TOOL -> tobitege/codlogs",
            "Visual-proof friction: PATCH SKILL -> ui-verification",
            "anonymized synthetic replays",
            "Neither case is a command-order rule",
        ):
            self.assertIn(required, readme)

    def test_readme_exposes_the_imperfect_data_pressure_test(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for required in (
            "## Imperfect-data pressure test",
            "python examples/run_messy_evidence_demo.py",
            "Messy evidence: 1 decision, 2 abstentions",
            "Coverage warning: 1 malformed JSONL line",
            "Unsafe retirement decisions: 0",
            "does not claim semantic clustering",
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
            "## Model-assisted review (recommended)",
            "codex-metabolism review --days 7 --advisor codex",
            "## Model-assisted safety contract",
            "`CREATE HARNESS`",
            "`KEEP RULE`",
            "non-authoritative",
            "48.5 seconds",
        ):
            self.assertIn(required, readme)

    def test_readmes_expose_opt_in_non_mutating_automation(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        traditional = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")

        for required in (
            "## Keep the loop running — opt in",
            "manual review or opt-in scheduled trigger",
            "No schedule is installed by default.",
            "codex-metabolism enable --every-days 7 --after-sessions 10",
            "codex-metabolism status",
            "codex-metabolism disable",
            "Windows Task Scheduler",
            "launchd",
            "systemd user timer",
            ".codex-metabolism/automation/run-scheduled-review.cmd",
            "~/Library/LaunchAgents/",
            "~/.config/systemd/user/",
            "Observe, Decide, and Stage",
            "never Apply",
            "With no prior staged review, sessions from before the first enable are not counted as new.",
            "`--search-oss` remains off",
            "config.json",
            "heartbeat.json",
            "NOTICE.md",
            "unregistered",
            "error",
            "overdue",
        ):
            self.assertIn(required, readme)
        for required in (
            "## 讓迴圈持續運轉——明確啟用",
            "手動 review 或明確啟用的排程觸發",
            "預設不會安裝任何排程",
            "codex-metabolism enable --every-days 7 --after-sessions 10",
            "codex-metabolism status",
            "codex-metabolism disable",
            "Windows Task Scheduler",
            "launchd",
            "systemd user timer",
            ".codex-metabolism/automation/run-scheduled-review.cmd",
            "~/Library/LaunchAgents/",
            "~/.config/systemd/user/",
            "不會自動 Apply",
            "若沒有先前 staged review，第一次啟用以前的 session 不算新 session",
            "`--search-oss` 維持關閉",
            "config.json",
            "heartbeat.json",
            "NOTICE.md",
            "unregistered",
            "error",
            "overdue",
        ):
            self.assertIn(required, traditional)
        self.assertIn("opt-in scheduler", devpost)
        self.assertIn("stage-only", devpost)

    def test_video_pack_is_timed_under_three_minutes_and_covers_required_topics(self) -> None:
        production_guide = ROOT / "docs" / "DEMO_VIDEO.md"
        subtitles = ROOT / "docs" / "demo-voiceover.en.srt"
        devpost = ROOT / "docs" / "DEVPOST.md"
        self.assertTrue(production_guide.is_file())
        self.assertTrue(subtitles.is_file())
        self.assertTrue(devpost.is_file())

        guide_text = production_guide.read_text(encoding="utf-8")
        subtitle_text = subtitles.read_text(encoding="utf-8")
        devpost_text = devpost.read_text(encoding="utf-8")
        cues = re.findall(
            r"(?m)^(\d{2}:\d{2}:\d{2},\d{3}) --> "
            r"(\d{2}:\d{2}:\d{2},\d{3})$",
            subtitle_text,
        )

        self.assertEqual(len(cues), 11)
        self.assertLessEqual(_seconds(cues[-1][1]), 160)
        blocks = re.split(r"\r?\n\s*\r?\n", subtitle_text.strip())
        for block in blocks:
            self.assertLessEqual(len(block.splitlines()[2:]), 2)
        for required in (
            "Codex Metabolism",
            "Codex",
            "GPT-5.6",
            "gpt-5.6-sol",
            "CREATE HARNESS",
            "KEEP RULE",
            "KEEP HARNESS",
            "synthetic",
            "zero false positives",
            "fifty percent recall",
            "exact reviewed",
        ):
            self.assertIn(required, subtitle_text)
        for required in (
            "human and AI improve the layer between them",
            "reusable path could become a skill",
            "human-approved collaboration lifecycle",
            "capture reusable work",
            "twenty-seven synthetic cases",
            "not proof of magical learning or real-world impact",
            "Like slime mold",
            "brightens what works",
            "unsupported branches fade",
            "shared collaboration layer grow—and let go",
        ):
            self.assertIn(required, subtitle_text)
        self.assertLess(
            subtitle_text.index("reusable path could become a skill"),
            subtitle_text.index("GPT-5.6 model gpt-5.6-sol"),
        )
        self.assertIn("privacy", guide_text.lower())
        for required in (
            "YouTube",
            "Shot",
            "English voiceover",
            "live advisor command",
            "--advisor codex --advisor-model gpt-5.6-sol",
            "slime-mold network",
            "future-session evidence",
            "unsupported branches fade",
            "2:40",
        ):
            self.assertIn(required, guide_text)
        self.assertIn("2:40 English voiceover", devpost_text)
        self.assertNotIn("2:35 English voiceover", devpost_text)
        self.assertNotIn("2:50 English voiceover", devpost_text)

    def test_devpost_checklist_records_the_completed_submission_without_public_feedback_id(self) -> None:
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")

        self.assertIn(
            "- [x] Publish repository: https://github.com/shihchengwei-lab/codex-metabolism",
            devpost,
        )
        self.assertIn(
            "- [x] Upload the rendered video to public YouTube: https://youtu.be/egZhaFeDkRE",
            devpost,
        )
        self.assertNotIn("24sUR7Gpe68", devpost)
        self.assertIn(
            "- [x] Enter the `/feedback` Codex Session ID in the organizer-only field.",
            devpost,
        )
        self.assertIn("- [x] Submit the Devpost project form.", devpost)
        self.assertNotIn("[USER ACTION", devpost)
        self.assertNotIn("- [ ]", devpost)
        self.assertNotRegex(
            devpost,
            r"Primary `/feedback` Session ID:\*\*\s*`?[0-9a-f]{8}-[0-9a-f-]{27,}",
        )

    def test_devpost_names_the_non_command_order_replay(self) -> None:
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")

        self.assertIn("README.md", devpost)
        self.assertIn("cross-layer", devpost)

    def test_devpost_names_the_imperfect_data_pressure_test(self) -> None:
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")

        self.assertIn("EVALUATION.md", devpost)
        self.assertIn("synthetic", devpost)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        traditional = (ROOT / "README.zh-TW.md").read_text(encoding="utf-8")
        self.assertIn("ordinary review", readme)
        self.assertIn("exports emitted decisions only", readme)
        self.assertIn("一般 review", traditional)
        self.assertIn("只輸出已產生的 decisions", traditional)

    def test_source_distribution_includes_submission_assets(self) -> None:
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

        self.assertIn("recursive-include docs *.md *.srt *.svg *.png", manifest)


if __name__ == "__main__":
    unittest.main()
