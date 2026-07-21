from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import (
    Coverage,
    AgentsDocument,
    InstalledSkill,
    InterventionReceipt,
    Observation,
    RepoAsset,
    SessionObservation,
    ToolExecution,
    UserMessage,
)


CORRECTION_RE = re.compile(
    r"(?:"
    r"^\s*no\s*(?:[.!,:;?\-—]|$)"
    r"|^\s*wrong\b"
    r"|^\s*instead\s*[.!,:;?\-—]"
    r"|^\s*(?:please\s+)?(?:do\s+not|don't)\b"
    r"|^\s*(?:(?:欸|咦|嗯|啊|蛤)[，,！!？?\s]*)?"
    r"(?:不是|不對|不要|改成|修正|請改成|請修正)"
    r")",
    re.IGNORECASE,
)
QUALITY_FEEDBACK_RE = re.compile(
    r"^\s*.{0,24}(?:輸出|結構|影片|字幕|旁白).{0,40}"
    r"(?:不行|不對|錯|亂掉|太長|太多|看不下去|糊在一起)",
    re.IGNORECASE,
)
SKILL_MENTION_RE = re.compile(r"\$([a-z0-9][a-z0-9_-]{1,80})", re.IGNORECASE)
EXIT_CODE_RE = re.compile(r"(?i)exit\s+code\s*:\s*(-?\d+)")
MAX_TEXT = 280
MAX_MESSAGES = 30
MAX_OUTPUT = 240


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_text(value: Any, limit: int) -> str:
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value)
    text = text.replace("\x00", "")
    return text[:limit]


def _walk_text(node: Any, *, role: str | None = None) -> Iterable[tuple[str | None, str]]:
    if isinstance(node, dict):
        node_type = node.get("type")
        next_role = node.get("role") if node_type == "message" else role
        if (
            isinstance(node_type, str)
            and node_type in {"input_text", "output_text"}
            and isinstance(node.get("text"), str)
        ):
            yield next_role, node["text"]
        for value in node.values():
            yield from _walk_text(value, role=next_role)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_text(value, role=role)


def _decode_arguments(raw: Any) -> Any:
    value = raw
    for _ in range(2):
        if not isinstance(value, str):
            break
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            break
    return value


def _find_command(node: Any) -> str:
    node = _decode_arguments(node)
    if isinstance(node, dict):
        command = node.get("command")
        if isinstance(command, str):
            return command.strip()
        for key in ("args", "input", "arguments"):
            if key in node:
                found = _find_command(node[key])
                if found:
                    return found
    return ""


def _status_from_output(output: Any) -> str:
    if isinstance(output, dict):
        if isinstance(output.get("success"), bool):
            return "success" if output["success"] else "failure"
        if isinstance(output.get("exit_code"), int):
            return "success" if output["exit_code"] == 0 else "failure"
        if output.get("isError") is True:
            return "failure"
    text = _safe_text(output, 5000)
    matches = EXIT_CODE_RE.findall(text)
    if matches:
        return "success" if int(matches[-1]) == 0 else "failure"
    lowered = text.lower()
    if "script failed" in lowered or '"iserror":true' in lowered:
        return "failure"
    if "script completed" in lowered:
        return "success"
    return "unknown"


def _skill_from_command(command: str) -> str | None:
    if "skill.md" not in command.lower():
        return None
    normalized = command.replace("\\", "/")
    match = re.search(r"/([^/\s'\"]+)/SKILL\.md", normalized, re.IGNORECASE)
    return match.group(1) if match else None


