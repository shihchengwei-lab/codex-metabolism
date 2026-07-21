from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import (
    AgentsDocument,
    Coverage,
    InstalledSkill,
    InterventionReceipt,
    Observation,
    SessionObservation,
    ToolExecution,
    UserMessage,
)


SKILL_MENTION_RE = re.compile(r"\$([a-z0-9][a-z0-9_-]{1,80})", re.IGNORECASE)
EXIT_CODE_RE = re.compile(r"(?i)exit\s+code\s*:\s*(-?\d+)")
MAX_TEXT = 280
MAX_MESSAGES = 120
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
    return text.replace("\x00", "")[:limit]


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
    calls: dict[str, dict[str, Any]] = {}
    outputs: dict[str, tuple[int, Any]] = {}
    skill_signals: set[str] = set()
    parse_errors = 0
    structured_skill_events = 0
    heuristic_skill_events = 0
    interrupted_turns = 0
    duplicate_user_events = 0
    last_user_text: str | None = None
    last_user_sequence = -10
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

            if (
                top_type == "event_msg"
                and payload_type == "user_message"
                and isinstance(payload.get("message"), str)
            ):
                candidate_messages = [("user", payload["message"])]
            elif (
                top_type == "response_item"
                and payload_type == "message"
                and payload.get("role") == "user"
            ):
                candidate_messages = list(_walk_text(payload))
            else:
                candidate_messages = []
            for role, text in candidate_messages:
                if role != "user":
                    continue
                cleaned = _safe_text(text, MAX_TEXT).strip()
                if not cleaned or cleaned.startswith("<"):
                    continue
                if cleaned == last_user_text and sequence - last_user_sequence <= 2:
                    duplicate_user_events += 1
                    continue
                last_user_text = cleaned
                last_user_sequence = sequence
                messages.append(UserMessage(sequence=sequence, text=cleaned))
                if len(messages) > MAX_MESSAGES:
                    messages.pop(0)
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
            elif isinstance(payload_type, str) and "skill" in payload_type.lower():
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
    return (
        SessionObservation(
            session_id=str(meta.get("session_id") or path.stem),
            timestamp=meta.get("timestamp"),
            cwd=meta.get("cwd"),
            cli_version=meta.get("cli_version"),
            model=model,
            source_file=str(path),
            messages=messages,
            interrupted_turns=interrupted_turns,
            tool_executions=tools,
            skill_signals=skill_signals,
            parse_errors=parse_errors,
            duplicate_user_events=duplicate_user_events,
        ),
        parse_errors,
        structured_skill_events,
        heuristic_skill_events,
    )


def _primary_session_file(session: SessionObservation) -> bool:
    """Prefer the root rollout over child-Agent snapshots that inherit its session id."""

    return Path(session.source_file).stem.casefold().endswith(session.session_id.casefold())


def _session_preference(session: SessionObservation) -> tuple[int, int, str]:
    event_count = len(session.messages) + len(session.tool_executions) + session.interrupted_turns
    return (int(_primary_session_file(session)), event_count, session.source_file.casefold())


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
                content = skill_md.read_bytes()
                stat = skill_md.stat()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            name, description = _frontmatter(skill_md)
            found.append(
                InstalledSkill(
                    name=name,
                    description=description,
                    path=str(skill_md),
                    root=str(root),
                    sha256=hashlib.sha256(content).hexdigest(),
                    age_days=max(0.0, (now.timestamp() - stat.st_mtime) / 86400),
                    protected=".system" in skill_md.parts,
                    usage_signals=counts[name.lower()],
                )
            )
    return sorted(found, key=lambda item: (item.name.lower(), item.path.lower()))


def _inventory_agents_documents(codex_home: Path, project_root: Path) -> list[AgentsDocument]:
    candidates: list[tuple[Path, str, int]] = []
    user_agents = codex_home / "AGENTS.md"
    if user_agents.is_file():
        candidates.append((user_agents, "user", 0))
    if project_root.is_dir():
        ignored = {
            ".git",
            ".venv",
            "node_modules",
            "__pycache__",
            ".codex-metabolism",
            ".demo-review",
            ".codex-metabolism-archive",
        }
        for path in project_root.rglob("AGENTS.md"):
            relative = path.relative_to(project_root)
            if any(part in ignored for part in relative.parts):
                continue
            depth = max(0, len(relative.parts) - 1)
            candidates.append((path, "project" if depth == 0 else "nested", depth))
    documents: list[AgentsDocument] = []
    seen: set[Path] = set()
    for path, scope, depth in candidates:
        try:
            resolved = path.resolve()
            raw = path.read_bytes()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            lines = raw.decode("utf-8").splitlines()
            whole_document_available = True
        except UnicodeDecodeError:
            lines = raw.decode("utf-8", errors="replace").splitlines()
            whole_document_available = False
        documents.append(
            AgentsDocument(
                path=str(path),
                scope=scope,
                depth=depth,
                content_sha256=hashlib.sha256(raw).hexdigest(),
                byte_count=len(raw),
                line_count=len(lines),
                whole_document_available=whole_document_available,
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
    intervention_records: list[InterventionReceipt] | None = None,
) -> Observation:
    current = now or _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    home = Path(codex_home).expanduser()
    project = Path(project_root or Path.cwd()).expanduser()
    sessions_root = home / "sessions"
    cutoff = current.timestamp() - days * 86400
    files: list[Path] = []
    if sessions_root.is_dir():
        for path in sessions_root.rglob("rollout-*.jsonl"):
            try:
                if path.stat().st_mtime >= cutoff:
                    files.append(path)
            except OSError:
                continue
    parsed_sessions: list[tuple[SessionObservation, int, int]] = []
    errors = files_parsed = 0
    for path in sorted(files):
        session, parse_errors, structured_events, heuristic_events = _parse_session(path)
        errors += parse_errors
        if session is not None:
            parsed_sessions.append((session, structured_events, heuristic_events))
            files_parsed += 1

    selected_by_id: dict[str, tuple[SessionObservation, int, int]] = {}
    for candidate in parsed_sessions:
        session = candidate[0]
        current_candidate = selected_by_id.get(session.session_id)
        if current_candidate is None or _session_preference(session) > _session_preference(
            current_candidate[0]
        ):
            selected_by_id[session.session_id] = candidate
    selected = list(selected_by_id.values())
    sessions = sorted(
        (item[0] for item in selected),
        key=lambda session: (session.timestamp or "", session.source_file.casefold()),
    )
    structured = sum(item[1] for item in selected)
    heuristic = sum(item[2] for item in selected)
    duplicate_user_events = sum(session.duplicate_user_events for session in sessions)
    invocation = (
        "partial"
        if errors
        else "structured"
        if structured
        else "heuristic"
        if sessions
        else "unavailable"
    )
    roots = [Path(root).expanduser() for root in skill_roots]
    return Observation(
        codex_home=str(home),
        project_root=str(project),
        skill_roots=[str(root) for root in roots],
        days=days,
        sessions=sessions,
        skills=_inventory_skills(roots, sessions, current),
        coverage=Coverage(
            files_selected=len(files),
            files_parsed=files_parsed,
            unique_sessions=len(sessions),
            duplicate_session_files=max(0, files_parsed - len(sessions)),
            duplicate_user_events=duplicate_user_events,
            parse_errors=errors,
            skill_invocation=invocation,
            structured_skill_events=structured,
            heuristic_skill_events=heuristic,
        ),
        agents_documents=_inventory_agents_documents(home, project),
        intervention_records=list(intervention_records or []),
    )
