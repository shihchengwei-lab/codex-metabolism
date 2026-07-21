# Codex Metabolism

> **Agent thinks; the runtime remembers and constrains.**

[繁體中文](README.zh-TW.md) · OpenAI Build Week: **Developer Tools** · [MIT](LICENSE)

[![CI](https://github.com/shihchengwei-lab/codex-metabolism/actions/workflows/ci.yml/badge.svg)](https://github.com/shihchengwei-lab/codex-metabolism/actions/workflows/ci.yml)

Codex is good at solving the task in front of it. Over time, however, its collaboration environment accumulates skills, rules, scripts, hooks, and one-off fixes. Useful paths become hard to find, stale paths remain forever, and the same human correction can return in another session.

**Codex Metabolism is an Agent Skill for improving that collaboration layer.** The active Codex Agent reads bounded evidence from recent sessions, recognizes reusable work and recurring friction, searches for existing capabilities, and authors the smallest suitable improvement. A small standard-library runtime preserves evidence and convergent target histories, binds approval to exact proposal bytes, and directly manages only the Skill mutations it can safely reverse.

**Codex owns semantic interpretation and artifact design; the runtime owns evidence boundaries, persistence, and safe mutation. The human owns the gate.**

## Why is there a program at all?

The Python runtime does not replace an AI capability. It removes three kinds of work that an Agent should not have to improvise every time:

- **Cross-session eyes:** stream changing JSONL logs into bounded, ordered, redacted evidence capsules while keeping parse gaps unknown.
- **A durable ledger:** carry each target's reasoning, expected effect, rollback condition, evidence, and status history across sessions.
- **Safe hands:** reject invented evidence, path escapes, stale targets, and proposal or artifact changes after approval; write atomically and preserve Skill rollback copies.

Without the Agent, this runtime cannot decide that two differently worded sessions express the same problem. Without the runtime, the Agent would have to handle raw logs, mutable files, provenance, and rollback from scratch. The product is the pair.

## Use it

Requirements: Python 3.11+ and Codex.

```powershell
git clone https://github.com/shihchengwei-lab/codex-metabolism "$HOME/.codex/skills/codex-metabolism"
python -m pip install -e "$HOME/.codex/skills/codex-metabolism"
```

Cloning into the Codex skills directory installs the product surface; the `pip` step installs its runtime command. Installing the Python wheel alone provides only the substrate, not skill discovery.

Restart Codex so it discovers the skill, then ask naturally:

```text
Use $codex-metabolism to review my last 7 days of collaboration.
Find reusable successful workflows and recurring friction, check existing
capabilities before creating anything, and show me every proposed diff.
Do not apply changes until I approve them.
```

Codex will:

1. run `codex-metabolism observe` to prepare neutral evidence;
2. interpret task intent, feedback, interruptions, tool trajectories, and portfolio state;
3. check Codex built-ins, installed capabilities, repository assets, and relevant external tools;
4. author zero to three evidence-linked proposals and their complete artifacts;
5. run `codex-metabolism stage` to validate and seal them;
6. show the evidence, uncertainty, expected effect, rollback condition, exact diff, and generated approval digest;
7. wait for explicit human approval before any live mutation.

After the first user-initiated review, the Skill offers one optional convenience: a **native Scheduled task** shortly before your **weekly usage reset**. You provide the reset time because the tool cannot infer it reliably. The scheduled run may prepare and stage a review, but it cannot apply, record, retire, commit, or push anything; findings wait in the Scheduled inbox for an interactive human decision. See the [stage-only task prompt](references/scheduled-review.md).

## The metabolic loop

```text
recent sessions + collaboration portfolio
                  |
                  v
       runtime prepares neutral evidence
                  |
                  v
     active Codex interprets and authors
                  |
                  v
       runtime validates and seals exact bytes
                  |
                  v
           human reviews the diff
                  |
                  v
       approved apply / record / archive
                  |
                  v
       receipt enters the next review ----+
                  ^                       |
                  +--- keep / repair / rollback
```

This is why the slime-mold metaphor matters. Later evidence returns beside the original success condition and withdrawal condition, so Codex and the human can reinforce, repair, or retire the same path instead of merely adding another one. **Everyone else can keep doing addition. Metabolism adds selection, validation, and subtraction.**

![Agent-first Codex Metabolism loop: Codex interprets and authors, the runtime validates, and the human approves](docs/assets/agent-first-loop.svg)

## 60-second isolated demo

No API key, Codex login, or personal session data is required:

```bash
python examples/run_agent_first_demo.py
```

The demo uses two synthetic session capsules and a clearly labeled, recorded Codex-authored fixture. It demonstrates the responsibility boundary, not model quality:

```text
Runtime interpretation: 0 semantic decisions
Recorded Codex fixture: CREATE SKILL deploy-safely
Human gate fixture: the exact displayed digest was approved
Receipt visible to the next review: ACTIVE
Rollback: live skill archived, not deleted
```

The two sessions deliberately use different commands and corrections. The fixture represents the semantic grouping Codex performs; the runtime merely validates cited evidence and preserves the exact artifact.

To put the AI role on screen, prepare only the neutral packet and give the printed prompt to the active Codex Agent:

```bash
python examples/run_agent_first_demo.py --prepare-only --output-root .demo-live
```

In a [fresh-Agent forward test](docs/FORWARD_TEST.md), an unfamiliar Codex Agent inspected the synthetic target, rejected the fixture's skill-shaped answer, and authored a smaller `PATCH / HARNESS` with a concrete patch that passed `git apply --check`. The runtime staged it and left the target unchanged.

## Real-session evaluation

The synthetic demo remains the fastest reproducible safety check. A separate public case study uses **real Codex sessions** from one seven-day window, with raw logs kept local and only manually paraphrased evidence committed:

```bash
python examples/run_real_session_evaluation.py
```

That run parsed 14/14 rollout files and found only six independent sessions: eight child-Agent fork/snapshot files and 210 dual-serialized user events had been inflating the evidence. It also exposed more than two thousand events in one session. The resulting runtime patch collapses those duplicates, accepts only explicit user-message sources, caps every session capsule at 160 events, and reports all sampling. The Agent then recommended one native scheduling patch and one honest no-change result because an existing rule already covered the observed behavior. Read the [method and claim boundary](docs/REAL_SESSION_EVALUATION.md).

## What can change?

| Layer | Who implements it after approval? | Examples |
|---|---|---|
| `SKILL` | sealed runtime apply | complete `SKILL.md` creation, patch, or reversible retirement |
| `HARNESS` | existing Git/repository mechanism, then evidence receipt | tests, hooks, scripts, configuration |
| `TOOL` | existing package/plugin/platform mechanism, then evidence receipt | adoption, configuration, enable, or disable |
| `RULE` | existing managed-region/Git mechanism, then evidence receipt | a small, bounded `AGENTS.md` change or retirement |

The runtime never installs an external tool or edits a non-skill artifact on its own. For those layers, Codex uses the existing mechanism, verifies the outcome, and gives `codex-metabolism record` a concise implementation-evidence file. The receipt preserves both the reviewed proposal hash and the resulting evidence hash, with CREATE/PATCH recorded as `ACTIVE` and retirement as `RETIRED`.

## CLI substrate

Most users should invoke the skill. These commands are the deterministic substrate it uses:

```text
observe   prepare bounded evidence; make no semantic decisions
stage     validate evidence, seal artifacts, and generate an approval digest
apply     apply one approved sealed skill change
record    preserve evidence from an approved non-skill change
reject    reject a staged proposal without touching live state
rollback  reverse an approved active skill change
restore   restore an approved retired skill
```

`apply` and `record` require the exact digest displayed with the reviewed version. Changing either proposal fields or artifact bytes invalidates that approval. A CLI cannot authenticate that the caller is human, so the Skill still requires Codex to wait for explicit approval in the conversation. See [the proposal schema](references/proposal-schema.md) for the complete contract.

## Safety and privacy boundary

- The runtime has **zero third-party dependencies** and never invokes another model.
- The active Codex session is the semantic engine; there is no nested advisor Agent.
- Evidence contains bounded excerpts with known paths and common secret patterns redacted. It is **not guaranteed anonymous**; inspect `.codex-metabolism/evidence.json` before sharing it.
- Parser gaps remain unknown. A missing event is never relabeled as non-use.
- Tool success and later silence are evidence, not proof of task success or intervention quality.
- Proposals must cite current evidence IDs; creation must record the existing-capability search.
- Skill apply is target-, hash-, and exact-artifact-gated. Retirement archives instead of deleting.
- A review is not approval. Apply and record bind the user's approval to one digest; rollback and restore still require an explicit approval assertion.
- One output directory is currently single-writer; do not run lifecycle mutations concurrently against the same ledger.

## Current boundary

Implemented today: neutral observation with fork/event deduplication and disclosed sampling, valid zero-change reviews, Agent-authored proposal validation, approval-digest binding, human-gated Skill lifecycle, action-accurate non-skill receipts, convergent target histories, reversible Skill archives, and an opt-in native scheduled-review prompt.

Not yet established: real-world precision/recall, causal improvement, automatic evaluation of an intervention, or long-term impact. A later Codex review can interpret new evidence and receipts, but **silence is not success** and the runtime does not manufacture a verdict.

This resembles unsupervised adaptation at the collaboration layer, but it is not model training. The model weights do not change; the human and Agent curate an inspectable procedural environment together.

## Development

```powershell
python -m unittest discover -s tests -v
python examples/run_agent_first_demo.py
python examples/run_real_session_evaluation.py
python -m build
```

CI runs the tests, demo, and package build on Python 3.11/3.12 for Ubuntu and Windows.

## Inspiration

The original inspirations were Hermes Agent's agent-managed skill creation, Claude Code Insights' session retrospectives, and the author's MIT-licensed [session-analytics](https://github.com/shihchengwei-lab/session-analytics) project. Codex Metabolism combines their missing halves: Agent-authored procedural memory, retrospective evidence, and deliberate pruning. It reimplements the mechanism and does not vendor their code.

## License

MIT. External tools retain their own licenses.