def _parse_session(path: Path) -> tuple[SessionObservation | None, int, int, int]:
    meta: dict[str, Any] = {}
    model: str | None = None
    messages: list[UserMessage] = []
    corrections: list[UserMessage] = []
    feedback_candidates: list[UserMessage] = []
    seen_messages: set[str] = set()
    calls: dict[str, dict[str, Any]] = {}
    outputs: dict[str, tuple[int, Any]] = {}
    skill_signals: set[str] = set()
    parse_errors = 0
    structured_skill_events = 0
    heuristic_skill_events = 0
    interrupted_turns = 0
    sequence = 0

    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return None, 1, 0, 0

    with handle:
        for line in handle:
            sequence += 1
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, UnicodeError):
                parse_errors += 1
                continue
            if not isinstance(obj, dict):
                parse_errors += 1
                continue
            top_type = obj.get("type")
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
            payload_type = payload.get("type")
            if top_type == "session_meta":
                for key in ("session_id", "timestamp", "cwd", "cli_version"):
                    if payload.get(key) is not None:
                        meta[key] = payload.get(key)
                if "session_id" not in meta and payload.get("id") is not None:
                    meta["session_id"] = payload.get("id")
            if top_type == "turn_context" and isinstance(payload.get("model"), str):
                model = payload["model"]
            if payload_type == "turn_aborted" and payload.get("reason") == "interrupted":
                interrupted_turns += 1

            if payload_type == "user_message" and isinstance(payload.get("message"), str):
                candidate_messages = [("user", payload["message"])]
            else:
                candidate_messages = list(_walk_text(payload))
            for role, text in candidate_messages:
                if role not in (None, "user"):
                    continue
                cleaned = _safe_text(text, MAX_TEXT).strip()
                if not cleaned or cleaned in seen_messages or cleaned.startswith("<"):
                    continue
                seen_messages.add(cleaned)
                message = UserMessage(sequence=sequence, text=cleaned)
                if len(messages) < MAX_MESSAGES:
                    messages.append(message)
                if CORRECTION_RE.search(cleaned):
                    corrections.append(message)
                    feedback_candidates.append(message)
                elif QUALITY_FEEDBACK_RE.search(cleaned):
                    feedback_candidates.append(message)
                for name in SKILL_MENTION_RE.findall(cleaned):
                    skill_signals.add(name.lower())
                    heuristic_skill_events += 1

            if payload_type in {"custom_tool_call", "function_call"}:
                call_id = str(payload.get("call_id") or payload.get("id") or f"line-{sequence}")
                raw_input = payload.get("input") if payload_type == "custom_tool_call" else payload.get("arguments")
                command = _find_command(raw_input)
                calls[call_id] = {
                    "sequence": sequence,
                    "tool_name": str(payload.get("name") or "unknown"),
                    "command": command,
                }
                skill_name = _skill_from_command(command)
                if skill_name:
                    skill_signals.add(skill_name.lower())
                    heuristic_skill_events += 1
            elif payload_type in {"custom_tool_call_output", "function_call_output"}:
                call_id = str(payload.get("call_id") or payload.get("id") or "")
                outputs[call_id] = (sequence, payload.get("output"))
            elif payload_type and "skill" in str(payload_type).lower():
                structured_skill_events += 1

    if not meta:
        return None, parse_errors, structured_skill_events, heuristic_skill_events

    tools: list[ToolExecution] = []
    for call_id, call in sorted(calls.items(), key=lambda item: item[1]["sequence"]):
        output_sequence, output = outputs.get(call_id, (call["sequence"], None))
        tools.append(
            ToolExecution(
                sequence=call["sequence"],
                output_sequence=output_sequence,
                call_id=call_id,
                tool_name=call["tool_name"],
                command=call["command"],
                status=_status_from_output(output),
                output_excerpt=_safe_text(output, MAX_OUTPUT),
            )
        )
    session = SessionObservation(
        session_id=str(meta.get("session_id") or path.stem),
        timestamp=meta.get("timestamp"),
        cwd=meta.get("cwd"),
        cli_version=meta.get("cli_version"),
        model=model,
        source_file=str(path),
        messages=messages,
        corrections=corrections,
        feedback_candidates=feedback_candidates,
        interrupted_turns=interrupted_turns,
        tool_executions=tools,
        skill_signals=skill_signals,
        parse_errors=parse_errors,
    )
    return session, parse_errors, structured_skill_events, heuristic_skill_events


