from __future__ import annotations

import re
import unittest
from pathlib import Path

import codex_metabolism


ROOT = Path(__file__).resolve().parents[1]


class PublicSurfaceContractTests(unittest.TestCase):
    def test_readme_front_loads_the_judge_hook_proof_and_test_path(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        first_screen = readme.split("## Why is there a program at all?", 1)[0]

        self.assertIn("Codex can create", first_screen)
        self.assertIn("reuse what exists", first_screen)
        self.assertIn("create or patch when justified", first_screen)
        self.assertIn("revisit later evidence", first_screen)
        self.assertIn("propose retirement", first_screen)
        self.assertIn("human approval for every live change", first_screen)
        self.assertNotIn("Most Agent tools help Codex add", first_screen)
        self.assertNotIn("Metabolism adds selection, validation, and subtraction", readme)
        self.assertIn("14 rollout files", first_screen)
        self.assertIn("six independent sessions", first_screen)
        self.assertIn("210 duplicate user events", first_screen)
        self.assertIn("GPT-5.6", first_screen)
        self.assertIn("python examples/run_agent_first_demo.py", first_screen)
        self.assertLess(len(first_screen.split()), 260)

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

    def test_devpost_story_is_concise_and_places_case_evidence_in_accomplishments(self) -> None:
        devpost = (ROOT / "docs" / "DEVPOST.md").read_text(encoding="utf-8")
        what_it_does = devpost.split("## What it does", 1)[1].split("## How we built it", 1)[0]
        inspiration = devpost.split("## Inspiration", 1)[1].split("## What it does", 1)[0]
        how_we_built_it = devpost.split("## How we built it", 1)[1].split("## Challenges", 1)[0]
        accomplishments = devpost.split("## Accomplishments", 1)[1].split("## What we learned", 1)[0]
        what_we_learned = devpost.split("## What we learned", 1)[1].split("## What's next", 1)[0]
        whats_next = devpost.split("## What's next", 1)[1].split("## Honest boundary", 1)[0]

        self.assertIn("Never talk about goblins", inspiration)
        self.assertIn("real problem", inspiration)
        self.assertIn("gives those interventions a lifecycle", inspiration)
        self.assertIn("session-analytics", inspiration)
        self.assertNotIn("175%", inspiration)
        self.assertNotIn("GPT-5.5", inspiration)
        self.assertLess(len(inspiration.split()), 80)

        self.assertIn("GPT-5.6", what_it_does)
        self.assertIn("evidence-linked proposals", what_it_does)
        self.assertIn("CREATE", what_it_does)
        self.assertIn("PATCH", what_it_does)
        self.assertIn("RETIRE_CANDIDATE", what_it_does)
        self.assertIn("zero semantic decisions", what_it_does)
        self.assertIn("human approval", what_it_does)
        self.assertNotIn("14 rollout files", what_it_does)
        self.assertNotIn("210 duplicate user events", what_it_does)
        self.assertNotIn("Use $codex-metabolism", what_it_does)
        self.assertLess(len(what_it_does.split()), 125)

        self.assertIn("GPT-5.6 interprets", how_we_built_it)
        self.assertIn("only the standard library", how_we_built_it)
        self.assertIn("Change one byte", how_we_built_it)
        self.assertIn("mixed-ownership", how_we_built_it)
        self.assertIn("rules, hooks, and schedulers", how_we_built_it)
        self.assertIn("duplicate-evidence failures", how_we_built_it)

        self.assertIn("one-user, seven-day case study", accomplishments)
        self.assertIn("14 rollout files", accomplishments)
        self.assertIn("six independent sessions", accomplishments)
        self.assertIn("210 duplicate user events", accomplishments)
        self.assertIn("NO CHANGE / REUSE", accomplishments)
        self.assertIn("not a benchmark", accomplishments)

        self.assertIn("**model for meaning, code for invariants, human for judgment.**", what_we_learned)
        self.assertIn("**The collaboration layer between them should improve too.**", whats_next)
        self.assertNotIn("Most Agent tools help Codex add", devpost)
        self.assertLess(len(devpost.split()), 700)

    def test_video_v8_shows_friction_accumulating_one_patch_at_a_time(self) -> None:
        srt = (ROOT / "docs" / "demo-voiceover.en.srt").read_text(encoding="utf-8")
        blocks = re.split(r"\n\s*\n", srt.strip())
        cues: list[tuple[float, float, list[str]]] = []

        def seconds(value: str) -> float:
            hours, minutes, remainder = value.split(":")
            secs, millis = remainder.split(",")
            return int(hours) * 3600 + int(minutes) * 60 + int(secs) + int(millis) / 1000

        for block in blocks:
            lines = block.splitlines()
            start_text, end_text = lines[1].split(" --> ")
            cues.append((seconds(start_text), seconds(end_text), lines[2:]))

        self.assertEqual(len(cues), 30)
        hook_cues = cues[:9]
        hook = " ".join(" ".join(lines) for start, end, lines in hook_cues)
        full_narration = re.sub(r"\s+", " ", srt)
        durations = [end - start for start, end, lines in cues]

        self.assertEqual(len(hook_cues), 9)
        self.assertGreaterEqual(hook_cues[-1][1], 30.0)
        self.assertLessEqual(hook_cues[-1][1], 40.0)
        self.assertIn("One Codex session fails", hook)
        self.assertIn("A rule is added", hook)
        self.assertIn("next session fails the same way", hook)
        self.assertIn("A Skill is added", hook)
        self.assertIn("It fails again", hook)
        self.assertIn("Another safeguard is added", hook)
        self.assertIn("environment keeps growing", hook)
        self.assertNotIn("Two Codex sessions repeat", hook)
        self.assertIn("Creation is not improvement", hook)
        self.assertIn("A session leaves evidence", hook)
        self.assertIn("human approves or rejects", hook)
        self.assertIn("loop is complete", hook)
        self.assertIn("Useful paths brighten", hook)
        self.assertIn("Unsupported branches fade", hook)

        self.assertTrue(all(1.5 <= duration <= 10.0 for duration in durations))
        self.assertGreaterEqual(len({round(duration, 1) for duration in durations}), 8)
        for previous, current in zip(cues, cues[1:]):
            self.assertAlmostEqual(previous[1], current[0], places=3)
        self.assertIn("GPT-5.6 reviewed six sessions", full_narration)
        self.assertIn("fourteen rollout files", full_narration)
        self.assertIn("210 duplicate user turns", full_narration)
        self.assertIn("PATCH", full_narration)
        self.assertIn("NO CHANGE / REUSE", full_narration)
        self.assertIn("existing rule already covered", full_narration)
        self.assertIn("zero semantic decisions", full_narration)
        self.assertIn("approval digest", full_narration)
        self.assertIn("Change a single byte", full_narration)
        self.assertIn("deterministic gate rejects it", full_narration)
        self.assertIn("A human approves", full_narration)
        self.assertIn("later review", full_narration)
        self.assertIn("retirement candidate", full_narration)
        self.assertIn("This is not model training", full_narration)
        self.assertIn("An Agent can add", full_narration)
        self.assertIn("A healthy collaboration can also let go", full_narration)

        for start, end, lines in cues:
            self.assertLessEqual(len(lines), 2)
            self.assertLessEqual(max(map(len, lines)), 38)
            self.assertGreater(end, start)
        self.assertLess(cues[-1][1], 180.0)

        video = (ROOT / "docs" / "DEMO_VIDEO.md").read_text(encoding="utf-8")
        self.assertIn("Around 0:30", video)
        self.assertIn("three complete ideas", video)
        self.assertIn("event density", video)
        self.assertIn("split screen", video)
        self.assertIn("Narration is the clock", video)
        self.assertIn("no fixed five-second holds", video)
        self.assertIn("loop is complete before the slime-mold transition", video)
        self.assertIn("natural voice pace", video)
        self.assertIn("under three minutes", video)
        self.assertIn("chain of custody", video.lower())
        self.assertIn("ISOLATED LIFECYCLE FIXTURE", video)
        self.assertIn("one real seven-day review", video)
        self.assertIn("not a benchmark", video)
        self.assertIn("An Agent can add. A healthy collaboration can also let go.", video)

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
