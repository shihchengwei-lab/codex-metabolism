# Codex Metabolism demo video production pack

This is the production plan for a **2:40 English voiceover** demo: 16:9, 1080p, public on YouTube, with clear audio and no copyrighted music. The canonical narration and timing live in [`demo-voiceover.en.srt`](demo-voiceover.en.srt).

## Privacy boundary

- Record only the public synthetic fixtures and isolated demo outputs.
- Do not show real sessions, private skills, account names, credentials, notifications, or unrelated paths.
- Use no third-party footage, logos, music, or unlicensed assets.

## Shot list

| Time | Shot | What the judge sees |
|---|---|---|
| 0:00–0:14 | Work, memory, friction | Three quick beats: human and Codex finish a difficult task; its path becomes a skill candidate; a later session still exposes friction while old interventions remain. End on `USEFUL WORK SHOULD GROW. FRICTION SHOULD NOT.` Label it synthetic. |
| 0:14–0:32 | Addition vs metabolism | Put `CREATE SKILL` inside the larger `METABOLIZE` loop, then hold the slime-mold network through four phases: useful work opens a path; future-session evidence arrives; the useful path brightens green; unsupported branches fade. |
| 0:32–0:45 | Shared collaboration loop | Show Complete work → Capture workflow → Future sessions → AI review → human approval → Keep/Repair/Archive. State that this changes the collaboration layer, not model weights, and that the replay is synthetic. |
| 0:45–0:59 | Conservative first review | Show failure → explicit correction → same-command recovery across two sessions, then run `python examples/run_closed_loop_demo.py` and pause on the four staged decisions. |
| 0:59–1:14 | Build less | Show the five-rung adoption ladder and the blocked-create state. |
| 1:14–1:28 | Mechanical trust boundary | Show the exact reviewed `preflight && deploy` sequence, adversarial denials, approval, and reversibility. |
| 1:28–1:43 | Validate | Show `KEEP HARNESS (VALIDATED)` and duplicate-proposal suppression. |
| 1:43–1:58 | Prune | Show evidence-gated `KEEP`, `RETIRE_CANDIDATE`, archive, and restore. |
| 1:58–2:11 | Honest evaluation | Show 27 synthetic cases: 8 TP, 0 FP, 8 FN, 11 TN; precision 1.0 and recall 0.5. |
| 2:11–2:32 | Codex and GPT-5.6 | Show `workflow_candidate` beside feedback/interruption evidence, then the live advisor command: `--advisor codex --advisor-model gpt-5.6-sol`. GPT-5.6 interprets; deterministic code validates evidence and schema; the human remains the mutation gate. |
| 2:32–2:40 | Close | Product name, repository URL, MIT license, and the one-line contrast. |

Keep subtitles to at most two short lines. Use hard cuts, large type, and one claim per shot; do not scroll a report during narration.

## Slime-mold visual language

The metaphor is procedural, not biological: completed work can open a reusable path; future-session evidence reveals whether it helps or causes friction; review reinforces, repairs, or withdraws it. Do not imply that tool success proves task completion or that one later success proves causality.

## Capture and verification

1. Record a fresh deterministic run from a clean clone on Python 3.11 or newer.
2. Show only the generated report, staged guard, bounded rule diff, receipt, and public evaluation.
3. Run the advisor only against synthetic packets. Label the hard cut and elapsed time; never imply instant completion.
4. Verify 1920×1080 H.264 video, AAC audio, English subtitles, 2:40 duration, and speech normalized near −16 LUFS.
5. Upload to YouTube as **Public**, not Unlisted or Private. Link `https://github.com/shihchengwei-lab/codex-metabolism` and state `MIT License`.
6. Add the primary build thread's `/feedback` Session ID to Devpost.

## Suggested YouTube metadata

**Title:** Codex Metabolism — Evidence-driven improvement for Codex collaboration

**Description:**

> Most agent improvement systems are built for addition. Codex Metabolism asks what earns the right to remain. It finds conservative evidence of recurring friction, adopts or creates the smallest useful intervention, validates it against later Codex sessions, and prunes what no longer helps. Built with Codex and GPT-5.6 for OpenAI Build Week. The public demo uses synthetic data and reports its current boundary: zero false positives and 50% recall across 27 author-defined cases. MIT-licensed source: https://github.com/shihchengwei-lab/codex-metabolism
