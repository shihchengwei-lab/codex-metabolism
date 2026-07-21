# Codex Metabolism

> **Everyone is building agent memory. We built agent metabolism.**

[繁體中文](README.zh-TW.md) · OpenAI Build Week track: **Developer Tools**

[![CI](https://github.com/shihchengwei-lab/codex-metabolism/actions/workflows/ci.yml/badge.svg)](https://github.com/shihchengwei-lab/codex-metabolism/actions/workflows/ci.yml)

**A shared improvement loop for humans and coding agents.** Human and AI improve the collaboration layer together: completed, high-effort work can become a reusable workflow; future sessions reveal where that workflow or the surrounding environment still causes friction; review then proposes what to add, repair, keep, or retire.

Codex setups accumulate rules, skills, hooks, scripts, and tools. Codex Metabolism is **not another memory store, skill generator, or session dashboard**: it connects skill formation to later review and subtraction. It **does not fine-tune model weights**. What grows is the inspectable procedural environment shared by one person and their Agent. **Same Codex, different metabolism.**

## Model-assisted review (recommended)

```powershell
codex-metabolism review --days 7 --advisor codex
```

**GPT-5.6 interprets collaboration opportunities; deterministic code constrains the evidence and safety boundary; the human decides.** Alongside feedback and interruptions, substantial tool-use sessions become `workflow_candidate`s—possible reusable work, never claimed as completed tasks. GPT-5.6 can recommend capturing a reusable workflow as a `SKILL`, removing friction with a `HARNESS` or `TOOL`, using a bounded `RULE`, or doing nothing. Its output never becomes a live mutation.

## Deterministic fallback

```powershell
codex-metabolism review --days 7 --advisor none
```

This local-only mode reports coverage, hard signals, abstention reasons, and exact-pattern decisions without semantic interpretation. It is useful for privacy-sensitive or unauthenticated environments, but it is the fallback—not the complete product experience.

## One failure, metabolized — synthetic replay

**Before:** two sessions repeated the same failed `deploy production` command and the same user correction: run `preflight` first. A useful skill and `old-unused` both looked permanent.

**After review:** the adoption ladder prefers a mechanical fix and can stage a `PreToolUse` guard, keep the used skill, and nominate `old-unused` for reversible archive—**never auto-delete** it. Live state stays untouched until a person approves one decision.

**After later sessions:** two verified successes produce `KEEP HARNESS (VALIDATED)` and suppress a duplicate proposal. The environment improves by adding, testing, reinforcing, and withdrawing paths—not by accumulating forever.

## Judge quick start — under 60 seconds

Requirements: Python 3.11 or newer. **No installation, API key, Codex login, or personal session data is required.**

```bash
git clone https://github.com/shihchengwei-lab/codex-metabolism.git
cd codex-metabolism
python examples/run_closed_loop_demo.py
```

Expected proof:

```text
First review: CREATE HARNESS + PATCH RULE
Second review: KEEP HARNESS (VALIDATED)
```

The command uses isolated synthetic fixtures and prints the retained artifact path. It neither reads nor changes real sessions, skills, hooks, or `AGENTS.md` files.

![Codex Metabolism judge demo: observe, intervene, evaluate, and prune](docs/assets/judge-demo.png)

## Evidence at a glance

| Evidence | Reproduce | What it establishes |
|---|---|---|
| Closed-loop replay | command above | first proposal, explicit approval in an isolated copy, later validation, duplicate suppression |
| Cross-layer replay | `python examples/run_friction_cases_demo.py` | existing tool and contextual skill paths—not only command-order rules |
| Imperfect evidence | `python examples/run_messy_evidence_demo.py` | action once, abstain twice, expose parser coverage, block unsafe retirement |
| Detector boundary | `python examples/run_detector_evaluation.py` | 27 labeled synthetic cases: precision `1.000`, recall `0.500`, zero false positives |
| Real-session review | [aggregate report](docs/REAL_SESSION_REVIEW.md) | 213/213 files parsed; friction observed; zero unsupported changes |

[Detector boundary evaluation](docs/EVALUATION.md) · [Real-session review](docs/REAL_SESSION_REVIEW.md) · [Devpost draft](docs/DEVPOST.md) · [Video production pack](docs/DEMO_VIDEO.md)

## Two more real-world friction patterns

The secondary command above uses **anonymized synthetic replays** and prints:

```text
Existing-tool friction: PATCH TOOL -> tobitege/codlogs
Visual-proof friction: PATCH SKILL -> ui-verification
```

Neither case is a command-order rule: one reuses a reviewed session tool instead of rebuilding it; the other patches `$ui-verification` after tests passed without rendered UI evidence.

## Imperfect-data pressure test

The noisy six-session replay prints:

```text
Messy evidence: 1 decision, 2 abstentions
Coverage warning: 1 malformed JSONL line
Unsafe retirement decisions: 0
```

It mixes wording changes, unrelated successes, incomplete recovery, malformed JSONL, a catalog distractor, and incomplete lifecycle evidence. It **does not claim semantic clustering**; unsupported cases produce no decision.

The replay also writes `friction-evidence.csv`: one decision and two explicit abstentions, with deterministic references and coverage fields but no raw prompts, evidence summaries, session IDs, or local paths. In an ordinary review, `--export-evidence` exports emitted decisions only; this challenge replay passes its already-computed abstentions to the exporter, which does not infer a fifth decision type.

## What makes it different

A memory store decides what to remember. A generator drafts another skill. A dashboard explains the past. **Codex Metabolism manages the lifecycle of the intervention portfolio.**

| Layer | Use it when | Examples |
|---|---|---|
| `HARNESS` | prevention can be mechanical | hooks, tests, scripts, config |
| `TOOL` | an existing capability fits | installed tools, plugins, reviewed OSS |
| `SKILL` | the solution is a contextual workflow | procedures and tool sequences |
| `RULE` | bounded durable guidance is necessary | managed `AGENTS.md` region |

Five constraints keep it small: existing before new; mechanical before prose; evidence before permanence; subtraction counts as improvement; humans own every live mutation.

## The human–AI metabolic loop

```text
human + Codex complete work
          |
          v
reusable workflow candidate -> proposed SKILL
          |
          v
future sessions -> use, feedback, interruption, recovery
          |
          v
manual review or opt-in scheduled trigger
          |
          v
GPT-5.6 review -> necessity -> built-in -> installed -> repo -> ecosystem
          |
          v
CREATE / PATCH / KEEP / RETIRE_CANDIDATE
          |
          v
stage evidence + exact artifact -> explicit human approval
          |
          v
future sessions -> VALIDATED / INEFFECTIVE / IDLE_CANDIDATE
          +-----------------------> keep / repair / rollback / archive
```

Parser failure is never re-labelled as non-use. Later silence is not proof of quality. The detector is deliberately conservative; the metabolic contribution is the inspectable evidence → intervention → later evaluation chain around it.

**Current boundary:** ordinary real-session reviews provide observation, abstention reasons, review guidance, and staged recommendations. The full loop below is implemented as lifecycle machinery and demonstrated by synthetic replay; long-term real-world validation remains future work.

## Who it is for

Frequent Codex users and teams that accumulate rules, skills, hooks, scripts, and tools faster than they can evaluate them—especially anyone who has repeated the same correction or inherited stale customization.

## How Codex and GPT-5.6 built this

### Codex and GPT-5.6 contributions

Codex with GPT-5.6 inspected real local JSONL variants, separated hard evidence from inference, searched existing tools before implementation, wrote failing tests for each slice, and closed the receipt/evaluation/rollback loop. The primary build thread's `/feedback` Session ID is supplied in Devpost.

### Human product decisions

The human collaborator expanded metabolism beyond skills, required mechanical safeguards before prose, capped managed rules, protected human-owned `AGENTS.md`, chose synthetic public data, and retained explicit approval for every mutation.

The deterministic judge demo intentionally makes no model call. This lets judges reproduce the lifecycle without authentication. Real model-assisted review uses GPT-5.6 through existing Codex authentication and remains non-authoritative.

## Install and review local history

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
codex-metabolism review --days 7 --advisor codex --export-evidence friction-evidence.csv
```

On macOS/Linux, activate with `source .venv/bin/activate`. Review scans recent `~/.codex/sessions/`, installed skills, repo assets, and active `AGENTS.md` scopes. The report shows the full friction-detection funnel—including feedback candidates, failures, recoveries, recognized corrections, and recurring patterns—so zero qualifying patterns is never presented as zero friction. It writes proposals only under `.codex-metabolism/`; reuse that directory so `interventions.jsonl` can connect approved changes to later evidence. `--export-evidence` is optional and exports only emitted decisions as structured, anonymized review evidence.

## Keep the loop running — opt in

**No schedule is installed by default.** Opt in once:

```powershell
codex-metabolism enable --every-days 7 --after-sessions 10
codex-metabolism status
codex-metabolism disable
```

Windows uses Windows Task Scheduler, macOS uses `launchd`, and Linux uses a systemd user timer. The artifacts are `.codex-metabolism/automation/run-scheduled-review.cmd`, `~/Library/LaunchAgents/`, and `~/.config/systemd/user/`; inspect `config.json`, `heartbeat.json`, and `NOTICE.md` locally.

The daily check requires at least one new session and either ten new sessions or seven days. **With no prior staged review, sessions from before the first enable are not counted as new.** Automation may **Observe, Decide, and Stage** but will **never Apply**, install, activate, archive, or delete. The GPT-5.6 advisor stays off and `--search-oss` remains off unless explicitly enabled.

`status` returns non-zero for `unregistered`, `error`, or `overdue`. A process that never starts cannot report itself, so OS scheduler history remains the external health check.

## `AGENTS.md` ownership boundary

The whole active user/project/nested portfolio is evaluated, but only a pre-existing valid region is machine-editable after approval:

```markdown
<!-- codex-metabolism:managed-start -->
- Keep this managed rules list bounded.
<!-- codex-metabolism:managed-end -->
```

Everything outside the markers is suggestion-only. Apply is full-file SHA-256 gated, malformed markers disable writing, the managed region is capped at ten directives, and changes are reversible. The real Codex filename is `AGENTS.md`, not `AGENT.md`.

## Human approval commands

```powershell
codex-metabolism apply <decision-id> --project-root .
codex-metabolism activate-harness <decision-id> --confirmed-trusted
codex-metabolism rollback <original-decision-id> --project-root .
codex-metabolism archive <decision-id>
codex-metabolism restore <original-decision-id>
codex-metabolism activate-tool <decision-id> --artifact <existing-path-or-command>
codex-metabolism retire-tool <decision-id> --confirmed-inactive
codex-metabolism reject <decision-id>
```

External tools are never downloaded, installed, disabled, or deleted automatically. New hooks remain `PENDING_TRUST` until reviewed with Codex `/hooks`.

## The adoption ladder

Every creation proposal records: necessity → Codex built-in → installed → repository → ecosystem. An unchecked ecosystem rung leaves a new `CREATE` as `needs_research`. `--search-oss` sends sanitized allowlisted keywords—not transcripts, paths, or credentials.

[SkillReaper](https://github.com/thousandflowers/skillreaper) supplies complete skill lifecycle evidence; [codlogs](https://github.com/tobitege/codlogs) was evaluated as an existing session explorer. The bounded semantic packet adapts the role-scoped sampling and privacy boundary from the author's MIT-licensed [session-analytics](https://github.com/shihchengwei-lab/session-analytics). None is vendored.

The original inspirations were Hermes Agent's agent-managed skill creation, Claude Code Insights' session-level retrospective analysis, and session-analytics' evidence-based workflow review and pruning. SkillReaper was discovered later through the adoption ladder and is an integration, not an original inspiration.

## Model-assisted safety contract

The GPT-5.6 interpreter is schema-bounded, ephemeral, read-only, and **non-authoritative**. It performs two jobs: challenge proposed deterministic changes, and analyze up to 24 bounded, pseudonymous workflow/friction candidates even when the strict detector abstains. GPT-5.6 may return at most eight evidence-citing recommendations; they remain separate from `CREATE`/`PATCH` decisions and cannot mutate live state. A verified synthetic run took **48.5 seconds**: it agreed on `CREATE HARNESS`, challenged deterministic `PATCH RULE` with `KEEP RULE`, and could not bypass safety gates. Relevant bounded excerpts are sent to OpenAI only when model-assisted review is explicitly invoked, and the CLI prints that disclosure before the call.

## Evidence and safety contract

- JSONL is streamed with bounded excerpts; coverage failures stay unknown.
- Substantial tool activity may nominate a reusable workflow, but cannot prove task completion; feedback and interrupted turns are weak friction candidates. None can create or patch an intervention by themselves.
- GPT-5.6 semantic recommendations require cited candidate IDs and `human_review_required=true`; they never become decisions automatically.
- Recurring friction requires two corrected same-command recoveries; no correction means abstain.
- The demonstration guard permits only the exact reviewed `required && protected` sequence.
- Review is stage-only; mutations are decision-ID and hash gated.
- Retirement remains a candidate until human approval; skills are archived, never deleted.
- Synthetic results are not presented as real-user impact or causal validation.

## Development and verification

```powershell
python -m unittest discover -s tests -v
python examples/run_detector_evaluation.py
python -m build
```

CI runs Python 3.11/3.12 on Ubuntu and Windows, all public demos, the detector evaluation, and package build.

## Supported platforms

- **Windows, Python 3.12:** verified in this checkout and from a clean public clone.
- **Linux, Python 3.12:** independently verified from a clean clone; the closed-loop demo and full test suite passed.
- **macOS, Python 3.11+:** designed for standard-library portability, not yet verified.

## License

MIT. External projects retain their own licenses and are not vendored here.
