# Codex Metabolism

> **Everyone is building agent memory. We built agent metabolism.**

[繁體中文](README.zh-TW.md) · OpenAI Build Week track: **Developer Tools**

**An evidence-driven lifecycle manager for the persistent interventions around Codex.** It turns recurring collaboration friction into the smallest useful change, checks that change against later sessions, and stages its retirement when it stops earning its cost.

Codex setups learn by accumulating rules, skills, hooks, scripts, and tools. That can make them more capable, but it can also create duplicated guidance, stale workflows, and permanent context cost. Codex Metabolism is **not another memory store, skill generator, or session dashboard**. It manages what should be added, where it should live, whether it worked, and whether it still deserves to remain.

It **does not fine-tune or update model weights**. What becomes personal is the inspectable procedural environment around the model: the safeguards, tools, workflows, and bounded guidance supported by a person's real friction. **Same Codex, different metabolism.**

## One failure, metabolized

**Before:** two sessions repeated the same failed `deploy production` command and the same user correction: run `preflight` first. Meanwhile, a useful skill and an `old-unused` skill occupied the same permanent-looking toolbox.

**After review:** the adoption ladder finds that prose is not the cheapest fix. Codex Metabolism can stage a `PreToolUse` guard that prevents the command-order mistake mechanically, keep the used skill, and mark `old-unused` as an archive candidate—never auto-delete it. Nothing touches live state until a person reviews the evidence and approves one decision.

**After later sessions:** two verified successes validate the guard, its receipt suppresses a duplicate proposal, and the next review returns `KEEP HARNESS (VALIDATED)`. The result is not simply more memory: repeated friction goes down while stale collaboration structure becomes removable.

## Judge quick start — under 60 seconds

Requirements: Python 3.11 or newer. No installation, API key, Codex login, or personal session data is required.

```bash
git clone https://github.com/shihchengwei-lab/codex-metabolism.git
cd codex-metabolism
python examples/run_closed_loop_demo.py
```

Expected proof of the two-generation loop:

```text
First review: CREATE HARNESS + PATCH RULE
Second review: KEEP HARNESS (VALIDATED)
```

The command copies synthetic fixtures into an isolated retained temporary directory, applies only to that copy, and prints the artifact path for inspection. It neither reads nor changes real Codex sessions, skills, hooks, or `AGENTS.md` files.

![Codex Metabolism judge demo: a zero-install terminal run closes the observe, adopt, evaluate, and prune loop](docs/assets/judge-demo.png)

[Editable SVG source](docs/assets/judge-demo.svg)

## Two more real-world friction patterns

The deployment story is deliberately small enough for a three-minute demo, but command order is not the product boundary. This secondary zero-install replay covers two recurring collaboration corrections. The public inputs are **anonymized synthetic replays**, not exported private sessions.

```bash
python examples/run_friction_cases_demo.py
```

Expected result:

```text
Existing-tool friction: PATCH TOOL -> tobitege/codlogs
Visual-proof friction: PATCH SKILL -> ui-verification
```

1. **Existing tool before reinvention:** Codex starts building another session explorer. The user redirects it to the already reviewed `codlogs` project. Metabolism climbs the adoption ladder and stages a `TOOL` adoption plan rather than another implementation.
2. **Tests are not visual proof:** Codex reports a dashboard complete after tests pass without inspecting the rendered UI. The same correction recurs, so Metabolism proposes patching the installed `$ui-verification` workflow with screenshot evidence.

Neither case is a command-order rule: both are repeated failure → correction → verified recovery patterns, routed to the existing intervention that best matches the evidence. The command retains an isolated temporary directory so judges can inspect the four synthetic JSONL sessions, `decisions.json`, evidence excerpts, and staged proposals.

## Imperfect-data pressure test

The golden demos above prove reproducibility, but their evidence is intentionally clean. This separate, hand-authored synthetic challenge tests the more important failure mode: whether noisy evidence makes the system overreact.

```bash
python examples/run_messy_evidence_demo.py
```

Expected result:

```text
Messy evidence: 1 decision, 2 abstentions
Actioned: PATCH TOOL -> tobitege/codlogs
Abstained: publish package -> only 1 verified recovery session
Abstained: review flaky tests -> repeated failures but no verified recovery path
Coverage warning: 1 malformed JSONL line; skill invocation evidence is partial and lifecycle evidence is incomplete
Unsafe retirement decisions: 0
```

