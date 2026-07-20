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
| 0:00–0:15 | Concrete pain | Put two repeated failed `deploy production` sessions side by side, then reveal a growing `AGENTS.md` and `old-unused` skill. Do not open with architecture. |
| 0:15–0:29 | Product | Show the observe → adopt → evaluate → prune loop and the one-line promise: use evidence to add, test, and remove collaboration structure. |
| 0:29–0:43 | Build evidence | Show the README section that separates Codex/GPT-5.6 contributions from human product decisions. |
| 0:43–0:58 | Safe fixtures | Open the two synthetic JSONL sessions and the demo `AGENTS.md`; keep text large enough to read. |
| 0:58–1:15 | First generation | From a clean clone, run `python examples/run_closed_loop_demo.py`; pause on `CREATE HARNESS + PATCH RULE`. |
| 1:15–1:31 | Adoption ladder | Open the generated report and highlight necessity, Codex built-in, installed, repository, and ecosystem. |
| 1:31–1:48 | Trust boundary | Show the staged hook, `PENDING_TRUST`, and the managed-region-only `AGENTS.md` diff. |
| 1:48–2:05 | Second generation | Return to the terminal and pause on `KEEP HARNESS (VALIDATED)`. |
| 2:05–2:20 | Pruning | Show `KEEP SKILL`, `RETIRE_CANDIDATE SKILL`, and the reversible archive/restore boundary. |
| 2:20–2:42 | Live model evidence | Show the **live synthetic advisor run** command, `--advisor codex --advisor-model gpt-5.6-sol`, then the real `CREATE HARNESS` agreement and `KEEP RULE` disagreement. Label it non-authoritative. |
| 2:42–2:50 | Close | Return to the title card with the repository URL. |

## Capture setup

1. Clone the public repository into a short neutral path such as `C:\demo\codex-metabolism`.
2. Set the terminal to at least 120 columns, hide the tab bar if it exposes a username, and enable Do Not Disturb.
3. Use Python 3.11 or newer and run the zero-install demo once before recording.
4. Record a fresh deterministic run, then open only the generated `report.md`, staged hook, managed rule diff, and receipt ledger.
5. Run the advisor only against the public fixtures. Its verified run took 48.5 seconds; show the start and real result with a labelled hard cut instead of pretending it completed instantly.
6. Keep text at 125–150% zoom. Use hard cuts instead of fast scrolling.
7. Add the provided SRT captions and normalize narration loudness before export.

## Final verification

- Video duration is below 3:00; the planned cut ends at 2:50.
- The voiceover explicitly explains what was built, how Codex was used, and how GPT-5.6 contributed.
- The deterministic demo is described truthfully as model-free; the separate `gpt-5.6-sol` advisor run is visibly live, optional, synthetic-only, and non-authoritative.
- Only synthetic data appears on screen.
- The video is uploaded to YouTube as **Public**, not Unlisted or Private.
- The description links to `https://github.com/shihchengwei-lab/codex-metabolism` and states `MIT License`.
- The final Devpost form contains the primary build thread's `/feedback` Session ID.

## Suggested YouTube metadata

**Title:** Codex Metabolism — Evidence-driven improvement for Codex collaboration

**Description:**

> Codex Metabolism observes recurring collaboration friction, adopts or creates the smallest useful intervention across harnesses, tools, skills, and bounded rules, then evaluates and prunes it using later Codex sessions. Built with Codex and GPT-5.6 for OpenAI Build Week. Public deterministic demo and MIT-licensed source: https://github.com/shihchengwei-lab/codex-metabolism
