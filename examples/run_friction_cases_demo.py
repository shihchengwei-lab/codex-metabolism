from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codex_metabolism.decide import decide
from codex_metabolism.observe import observe
from codex_metabolism.stage import stage_review


REVIEW_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _message(text: str) -> dict:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def _tool(call_id: str, command: str, *, success: bool, output: str) -> list[dict]:
    status = "Script completed" if success else "Script failed"
    exit_code = 0 if success else 1
    return [
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "call_id": call_id,
                "name": "functions.exec",
                "input": json.dumps({"command": command}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": call_id,
                "output": f"{status}\nExit code: {exit_code}\nOutput:\n{output}",
            },
        },
    ]


def _records(
    session_id: str,
    *,
    timestamp: datetime,
    prompt: str,
    signature: str,
    failed_output: str,
    correction: str,
    recovery_command: str,
    recovery_output: str,
    success_output: str,
) -> list[dict]:
    records = [
        {
            "type": "session_meta",
            "payload": {
                "session_id": session_id,
                "timestamp": timestamp.isoformat(),
                "cwd": "C:/demo/repo",
                "cli_version": "0.144.5",
            },
        },
        {
            "type": "turn_context",
            "payload": {"model": "gpt-5.6", "cwd": "C:/demo/repo"},
        },
        _message(prompt),
    ]
    records.extend(
        _tool(
            f"{session_id}-failure",
            signature,
            success=False,
            output=failed_output,
        )
    )
    records.append(_message(correction))
    records.extend(
        _tool(
            f"{session_id}-recovery",
            recovery_command,
            success=True,
            output=recovery_output,
        )
    )
    records.extend(
        _tool(
            f"{session_id}-success",
            signature,
            success=True,
            output=success_output,
        )
    )
    return records


def _write_jsonl(path: Path, records: list[dict], timestamp: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    stamp = timestamp.timestamp()
    os.utime(path, (stamp, stamp))


def _write_ui_skill(skill_root: Path) -> None:
    skill = skill_root / "ui-verification" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        "---\n"
        "name: ui-verification\n"
        "description: Review dashboard completion with rendered screenshot evidence\n"
        "---\n\n"
        "# UI verification\n\n"
        "Run tests and inspect the rendered interface before reporting completion.\n",
        encoding="utf-8",
    )


def _seed_cases(codex_home: Path, skill_root: Path) -> None:
    _write_ui_skill(skill_root)
    cases = [
        {
            "prefix": "existing-tool",
            "prompt": "Explore recent Codex logs without exposing private session text.",
            "signature": "explore codex logs",
            "failed_output": "started a parallel parser without checking reviewed tools",
            "correction": (
                "No—do not build another session explorer. "
                "Evaluate the reviewed codlogs project instead."
            ),
            "recovery_command": "review codlogs provenance and license",
            "recovery_output": "codlogs review completed",
            "success_output": "bounded session exploration completed with codlogs",
        },
        {
            "prefix": "visual-proof",
            "prompt": "Review this dashboard and report whether the UI work is complete.",
            "signature": "review dashboard completion",
            "failed_output": "tests passed, but no rendered interface was inspected",
            "correction": (
                "No. Tests passing does not prove the UI is correct. Use $ui-verification "
                "and inspect a rendered screenshot before claiming completion."
            ),
            "recovery_command": "capture and inspect dashboard screenshot",
            "recovery_output": "rendered screenshot inspected",
            "success_output": "dashboard completion reviewed with rendered evidence",
        },
    ]
    for case_index, case in enumerate(cases):
        for session_index in (1, 2):
            timestamp = REVIEW_AT - timedelta(hours=case_index * 2 + session_index)
            session_id = f"{case['prefix']}-{session_index}"
            _write_jsonl(
                codex_home
                / "sessions"
                / "2026"
                / "07"
                / "20"
                / f"rollout-{session_id}.jsonl",
                _records(
                    session_id,
                    timestamp=timestamp,
                    prompt=str(case["prompt"]),
                    signature=str(case["signature"]),
                    failed_output=str(case["failed_output"]),
                    correction=str(case["correction"]),
                    recovery_command=str(case["recovery_command"]),
                    recovery_output=str(case["recovery_output"]),
                    success_output=str(case["success_output"]),
                ),
                timestamp,
            )


def run(output_root: Path) -> int:
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"demo output directory must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    codex_home = output_root / "demo-home" / ".codex"
    skill_root = output_root / "demo-home" / ".agents" / "skills"
    project_root = output_root / "demo-project"
    project_root.mkdir(parents=True)
    _seed_cases(codex_home, skill_root)
    staging = output_root / ".codex-metabolism"

    catalog = json.loads(
        (REPO_ROOT / "examples" / "reviewed-catalog.json").read_text(encoding="utf-8")
    )
    snapshot = observe(
        codex_home,
        [skill_root],
        days=7,
        now=REVIEW_AT,
        project_root=project_root,
        catalog_entries=catalog,
        catalog_checked=True,
    )
    decisions = decide(snapshot, now=REVIEW_AT)
    stage_review(snapshot, decisions, staging, generated_at=REVIEW_AT)
    ready = sum(1 for item in decisions if item.readiness == "ready")
    print(
        f"Staged {len(decisions)} decisions ({ready} ready, "
        f"{len(decisions) - ready} needs research) at {staging}"
    )

    payload = json.loads((staging / "decisions.json").read_text(encoding="utf-8"))
    by_signature = {
        item.get("metadata", {}).get("signature"): item
        for item in payload["decisions"]
    }
    existing_tool = by_signature["explore codex logs"]
    visual_proof = by_signature["review dashboard completion"]
    print(
        f"Existing-tool friction: {existing_tool['decision']} "
        f"{existing_tool['target_kind']} -> {existing_tool['target']}"
    )
    print(
        f"Visual-proof friction: {visual_proof['decision']} "
        f"{visual_proof['target_kind']} -> {visual_proof['target']}"
    )
    print(f"Inspect the retained case artifacts at: {output_root.resolve()}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay two non-command-order Codex collaboration friction cases"
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Empty directory for the isolated cases; defaults to a retained temporary directory",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output_root or Path(tempfile.mkdtemp(prefix="codex-metabolism-friction-"))
    try:
        return run(output)
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
