from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from .models import AgentsDocument, Decision, Observation


RULE_BUDGET = 10
MAX_RECOMMENDATIONS = 10
MAX_NEW_RULE_SUGGESTIONS = 3
MANAGED_START = "<!-- codex-metabolism:managed-start -->"
MANAGED_END = "<!-- codex-metabolism:managed-end -->"


def managed_region(content: str) -> dict[str, Any]:
    """Locate one explicit, standalone managed region without changing its contents."""
    starts = [match.start() for match in re.finditer(re.escape(MANAGED_START), content)]
    ends = [match.start() for match in re.finditer(re.escape(MANAGED_END), content)]
    present = bool(starts or ends)
    if len(starts) != 1 or len(ends) != 1:
        return {
            "present": present,
            "valid": False,
            "reason": "exactly one managed-start and one managed-end marker are required",
        }
    start = starts[0]
    end = ends[0]
    content_start = start + len(MANAGED_START)
    if end <= content_start:
        return {
            "present": True,
            "valid": False,
            "reason": "managed markers are out of order or overlap",
        }

    def standalone(offset: int, marker: str) -> bool:
        line_start = content.rfind("\n", 0, offset) + 1
        line_end = content.find("\n", offset)
        if line_end < 0:
            line_end = len(content)
        return content[line_start:line_end].strip(" \t\r") == marker

    if not standalone(start, MANAGED_START) or not standalone(end, MANAGED_END):
        return {
            "present": True,
            "valid": False,
            "reason": "managed markers must each be on a standalone line",
        }
    return {
        "present": True,
        "valid": True,
        "reason": "one valid managed region found",
        "start_offset": start,
        "content_start": content_start,
        "content_end": end,
        "end_offset": end + len(MANAGED_END),
        "start_line": content.count("\n", 0, start) + 1,
        "end_line": content.count("\n", 0, end) + 1,
        "content": content[content_start:end],
    }


def directive_units(document: AgentsDocument) -> list[dict[str, Any]]:
    """Extract countable directive candidates while still auditing the whole document."""
    units: list[dict[str, Any]] = []
    region = managed_region(document.content)
    in_fence = False
    pattern = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+?)\s*$")
    for line_number, raw in enumerate(document.content.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith(("#", "<!--", ">")):
            continue
        match = pattern.match(raw)
        if not match:
            continue
        text = match.group(1).strip()
        normalized = re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).strip()
        if normalized:
            units.append(
                {
                    "line": line_number,
                    "text": text,
                    "normalized": normalized,
                    "managed": bool(
                        region.get("valid")
                        and region["start_line"] < line_number < region["end_line"]
                    ),
                }
            )
    return units