The six-session fixture mixes differently worded corrections, unrelated successful commands, a one-off recovery, repeated failures without same-session recovery, a success in the wrong session, one malformed JSONL line, a high-star catalog distractor, and an old skill backed by an incomplete lifecycle report. Only the pattern with two verified recovery sessions crosses the action threshold. The popular-but-weak catalog match loses to the more relevant reviewed tool, and incomplete coverage cannot become a retirement proposal.

`ABSTAIN` is not smuggled in as a fifth decision type: these are cases for which the core emits no decision. The retained `challenge-results.json` makes those non-actions and their observed counts inspectable. This synthetic challenge **does not claim semantic clustering** or real-world outcome validation; recurring commands still use normalized exact signatures. Its narrower claim is testable: imperfect input produces one supported action and conservative non-action everywhere else.

## What makes it different

A memory store decides what to remember. A skill generator drafts reusable workflows. A session dashboard explains what happened. **Codex Metabolism manages the lifecycle of the entire intervention portfolio.**

It routes each recurring friction signal across four layers instead of assuming every answer is another rule or skill:

| Layer | Use it when | Examples |
|---|---|---|
| `HARNESS` | The failure can be prevented mechanically | hooks, tests, scripts, config, permissions |
| `TOOL` | An existing capability can do the job | installed tools, plugins, CLIs, reviewed open source |
| `SKILL` | The solution is a reusable contextual workflow | procedures, decision paths, tool sequences |
| `RULE` | Codex needs durable bounded guidance | the managed region in `AGENTS.md` |

The lifecycle follows five constraints:

- **Existing before new:** check necessity, Codex built-ins, installed capabilities, repository assets, and the external ecosystem before creating anything.
- **Mechanical before prose:** prefer an enforceable check over another instruction when both solve the same problem.
- **Evidence before permanence:** connect each approved intervention to later matching opportunities through a local receipt ledger.
- **Subtraction is improvement:** keep, repair, roll back, or retire an intervention according to later evidence and context cost.
- **Humans own live state:** review stages evidence and diffs; one explicit approval is required for each mutation.

## The metabolic loop

```text
Codex collaboration sessions
          |
          v
manual review or opt-in scheduled trigger
          |
          v
observe evidence + parser coverage + current intervention receipts
          |
          v
necessity -> Codex built-in -> installed -> repo -> external ecosystem
          |
          v
CREATE / PATCH / KEEP / RETIRE_CANDIDATE
          |
          v
stage evidence + artifact or bounded recommendation
          |
          v
explicit human approval
          |
          v
future sessions -> VALIDATED / INEFFECTIVE / IDLE_CANDIDATE
          |
          +--------------------------> keep / repair / rollback / archive
```

An active intervention suppresses duplicate creation. Two later matching successes can validate it; two later matching failures nominate a patch. At least 28 days and ten later sessions without a matching opportunity can produce only a low-confidence retirement candidate. Silence is never treated as proof of quality, and parser failure is never re-labelled as non-use.

The durable product asset is not raw session history. It is an inspectable chain of evidence:

```text
friction signature -> chosen intervention -> later opportunity -> observed outcome
```

That chain lets the collaboration environment become more fitted without becoming an opaque personalized model or an ever-growing rule pile.

## Who it is for

Codex Metabolism is for developers and teams whose Codex setup accumulates rules, skills, hooks, scripts, and tools faster than anyone can evaluate them. The strongest fit is a frequent Codex user who has already typed the same correction twice, inherited stale customization, or watched a useful workaround harden into permanent context.

## How Codex and GPT-5.6 built this

### Codex and GPT-5.6 contributions

The primary build thread used Codex with GPT-5.6 to inspect real local JSONL variants, separate hard signals from inference, search for existing open-source components before building, write failing tests for each implementation slice, and close the receipt/evaluation/rollback loop. The required `/feedback` Session ID for that thread will be supplied directly in the Devpost submission.

### Human product decisions

The human collaborator chose the product boundaries: expand metabolism beyond skills, prefer mechanical safeguards over more prose, search installed and external tools before creating anything, cap managed rules, preserve human-owned `AGENTS.md` content, use synthetic public data, and require explicit approval at every mutation boundary.

