# Codex Metabolism — project story

> **Agent-first architecture:** Codex interprets and authors. A small runtime preserves evidence, binds approval to exact proposal bytes, and safely manages the mutations it owns.

## Project details

- **Track:** Developer Tools
- **Tagline:** Let human–AI collaboration grow what helps—and retire what does not.
- **Repository:** https://github.com/shihchengwei-lab/codex-metabolism
- **Original Build Week video (v0.1):** https://youtu.be/egZhaFeDkRE
- **Current reproducible demo:** `python examples/run_agent_first_demo.py`

## Inspiration

OpenAI once documented a [literal goblin problem](https://openai.com/index/where-the-goblins-came-from/): Codex needed a prompt patch saying, “Never talk about goblins.” The patch made sense—but how many rules in your `AGENTS.md` still solve a problem your recent sessions actually have?

Coding agents are good at adding memory, rules, skills, and tools. They are worse at proving that an intervention still helps—or removing it when it does not. **Accumulation is not improvement.**

Codex Metabolism borrows its mental model from slime mold: useful work opens a path, later traffic reveals whether to reinforce or repair it, and unsupported branches fade.

The original inspirations were Hermes Agent's agent-managed skill creation, Claude Code Insights' session retrospectives, and my MIT-licensed [`session-analytics`](https://github.com/shihchengwei-lab/session-analytics) project.

## What it does

Codex Metabolism is a skill the active Codex Agent uses to review its recent collaboration with one person.

```text
Use $codex-metabolism to review my last 7 days.
Find reusable work and recurring friction, check existing capabilities first,
and show every proposed diff. Do not apply anything until I approve it.
```

The runtime turns changing local JSONL into bounded, ordered evidence. **It makes zero semantic decisions.** Codex groups evidence by user intent, distinguishes a reusable trajectory from a retry, searches existing capabilities, and authors zero to three complete improvements. The runtime checks every evidence reference, seals exact artifact bytes, and generates an approval digest. Changing either proposal or artifact invalidates that reviewed digest.

Approved skills are hash-gated and reversible. Repository harnesses, tools, and bounded rules use existing Git or platform mechanisms; Metabolism preserves the approved proposal hash, the actual implementation-evidence hash, and the correct ACTIVE or RETIRED state so a future review can reason about what changed.

**The model does not retrain. The collaboration layer becomes more inspectable and personal.**

## How we built it

### Only the standard library

The Python 3.11+ substrate streams JSONL, bounds excerpts, reports coverage, inventories installed skills and `AGENTS.md` metadata, writes atomically, and preserves receipts without adding a dependency stack to a cleanup tool.

### Mixed ownership + hash-gated apply

Human files and Agent-managed artifacts do not share the same authority. Skill changes cite an observed target, seal a base hash, and fail if either the live file or reviewed artifact changes. Non-skill changes are never secretly implemented by the runtime.

### Agent-first, not an advisor wrapper

GPT-5.6 is the active Codex Agent, not a nested model call hidden behind Python. It performs the hard semantic work and writes the real artifact. Deterministic code can reject unsafe structure, but it cannot choose what a user's interruption means or which intervention layer is best. The human still decides whether anything becomes live.

## Challenges

> **Parse gaps must remain unknown.**

Codex JSONL is useful but not a stable public analytics schema. Coverage failures can never be relabeled as non-use.

---

> **Silence is not success.**

Exit codes and tests are stronger signals than “the user did not complain.” Even a successful tool call cannot prove that a task deserves a skill—or that an intervention helped later.

---

> **Trust was the product boundary.**

A self-editing demo is easy to make and hard to trust. Proposal is not permission: Skill apply is bound to the exact digest the user reviewed, and retirement means archive, not silent deletion. A CLI cannot authenticate human identity, so Codex must still wait for explicit approval in the conversation. Non-skill changes retain the native Git or platform rollback path instead of pretending the runtime owns them.

## Accomplishments

- Replaced a large deterministic decision engine with a small Agent-first contract.
- Reduced the runtime to neutral observation, proposal validation, receipts, safe mutation, and rollback.
- Added an isolated demo whose first line is `Runtime interpretation: 0 semantic decisions`.
- A fresh Codex Agent ignored the recorded skill-shaped fixture, reused the repository preflight, and authored a smaller `PATCH / HARNESS`; its patch passed `git apply --check` and remained stage-only.
- Reject invented evidence IDs, path escapes, stale targets, duplicate IDs, unknown schema fields, and proposal or artifact changes after approval.
- Keep the project zero-dependency and test it on Python 3.11/3.12 for Ubuntu and Windows.

## What we learned

The first version extracted ideas from Agent products but accidentally removed the Agent from the center. Python tried to infer friction with exact patterns while GPT-5.6 sat outside as an optional advisor. The result was safe, but conceptually backward.

The better division is simple:

- **Codex understands and creates.**
- **The runtime remembers and constrains.**
- **The human approves an exact digest; Skill mutations are reversible, while other layers retain their native rollback path.**

That makes the program necessary without pretending it is intelligent.

## What's next

Models improve, and users learn how to work with them. The collaboration layer between them should improve too.

The long-term loop is: an Agent completes difficult or repeated work, captures a reusable path, encounters new friction in later sessions, and reviews with the human what deserves reinforcement, repair, or withdrawal. With stronger longitudinal outcome evidence, this could become a native Codex capability: personal without becoming opaque, adaptive without surrendering control.

## Honest boundary

The current release implements observation → zero-to-three Agent proposals → validation and approval digest → human decision → action-accurate receipt → Skill rollback or native external rollback. Each target's next review receives its prior reasoning, evidence, expected effect, withdrawal condition, and bounded status history. The public replay is synthetic. It does **not** claim real-world precision/recall, causal improvement, automatic intervention evaluation, or long-term impact.

The [README](../README.md) contains installation, safety details, and the current command surface. The [video production pack](DEMO_VIDEO.md) describes an Agent-first replacement demo.