def _managed_proposal(
    document: AgentsDocument,
    units: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    region = managed_region(document.content)
    public = {
        "present": bool(region.get("present")),
        "valid": bool(region.get("valid")),
        "reason": str(region.get("reason") or "managed region not present"),
        "applyable": False,
        "rule_count": sum(1 for unit in units if unit.get("managed")),
        "proposed_rule_count": sum(1 for unit in units if unit.get("managed")),
    }
    if not document.whole_document_evaluated:
        public["reason"] = "AGENTS.md is not valid UTF-8, so complete review and direct apply are disabled"
        return public
    if not region.get("valid"):
        return public
    public.update({"start_line": region["start_line"], "end_line": region["end_line"]})

    removable: set[int] = set()
    for item in recommendations:
        if item.get("action") == "SUPERSEDE" and item.get("managed") and item.get("line"):
            removable.add(int(item["line"]))
        elif item.get("action") == "MERGE":
            lines = [int(line) for line in item.get("lines", [])]
            managed_lines = [int(line) for line in item.get("managed_lines", [])]
            if not lines:
                continue
            retained = min(lines)
            removable.update(line for line in managed_lines if line != retained)
    if not removable:
        public["reason"] = "managed region is valid, but this review has no deterministic managed edit"
        return public

    lines = document.content.splitlines(keepends=True)
    proposed_document = "".join(
        line for line_number, line in enumerate(lines, start=1) if line_number not in removable
    )
    proposed_region = managed_region(proposed_document)
    if not proposed_region.get("valid"):
        public["reason"] = "the staged edit would invalidate managed markers"
        return public
    proposed_document_model = AgentsDocument(
        path=document.path,
        scope=document.scope,
        depth=document.depth,
        content_sha256=document.content_sha256,
        byte_count=len(proposed_document.encode("utf-8")),
        line_count=len(proposed_document.splitlines()),
        codex_context_limit=document.codex_context_limit,
        whole_document_evaluated=True,
        content=proposed_document,
    )
    proposed_count = sum(
        1 for unit in directive_units(proposed_document_model) if unit.get("managed")
    )
    public["proposed_rule_count"] = proposed_count
    if proposed_count > RULE_BUDGET:
        public["reason"] = (
            f"deterministic cleanup still leaves {proposed_count} managed rules, above the "
            f"budget of {RULE_BUDGET}"
        )
        return public
    public.update(
        {
            "applyable": True,
            "reason": "approved apply may replace only the marked managed content",
            "original_content_sha256": hashlib.sha256(
                region["content"].encode("utf-8")
            ).hexdigest(),
            "proposed_content": proposed_region["content"],
        }
    )
    return public


def _words(*values: str) -> set[str]:
    ignored = {
        "before",
        "after",
        "always",
        "never",
        "should",
        "project",
        "production",
        "directly",
        "with",
        "this",
        "that",
    }
    return {
        word
        for value in values
        for word in re.findall(r"[a-z][a-z0-9_-]{2,}", value.casefold())
        if word not in ignored
    }


def _matching_unit(units: list[dict[str, Any]], signature: str, required: str) -> dict[str, Any] | None:
    wanted = _words(signature, required)
    if not wanted:
        return None
    ranked: list[tuple[int, dict[str, Any]]] = []
    for unit in units:
        text = unit["text"].casefold()
        matched = sum(1 for word in wanted if word in text)
        if matched >= min(2, len(wanted)):
            ranked.append((matched, unit))
    return max(ranked, key=lambda item: item[0])[1] if ranked else None


def assess_document(
    document: AgentsDocument,
    friction_decisions: Iterable[Decision],
) -> dict[str, Any]:
    units = directive_units(document)
    recommendations: list[dict[str, Any]] = []

    for friction in friction_decisions:
        signature = str(friction.metadata.get("signature") or "")
        required = str(friction.metadata.get("required_command") or "")
        unit = _matching_unit(units, signature, required)
        if unit is None:
            continue
        action = "SUPERSEDE" if friction.target_kind == "HARNESS" else "REWRITE"
        recommendations.append(
            {
                "action": action,
                "line": unit["line"],
                "excerpt": unit["text"][:160],
                "managed": unit["managed"],
                "reason": (
                    "Matching guidance was present while the same friction still recurred. "
                    "Prefer the proposed mechanical intervention and let the user decide whether "
                    "to retire or rewrite this guidance."
                ),
                "evidence_ids": [item["id"] for item in friction.evidence],
            }
        )

    duplicates: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        duplicates.setdefault(unit["normalized"], []).append(unit)
    for group in duplicates.values():
        if len(group) < 2:
            continue
        recommendations.append(
            {
                "action": "MERGE",
                "lines": [item["line"] for item in group],
                "managed_lines": [item["line"] for item in group if item["managed"]],
                "excerpt": group[0]["text"][:160],
                "reason": "The same directive appears more than once in this AGENTS.md.",
                "evidence_ids": [],
            }
        )

    if document.byte_count > document.codex_context_limit:
        recommendations.append(
            {
                "action": "CONSOLIDATE",
                "line": None,
                "excerpt": "",
                "reason": (
                    f"The file is {document.byte_count} bytes, above the configured Codex "
                    f"project-document limit of {document.codex_context_limit} bytes."
                ),
                "evidence_ids": [],
            }
        )
    if len(units) > RULE_BUDGET:
        recommendations.append(
            {
                "action": "CONSOLIDATE",
                "line": None,
                "excerpt": "",
                "reason": (
                    f"Estimated durable directives ({len(units)}) exceed the portfolio review "
                    f"threshold of {RULE_BUDGET}; adding another rule should require merge, "
                    "rewrite, or retirement."
                ),
                "evidence_ids": [],
            }
        )

    priority = {"SUPERSEDE": 0, "REWRITE": 1, "MERGE": 2, "CONSOLIDATE": 3}
    recommendations.sort(key=lambda item: (priority.get(item["action"], 9), item.get("line") or 0))
    recommendations = recommendations[:MAX_RECOMMENDATIONS]
    managed = _managed_proposal(document, units, recommendations)
    return {
        "source_path": document.path,
        "scope": document.scope,
        "depth": document.depth,
        "content_sha256": document.content_sha256,
        "byte_count": document.byte_count,
        "line_count": document.line_count,
        "codex_context_limit": document.codex_context_limit,
        "whole_document_evaluated": document.whole_document_evaluated,
        "decode_errors": document.decode_errors,
        "directive_count_estimate": len(units),
        "rule_budget": RULE_BUDGET,
        "recommendations": recommendations,
        "managed_region": managed,
        "unmanaged_suggestion_only": True,
        "suggestion_only": not managed["applyable"],
    }


def _evidence_id(document: AgentsDocument, kind: str) -> str:
    digest = hashlib.sha256(f"{document.path}|{document.content_sha256}|{kind}".encode()).hexdigest()
    return f"ev-{digest[:10]}"


def agents_review_decisions(
    observation: Observation,
    friction_decisions: Iterable[Decision],
) -> list[Decision]:
    friction = list(friction_decisions)
    decisions: list[Decision] = []
    for document in observation.agents_documents:
        assessment = assess_document(document, friction)
        recommendations = assessment["recommendations"]
        decision_name = "PATCH" if recommendations else "KEEP"
        target = f"{document.scope}-agents-{document.content_sha256[:8]}"
        summary = (
            f"Evaluated all {document.byte_count} bytes and {document.line_count} lines of "
            f"{document.path}; estimated {assessment['directive_count_estimate']} durable directives."
        )
        decision_id = "met-" + hashlib.sha256(
            f"AGENTS|{document.path}|{document.content_sha256}|{decision_name}".encode()
        ).hexdigest()[:10]
        decisions.append(
            Decision(
                id=decision_id,
                decision=decision_name,
                target_kind="RULE",
                target=target,
                mechanism="agents_review",
                evidence=[
                    {
                        "id": _evidence_id(document, "whole_document"),
                        "session_id": None,
                        "kind": "whole_document_review",
                        "summary": summary,
                        "source": document.path,
                        "hard": True,
                    }
                ],
                confidence="high" if recommendations else "medium",
                proposed_change=(
                    (
                        "After explicit approval, replace only the existing marked managed region; "
                        "all recommendations outside it remain suggestion-only."
                        if assessment["managed_region"]["applyable"]
                        else "Review the bounded recommendations. No valid deterministic managed-region "
                        "edit is available, so AGENTS.md remains suggestion-only."
                    )
                ),
                coverage=observation.coverage.to_dict(),
                adoption_ladder=[
                    {"name": "necessity", "checked": True, "result": "portfolio_review", "details": summary},
                    {"name": "builtin", "checked": True, "result": "agents_guidance", "details": "AGENTS.md is a Codex durable-guidance surface."},
                    {"name": "installed", "checked": True, "result": "not_applicable", "details": "Existing guidance review."},
                    {"name": "repo", "checked": True, "result": "reviewed", "details": document.path},
                    {"name": "ecosystem", "checked": True, "result": "not_applicable", "details": "No new implementation is proposed."},
                ],
                metadata=assessment,
            )
        )
    return decisions


def new_rule_suggestion(
    observation: Observation,
    correction: str,
    evidence: list[dict[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    project_document = next(
        (document for document in observation.agents_documents if document.scope == "project"),
        None,
    )
    source_path = (
        project_document.path
        if project_document is not None
        else str(Path(observation.project_root) / "AGENTS.md")
    )
    count = len(directive_units(project_document)) if project_document is not None else 0
    region = managed_region(project_document.content) if project_document is not None else {
        "present": False,
        "valid": False,
        "reason": "AGENTS.md or managed region is absent",
    }
    managed_count = (
        sum(1 for unit in directive_units(project_document) if unit.get("managed"))
        if project_document is not None
        else 0
    )
    at_cap = managed_count >= RULE_BUDGET
    action = "REWRITE" if at_cap else "ADD"
    recommendation = {
        "action": action,
        "line": None,
        "excerpt": correction[:160],
        "reason": (
            "The rule budget is full; rewrite, merge, or retire existing guidance before adding."
            if at_cap
            else "Repeated user correction appears durable but is not mechanically enforceable."
        ),
        "evidence_ids": [item["id"] for item in evidence],
    }
    metadata = {
        "source_path": source_path,
        "scope": "project",
        "content_sha256": project_document.content_sha256 if project_document else None,
        "whole_document_evaluated": bool(project_document),
        "directive_count_estimate": count,
        "rule_budget": RULE_BUDGET,
        "recommendations": [recommendation][:MAX_NEW_RULE_SUGGESTIONS],
        "unmanaged_suggestion_only": True,
        "suggestion_only": True,
    }
    managed_metadata = {
        "present": bool(region.get("present")),
        "valid": bool(region.get("valid")),
        "reason": str(region.get("reason") or "managed region not present"),
        "applyable": False,
        "rule_count": managed_count,
        "proposed_rule_count": managed_count,
    }
    if project_document is not None and region.get("valid") and not at_cap:
        newline = "\r\n" if "\r\n" in project_document.content else "\n"
        current = str(region["content"])
        if not current:
            proposed = newline
        else:
            proposed = current
            if not proposed.endswith(("\n", "\r")):
                proposed += newline
        proposed += f"- {correction.strip()}{newline}"
        managed_metadata.update(
            {
                "applyable": True,
                "reason": "approved apply may append this rule only inside the marked region",
                "start_line": region["start_line"],
                "end_line": region["end_line"],
                "proposed_rule_count": managed_count + 1,
                "original_content_sha256": hashlib.sha256(
                    str(region["content"]).encode("utf-8")
                ).hexdigest(),
                "proposed_content": proposed,
            }
        )
        metadata["suggestion_only"] = False
    metadata["managed_region"] = managed_metadata
    return ("PATCH" if project_document else "CREATE"), source_path, metadata
