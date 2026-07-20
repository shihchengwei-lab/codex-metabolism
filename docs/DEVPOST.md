# OpenAI Build Week submission draft

## Submission fields

- **Project:** Codex Metabolism
- **Track:** Developer Tools
- **Tagline:** Evidence-driven metabolism for the whole Codex collaboration stack.
- **One sentence:** Codex Metabolism learns from session friction, finds or creates the smallest useful intervention across harnesses, tools, skills, and bounded rules, then evaluates and prunes it using later sessions.

## Inspiration

Coding agents readily accumulate rules, memories, and skills, but accumulation is not improvement. A repeated failure may be better solved by a test, hook, script, installed plugin, or existing open-source tool. We wanted Codex to maintain a finite and auditable collaboration environment: grow useful structure, repair what still causes friction, and remove what no longer earns its cost.

Hermes Agent demonstrated agent-managed skill creation. Session-level retrospective tools demonstrated that trajectories contain more useful evidence than token totals. SkillReaper demonstrated evidence-based, reversible skill pruning. Codex Metabolism connects those ideas inside Codex and expands the unit of metabolism from “a skill” to the full collaboration intervention stack.

## What it does

`codex-metabolism review --days 7` streams recent Codex JSONL sessions, reports parser coverage, inventories installed skills and project tooling, evaluates active `AGENTS.md` scopes, and loads prior intervention receipts.

Before creating anything, it climbs five rungs: necessity, Codex built-ins, installed capabilities, repository assets, and the external open-source ecosystem. It emits only `CREATE`, `PATCH`, `KEEP`, or `RETIRE_CANDIDATE`, targeting one of four layers:

- `HARNESS` for mechanical prevention.
- `TOOL` for an existing installed or external capability.
- `SKILL` for contextual reusable workflows.
- `RULE` for bounded durable guidance.

All proposals are staged. Approved interventions receive a local ledger entry. Later sessions can validate them, show that friction recurred, or nominate an idle intervention for retirement. Active receipts suppress duplicate creation proposals, closing the loop instead of repeatedly rediscovering the same problem.

`AGENTS.md` has a mixed-ownership boundary. The entire active document is evaluated, but only bytes between an existing valid `codex-metabolism:managed-start` / `managed-end` marker pair can be changed after explicit approval. Everything else remains recommendation-only. Full-file hashes, a ten-rule managed cap, and rollback protect the human-owned file.

## How we built it

- Python 3.11+ with a standard-library-only runtime.
- Streaming, bounded Codex JSONL parser with explicit coverage and conservative schema handling.
- Deterministic evidence and cross-layer routing engine.
- Five-rung existing-tool ladder and sanitized GitHub public search.
- Optional SkillReaper JSON adapter rather than rebuilding mature skill-lifecycle analysis.
- Whole-file `AGENTS.md` review with byte-preserving managed-region patches.
- Staging renderer for reports, diffs, hook proposals, skill changes, rules, and adoption plans.
- Intervention receipts plus later-session `VALIDATED`, `INEFFECTIVE`, and `IDLE_CANDIDATE` verdicts. New project hooks remain `PENDING_TRUST` until the user reviews them through Codex `/hooks` and confirms activation.
- Hash-gated apply, rollback, skill archive/restore, and manual external-tool activation/retirement recording.
- Optional GPT-5.6 second opinion through ephemeral, read-only `codex exec` with a strict schema.
- Failing tests were written before each implementation slice.

## Challenges

Codex JSONL is useful but not a stable public analytics schema. The parser therefore reports coverage and treats parse gaps as unknown. Inspected versions did not expose a stable structured “this skill was invoked” event, so invocation remains explicitly heuristic.

Task success is not a single reliable label. Exit status and tests are harder signals; user corrections and inferred outcomes remain weaker. Codex Metabolism does not claim to know true quality from “the user did not complain.”

The ownership boundary was also subtle. A fully automatic `AGENTS.md` rewrite would be powerful but difficult to trust. The product instead evaluates the whole file, allows direct changes only in an explicit managed block, and preserves every byte outside it.

