# OpenAI Build Week submission draft

## Submission fields

- **Project:** Codex Metabolism
- **Track:** Developer Tools
- **Tagline:** Evidence-driven metabolism for the whole Codex collaboration stack.
- **One sentence:** Codex Metabolism learns from session friction, finds or creates the smallest useful intervention across harnesses, tools, skills, and bounded rules, then evaluates and prunes it using later sessions.
- **Repository:** https://github.com/shihchengwei-lab/codex-metabolism
- **Demo video:** `[USER ACTION: add public YouTube URL]`
- **Primary `/feedback` Session ID:** `[USER ACTION: run /feedback in the primary build thread]`

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

## Demo video

The ready-to-record [video production pack](DEMO_VIDEO.md) contains a 2:50 English voiceover, privacy-safe shot list, capture checklist, YouTube metadata, and timed [SRT captions](demo-voiceover.en.srt). It uses only the repository's synthetic data and leaves ten seconds of safety margin below the three-minute limit.

## What's next

- Validate the streaming parser against additional documented Codex JSONL variants while preserving explicit coverage reporting.
- Add adapters for mature lifecycle and session tools instead of rebuilding their capabilities.
- Run longer opt-in evaluations to calibrate validation and retirement thresholds without treating silence as success.

## Submission checklist

The [OpenAI Build Week page](https://openai.devpost.com/) currently requires a working project using Codex with GPT-5.6, a category, project description, a public YouTube demo under three minutes with audio explaining both Codex and GPT-5.6 use, a testable repository URL with README and sample data, and the `/feedback` Codex Session ID for the session containing most core implementation. Developer tools also need installation instructions, supported platforms, and a judge-ready test path.

- [x] Working local project.
- [x] Developer Tools category selected in project copy.
- [x] Setup instructions and sample data.
- [x] One-command isolated two-generation demo.
- [x] Supported-platform status stated honestly.
- [x] Codex/GPT-5.6 contribution and human decisions documented.
- [x] English voiceover script, timed captions, and privacy-safe shot list prepared.
- [x] Publish repository: https://github.com/shihchengwei-lab/codex-metabolism
- [ ] Record and upload a public YouTube video shorter than three minutes with audio.
- [ ] Obtain and enter the `/feedback` Codex Session ID.
- [ ] Create and submit the Devpost project form.

The listed deadline is **July 21, 2026 at 5:00 PM Pacific Time**. Confirm it again on Devpost before final submission.
