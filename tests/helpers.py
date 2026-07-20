from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def write_jsonl(path: Path, records: list[dict], *, malformed: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        if malformed:
            handle.write("{not-json\n")
    stamp = NOW.timestamp()
    os.utime(path, (stamp, stamp))
    return path


def session_records(
    session_id: str,
    *,
    failed_command: str = "deploy production",
    prerequisite: str = "preflight",
    correction: str | None = None,
    skill_name: str | None = None,
) -> list[dict]:
    correction = correction or f"No. Run `{prerequisite}` before `{failed_command}`."
    prompt = f"${skill_name} deploy this" if skill_name else "Deploy this"
    return [
        {
            "type": "session_meta",
            "payload": {
                "session_id": session_id,
                "timestamp": "2026-07-20T08:00:00Z",
                "cwd": "C:/demo/repo",
                "cli_version": "0.144.5",
            },
        },
        {
            "type": "turn_context",
            "payload": {"model": "gpt-5.6", "cwd": "C:/demo/repo"},
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "call_id": f"{session_id}-fail",
                "name": "functions.exec",
                "input": json.dumps({"command": failed_command}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": f"{session_id}-fail",
                "output": "Script failed\nExit code: 1\nOutput:\npreflight required",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": correction}],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "call_id": f"{session_id}-preflight",
                "name": "functions.exec",
                "input": json.dumps({"command": prerequisite}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": f"{session_id}-preflight",
                "output": "Script completed\nExit code: 0\nOutput:\nok",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "call_id": f"{session_id}-success",
                "name": "functions.exec",
                "input": json.dumps({"command": failed_command}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": f"{session_id}-success",
                "output": "Script completed\nExit code: 0\nOutput:\ndeployed",
            },
        },
    ]


def write_skill(root: Path, name: str, *, description: str = "Demo skill", age_days: int = 40) -> Path:
    skill = root / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    stamp = NOW.timestamp() - age_days * 86400
    os.utime(skill, (stamp, stamp))
    os.utime(skill.parent, (stamp, stamp))
    return skill


def make_deploy_home(base: Path, *, malformed: bool = False) -> tuple[Path, Path]:
    codex_home = base / ".codex"
    skills_root = base / ".agents" / "skills"
    write_jsonl(
        codex_home / "sessions" / "2026" / "07" / "20" / "rollout-one.jsonl",
        session_records("session-one"),
        malformed=malformed,
    )
    write_jsonl(
        codex_home / "sessions" / "2026" / "07" / "20" / "rollout-two.jsonl",
        session_records("session-two"),
    )
    return codex_home, skills_root