Finally, several open-source projects already solve parts of exploration, evolution, or pruning. The adoption ladder became both a product feature and our implementation discipline: integrate or adopt before building another tool.

## Accomplishments

- The public demo replays two generations: repeated friction produces an intervention, two later successful sessions validate it, and duplicate creation is suppressed.
- One review spans mechanical harnesses, external tools, skills, and bounded `AGENTS.md` rules.
- A complete demo review produces harness creation, managed-rule pruning, skill retention, and a skill retirement candidate.
- Review never mutates live state.
- Managed `AGENTS.md` patches preserve bytes outside the marker region and can be rolled back exactly.
- External projects are proposed and tracked but never silently downloaded, installed, or deleted.
- Incomplete lifecycle or parser evidence cannot become a retirement claim.
- Retirement remains a human decision; local skills are archived and restorable.

## What we learned

“Self-improving” is too vague. The useful boundary here is procedural collaboration context, not model weights. Improvement also needs subtraction: a system that only adds memory becomes harder to understand and trust.

The slime-mold analogy proved useful. The system grows a path only when repeated evidence justifies it, tests the path against future traffic, reinforces what works, and withdraws low-value structure. The key product object is therefore not a generated skill; it is the entire evidence-to-intervention-to-evaluation cycle.

## Under-three-minute demo plan

**0:00–0:20 — Problem.** Show an overloaded collaboration setup. Explain that agents naturally add context but do not naturally maintain a clean finite system.

**0:20–0:40 — Evidence.** Show two synthetic Codex sessions with the same failed deployment, user correction, and verified recovery.

**0:40–1:00 — First review.** Run `python examples/run_closed_loop_demo.py`. Show `CREATE HARNESS`, `PATCH RULE`, `KEEP SKILL`, and `RETIRE_CANDIDATE SKILL`.

**1:00–1:30 — Router and trust boundary.** Open the five-rung ladder, staged hook, and `AGENTS.md` diff. Show that the human-owned prefix and suffix are unchanged and only the marked region is patchable.

**1:30–2:00 — Closed loop.** Show the project hook's `PENDING_TRUST` receipt and the explicit `/hooks` trust boundary. The isolated replay records that confirmation, adds two later successful sessions, and runs review again. Show `KEEP HARNESS (VALIDATED)` and the active receipt that prevents duplicate creation.

**2:00–2:25 — Pruning and reversibility.** Show `RETIRE_CANDIDATE old-unused`, `archive`, `restore`, and `rollback`. Explain that review deletes nothing.

**2:25–2:45 — Existing tools.** Show the adoption ladder and an external-tool proposal. Explain `activate-tool` and `retire-tool` only record user-reviewed actions; they never install or delete third-party code.

**2:45–3:00 — Close.** “Codex Metabolism helps AI collaboration improve without only accumulating: observe, adopt, evaluate, and prune.”

## Submission checklist

The [OpenAI Build Week page](https://openai.devpost.com/) currently requires a working project using Codex with GPT-5.6, a category, project description, a public YouTube demo under three minutes with audio explaining both Codex and GPT-5.6 use, a testable repository URL with README and sample data, and the `/feedback` Codex Session ID for the session containing most core implementation. Developer tools also need installation instructions, supported platforms, and a judge-ready test path.

- [x] Working local project.
- [x] Developer Tools category selected in project copy.
- [x] Setup instructions and sample data.
- [x] One-command isolated two-generation demo.
- [x] Supported-platform status stated honestly.
- [x] Codex/GPT-5.6 contribution and human decisions documented.
- [ ] Publish repository or share the private repository with the required judging addresses.
- [ ] Record and upload a public YouTube video shorter than three minutes with audio.
- [ ] Obtain and enter the `/feedback` Codex Session ID.
- [ ] Create and submit the Devpost project form.

The listed deadline is **July 21, 2026 at 5:00 PM Pacific Time**. Confirm it again on Devpost before final submission.
