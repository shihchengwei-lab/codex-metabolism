# Fresh-Agent forward test

This test asks whether the `$codex-metabolism` skill is usable by a Codex Agent that did not participate in the refactor—and whether the Agent contributes real semantic judgment instead of repeating a hard-coded fixture.

This recorded run predates the approval-digest binding added in the subsequent lifecycle hardening. It evaluates the Agent/runtime responsibility split, not the current approval mechanism.

## Setup

A fresh Codex Agent received only:

- the current root `SKILL.md` and proposal schema;
- a neutral evidence packet containing two synthetic sessions;
- a small synthetic target repository;
- permission to write a draft and stage it, but **not** to modify the target or apply anything.

The Agent was explicitly told not to inspect the tests or demo implementation.

The sessions used different production entry points: Python and PowerShell. Each failed before preflight, received a differently worded user correction, and then showed the existing production preflight succeeding. The target repository confirmed that both release entry points existed, neither invoked preflight, and no shared release boundary existed.

## Agent result

The recorded deterministic demo fixture proposes `CREATE / SKILL`. The fresh Codex Agent did not copy it. It proposed exactly one **`PATCH / HARNESS`** because the repository already contained the necessary preflight capability and the friction could be removed mechanically.

It authored a concrete 930-byte patch that:

- gates each observed production entry point with the existing preflight;
- propagates preflight failure before deployment output;
- leaves development behavior unchanged;
- adds no dependency and duplicates no preflight logic.

The Agent checked the patch with `git apply --check`, cited six evidence IDs, stated that no successful post-preflight deployment was observed, and bounded its claim to ordering and failure propagation.

## Runtime result

Staging succeeded with status `awaiting_human_approval`. The sealed patch SHA-256 was:

```text
5f677ea6e56bf1954be1a67e73dd79501df7c97278e8d6181484d1138e6d2ab6
```

The staged artifact exactly matched the Agent-authored draft. **The target repository remained unchanged.** No apply, record, install, archive, restore, reject, or rollback action ran.

## What this establishes

- The active Agent—not Python—can group differently worded collaboration evidence.
- Existing-before-new and mechanical-before-prose can change the intervention layer.
- The runtime can accept an Agent-authored non-skill artifact without becoming its author.
- The human gate remains intact after semantic review and staging.

This is a synthetic forward test of product roles and usability, **not an impact study**, model benchmark, or proof that the proposed patch would reduce long-term friction.
