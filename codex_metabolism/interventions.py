from __future__ import annotations

import json
import os
import tempfile
from dataclasses import fields
from pathlib import Path
from typing import Iterable

from .models import InterventionReceipt


class InterventionError(RuntimeError):
    pass


def _from_dict(payload: dict) -> InterventionReceipt:
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
    latest: dict[str, InterventionReceipt] = {}
    for record in records:
        latest[record.decision_id] = record
    return list(latest.values())
