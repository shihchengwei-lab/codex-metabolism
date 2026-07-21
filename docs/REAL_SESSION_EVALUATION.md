# Real-session evaluation

This evaluation uses a seven-day window from one real Codex user. Raw JSONL logs remain local. The committed fixture contains manually paraphrased, de-identified evidence only.

Run the public check:

```bash
python examples/run_real_session_evaluation.py
```

## Coverage before judgment

| Measure | Result |
|---|---:|
| Rollout files selected | 14 |
| Files parsed | 14 |
| Unique collaboration sessions | 6 |
| Fork/snapshot files collapsed | 8 |
| Duplicate user events collapsed | 210 |
| Malformed lines | 0 |
| Maximum events exposed per session | 160 |

The initial run was materially worse: child-Agent snapshots repeated the parent conversation, dual Codex event representations repeated user turns, compaction history was misclassified as new input, and one long session contributed more than two thousand tool events. Synthetic fixtures did not reveal those defects.

The runtime now:

1. prefers the root rollout when child-Agent files inherit the same session identity;
2. collapses adjacent dual serialization of the same user turn;
3. accepts user text only from explicit user-message sources;
4. samples long sessions by event kind under a disclosed hard cap;
5. reports every collapsed or truncated count before the Agent interprets meaning.

## Agent review outcomes

| Real observation | Agent judgment | Outcome |
|---|---|---|
| Forked logs and dual events inflated one session | Evidence-quality defect; no semantic inference required | `PATCH / HARNESS` implemented and regression-tested |
| Scheduling was difficult to discover in two projects | Reuse Codex's visible native Scheduled tasks instead of restoring a custom scheduler | `PATCH / SKILL`, stage-only and opt-in |
| Plain-language explanations were requested in independent projects | Existing global guidance already covers it; another rule would duplicate policy | `NO CHANGE / REUSE` |

The full sanitized evidence and judgments are in [`examples/anonymized-real-session-evaluation.json`](../examples/anonymized-real-session-evaluation.json).

## What this proves—and what it does not

This proves that the current parser can process a real seven-day window, that real data changed the implementation, and that an Agent can return both an intervention and an abstention from the same review.

It is **not** a labeled precision/recall benchmark, a multi-user study, or evidence that the interventions caused future collaboration to improve. That requires later sessions and human evaluation. Silence is not success.