### Runtime boundary

The deterministic judge demo intentionally makes no model call. It proves the closed loop reproducibly with synthetic fixtures. The separate `--advisor codex` option can request a bounded GPT-5.6 second opinion through the user's existing Codex authentication; the verified default is `gpt-5.6-sol`. That advice is non-authoritative and cannot bypass deterministic safety gates.

See [the Devpost submission draft](docs/DEVPOST.md) and [the English video production pack](docs/DEMO_VIDEO.md) for the build story and demo plan.

## Public deterministic demo

Requirements: Python 3.11 or newer. The core has no third-party runtime dependencies.

```powershell
python -m codex_metabolism review --days 7 `
  --codex-home examples/demo-home/.codex `
  --skill-root examples/demo-home/.agents/skills `
  --project-root examples/demo-project `
  --catalog-file examples/reviewed-catalog.json `
  --skillreaper-report examples/skillreaper-report.json `
  --output-dir .demo-review `
  --now 2026-07-20T12:00:00+00:00
```

Bash/zsh equivalent:

```bash
python -m codex_metabolism review --days 7 \
  --codex-home examples/demo-home/.codex \
  --skill-root examples/demo-home/.agents/skills \
  --project-root examples/demo-project \
  --catalog-file examples/reviewed-catalog.json \
  --skillreaper-report examples/skillreaper-report.json \
  --output-dir .demo-review \
  --now 2026-07-20T12:00:00+00:00
```

Expected result:

```text
Staged 4 decisions (4 ready, 0 needs research) at .demo-review
```

The synthetic, private-data-free scenario produces:

- `CREATE HARNESS`: stage a narrow `PreToolUse` guard for repeated deployment friction.
- `PATCH RULE`: evaluate the entire demo `AGENTS.md`, stage a managed-region-only diff, and leave human-owned content untouched.
- `KEEP SKILL`: retain `healthy-skill` from positive SkillReaper evidence.
- `RETIRE_CANDIDATE SKILL`: nominate `old-unused` from complete lifecycle evidence; review moves or deletes nothing.

Open `.demo-review/report.md`, `decisions.json`, and the proposal directories to inspect the evidence and diffs.

To replay the actual two-generation loop in an isolated retained temporary directory, run:

```powershell
python examples/run_closed_loop_demo.py
```

It performs the first review, applies the staged harness and managed-region patch only inside the copied demo project, records the explicit hook-trust confirmation step, adds two later successful synthetic sessions, and runs review again. The final output must include `Second review: KEEP HARNESS (VALIDATED)`. Because this is an isolated synthetic replay, it does not alter Codex's real hook trust store.

## Install and review local history

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
codex-metabolism review --days 7 --search-oss
```

On macOS or Linux, activate with `source .venv/bin/activate`.

By default, review scans recent `~/.codex/sessions/`, installed skills, the current repository's mechanical assets, and active `AGENTS.md` scopes. It writes staged output only under `.codex-metabolism/`:

```text
.codex-metabolism/
├── report.md
├── decisions.json
├── interventions.jsonl
├── proposed-adoptions/
├── proposed-harness/
├── proposed-rules/
└── proposed-skills/
```

Reuse the same output directory across reviews. `interventions.jsonl` is the local receipt ledger that connects an approved change to later session evidence.

## Keep the loop running — opt in

A manual review loop still fails if the user has to remember it. **No schedule is installed by default.** After one explicit opt-in, Codex Metabolism installs a native user-level schedule:

```powershell
codex-metabolism enable --every-days 7 --after-sessions 10
codex-metabolism status
codex-metabolism disable
```

| Platform | Native backend | Installed scheduler artifact |
|---|---|---|
| Windows | Windows Task Scheduler | `.codex-metabolism/automation/run-scheduled-review.cmd` |
| macOS | `launchd` agent | `~/Library/LaunchAgents/<schedule-id>.plist` |
| Linux | systemd user timer | `~/.config/systemd/user/<schedule-id>.service` and `.timer` |

The schedule checks once per day, but it runs a review only when at least one new Codex session exists and either threshold is reached: ten new sessions, or seven days since the last successful review. With no new sessions it records an idle heartbeat and does not run analysis. A previous staged review provides the initial time anchor when available; otherwise the first enable time is the anchor. **With no prior staged review, sessions from before the first enable are not counted as new.**

