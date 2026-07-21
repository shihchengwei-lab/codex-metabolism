# Native scheduled review

Use Codex's native Scheduled task capability instead of installing a custom scheduler. Ask the user for the local time of their weekly usage reset; Codex Metabolism cannot reliably infer it. Recommend a run shortly before that reset, when unused weekly capacity would otherwise expire.

Create the task only after explicit confirmation. Prefer a standalone weekly task in the local project so findings appear in the Scheduled inbox and the same `.codex-metabolism` ledger remains available. Do not schedule concurrent runs against one ledger.

Use this durable task prompt:

```text
Use $codex-metabolism to review the last 7 days of collaboration for this project.

SCHEDULED REVIEW — STAGE ONLY.

Prepare bounded evidence, report parser coverage and truncation first, interpret
reusable successes and recurring friction, and search existing capabilities before
proposing anything new. Author zero to three evidence-linked proposals. A no-change
result is valid. Stage the exact proposals and report their evidence, uncertainty,
expected effect, rollback condition, diff, and approval digest in the Scheduled inbox.

Do not apply, record, rollback, restore, install, enable, disable, archive, commit,
push, or otherwise mutate live collaboration state. Human approval must happen later
in an interactive Codex conversation.
```

Test the prompt once in a normal interactive review before scheduling it. Keep the computer and Codex app running when the task needs local session files. Use the narrowest permissions that allow reading Codex sessions and writing only `.codex-metabolism` staging artifacts.
