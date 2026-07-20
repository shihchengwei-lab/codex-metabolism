from __future__ import annotations

import difflib
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .agents_review import managed_region
from .models import Decision, Observation
from .names import safe_name


GUARD_SOURCE = '''from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    rule = json.loads(Path(__file__).with_name("rule.json").read_text(encoding="utf-8"))
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if event.get("hook_event_name") != "PreToolUse" or event.get("tool_name") != "Bash":
        return 0
    command = str((event.get("tool_input") or {}).get("command") or "")
    folded = command.casefold()
    protected = rule["protected_command"].casefold()
    required = rule["required_command"].casefold()
    protected_at = folded.find(protected)
    if protected_at < 0:
        return 0
    required_at = folded.find(required)
    if 0 <= required_at < protected_at:
        return 0
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Codex Metabolism guard: run `{rule['required_command']}` before "
                f"`{rule['protected_command']}` in the same shell command."
            ),
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current if current.tzinfo else current.replace(tzinfo=timezone.utc)


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _atomic_json(path: Path, payload: object) -> None:
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _report(observation: Observation, decisions: list[Decision], generated_at: datetime) -> str:
    coverage = observation.coverage
    lines = [
        "# Codex Metabolism Review",
        "",
        f"Generated: {generated_at.isoformat()}",
        f"Window: {observation.days:g} days · {len(observation.sessions)} sessions",
        (
            "Coverage: "
            f"{coverage.files_parsed}/{coverage.files_selected} session files parsed · "
            f"{coverage.parse_errors} malformed lines · skill usage={coverage.skill_invocation} · "
            f"skill lifecycle={coverage.skill_lifecycle_source} "
            f"({'complete' if coverage.skill_lifecycle_complete else 'conservative'}) · "
            f"observed installed tools={len(observation.installed_tools)} · "
            f"external catalog={'checked' if coverage.catalog_checked else 'not checked'}"
        ),
        "",
        "> Outcomes and friction are weak-signal inferences unless an evidence item is marked hard. "
        "A missing parser signal is never treated as proof of non-use.",
        "",
        "## Decisions",
        "",
    ]
    if not decisions:
        lines.append("No evidence met the decision thresholds.")
        return "\n".join(lines) + "\n"
    for decision in decisions:
        lines.extend(
            [
                f"### {decision.decision} {decision.target_kind}: {decision.target}",
                "",
                f"ID: `{decision.id}` · confidence: {decision.confidence} · readiness: {decision.readiness}",
                "",
                decision.proposed_change,
                "",
                "Adoption ladder:",
                "",
            ]
        )
        for rung in decision.adoption_ladder:
            mark = "x" if rung.get("checked") else " "
            lines.append(
                f"- [{mark}] {rung['name']}: {rung['result']} — {rung.get('details', '')}"
            )
        lines.extend(["", "Evidence:", ""])
        for evidence in decision.evidence:
            strength = "hard" if evidence.get("hard") else "weak"
            lines.append(f"- `{evidence['id']}` ({strength}) {evidence['summary']}")
        advisor = decision.metadata.get("codex_advisor")
        if advisor:
            lines.extend(
                [
                    "",
                    "Codex advisor (non-authoritative):",
                    "",
                    (
                        f"- {advisor['decision']} {advisor['target_kind']} · "
                        f"{advisor['confidence']} — {advisor['reasoning']}"
                    ),
                ]
            )
        lines.append("")
    return "\n".join(lines)


def _stage_harness(output: Path, decision: Decision) -> None:
    proposal = output / "proposed-harness" / decision.id
    proposal.mkdir(parents=True, exist_ok=True)
    if decision.mechanism != "pretool_guard":
        _atomic_text(proposal / "proposal.md", decision.proposed_change + "\n")
        return
    rule = {
        "schema_version": 1,
        "decision_id": decision.id,
        "required_command": decision.metadata["required_command"],
        "protected_command": decision.metadata["protected_command"],
        "evidence_ids": [item["id"] for item in decision.evidence],
    }
    fragment = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "^Bash$",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "__CODEX_METABOLISM_GUARD__",
                            "commandWindows": "__CODEX_METABOLISM_GUARD__",
                            "timeout": 10,
                            "statusMessage": "Checking evidence-backed preflight guard",
                        }
                    ],
                }
            ]
        }
    }
    _atomic_text(proposal / "guard.py", GUARD_SOURCE)
    _atomic_json(proposal / "rule.json", rule)
    _atomic_json(proposal / "hooks.fragment.json", fragment)


def _stage_skill(output: Path, decision: Decision) -> None:
    proposal = output / "proposed-skills" / safe_name(decision.target)
    proposal.mkdir(parents=True, exist_ok=True)
    evidence_lines = "\n".join(
        f"- {item['summary']} (session: {item.get('session_id') or 'inventory'})"
        for item in decision.evidence
    )
    if decision.decision == "PATCH" and decision.metadata.get("existing_path"):
        source = Path(decision.metadata["existing_path"])
        original = source.read_text(encoding="utf-8", errors="replace")
        addition = (
            "\n\n## Evidence-backed update\n\n"
            f"{decision.proposed_change}\n\nEvidence:\n{evidence_lines}\n"
        )
        proposed = original.rstrip() + addition
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                proposed.splitlines(keepends=True),
                fromfile=str(source),
                tofile=f"proposed/{decision.target}/SKILL.md",
            )
        )
        _atomic_text(proposal / "SKILL.md", proposed)
        _atomic_text(proposal / "original.SKILL.md", original)
        _atomic_text(proposal / "changes.diff", diff)
    else:
        content = (
            "---\n"
            f"name: {safe_name(decision.target)}\n"
            f"description: Evidence-backed workflow for {decision.target}.\n"
            "---\n\n"
            f"# {decision.target}\n\n"
            f"{decision.proposed_change}\n\n"
            "## Evidence used to draft this proposal\n\n"
            f"{evidence_lines}\n"
        )
        _atomic_text(proposal / "SKILL.md", content)


def _stage_external(output: Path, decision: Decision) -> None:
    proposal = output / "proposed-adoptions" / decision.id
    tool = decision.metadata.get("external_tool", {})
    content = (
        f"# Adopt {tool.get('name', decision.target)}\n\n"
        f"URL: {tool.get('url', 'unknown')}\n\n"
        f"License reported by catalog: {tool.get('license', 'UNKNOWN')}\n\n"
        f"Last updated: {tool.get('updated_at', 'unknown')}\n\n"
        f"{decision.proposed_change}\n\n"
        "This plan does not download or execute the third-party project. Review its source, "
        "license, maintenance status, and install instructions before approval.\n"
    )
    _atomic_text(proposal / "plan.md", content)


def _stage_installed_tool(output: Path, decision: Decision) -> None:
    proposal = output / "proposed-adoptions" / decision.id
    tool = decision.metadata.get("installed_tool", {})
    content = (
        f"# Configure existing tool: {tool.get('name', decision.target)}\n\n"
        f"Resolved path: {tool.get('path', 'unknown')}\n\n"
        f"Observed source: {tool.get('source', 'unknown')}\n\n"
        f"{decision.proposed_change}\n\n"
        "This plan does not execute, replace, or reinstall the tool. Review its identity and "
        "configuration before recording activation.\n"
    )
    _atomic_text(proposal / "plan.md", content)


def _stage_rule(output: Path, decision: Decision) -> None:
    proposal = output / "proposed-rules" / decision.id
    recommendations = decision.metadata.get("recommendations", [])
    managed = decision.metadata.get("managed_region", {})
    lines = [
        f"# AGENTS.md review: {decision.target}",
        "",
        (
            "> Mixed ownership: after explicit approval, Codex Metabolism may replace only the "
            "existing marked managed region. Everything outside it is suggestion-only."
            if managed.get("applyable")
            else "> Suggestion only. No applyable managed-region edit is available."
        ),
        "",
        f"Source: {decision.metadata.get('source_path', 'not created yet')}",
        f"Scope: {decision.metadata.get('scope', 'project')}",
        f"Whole document evaluated: {decision.metadata.get('whole_document_evaluated', False)}",
        f"Content SHA-256: {decision.metadata.get('content_sha256') or 'not applicable'}",
        (
            "Estimated durable directives: "
            f"{decision.metadata.get('directive_count_estimate', 0)} / "
            f"budget {decision.metadata.get('rule_budget', 10)}"
        ),
        (
            "Managed region: "
            f"{'valid' if managed.get('valid') else 'not applyable'}; "
            f"{managed.get('rule_count', 0)} / {decision.metadata.get('rule_budget', 10)} rules; "
            f"{managed.get('reason', 'not present')}"
        ),
        "",
        "## Recommendations",
        "",
    ]
    if not recommendations:
        lines.append("No actionable structural or evidence-backed recommendation in this review window.")
    for item in recommendations:
        location = ""
        if item.get("line"):
            location = f" line {item['line']}"
        elif item.get("lines"):
            location = " lines " + ", ".join(str(value) for value in item["lines"])
        excerpt = f" — `{item['excerpt']}`" if item.get("excerpt") else ""
        lines.append(f"- **{item['action']}**{location}{excerpt}: {item['reason']}")
    lines.extend(
        [
            "",
            (
                "A managed-region-only diff is staged separately. Copy, rewrite, merge, or reject "
                "all recommendations outside that region manually."
                if managed.get("applyable")
                else "No AGENTS.md patch is generated. Copy, rewrite, merge, or reject these "
                "suggestions manually."
            ),
            "",
        ]
    )
    _atomic_text(proposal / "review.md", "\n".join(lines))
    if not managed.get("applyable"):
        return
    source = Path(decision.metadata["source_path"])
    source_bytes = source.read_bytes()
    current = source_bytes.decode("utf-8")
    current_sha = hashlib.sha256(source_bytes).hexdigest()
    if current_sha != decision.metadata.get("content_sha256"):
        raise ValueError(f"AGENTS.md changed after observation: {source}")
    located = managed_region(current)
    if not located.get("valid"):
        raise ValueError(f"AGENTS.md managed region is no longer valid: {source}")
    original_content = str(located["content"])
    proposed_content = str(managed["proposed_content"])
    proposed_document = (
        current[: located["content_start"]]
        + proposed_content
        + current[located["content_end"] :]
    )
    diff = "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            proposed_document.splitlines(keepends=True),
            fromfile=str(source),
            tofile=f"proposed/{source.name}",
        )
    )
    _atomic_text(proposal / "managed-block.original.txt", original_content)
    _atomic_text(proposal / "managed-block.proposed.txt", proposed_content)
    _atomic_text(proposal / "changes.diff", diff)


def stage_review(
    observation: Observation,
    decisions: Iterable[Decision],
    output_dir: Path | str,
    *,
    generated_at: datetime | None = None,
) -> Path:
    output = Path(output_dir)
    generated = _now(generated_at)
    items = list(decisions)
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": generated.isoformat(),
        "observation": {
            "codex_home": observation.codex_home,
            "project_root": observation.project_root,
            "days": observation.days,
            "session_count": len(observation.sessions),
            "skill_count": len(observation.skills),
            "installed_tool_count": len(observation.installed_tools),
            "installed_tools": [
                {
                    "name": tool.get("name"),
                    "path": tool.get("path"),
                    "source": tool.get("source"),
                }
                for tool in observation.installed_tools
            ],
            "agents_document_count": len(observation.agents_documents),
            "agents_documents": [
                {
                    "path": document.path,
                    "scope": document.scope,
                    "depth": document.depth,
                    "content_sha256": document.content_sha256,
                    "byte_count": document.byte_count,
                    "line_count": document.line_count,
                    "codex_context_limit": document.codex_context_limit,
                    "whole_document_evaluated": document.whole_document_evaluated,
                    "decode_errors": document.decode_errors,
                }
                for document in observation.agents_documents
            ],
            "coverage": observation.coverage.to_dict(),
        },
        "decisions": [decision.to_dict() for decision in items],
    }
    _atomic_json(output / "decisions.json", payload)
    _atomic_text(output / "report.md", _report(observation, items, generated))
    for decision in items:
        if decision.readiness != "ready" or decision.status != "proposed":
            continue
        if decision.target_kind == "RULE":
            _stage_rule(output, decision)
        elif decision.mechanism == "adopt_external":
            _stage_external(output, decision)
        elif decision.mechanism == "configure_installed":
            _stage_installed_tool(output, decision)
        elif decision.target_kind == "HARNESS" and decision.decision in {"CREATE", "PATCH"}:
            _stage_harness(output, decision)
        elif decision.target_kind == "SKILL" and decision.decision in {"CREATE", "PATCH"}:
            _stage_skill(output, decision)
    return output