def _frontmatter(path: Path) -> tuple[str, str]:
    name = path.parent.name
    description = ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return name, description
    if not lines or lines[0].strip() != "---":
        return name, description
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if not separator:
            continue
        if key.strip() == "name" and value.strip():
            name = value.strip().strip("'\"")
        elif key.strip() == "description":
            description = value.strip().strip("'\"")
    return name, description


def _inventory_skills(
    roots: Iterable[Path], sessions: list[SessionObservation], now: datetime
) -> list[InstalledSkill]:
    counts = Counter(name for session in sessions for name in session.skill_signals)
    found: list[InstalledSkill] = []
    seen: set[Path] = set()
    for root in roots:
        root = root.expanduser()
        if not root.is_dir():
            continue
        for skill_md in root.rglob("SKILL.md"):
            if ".codex-metabolism-archive" in skill_md.parts:
                continue
            try:
                resolved = skill_md.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            name, description = _frontmatter(skill_md)
            try:
                content = skill_md.read_bytes()
                stat = skill_md.stat()
            except OSError:
                continue
            age = max(0.0, (now.timestamp() - stat.st_mtime) / 86400)
            protected = ".system" in skill_md.parts
            found.append(
                InstalledSkill(
                    name=name,
                    description=description,
                    path=str(skill_md),
                    root=str(root),
                    sha256=hashlib.sha256(content).hexdigest(),
                    age_days=age,
                    protected=protected,
                    usage_signals=counts[name.lower()],
                )
            )
    return sorted(found, key=lambda skill: (skill.name.lower(), skill.path.lower()))


def _repo_assets(project_root: Path) -> list[RepoAsset]:
    candidates: list[Path] = []
    # AGENTS.md is reviewed as durable guidance, never mistaken for a mechanical repo asset.
    for relative in (".codex/hooks.json", ".codex/config.toml", "package.json", "pyproject.toml"):
        path = project_root / relative
        if path.is_file():
            candidates.append(path)
    for dirname in (".codex/hooks", "scripts", "bin", "tools"):
        folder = project_root / dirname
        if folder.is_dir():
            for path in folder.rglob("*"):
                if path.is_file() and path.stat().st_size <= 128_000:
                    candidates.append(path)
    assets: list[RepoAsset] = []
    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            text = path.read_text(encoding="utf-8", errors="replace")[:20_000]
        except OSError:
            continue
        assets.append(
            RepoAsset(
                path=str(path),
                kind="hook" if ".codex" in path.parts and "hooks" in str(path).lower() else "repo",
                searchable_text=f"{path.name} {text}".lower(),
            )
        )
    return assets


def _installed_tools(sessions: Iterable[SessionObservation]) -> list[dict[str, Any]]:
    """Resolve only command names already present in the selected session evidence."""
    ignored = {
        "cd",
        "echo",
        "export",
        "set",
        "set-item",
        "source",
        "test",
    }
    names: set[str] = set()
    for session in sessions:
        for execution in session.tool_executions:
            for segment in re.split(r"&&|\|\||[;\r\n]", execution.command):
                match = re.match(
                    r"\s*(?:&\s*)?(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))",
                    segment,
                )
                if not match:
                    continue
                name = next((value for value in match.groups() if value), "").strip()
                if name and name.casefold() not in ignored and "=" not in name:
                    names.add(name)
    tools: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in sorted(names, key=str.casefold):
        located = shutil.which(name)
        if not located:
            continue
        path = str(Path(located).resolve())
        key = path.casefold()
        if key in seen:
            continue
        seen.add(key)
        tools.append(
            {
                "kind": "installed-command",
                "name": Path(path).stem,
                "description": f"Executable observed in session commands and resolved on PATH as {name}",
                "path": path,
                "status": "available",
                "source": "session-command-path-probe",
            }
        )
    return tools


def _project_doc_limit(codex_home: Path, project_root: Path) -> int:
    limit = 32_768
    for path in (codex_home / "config.toml", project_root / ".codex" / "config.toml"):
        if not path.is_file():
            continue
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
            candidate = payload.get("project_doc_max_bytes")
            if isinstance(candidate, int) and candidate > 0:
                limit = candidate
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            continue
    return limit


