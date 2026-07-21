from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .interventions import intervention_histories, latest_interventions
from .models import Observation, SessionObservation


_SECRET_TOKEN_RE = re.compile(r"(?i)\bsk-[a-z0-9_-]{8,}\b")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|api[_-]?key|password|secret)\s*[:=]\s*([^\s`]+)"
)


def _digest(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()[:12]


def _session_keys(session: SessionObservation) -> tuple[str, str, str]:
    identity = f"{session.session_id}|{session.source_file}"
    return (
        identity,
        _digest(identity),
        _digest(str(session.cwd or "unknown").casefold()),
    )


def _redact(text: str, sensitive_paths: list[str]) -> str:
    result = text
    variants: set[str] = set()
    for value in sensitive_paths:
        if not value:
            continue
        variants.update({value, value.replace("\\", "/"), value.replace("/", "\\")})
    for value in sorted(variants, key=len, reverse=True):
        result = re.sub(re.escape(value), "<PATH>", result, flags=re.IGNORECASE)
    result = _SECRET_TOKEN_RE.sub("<REDACTED>", result)
    result = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=<REDACTED>", result)
    return result


def _session_capsules(observation: Observation, *, limit: int) -> list[dict[str, Any]]:
    capsules: list[dict[str, Any]] = []
    for session in reversed(observation.sessions[-limit:]):
        identity, session_key, project_key = _session_keys(session)
        sensitive_paths = [observation.codex_home, observation.project_root, session.cwd or ""]
        events: list[dict[str, Any]] = []
        for message in session.messages:
            events.append(
                {
                    "id": f"evidence-{_digest(identity, 'message', str(message.sequence))}",
                    "kind": "user_message",
                    "sequence": message.sequence,
                    "excerpt": _redact(message.text, sensitive_paths)[:200],
                }
            )
        for tool in session.tool_executions:
            events.append(
                {
                    "id": f"evidence-{_digest(identity, 'tool', tool.call_id)}",
                    "kind": "tool_execution",
                    "sequence": tool.sequence,
                    "tool_name": tool.tool_name,
                    "command_excerpt": _redact(tool.command, sensitive_paths)[:240],
                    "status": tool.status,
                    "output_excerpt": _redact(tool.output_excerpt, sensitive_paths)[:240],
                }
            )
        if session.interrupted_turns:
            events.append(
                {
                    "id": f"evidence-{_digest(identity, 'interruptions')}",
                    "kind": "interrupted_turns",
                    "occurrence_count": session.interrupted_turns,
                }
            )
        if events:
            capsules.append(
                {
                    "id": f"evidence-{_digest(identity, 'session')}",
                    "kind": "session_capsule",
                    "session_key": session_key,
                    "project_key": project_key,
                    "timestamp": session.timestamp,
                    "model": session.model,
                    "events": sorted(events, key=lambda item: int(item.get("sequence", 10**12))),
                }
            )
    return capsules


def _portfolio(observation: Observation) -> dict[str, list[dict[str, Any]]]:
    skills: list[dict[str, Any]] = []
    for skill in observation.skills:
        skills.append(
            {
                "id": f"evidence-{_digest('skill', skill.path, skill.sha256)}",
                "kind": "installed_skill",
                "name": skill.name,
                "description": _redact(
                    skill.description,
                    [observation.codex_home, observation.project_root, skill.root],
                )[:240],
                "content_sha256": skill.sha256,
                "age_days": round(skill.age_days, 1),
                "usage_signals": skill.usage_signals,
                "protected": skill.protected,
            }
        )

    agents_documents = [
        {
            "id": f"evidence-{_digest('agents', item.path, item.content_sha256)}",
            "kind": "agents_document",
            "scope": item.scope,
            "depth": item.depth,
            "content_sha256": item.content_sha256,
            "byte_count": item.byte_count,
            "line_count": item.line_count,
            "whole_document_available": item.whole_document_available,
        }
        for item in observation.agents_documents
    ]
    sensitive_paths = [observation.codex_home, observation.project_root]
    histories = intervention_histories(observation.intervention_records)
    interventions: list[dict[str, Any]] = []
    for item in latest_interventions(observation.intervention_records):
        key = (item.target_kind.casefold(), item.target.casefold(), item.scope.casefold())
        complete_history = histories.get(key, [])
        visible_history = complete_history[-12:]
        interventions.append(
            {
                "id": f"evidence-{_digest('intervention', item.intervention_id, item.status)}",
                "kind": "intervention_receipt",
                "intervention_id": item.intervention_id,
                "proposal_id": item.proposal_id,
                "layer": item.target_kind,
                "target": item.target,
                "scope": item.scope,
                "status": item.status,
                "action": item.metadata.get("action"),
                "review_id": item.metadata.get("review_id"),
                "execution_mode": item.metadata.get("execution_mode"),
                "approved_artifact_sha256": item.metadata.get("approved_artifact_sha256"),
                "implementation_evidence_sha256": item.metadata.get(
                    "implementation_evidence_sha256"
                ),
                "activated_at": item.activated_at,
                "reasoning": _redact(item.reasoning, sensitive_paths)[:500],
                "expected_effect": _redact(item.expected_effect, sensitive_paths)[:500],
                "rollback_when": _redact(item.rollback_when, sensitive_paths)[:500],
                "evidence_ids": list(item.evidence_ids),
                "history": [
                    {
                        "proposal_id": transition.proposal_id,
                        "status": transition.status,
                        "action": transition.metadata.get("action"),
                        "review_id": transition.metadata.get("review_id"),
                        "changed_at": (
                            transition.metadata.get("rolled_back_at")
                            or transition.metadata.get("restored_at")
                            or transition.activated_at
                        ),
                        "reasoning": _redact(transition.reasoning, sensitive_paths)[:500],
                        "expected_effect": _redact(
                            transition.expected_effect,
                            sensitive_paths,
                        )[:500],
                        "rollback_when": _redact(
                            transition.rollback_when,
                            sensitive_paths,
                        )[:500],
                        "evidence_ids": list(transition.evidence_ids),
                    }
                    for transition in visible_history
                ],
                "history_truncated": max(0, len(complete_history) - len(visible_history)),
            }
        )
    return {
        "skills": skills,
        "agents_documents": agents_documents,
        "interventions": interventions,
    }


def build_evidence_packet(
    observation: Observation,
    *,
    generated_at: datetime | None = None,
    candidate_limit: int = 24,
) -> dict[str, Any]:
    if candidate_limit < 1 or candidate_limit > 48:
        raise ValueError("candidate_limit must be between 1 and 48")
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    sessions = _session_capsules(observation, limit=candidate_limit)
    portfolio = _portfolio(observation)
    evidence_ids = sorted(
        item["id"]
        for item in portfolio["skills"]
        + portfolio["agents_documents"]
        + portfolio["interventions"]
    )
    evidence_ids.extend(
        event["id"]
        for session in sessions
        for event in session["events"]
    )
    evidence_ids.extend(session["id"] for session in sessions)
    evidence_ids.sort()
    review_id = "review-" + _digest(generated.isoformat(), *evidence_ids)
    return {
        "schema_version": 2,
        "review_id": review_id,
        "generated_at": generated.isoformat(),
        "authority": "evidence_only",
        "window": {"days": observation.days, "session_count": len(observation.sessions)},
        "coverage": observation.coverage.to_dict(),
        "sessions": sessions,
        "portfolio": portfolio,
        "constraints": {
            "max_proposals": 3,
            "human_review_required": True,
            "allowed_actions": ["CREATE", "PATCH", "RETIRE_CANDIDATE"],
            "allowed_layers": ["HARNESS", "TOOL", "SKILL", "RULE"],
            "runtime_makes_semantic_decisions": False,
        },
    }


def write_evidence_packet(packet: dict[str, Any], output_dir: Path | str) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "evidence.json"
    descriptor, temporary = tempfile.mkstemp(prefix=".evidence.", dir=output, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(packet, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return destination
