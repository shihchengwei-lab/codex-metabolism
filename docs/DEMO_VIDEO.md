# Codex Metabolism demo video production pack

This is the production plan for a **2:50 English voiceover** demo. The target is a 16:9, 1080p public YouTube video with no copyrighted music. Keep the final cut below three minutes even after platform processing.

The canonical narration and subtitle timing lives in [`demo-voiceover.en.srt`](demo-voiceover.en.srt). A local Windows TTS draft may be generated at `.submission/codex-metabolism-voiceover-draft.mp3`; it is a timing aid, not a committed project artifact or a ChatGPT Voice recording.

## Privacy boundary

- Record only `examples/demo-home`, `examples/demo-project`, and the isolated temporary output printed by the demo.
- Do not show real `~/.codex/sessions`, installed private skills, account names, notifications, browser tabs, credentials, or unrelated paths.
- Crop the terminal so the retained temporary path is not the visual focus.
- Use no third-party logos, music, or footage. Product names may be spoken as part of the technical explanation.

## Shot list

| Time | Shot | On-screen action |
|---|---|---|
| 0:00–0:13 | Problem | Title card, then briefly show the four intervention layers accumulating around an agent. |
| 0:13–0:29 | Product | Show the observe → adopt → evaluate → prune loop from the README preview. |
| 0:29–0:45 | Build evidence | Show the README section that separates Codex/GPT-5.6 contributions from human decisions. |
| 0:45–1:00 | Safe fixtures | Open the two synthetic JSONL sessions and the demo `AGENTS.md`; keep text large enough to read. |
| 1:00–1:18 | First generation | From a clean clone, run `python examples/run_closed_loop_demo.py`; pause on `CREATE HARNESS + PATCH RULE`. |
| 1:18–1:35 | Adoption ladder | Open the generated report and highlight necessity, Codex built-in, installed, repository, and ecosystem. |
| 1:35–1:53 | Trust boundary | Show the staged hook, `PENDING_TRUST`, and the managed-region-only `AGENTS.md` diff. |
| 1:53–2:12 | Second generation | Return to the terminal and pause on `KEEP HARNESS (VALIDATED)`. |
| 2:12–2:29 | Pruning | Show `KEEP SKILL`, `RETIRE_CANDIDATE SKILL`, and the reversible archive/restore commands. |
| 2:29–2:42 | Tools and model boundary | Show the external-tool ladder and the optional `--advisor codex` command without invoking private data. |
| 2:42–2:50 | Close | Return to the title card with the repository URL. |

## Capture setup

1. Clone the public repository into a short neutral path such as `C:\demo\codex-metabolism`.
2. Set the terminal to at least 120 columns, hide the tab bar if it exposes a username, and enable Do Not Disturb.
3. Use Python 3.11 or newer and run the zero-install demo once before recording.
4. Record a fresh run, then open only the generated `report.md`, staged hook, managed rule diff, and receipt ledger.
5. Keep text at 125–150% zoom. Use hard cuts instead of fast scrolling.
6. Add the provided SRT captions and normalize narration loudness before export.

## Final verification

- Video duration is below 3:00; the planned cut ends at 2:50.
- The voiceover explicitly explains what was built, how Codex was used, and how GPT-5.6 contributed.
- The deterministic demo is described truthfully as model-free; the GPT-5.6 advisor is identified as optional.
- Only synthetic data appears on screen.
- The video is uploaded to YouTube as **Public**, not Unlisted or Private.
- The description links to `https://github.com/shihchengwei-lab/codex-metabolism` and states `MIT License`.
- The final Devpost form contains the primary build thread's `/feedback` Session ID.

## Suggested YouTube metadata

**Title:** Codex Metabolism — Evidence-driven improvement for Codex collaboration

**Description:**

> Codex Metabolism observes recurring collaboration friction, adopts or creates the smallest useful intervention across harnesses, tools, skills, and bounded rules, then evaluates and prunes it using later Codex sessions. Built with Codex and GPT-5.6 for OpenAI Build Week. Public deterministic demo and MIT-licensed source: https://github.com/shihchengwei-lab/codex-metabolism
