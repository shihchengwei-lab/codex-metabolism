---
name: codex-metabolism
description: Review recent Codex sessions for reusable successful workflows and recurring collaboration friction, compare existing capabilities, draft complete evidence-linked improvements, and safely stage, apply, evaluate, archive, or roll them back. Use when the user asks to metabolize recent work, improve recurring Codex collaboration, capture or repair a skill from past work, evaluate whether an intervention helped, or prune stale collaboration infrastructure.
---

# Codex Metabolism

Treat this skill as the product surface. **Codex owns semantic interpretation and artifact design; the runtime owns evidence boundaries, persistence, and safe mutation.** Do not invoke another model or let the runtime decide what user behavior means.

## Observe

1. Run:

   ```powershell
   codex-metabolism observe --days 7 --project-root . --output-dir .codex-metabolism
   ```

   If the console entry point is unavailable while working from this repository, use `python -m codex_metabolism` in its place. Otherwise stop and tell the user that the runtime is not installed.

2. Read `.codex-metabolism/evidence.json`.
3. Report coverage and parser gaps before drawing conclusions.
4. Interpret the neutral, ordered session capsules yourself. Treat a command status, interruption, silence, or user message as evidence, never automatic proof of success, failure, or friction.
5. Group evidence by user intent and task shape, not filename, word overlap, or exact command spelling.

## Decide

Consider zero to three interventions. An evidence-supported conclusion that nothing should change is valid; do not create a `KEEP` proposal or bookkeeping receipt.

For each candidate:

1. Explain the underlying problem in plain language.
2. Cite exact evidence IDs.
3. **Search existing capabilities before proposing anything new:** check Codex built-ins, installed skills and tools, repository assets, then relevant external tools.
4. Prefer no change, reuse, or a small patch over creation.
5. Prefer a mechanical repository fix over durable prose when it directly removes the friction.
6. Abstain when the successful trajectory, recurrence, or expected effect is not sufficiently supported.

Codex makes these semantic judgments. The runtime may reject malformed or unsafe bundles, but it must not choose the intervention layer.

## Draft

Create one draft bundle under `.codex-metabolism/drafts/<draft-name>/`:

```text
proposal.json
artifacts/
`-- <artifact files written by Codex>
```

Follow [references/proposal-schema.md](references/proposal-schema.md). Put reasoning, cited evidence, alternatives checked, expected effect, and rollback condition in `proposal.json`.

When no intervention is justified, write the same envelope with an empty `proposals` list and stage it as a no-change review.

For a skill artifact:

- Write a complete, useful `SKILL.md`; do not emit a generic evidence appendix or placeholder workflow.
- Put triggering contexts in the frontmatter description.
- Use imperative instructions grounded in the successful trajectory.
- Include verification, stopping conditions, and relevant fallbacks.
- Keep metabolism bookkeeping out of the live skill.

## Validate and stage

Run:

```powershell
codex-metabolism stage .codex-metabolism/drafts/<draft-name>/proposal.json `
  --evidence .codex-metabolism/evidence.json `
  --output-dir .codex-metabolism
```

Fix validation failures; never bypass them. Staging may only seal the exact Agent-authored artifact and write inside `.codex-metabolism`.

Present the user with:

- the observed problem;
- why this is the smallest suitable intervention;
- cited evidence and uncertainty;
- the exact artifact or diff;
- the generated approval digest for that exact version;
- expected effect and rollback condition.

**Show the exact diff and wait for explicit human approval.** Do not treat the request to review as permission to apply.

## Apply or reject

After explicit approval, run:

```powershell
codex-metabolism apply <proposal-id> --output-dir .codex-metabolism `
  --approved-digest <displayed-digest>
```

For an existing skill, resolve the exact installed root by matching the observed target and content hash, then pass it with `--skill-root <root>`. Never guess between `.agents/skills`, `.codex/skills`, or another configured root. For a new skill, confirm the intended root with the user if it is not already clear.

If rejected, run:

```powershell
codex-metabolism reject <proposal-id> --output-dir .codex-metabolism
```

For repository harnesses, rules, or tools, use the existing Git, configuration, package-manager, plugin-manager, or platform mechanism after approval. Verify the result and save a concise implementation-evidence file containing the final diff, state, command receipt, and relevant verification. Then record it:

```powershell
codex-metabolism record <proposal-id> --artifact <implementation-evidence-file> `
  --output-dir .codex-metabolism --approved-digest <displayed-digest>
```

Never download, install, enable, or delete an external tool automatically. Restore an approved retired skill with `codex-metabolism restore <proposal-id> --human-approved`.

For `RULE`, respect existing ownership boundaries and managed-region validators. Outside an explicitly managed region, show the proposed `AGENTS.md` diff and use the normal Codex editing workflow only after approval. Record CREATE/PATCH as `ACTIVE` and a removal or disable action as `RETIRED`; do not relabel every external change as active.

Treat one output directory as single-writer: do not run apply, record, rollback, or restore concurrently against the same `.codex-metabolism` ledger.

## Re-evaluate

On a later review, inspect the target's receipt history alongside post-activation session evidence. Compare the original reasoning, expected effect, evidence IDs, and rollback condition with what actually happened. No change remains a report result; repair or retirement goes through the same draft -> stage -> digest approval path.

After explicit approval, roll back an active Agent-authored skill with:

```powershell
codex-metabolism rollback <intervention-id> --output-dir .codex-metabolism --human-approved
```

Do not let absence of evidence become evidence of success. Retirement remains reversible, and human approval remains required for every live mutation.