def _inventory_agents_documents(codex_home: Path, project_root: Path) -> list[AgentsDocument]:
    limit = _project_doc_limit(codex_home, project_root)
    candidates: list[tuple[Path, str, int]] = []
    user_agents = codex_home / "AGENTS.md"
    if user_agents.is_file():
        candidates.append((user_agents, "user", 0))
    if project_root.is_dir():
        for path in project_root.rglob("AGENTS.md"):
            relative = path.relative_to(project_root)
            ignored = {
                ".git",
                ".venv",
                "node_modules",
                "__pycache__",
                ".codex-metabolism",
                ".demo-review",
                ".codex-metabolism-archive",
            }
            if any(part in ignored for part in relative.parts):
                continue
            depth = max(0, len(relative.parts) - 1)
            candidates.append((path, "project" if depth == 0 else "nested", depth))

    documents: list[AgentsDocument] = []
    seen: set[Path] = set()
    for path, scope, depth in candidates:
        try:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            raw = path.read_bytes()
        except OSError:
            continue
        try:
            content = raw.decode("utf-8")
            decode_errors = 0
        except UnicodeDecodeError:
            content = raw.decode("utf-8", errors="replace")
            decode_errors = 1
        documents.append(
            AgentsDocument(
                path=str(path),
                scope=scope,
                depth=depth,
                content_sha256=hashlib.sha256(raw).hexdigest(),
                byte_count=len(raw),
                line_count=len(content.splitlines()),
                codex_context_limit=limit,
                whole_document_evaluated=decode_errors == 0,
                content=content,
                decode_errors=decode_errors,
            )
        )
    return sorted(documents, key=lambda item: (item.scope, item.depth, item.path.casefold()))


def observe(
    codex_home: Path | str,
    skill_roots: Iterable[Path | str],
    *,
    days: float = 7,
    now: datetime | None = None,
    project_root: Path | str | None = None,
    catalog_entries: list[dict[str, Any]] | None = None,
    catalog_checked: bool = False,
    intervention_records: list[InterventionReceipt] | None = None,
) -> Observation:
    now = now or _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    codex_home = Path(codex_home).expanduser()
    project_root = Path(project_root or Path.cwd()).expanduser()
    sessions_root = codex_home / "sessions"
    cutoff = now.timestamp() - days * 86400
    files = []
    if sessions_root.is_dir():
        for path in sessions_root.rglob("rollout-*.jsonl"):
            try:
                if path.stat().st_mtime >= cutoff:
                    files.append(path)
            except OSError:
                continue
    sessions: list[SessionObservation] = []
    errors = 0
    structured = 0
    heuristic = 0
    files_parsed = 0
    for path in sorted(files):
        session, parse_errors, structured_events, heuristic_events = _parse_session(path)
        errors += parse_errors
        structured += structured_events
        heuristic += heuristic_events
        if session is not None:
            sessions.append(session)
            files_parsed += 1
    if errors:
        invocation = "partial"
    elif structured:
        invocation = "structured"
    elif sessions:
        invocation = "heuristic"
    else:
        invocation = "unavailable"
    coverage = Coverage(
        files_selected=len(files),
        files_parsed=files_parsed,
        parse_errors=errors,
        skill_invocation=invocation,
        structured_skill_events=structured,
        heuristic_skill_events=heuristic,
        catalog_checked=catalog_checked,
    )
    roots = [Path(root) for root in skill_roots]
    return Observation(
        codex_home=str(codex_home),
        project_root=str(project_root),
        days=days,
        sessions=sessions,
        skills=_inventory_skills(roots, sessions, now),
        repo_assets=_repo_assets(project_root),
        catalog_entries=list(catalog_entries or []),
        coverage=coverage,
        installed_tools=_installed_tools(sessions),
        agents_documents=_inventory_agents_documents(codex_home, project_root),
        intervention_records=list(intervention_records or []),
    )