Automation preserves the same trust boundary as an interactive review. It may automatically **Observe, Decide, and Stage**; it will **never Apply**, activate a hook, install a tool, rewrite live guidance, archive a skill, or delete anything. It uses the deterministic router, does not enable the GPT-5.6 advisor, and `--search-oss` remains off unless the user explicitly adds that flag to `enable`.

State is inspectable under `.codex-metabolism/automation/`:

```text
automation/
├── config.json       # thresholds and the exact staged-review command
├── heartbeat.json    # last check, last success, backlog, and last error
└── NOTICE.md         # latest staged-review notice, after a review runs
```

The native scheduler artifacts live at the platform paths shown above. `launchd` writes stdout and stderr logs into the automation directory; systemd execution history remains in the user journal, and Windows execution history remains in Task Scheduler.

`codex-metabolism status` verifies that the native schedule is still registered. A missing schedule, a failed review, or a heartbeat older than 48 hours is reported as `unregistered`, `error`, or `overdue`; the command exits non-zero for those unhealthy states. Successful manual reviews refresh the same heartbeat, so the scheduler does not immediately repeat work. Local OS notifications are best-effort and can be disabled with `--no-notify`.

`disable` removes the native schedule but retains configuration and heartbeat files as an audit trail. Re-enabling is explicit. Because a process that never starts cannot report its own failure, `status` and the operating system's scheduler history remain the external health checks.

## `AGENTS.md` ownership boundary

Codex Metabolism inventories and evaluates the whole active `AGENTS.md` portfolio: user, project, and nested scopes. It reports the file hash, size, line count, estimated directive count, duplicate guidance, recurrent friction despite guidance, and context-budget pressure.

Only a pre-existing, valid managed region is machine-editable:

```markdown
<!-- codex-metabolism:managed-start -->
- Keep this managed rules list bounded.
<!-- codex-metabolism:managed-end -->
```

The boundary is strict:

- Review never modifies a live file.
- An approved `apply` may replace only bytes between one valid marker pair.
- Everything outside the markers is recommendation-only.
- The full-file SHA-256 must still match the reviewed version.
- Missing, duplicate, nested, non-standalone, or reordered markers disable direct apply.
- The managed region has a maximum of ten rule directives; each new-rule proposal is bounded to three recommendations.
- If no managed region exists, the tool suggests adding one but does not insert it.
- Managed-region changes have receipts and can be rolled back.

This uses Codex's real filename, `AGENTS.md`, and follows its user, repository, and nested-scope model. See the official [Codex `AGENTS.md` documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Human approval commands

Review the staged evidence and exact artifact before running a lifecycle command.

```powershell
# Apply a staged harness, skill patch, or valid AGENTS.md managed-region patch
codex-metabolism apply <decision-id> --project-root .

# Project hooks remain pending until you review/trust them with Codex `/hooks`;
# then explicitly begin evidence evaluation
codex-metabolism activate-harness <decision-id> --confirmed-trusted

# Revert an active harness, skill change, or managed-region change
codex-metabolism rollback <original-decision-id> --project-root .

# Archive and restore a skill retirement candidate
codex-metabolism archive <decision-id>
codex-metabolism restore <original-decision-id>

# After manually reviewing and installing an external tool, start evaluation
codex-metabolism activate-tool <decision-id> --artifact <existing-path-or-command>

# After manually disabling or uninstalling an idle external tool, record retirement
codex-metabolism retire-tool <retirement-decision-id> --confirmed-inactive

codex-metabolism reject <decision-id>
```

External projects are never downloaded, executed, installed, disabled, or deleted by Codex Metabolism. `activate-tool` verifies an existing artifact and records it; `retire-tool` records the user's confirmed action while leaving the artifact untouched.

New or changed Codex project hooks are also not assumed active merely because files were written. `apply` records them as `PENDING_TRUST`; after the user reviews and trusts the hook with Codex `/hooks`, `activate-harness` changes the receipt to `ACTIVE`. This mirrors the official [Codex hooks trust flow](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).

## The adoption ladder

Every creation proposal records five rungs:

