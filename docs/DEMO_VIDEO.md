# Codex Metabolism demo video production pack

This is the production plan for a **2:35 English voiceover** demo: 16:9, 1080p, public on YouTube, with clear audio and no copyrighted music. The canonical narration and timing live in [`demo-voiceover.en.srt`](demo-voiceover.en.srt).

## Privacy boundary

- Record only the public synthetic fixtures and isolated demo outputs.
- Do not show real sessions, private skills, account names, credentials, notifications, or unrelated paths.
- Use no third-party footage, logos, music, or unlicensed assets.

## Shot list

| Time | Shot | What the judge sees |
|---|---|---|
| 0:00–0:14 | Pain first | Two repeated deploy failures beside growing rules and an unused skill. |
| 0:14–0:27 | Why metabolism | An abstract slime-mold network uses future-session evidence: the useful path brightens while later evidence fades unused branches. |
| 0:27–0:40 | Conservative evidence | The exact supported chain: failure → correction → same-command success, repeated across two sessions. Label the data synthetic. |
| 0:40–0:54 | First review | Run `python examples/run_closed_loop_demo.py`; pause on the four staged decisions. |
| 0:54–1:09 | Build less | Show the five-rung adoption ladder and the blocked-create state. |
| 1:09–1:23 | Mechanical trust boundary | Show the exact reviewed `preflight && deploy` sequence, adversarial denials, approval, and reversibility. |
| 1:23–1:38 | Validate | Show `KEEP HARNESS (VALIDATED)` and duplicate-proposal suppression. |
| 1:38–1:53 | Prune | Show evidence-gated `KEEP`, `RETIRE_CANDIDATE`, archive, and restore. |
| 1:53–2:06 | Honest evaluation | Show 24 synthetic cases: 8 TP, 0 FP, 8 FN, 8 TN; precision 1.0 and recall 0.5. |
| 2:06–2:27 | Codex and GPT-5.6 | Show cross-platform CI and the live synthetic advisor run, `--advisor codex --advisor-model gpt-5.6-sol`; its `KEEP RULE` disagreement remains non-authoritative. |
| 2:27–2:35 | Close | Product name, repository URL, MIT license, and the one-line contrast. |

Keep subtitles to at most two short lines. Use hard cuts, large type, and one claim per shot; do not scroll a report during narration.

## Slime-mold visual language

The metaphor is procedural, not biological: recurring friction opens candidate paths; future-session evidence reinforces a path that works and withdraws support from one that does not. Do not imply that one later success proves causality.

## Capture and verification

1. Record a fresh deterministic run from a clean clone on Python 3.11 or newer.
2. Show only the generated report, staged guard, bounded rule diff, receipt, and public evaluation.
3. Run the advisor only against synthetic packets. Label the hard cut and elapsed time; never imply instant completion.
4. Verify 1920×1080 H.264 video, AAC audio, English subtitles, 2:35 duration, and speech normalized near −16 LUFS.
5. Upload to YouTube as **Public**, not Unlisted or Private. Link `https://github.com/shihchengwei-lab/codex-metabolism` and state `MIT License`.
6. Add the primary build thread's `/feedback` Session ID to Devpost.

## Suggested YouTube metadata

**Title:** Codex Metabolism — Evidence-driven improvement for Codex collaboration

**Description:**

> Agent memory asks what to add; metabolism asks what earns the right to remain. Codex Metabolism finds conservative evidence of recurring friction, adopts or creates the smallest useful intervention, validates it against later Codex sessions, and prunes what no longer helps. Built with Codex and GPT-5.6 for OpenAI Build Week. The public demo uses synthetic data and reports its current boundary: zero false positives and 50% recall across 24 author-defined cases. MIT-licensed source: https://github.com/shihchengwei-lab/codex-metabolism
