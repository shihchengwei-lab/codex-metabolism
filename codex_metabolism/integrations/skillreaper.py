from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..models import SkillLifecycleEvidence


@dataclass(slots=True)
class SkillReaperImport:
    evidence: list[SkillLifecycleEvidence]
    complete: bool
    sessions: int
    malformed_lines: int
    warnings: list[str]
    generated_at: str | None


def _value(mapping: Mapping[str, Any], pascal: str, snake: str, default: Any = None) -> Any:
    if pascal in mapping:
        return mapping[pascal]
    return mapping.get(snake, default)


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_skillreaper_report(payload: Mapping[str, Any] | str | bytes) -> SkillReaperImport:
    """Normalize SkillReaper's public JSON report without trusting it to mutate files."""
    if isinstance(payload, (str, bytes)):
        payload = json.loads(payload)
    if not isinstance(payload, Mapping):
        raise ValueError("SkillReaper report must be a JSON object")

    rows = _value(payload, "Rows", "rows", [])
    warnings_payload = _value(payload, "Warnings", "warnings", [])
    if not isinstance(rows, list) or not isinstance(warnings_payload, list):
        raise ValueError("SkillReaper report has invalid Rows or Warnings")

    warning_texts: list[str] = []
    for warning in warnings_payload:
        if isinstance(warning, Mapping):
            path = str(_value(warning, "Path", "path", "") or "")
            message = str(_value(warning, "Msg", "msg", "") or "")
            warning_texts.append(f"{path}: {message}".strip(": "))
        else:
            warning_texts.append(str(warning))

    sessions = _integer(_value(payload, "Sessions", "sessions", 0))
    malformed = _integer(_value(payload, "MalformedLines", "malformed_lines", 0))
    unsafe_markers = ("incomplete", "unreadable", "malformed", "parse error", "no-transcript")
    unsafe_warning = any(
        marker in warning.casefold() for warning in warning_texts for marker in unsafe_markers
    )
    complete = sessions > 0 and malformed == 0 and not unsafe_warning
    generated_at = _value(payload, "GeneratedAt", "generated_at")

    evidence: list[SkillLifecycleEvidence] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        category = str(_value(row, "Category", "category", "")).casefold()
        platform = str(_value(row, "Platform", "platform", "")).casefold()
        if category != "skill" or platform != "codex":
            continue
        name = str(_value(row, "Name", "name", "") or "").strip()
        path = str(_value(row, "Path", "path", "") or "").strip()
        if not name or not path:
            continue
        evidence.append(
            SkillLifecycleEvidence(
                source="skillreaper",
                skill_name=name,
                skill_path=path,
                verdict=str(_value(row, "Verdict", "verdict", "REVIEW") or "REVIEW").upper(),
                reason=str(_value(row, "Reason", "reason", "") or ""),
                uses=_integer(_value(row, "Uses", "uses", 0)),
                sessions=sessions,
                removable=bool(_value(row, "Removable", "removable", False)),
                complete=complete,
                generated_at=str(generated_at) if generated_at else None,
            )
        )
    return SkillReaperImport(
        evidence=evidence,
        complete=complete,
        sessions=sessions,
        malformed_lines=malformed,
        warnings=warning_texts,
        generated_at=str(generated_at) if generated_at else None,
    )


def load_skillreaper_report(path: Path | str) -> SkillReaperImport:
    return parse_skillreaper_report(Path(path).read_text(encoding="utf-8"))


def find_skillreaper() -> str | None:
    return shutil.which("reap") or shutil.which("skillreaper")


def collect_skillreaper(days: float, *, executable: str | None = None) -> SkillReaperImport:
    command = executable or find_skillreaper()
    if not command:
        raise FileNotFoundError("SkillReaper is not installed")
    result = subprocess.run(
        [command, "--days", str(max(1, int(days))), "--json", "--no-nudge"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=90,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"SkillReaper scan failed: {detail}")
    return parse_skillreaper_report(result.stdout)
