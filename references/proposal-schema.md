# Agent proposal schema

Read this reference only when drafting or repairing a proposal bundle.

## Required envelope

```json
{
  "schema_version": 1,
  "review_id": "review-...",
  "proposals": []
}
```

Include zero to three proposals. An empty list is a valid no-change review and needs no approval.

Each proposed change requires:

```json
{
  "proposal_id": "lowercase-safe-name",
  "action": "CREATE | PATCH | RETIRE_CANDIDATE",
  "layer": "HARNESS | TOOL | SKILL | RULE",
  "target": "lowercase-safe-name",
  "evidence_ids": ["evidence-..."],
  "reasoning": "Why the cited evidence supports this intervention.",
  "expected_effect": "What should become observably easier or safer.",
  "rollback_when": "What later evidence should trigger repair or withdrawal.",
  "alternatives_checked": [
    {"level": "builtin", "result": "..."},
    {"level": "installed", "result": "..."},
    {"level": "repository", "result": "..."},
    {"level": "ecosystem", "result": "..."}
  ],
  "artifact": {"path": "artifacts/example.patch"}
}
```

`CREATE` requires all four `alternatives_checked` levels exactly once. Other actions may include only the checks relevant to the change; every supplied level must be unique and use the same schema.

`CREATE` and `PATCH` require a complete Agent-authored artifact for every layer. A non-skill `RETIRE_CANDIDATE` also requires the exact reviewed diff, command plan, or configuration change. Artifact paths are relative to the directory containing `proposal.json`; absolute paths and `..` escapes are invalid.

For `SKILL` `PATCH` or `RETIRE_CANDIDATE`, also include:

```json
{"target_evidence_id": "evidence-installed-skill-for-the-exact-target"}
```

The target evidence must point to the exact installed-skill entry in the current evidence packet. `SKILL` `CREATE` and `PATCH` require a complete `SKILL.md`; its frontmatter `name` must match `target`. A Skill retirement has no replacement artifact because the reviewed live hash is archived intact.

Do not author `approval_digest`. `codex-metabolism stage` generates it from every immutable proposal field and the sealed artifact hash. Show that digest with the exact diff. After the user explicitly approves that version, pass the same digest to `apply` or `record`; any later proposal or artifact change invalidates it.

The runtime directly applies only Skill changes. For `HARNESS`, `TOOL`, and `RULE`, use the repository or platform's existing mechanism after approval, verify the result, save a concise implementation-evidence file, then pass that file to `record`. The runtime preserves both the approved artifact hash and the implementation-evidence hash, and records `RETIRE_CANDIDATE` as `RETIRED` rather than `ACTIVE`.
