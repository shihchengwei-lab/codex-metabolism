from __future__ import annotations

import json
import os
import tempfile
import hashlib
from dataclasses import fields
from pathlib import Path
from typing import Iterable

from .models import InterventionReceipt


class InterventionError(RuntimeError):
    pass


def intervention_identity(target_kind: str, target: str, scope: str) -> str:
    """Return one stable lifecycle identity for a layer/target/scope tuple."""
    material = "\x1f".join(
        (target_kind.strip().casefold(), target.strip().casefold(), scope.strip().casefold())
    )
    return "intervention-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _from_dict(payload: dict) -> InterventionReceipt:
    if "intervention_id" not in payload and "decision_id" in payload:
        payload = {**payload, "intervention_id": payload["decision_id"]}
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if not payload.get("proposal_id") and payload.get("intervention_id"):
        payload = {**payload, "proposal_id": payload["intervention_id"]}
    if "rollback_when" not in payload and metadata.get("rollback_when") is not None:
        payload = {**payload, "rollback_when": metadata["rollback_when"]}
    if "evidence_ids" not in payload and isinstance(metadata.get("evidence_ids"), list):
        payload = {**payload, "evidence_ids": metadata["evidence_ids"]}
    allowed = {item.name for item in fields(InterventionReceipt)}
    values = {key: value for key, value in payload.items() if key in allowed}
    try:
        return InterventionReceipt(**values)
    except TypeError as exc:
        raise InterventionError("intervention receipt is missing required fields") from exc


def load_interventions(path: Path | str) -> list[InterventionReceipt]:
    ledger = Path(path)
    if not ledger.is_file():
        return []
    records: list[InterventionReceipt] = []
    try:
        with ledger.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise InterventionError(f"invalid intervention receipt at line {line_number}")
                records.append(_from_dict(payload))
    except (OSError, json.JSONDecodeError) as exc:
        raise InterventionError(f"invalid intervention ledger: {ledger}") from exc
    return records


def write_interventions(path: Path | str, records: Iterable[InterventionReceipt]) -> None:
    ledger = Path(path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{ledger.name}.", dir=ledger.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        os.replace(temporary, ledger)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def append_intervention(path: Path | str, record: InterventionReceipt) -> None:
    records = load_interventions(path)
    records.append(record)
    write_interventions(path, records)


def latest_interventions(records: Iterable[InterventionReceipt]) -> list[InterventionReceipt]:
    latest: dict[tuple[str, str, str], InterventionReceipt] = {}
    for record in records:
        key = (
            record.target_kind.casefold(),
            record.target.casefold(),
            record.scope.casefold(),
        )
        latest[key] = record
    return list(latest.values())


def intervention_histories(
    records: Iterable[InterventionReceipt],
) -> dict[tuple[str, str, str], list[InterventionReceipt]]:
    histories: dict[tuple[str, str, str], list[InterventionReceipt]] = {}
    for record in records:
        key = (
            record.target_kind.casefold(),
            record.target.casefold(),
            record.scope.casefold(),
        )
        histories.setdefault(key, []).append(record)
    return histories
