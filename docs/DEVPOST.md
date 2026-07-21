# Codex Metabolism — project story

> **Codex can create. Codex Metabolism closes the lifecycle: reuse what exists, create or patch when justified, revisit later evidence, and propose retirement—with human approval for every live change.**

## Project details

- **Track:** Developer Tools
- **Tagline:** Let human–AI collaboration grow what helps—and retire what does not.
- **Repository:** https://github.com/shihchengwei-lab/codex-metabolism
- **Current Build Week video:** https://youtu.be/7aYSEC4RQ8A
- **60-second test path:** `python examples/run_agent_first_demo.py`

## Inspiration

[OpenAI once patched Codex](https://openai.com/index/where-the-goblins-came-from/) with **“Never talk about goblins.”** Funny—but it exposes a real problem: Agent environments keep emergency rules, Skills, and tools after their reason disappears.

**Codex Metabolism gives those interventions a lifecycle:** reuse, create or patch, revisit with session evidence, and propose retirement—with human approval.

Inspired by Hermes Agent, Claude Code Insights, and my [`session-analytics`](https://github.com/shihchengwei-lab/session-analytics).

## What it does

Codex Metabolism is a GPT-5.6 Agent Skill that reviews recent Codex sessions, finds reusable work or recurring friction, and proposes the smallest useful intervention.

**Observe → interpret → search existing capabilities → reuse or propose `CREATE`, `PATCH`, or `RETIRE_CANDIDATE` → human approval → revisit.**

GPT-5.6 authors up to three evidence-linked proposals—or recommends no change. A small Python runtime bounds and validates the evidence, seals the exact reviewed bytes, and records reversible changes. It makes **zero semantic decisions**, and nothing goes live without human approval.

## How we built it

We split the Agent-first system by responsibility:

- **GPT-5.6 interprets.** Codex groups sessions by intent, identifies reusable work and friction, searches existing capabilities, and authors complete proposals—or abstains.
- **Python enforces invariants—with only the standard library.** It streams JSONL, reports parse coverage, removes duplicate forks and events, bounds evidence, and writes atomically.
- **Humans authorize.** Reviewed artifacts are sealed into an approval digest. Change one byte and approval becomes invalid; applied changes leave receipts and rollback paths.

This mixed-ownership design preserves native mechanisms: Skills use hash-gated apply, while rules, hooks, and schedulers retain their own ownership and safety controls.

Codex also helped build the architecture. It replaced our first deterministic semantic detector, analyzed real Codex logs, and turned duplicate-evidence failures into regression tests.

## Challenges

> **Parse gaps must remain unknown.** Codex JSONL is evidence, not a stable public analytics schema; missing coverage cannot become non-use.

> **Silence is not success.** Tests and exit codes are stronger than “the user did not complain”; the current release does not manufacture causal verdicts.

> **Trust was the product boundary.** Proposal is not permission. Changed bytes void approval, retirement archives instead of deleting, and scheduled runs remain stage-only.

## Accomplishments

- Built a zero-dependency Agent Skill with human-gated `CREATE`, `PATCH`, `RETIRE_CANDIDATE`, restore, and rollback.
- In a **one-user, seven-day case study—not a benchmark**—the runtime reduced 14 rollout files to six independent sessions after identifying eight fork snapshots and 210 duplicate user events. GPT-5.6 then proposed one `PATCH` and one `NO CHANGE / REUSE`.
- Preserved mixed ownership: sealed Skills use hash-gated apply, while rules, hooks, tools, and schedulers remain under their native controls.
- Shipped a reproducible synthetic lifecycle demo and CI across Python 3.11/3.12 on Ubuntu and Windows, including package builds.

## What we learned

Our first version extracted ideas from Agent products and accidentally removed the Agent from the center. Python inferred meaning from exact patterns while GPT-5.6 sat outside as an optional advisor. The simpler architecture is stronger: **model for meaning, code for invariants, human for judgment.**

## What's next

Models improve, and users learn. **The collaboration layer between them should improve too.** With opt-in longitudinal evidence and more users, this could become native to Codex: capture difficult work, notice later friction, then jointly reinforce, repair, or withdraw interventions—personal without becoming opaque.

## Honest boundary

The release implements observation → Agent proposal or abstention → sealed digest → human decision → receipt → reversible Skill or native rollback. The real evaluation is one user's seven-day case, **not a benchmark**. It claims neither causal gains nor long-term impact. Model weights do not change; the human and Agent curate an inspectable collaboration layer.

See the [README](../README.md) for setup and the [video pack](DEMO_VIDEO.md) for storyboard and captions.
