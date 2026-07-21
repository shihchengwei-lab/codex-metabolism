# OpenAI Build Week submission

## Submission fields

- **Project:** Codex Metabolism
- **Track:** Developer Tools
- **Tagline:** Let human–AI collaboration grow what helps—and retire what does not.
- **One sentence:** Codex Metabolism helps a human and coding agent evolve their shared collaboration layer: capture reusable work, find later friction, and decide together what to add, repair, keep, or retire.
- **Repository:** https://github.com/shihchengwei-lab/codex-metabolism
- **Demo video:** https://youtu.be/egZhaFeDkRE
- **Primary `/feedback` Session ID:** Entered in Devpost's organizer-only field; intentionally not repeated here.

## Devpost cover image

![Codex Metabolism closed loop: human and Codex capture useful work, review later friction, validate interventions, and metabolize the shared collaboration layer](assets/metabolism-loop.png)

Editable source: [`assets/metabolism-loop.svg`](assets/metabolism-loop.svg).

## Inspiration

OpenAI once documented a [literal goblin problem](https://openai.com/index/where-the-goblins-came-from/): Codex needed a prompt patch saying, “Never talk about goblins.” The patch made sense—but how many rules in your `AGENTS.md` still solve a problem your recent sessions actually have?

Coding agents are excellent at adding memory, rules, skills, and tools. They are worse at proving that an intervention still helps—or removing it when it does not. **Accumulation is not improvement.**

Codex Metabolism borrows its mental model from slime mold: useful work opens a path, future traffic reinforces or repairs it, and unsupported branches fade. The original inspirations were Hermes Agent's agent-managed skill creation, Claude Code Insights' session-level retrospectives, and my MIT-licensed [`session-analytics`](https://github.com/shihchengwei-lab/session-analytics) project. SkillReaper was discovered later through our existing-tool ladder and integrated as optional lifecycle evidence—not claimed as an original inspiration.

## What it does

```bash
codex-metabolism review --days 7 --advisor codex
```

**Current MVP boundary:** GPT-5.6 is the semantic interpreter; deterministic code is the evidence and safety envelope; the human is the mutation gate.

The review:

- observes bounded reusable workflow candidates, feedback, interruptions, failures, recoveries, installed skills, tools, and active `AGENTS.md` scopes;
- asks GPT-5.6 what looks reusable and what still causes friction, without treating tool activity or silence as proof of success;
- checks necessity → Codex built-ins → installed capabilities → repository assets → external tools before proposing anything new;
- stages only `CREATE`, `PATCH`, `KEEP`, or `RETIRE_CANDIDATE` across `HARNESS`, `TOOL`, `SKILL`, and bounded `RULE` layers.

Approved interventions receive receipts so future sessions can validate, repair, roll back, or archive them. An opt-in scheduler can launch a local, stage-only review; it never applies changes automatically.

The public demo uses synthetic sessions to exercise the implemented lifecycle. Real-session review currently demonstrates observation, semantic recommendations, and honest abstention—not causal improvement. Proving durable improvement over future sessions is the long-term goal.

Detailed judge paths, cross-layer examples, and installation instructions are in [`README.md`](../README.md). Detector limits are published in [`EVALUATION.md`](EVALUATION.md), and the privacy-safe real review is in [`REAL_SESSION_REVIEW.md`](REAL_SESSION_REVIEW.md).

## How we built it

- **Only the standard library.** The Python 3.11+ runtime streams JSONL, bounds excerpts, reports parser coverage, inventories the environment, stages artifacts, and records reversible receipts without adding a dependency stack to a cleanup tool.
- **Mixed ownership + hash-gated apply.** Codex Metabolism evaluates the whole `AGENTS.md`, but can only rewrite an existing marked region after approval. Everything outside it remains suggestion-only; full-file hashes prevent stale patches.
- **A non-authoritative advisor.** GPT-5.6 runs through ephemeral, read-only `codex exec` with strict schemas and cited evidence IDs. In one synthetic run it agreed with `CREATE HARNESS` but challenged `PATCH RULE` with `KEEP RULE`; deterministic gates and human approval still won. In a real review it also exposed duplicate candidate IDs, which we converted into a pre-analysis integrity check and regression test.

## Challenges

**Parse gaps must remain unknown.** Codex JSONL is useful but not a stable public analytics schema, so failed coverage can never be relabeled as non-use.

**Silence is not success.** Exit codes and tests are stronger signals than “the user did not complain.” Workflow activity can nominate a candidate, but it cannot prove that the task finished or deserves a skill.

**Trust was the product boundary.** A self-editing system is easy to demo and hard to trust. Every proposal is staged, model output stays advisory, human-owned text is protected, and retirement means reversible archive rather than silent deletion.

## Accomplishments

- One zero-install demo replays proposal → human approval → later validation → duplicate suppression.
- The 27-case detector boundary evaluation reports 1.000 precision, 0.500 recall, and zero false positives; the public video shows the current 27-case suite. These are synthetic boundary results, not real-world impact.
- A 30-day real review parsed 213/213 Codex session files. GPT-5.6 reviewed 24 unique pseudonymous candidates, produced four evidence-citing recommendations, and proposed zero skill captures because completion evidence was insufficient.
- Review spans mechanical safeguards, existing tools, skills, and bounded rules while keeping every live mutation human-gated and reversible.

## What we learned

“Self-improving agent” is too vague. The model weights are not changing here; the procedural collaboration layer is.

Skill creation is only growth. Metabolism also requires future use, friction review, validation, repair, and subtraction. That lifecycle—not another generated skill—is the product.

## Demo video

The [public YouTube demo](https://youtu.be/egZhaFeDkRE) uses a 2:40 English voiceover and synthetic data. The production notes and timed captions are in [`DEMO_VIDEO.md`](DEMO_VIDEO.md) and [`demo-voiceover.en.srt`](demo-voiceover.en.srt).

## What's next

Models keep improving, and users keep learning how to work with them. The collaboration layer between them should grow too.

The next step is to let Codex propose a skill immediately after a human-confirmed difficult or recurring success, then let Metabolism follow that intervention through future sessions: did it reduce friction, need repair, or stop earning its cost? With stronger outcome evidence and longer opt-in evaluation, this loop could become a native Codex capability—personal without being opaque, adaptive without giving up human control.

## Submission checklist

The [OpenAI Build Week page](https://openai.devpost.com/) requires a working project using Codex with GPT-5.6, a public YouTube demo under three minutes, a testable repository, and the primary `/feedback` Session ID. Developer tools also need installation instructions, supported platforms, and a judge-ready test path.

- [x] Working local project.
- [x] Developer Tools category selected in project copy.
- [x] Setup instructions and sample data.
- [x] One-command isolated two-generation demo.
- [x] Supported-platform status stated honestly.
- [x] Independent Linux + Python 3.12 clean-clone verification completed.
- [x] Codex/GPT-5.6 contribution and human decisions documented.
- [x] English voiceover script, timed captions, and privacy-safe shot list prepared.
- [x] Publish repository: https://github.com/shihchengwei-lab/codex-metabolism
- [x] Upload the rendered video to public YouTube: https://youtu.be/egZhaFeDkRE
- [x] Enter the `/feedback` Codex Session ID in the organizer-only field.
- [x] Submit the Devpost project form.

Submission status was confirmed on Devpost on **July 20, 2026**: `Submitted`, with `5/5 steps done`. The listed deadline remains **July 21, 2026 at 5:00 PM Pacific Time**.
