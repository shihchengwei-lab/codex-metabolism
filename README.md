# Codex Metabolism

> **Everyone is building agent memory. We built agent metabolism.**

[繁體中文](README.zh-TW.md) · OpenAI Build Week track: **Developer Tools**

[![CI](https://github.com/shihchengwei-lab/codex-metabolism/actions/workflows/ci.yml/badge.svg)](https://github.com/shihchengwei-lab/codex-metabolism/actions/workflows/ci.yml)

**An evidence-driven lifecycle manager for the persistent interventions around Codex.** It turns recurring collaboration friction into the smallest useful change, checks that change against later sessions, and stages its retirement when it stops earning its cost.

Codex setups accumulate rules, skills, hooks, scripts, and tools. Codex Metabolism is **not another memory store, skill generator, or session dashboard**: it decides what deserves to be added, where it belongs, whether it worked, and whether it should remain. It **does not fine-tune or update model weights**. What becomes personal is the inspectable procedural environment around the model. **Same Codex, different metabolism.**

## One failure, metabolized

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
| Detector boundary | `python examples/run_detector_evaluation.py` | 24 labeled synthetic cases: precision `1.000`, recall `0.500`, zero false positives |

[Detector boundary evaluation](docs/EVALUATION.md) · [Devpost draft](docs/DEVPOST.md) · [Video production pack](docs/DEMO_VIDEO.md)

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

## What makes it different

A memory store decides what to remember. A generator drafts another skill. A dashboard explains the past. **Codex Metabolism manages the lifecycle of the intervention portfolio.**

| Layer | Use it when | Examples |
|---|---|---|
| `HARNESS` | prevention can be mechanical | hooks, tests, scripts, config |
| `TOOL` | an existing capability fits | installed tools, plugins, reviewed OSS |
| `SKILL` | the solution is a contextual workflow | procedures and tool sequences |
| `RULE` | bounded durable guidance is necessary | managed `AGENTS.md` region |

Five constraints keep it small: existing before new; mechanical before prose; evidence before permanence; subtraction counts as improvement; humans own every live mutation.

## The metabolic loop

```text
Codex collaboration sessions
          |
          v
manual review or opt-in scheduled trigger
          |
          v
failure -> correction -> same-command success in 2 sessions
          |
          v
necessity -> built-in -> installed -> repo -> external ecosystem
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

## Who it is for

Frequent Codex users and teams that accumulate rules, skills, hooks, scripts, and tools faster than they can evaluate them—especially anyone who has repeated the same correction or inherited stale customization.

## How Codex and GPT-5.6 built this

### Codex and GPT-5.6 contributions

Codex with GPT-5.6 inspected real local JSONL variants, separated hard evidence from inference, searched existing tools before implementation, wrote failing tests for each slice, and closed the receipt/evaluation/rollback loop. The primary build thread's `/feedback` Session ID is supplied in Devpost.

### Human product decisions

The human collaborator expanded metabolism beyond skills, required mechanical safeguards before prose, capped managed rules, protected human-owned `AGENTS.md`, chose synthetic public data, and retained explicit approval for every mutation.

The deterministic judge demo intentionally makes no model call. The optional advisor uses GPT-5.6 through existing Codex authentication and remains non-authoritative.

## Install and review local history

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
codex-metabolism review --days 7 --search-oss
```

On macOS/Linux, activate with `source .venv/bin/activate`. Review scans recent `~/.codex/sessions/`, installed skills, repo assets, and active `AGENTS.md` scopes. It writes proposals only under `.codex-metabolism/`; reuse that directory so `interventions.jsonl` can connect approved changes to later evidence.

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

[SkillReaper](https://github.com/thousandflowers/skillreaper) supplies complete skill lifecycle evidence; [codlogs](https://github.com/tobitege/codlogs) was evaluated as an existing session explorer; Hermes Agent inspired agent-managed skills. None is vendored.

## Optional live GPT-5.6 advisor

```powershell
codex-metabolism review --days 7 --advisor codex --advisor-model gpt-5.6-sol
```

The advisor is schema-bounded, read-only, and **non-authoritative**. A verified synthetic run took **48.5 seconds**: it agreed on `CREATE HARNESS`, challenged deterministic `PATCH RULE` with `KEEP RULE`, and could not bypass safety gates. Relevant bounded excerpts are sent to OpenAI only when this option is invoked.

## Evidence and safety contract

- JSONL is streamed with bounded excerpts; coverage failures stay unknown.
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
