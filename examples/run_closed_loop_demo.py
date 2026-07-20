from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codex_metabolism.cli import main as metabolism_main
from codex_metabolism.lifecycle import activate_harness, apply_decision


FIRST_REVIEW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
SECOND_REVIEW = FIRST_REVIEW + timedelta(days=1)


def _success_records(session_id: str, timestamp: datetime) -> list[dict]:
    call_id = f"{session_id}-deploy"
    return [
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
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "call_id": call_id,
                "name": "functions.exec",
                "input": json.dumps({"command": "preflight && deploy production"}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": call_id,
                "output": "Script completed\nExit code: 0\nOutput:\ndeployed",
            },
        },
    ]


def _write_jsonl(path: Path, records: list[dict], timestamp: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    stamp = timestamp.timestamp()
    os.utime(path, (stamp, stamp))


def _review(
    *,
    codex_home: Path,
    skill_root: Path,
    project_root: Path,
    staging: Path,
    catalog: Path,
    skillreaper_report: Path,
    now: datetime,
) -> int:
    return metabolism_main(
        [
            "review",
            "--days",
            "7",
            "--codex-home",
            str(codex_home),
            "--skill-root",
            str(skill_root),
            "--project-root",
            str(project_root),
            "--catalog-file",
            str(catalog),
            "--skillreaper-report",
            str(skillreaper_report),
            "--output-dir",
            str(staging),
            "--now",
            now.isoformat(),
        ]
    )


def run(output_root: Path) -> int:
    repo = REPO_ROOT
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"demo output directory must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    demo_home = output_root / "demo-home"
    project_root = output_root / "demo-project"
    shutil.copytree(repo / "examples" / "demo-home", demo_home)
    shutil.copytree(repo / "examples" / "demo-project", project_root)
    codex_home = demo_home / ".codex"
    skill_root = demo_home / ".agents" / "skills"
    staging = output_root / ".codex-metabolism"

    first_code = _review(
        codex_home=codex_home,
        skill_root=skill_root,
        project_root=project_root,
        staging=staging,
        catalog=repo / "examples" / "reviewed-catalog.json",
        skillreaper_report=repo / "examples" / "skillreaper-report.json",
        now=FIRST_REVIEW,
    )
    if first_code:
        return first_code
    first = json.loads((staging / "decisions.json").read_text(encoding="utf-8"))
    harness = next(
        item
        for item in first["decisions"]
        if item["decision"] == "CREATE" and item["target_kind"] == "HARNESS"
    )
    rule = next(
        item
        for item in first["decisions"]
        if item["decision"] == "PATCH" and item["target_kind"] == "RULE"
    )
    print("First review: CREATE HARNESS + PATCH RULE")

    for decision in (harness, rule):
        apply_decision(
            staging,
            decision["id"],
            project_root=project_root,
            skill_root=skill_root,
            codex_home=codex_home,
            changed_at=FIRST_REVIEW,
        )
    activate_harness(
        staging,
        harness["id"],
        confirmed_trusted=True,
        activated_at=FIRST_REVIEW,
    )

    for index in (1, 2):
        timestamp = FIRST_REVIEW + timedelta(hours=index)
        _write_jsonl(
            codex_home
            / "sessions"
            / "2026"
            / "07"
            / "20"
            / f"rollout-future-success-{index}.jsonl",
            _success_records(f"future-success-{index}", timestamp),
            timestamp,
        )

    second_code = _review(
        codex_home=codex_home,
        skill_root=skill_root,
        project_root=project_root,
        staging=staging,
        catalog=repo / "examples" / "reviewed-catalog.json",
        skillreaper_report=repo / "examples" / "skillreaper-report.json",
        now=SECOND_REVIEW,
    )
    if second_code:
        return second_code
    second = json.loads((staging / "decisions.json").read_text(encoding="utf-8"))
    validation = next(
        item
        for item in second["decisions"]
        if item.get("metadata", {}).get("intervention_id") == harness["id"]
        and item.get("metadata", {}).get("lifecycle_verdict") == "VALIDATED"
    )
    if validation["decision"] != "KEEP":
        raise RuntimeError("closed-loop demo did not validate the active harness")
    print("Second review: KEEP HARNESS (VALIDATED)")
    print(f"Inspect the retained demo artifacts at: {output_root.resolve()}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the two-generation Codex Metabolism demo")
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Empty directory for the isolated demo; defaults to a retained temporary directory",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output_root or Path(tempfile.mkdtemp(prefix="codex-metabolism-demo-"))
    try:
        return run(output)
    except (OSError, RuntimeError, StopIteration, ValueError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
