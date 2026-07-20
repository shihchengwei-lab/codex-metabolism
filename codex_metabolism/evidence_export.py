from __future__ import annotations

import csv
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .models import Decision, Observation


CSV_FIELDS = (
    "schema_version",
    "record_type",
    "record_id",
    "task_ref",
    "session_refs",
    "observed_signals",
    "session_counts",
    "decision",
    "intervention",
    "confidence",
    "result",
    "rollback_condition",
    "coverage",
    "evidence_refs",
)

_SAFE_CODE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _code(value: object, fallback: str = "") -> str:
    rendered = str(value or "").strip()
    return rendered if _SAFE_CODE.fullmatch(rendered) else fallback


def _values(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value if item is not None and str(item)]


def _aliases(prefix: str, values: Iterable[str]) -> dict[str, str]:
    return {
        value: f"{prefix}-{index:03d}"
        for index, value in enumerate(sorted(set(values)), start=1)
    }


def _task_key(decision: Decision) -> str:
    return str(decision.metadata.get("signature") or "\x1f".join(
        (decision.target_kind, decision.target, decision.mechanism)
    ))


def _session_ids(decision: Decision) -> list[str]:
    session_ids = set(_values(decision.metadata.get("session_ids")))
    session_ids.update(
        str(item["session_id"])
        for item in decision.evidence
        if item.get("session_id")
    )
    return sorted(session_ids)


def _count(value: object) -> str:
    if isinstance(value, bool):
        return "unknown"
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "unknown"
    return str(parsed) if parsed >= 0 else "unknown"


def _decision_counts(decision: Decision) -> str:
    recovered = {
        str(item["session_id"])
        for item in decision.evidence
        if item.get("kind") == "verified_recovery" and item.get("session_id")
    }
    failures = decision.metadata.get("post_failure_sessions")
    successes = decision.metadata.get("post_success_sessions")
    return ";".join(
        (
            f"failure={_count(failures) if failures is not None else _count(len(recovered))}",
            f"recovery={_count(len(recovered)) if recovered else 'unknown'}",
            f"success_only={_count(successes)}",
        )
    )


def _abstention_counts(abstention: Mapping[str, Any]) -> str:
    return ";".join(
        (
            f"failure={_count(abstention.get('failure_sessions'))}",
            f"recovery={_count(abstention.get('verified_recovery_sessions'))}",
            f"success_only={_count(abstention.get('success_only_sessions'))}",
        )
    )


def _coverage(observation: Observation) -> str:
    coverage = observation.coverage
    return ";".join(
        (
            f"parsed={coverage.files_parsed}/{coverage.files_selected}",
            f"errors={coverage.parse_errors}",
            f"skill_usage={_code(coverage.skill_invocation, 'unknown')}",
            f"lifecycle={_code(coverage.skill_lifecycle_source, 'unknown')}",
            f"retirement_safe={str(coverage.retirement_safe).lower()}",
        )
    )


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def export_evidence_csv(
    observation: Observation,
    decisions: Iterable[Decision],
    destination: Path | str,
    *,
    abstentions: Iterable[Mapping[str, Any]] = (),
) -> Path:
    """Export structured evidence without raw prompts, summaries, session IDs, or paths."""

    decision_items = sorted(decisions, key=lambda item: item.id)
    abstention_items = sorted(
        (dict(item) for item in abstentions),
        key=lambda item: (str(item.get("signature") or ""), str(item.get("reason") or "")),
    )
    task_keys = [_task_key(item) for item in decision_items] + [
        str(item.get("signature") or f"abstention-{index}")
        for index, item in enumerate(abstention_items, start=1)
    ]
    task_refs = _aliases("task", task_keys)
    target_refs = _aliases("target", (item.target for item in decision_items))
    session_refs = _aliases(
        "session",
        (
            session_id
            for decision in decision_items
            for session_id in _session_ids(decision)
        ),
    )
    coverage = _coverage(observation)
    rows: list[dict[str, object]] = []

    for index, decision in enumerate(decision_items, start=1):
        sessions = _session_ids(decision)
        signals = sorted({_code(item.get("kind")) for item in decision.evidence} - {""})
        evidence_refs = sorted({_code(item.get("id")) for item in decision.evidence} - {""})
        verdict = _code(decision.metadata.get("lifecycle_verdict"))
        rows.append(
            {
                "schema_version": 1,
                "record_type": "decision",
                "record_id": _code(decision.id, f"decision-{index:03d}"),
                "task_ref": task_refs[_task_key(decision)],
                "session_refs": ";".join(session_refs[item] for item in sessions),
                "observed_signals": ";".join(signals),
                "session_counts": _decision_counts(decision),
                "decision": _code(decision.decision),
                "intervention": ":".join(
                    (
                        _code(decision.target_kind),
                        _code(decision.mechanism),
                        target_refs[decision.target],
                    )
                ),
                "confidence": _code(decision.confidence),
                "result": verdict or _code(decision.status, "proposed"),
                "rollback_condition": {
                    "INEFFECTIVE": "repeated_post_activation_failure",
                    "IDLE_CANDIDATE": "idle_threshold_reached",
                }.get(verdict, ""),
                "coverage": coverage,
                "evidence_refs": ";".join(evidence_refs),
            }
        )

    for index, abstention in enumerate(abstention_items, start=1):
        signature = str(abstention.get("signature") or f"abstention-{index}")
        reason = _code(abstention.get("reason"), "unspecified")
        rows.append(
            {
                "schema_version": 1,
                "record_type": "abstention",
                "record_id": f"abstention-{index:03d}",
                "task_ref": task_refs[signature],
                "session_refs": "",
                "observed_signals": "aggregate_session_counts",
                "session_counts": _abstention_counts(abstention),
                "decision": "",
                "intervention": "",
                "confidence": "",
                "result": f"abstained:{reason}",
                "rollback_condition": "",
                "coverage": coverage,
                "evidence_refs": "",
            }
        )

    output = Path(destination)
    _write(output, rows)
    return output
