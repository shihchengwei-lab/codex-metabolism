# Real-session review

On July 21, 2026, the current working build ran a local, stage-only 30-day review against the author's real Codex history. The run did not print or publish raw prompts, commands, session IDs, or local paths; the figures below come from aggregate report fields.

## Observed

| Signal | Result |
|---|---:|
| Session files parsed | 213/213 |
| Malformed JSONL lines | 0 |
| User feedback candidates | 9 |
| Structured interrupted turns | 20 |
| Tool failures with a command | 1,286 |
| Same-command recoveries | 352 |
| Recoveries with a recognized correction | 1 |
| Recurring friction patterns meeting the decision threshold | 0 |
| Review result | 0 proposed changes; 6 KEEP items |

The six KEEP items were four skills with positive heuristic usage signals and two suggestion-only whole-document `AGENTS.md` reviews. Skill invocation remained heuristic because the inspected JSONL contained no structured skill-invocation events. Retirement was disabled because complete external lifecycle evidence was unavailable.

## What this establishes

This is **observability evidence**: the parser handled the selected real files, exposed interruptions and feedback that the earlier detector missed, showed exactly where the conservative funnel abstained, and did not invent a change to make the result look successful.

This is **not causal improvement evidence**. No real intervention was approved from this run, no persistent intervention receipt existed for a before/after comparison, and the 30-day window cannot prove that collaboration became smoother.

## Live GPT-5.6 collaboration review

With explicit user authorization, the same window was reviewed again with `--advisor codex --advisor-model gpt-5.6-sol`. The semantic packet contained 24 pseudonymous candidates and 26 bounded user excerpts selected only from sessions with feedback or structured interruptions. It contained no session IDs, paths, full transcripts, or raw commands.

GPT-5.6 returned three structured, human-gated recommendations:

- a high-confidence direction-mismatch task anchor;
- a high-confidence output-quality evidence gate;
- a medium-confidence checkpoint after repeated interruptions.

Every suggestion cited supplied candidate IDs and returned `human_review_required=true`. The deterministic result remained **0 proposed changes and 6 KEEP items**: model interpretation did not become a lifecycle decision or live mutation. These results demonstrate useful semantic recommendation on real bounded evidence, not that any recommendation is correct or that collaboration improved.

After expanding review from friction alone to the shared collaboration layer, a follow-up run balanced friction signals with substantial-workflow candidates. Each workflow candidate carried bounded user-task samples, aggregate tool activity, an eight-step maximum tool-name/status trace, a verification-like success count, and `completion_verified=false`; no raw command was sent. The first run exposed conflicting duplicate candidate IDs from separate files that shared a session ID. GPT-5.6 flagged the integrity problem instead of silently choosing one, and the deterministic layer was then changed to derive IDs from both session and source identity and to reject duplicates before analysis.

The verified rerun sent **24 unique pseudonymous candidates with 37 bounded user excerpts**. GPT-5.6 returned four human-gated recommendations: three concerned collaboration friction, and one required stronger workflow evidence. It proposed **zero skill captures**, explicitly because all supplied workflow candidates lacked verified completion and verification-like success. The deterministic result again remained **0 proposed changes and 6 KEEP items**. This demonstrates the intended division of labor: the model interprets reusable-work and friction evidence, deterministic code enforces integrity, and the human remains the mutation gate.

## Current boundary

The current MVP observes recent collaboration, reports coverage, nominates substantial work without claiming completion, combines GPT-5.6 interpretation with deterministic guidance, and stages evidence for human judgment. The isolated synthetic demos exercise the implemented receipt, validation, rollback, and retirement mechanics. Demonstrating durable improvement across future real sessions is the long-term product goal, not a claim made from this run.