1. **Necessity** — did the same problem recur in at least two sessions with a verifiable recovery?
2. **Codex built-in** — can a native hook, skill, config, or other supported capability solve it?
3. **Installed** — is a suitable tool, plugin, skill, or dependency already present?
4. **Repository** — is there an existing hook, test, script, config, or harness to extend?
5. **Ecosystem** — is there a reviewed open-source tool to adopt before building another one?

If the ecosystem rung is unchecked, a new `CREATE` remains `needs_research` and no applyable artifact is staged. `--search-oss` sends only sanitized, allowlisted keywords to GitHub public repository search—not session text, prompts, paths, credentials, or arbitrary command arguments.

## Existing tools are components

- [SkillReaper](https://github.com/thousandflowers/skillreaper) supplies complete skill lifecycle evidence. Without it, positive local evidence can produce `KEEP`, but missing observations cannot produce retirement.
- [codlogs](https://github.com/tobitege/codlogs) was evaluated as a mature read-only session explorer. The MVP keeps a zero-dependency streaming parser behind an adapter-shaped observation layer.
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) and [Hermes Curator Evolver](https://github.com/pingchesu/hermes-curator-evolver) inspired agent-managed skill generation and evidence-gated evolution. Their code is not vendored.

## Optional live GPT-5.6 advisor

The deterministic router remains authoritative:

```powershell
codex-metabolism review --days 7 --advisor codex --advisor-model gpt-5.6-sol
```

This explicit option starts an ephemeral `codex exec` run in a read-only sandbox with a strict output schema. It supports all four target layers, cites only supplied evidence IDs, cannot bypass an incomplete adoption ladder or the mechanical-first invariant, and stores its output as non-authoritative metadata.

On July 20, 2026, the same public synthetic fixtures were sent through Codex CLI 0.144.5 and `gpt-5.6-sol`. The live run completed in **48.5 seconds** and produced four schema-valid suggestions:

| Evidence target | Deterministic decision | GPT-5.6 advice | What the contrast shows |
|---|---|---|---|
| Repeated deployment recovery | `CREATE HARNESS` | `CREATE HARNESS` · high | Prefer mechanical prevention over another prose reminder. |
| Reviewed `AGENTS.md` region | `PATCH RULE` | `KEEP RULE` · high | The model challenged a patch because the packet proved full review, not a specific defect. |
| Recently used skill | `KEEP SKILL` | `KEEP SKILL` · high | Positive use evidence supports retention. |
| `old-unused` skill | `RETIRE_CANDIDATE` | `RETIRE_CANDIDATE` · medium | Non-use is a soft signal, so removal still requires human judgment. |

The disagreement is intentional and visible: GPT-5.6 advises, while deterministic evidence and safety gates decide what may be staged. Neither path applies a change automatically.

Privacy boundary: the option sends bounded decision and evidence summaries—including relevant command and correction excerpts—to OpenAI using the user's Codex authentication. It is off by default.

## Evidence and safety contract

- JSONL is parsed line by line, with bounded excerpts instead of entire transcripts.
- Coverage is a first-class output. Parse failure means “unknown,” never “unused.”
- Exit status and tests are hard signals; user corrections and inferred outcomes are weaker signals.
- Skill invocation remains heuristic because inspected Codex JSONL versions did not expose a stable structured invocation event.
- Review is stage-only; mutation requires one explicitly approved decision ID.
- Skill patches and `AGENTS.md` changes are hash-gated against the reviewed live file.
- Retirement is a candidate until a person approves it; skills are archived, never deleted.
- The sample pre-tool guard only checks command order within one shell invocation. It is not a general policy engine.

## Development and verification

```powershell
python -m unittest discover -s tests -v
# Optional, when pytest is installed: python -m pytest -q
python -m build
```

The test suite covers JSONL variants and malformed input, parser coverage, adoption-ladder routing, external-tool privacy, SkillReaper import, whole-file `AGENTS.md` review, managed-region byte preservation, staging, hash-gated apply, future-session evaluation, duplicate suppression, rollback, skill archive/restore, manual external-tool activation/retirement, and the structured advisor.

## Supported platforms

- **Windows, Python 3.12:** verified in this checkout and again from a clean public clone.
- **Linux, Python 3.12:** independently verified from a clean clone; the closed-loop demo and full test suite passed.
- **macOS, Python 3.11+:** designed for standard-library portability, not yet verified.

## License

MIT. External projects retain their own licenses and are not vendored here.
