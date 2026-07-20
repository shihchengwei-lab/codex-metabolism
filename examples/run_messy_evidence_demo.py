from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codex_metabolism.decide import decide
from codex_metabolism.integrations.skillreaper import parse_skillreaper_report
from codex_metabolism.models import Observation
from codex_metabolism.observe import observe
from codex_metabolism.stage import stage_review


REVIEW_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
ACTION_SIGNATURE = "explore codex logs safely"
SINGLE_RECOVERY_SIGNATURE = "publish package"
NO_RECOVERY_SIGNATURE = "review flaky tests"


def _message(text: str) -> dict[str, Any]:
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }


def _tool(
    call_id: str,
    command: str,
    *,
    success: bool,
    output: str,
) -> list[dict[str, Any]]:
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
                "output": (
                    f"{status}\nExit code: {exit_code}\nOutput:\n{output}"
                ),
            },
        },
    ]


def _records(
    session_id: str,
    *,
    timestamp: datetime,
    prompt: str,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = [
        {
            "type": "session_meta",
            "payload": {
                "session_id": session_id,
                "timestamp": timestamp.isoformat(),
                "cwd": "C:/demo/noisy-repo",
                "cli_version": "0.144.5",
            },
        },
        {
            "type": "turn_context",
            "payload": {"model": "gpt-5.6", "cwd": "C:/demo/noisy-repo"},
        },
        _message(prompt),
    ]
    for index, event in enumerate(events, start=1):
        if event["kind"] == "message":
            records.append(_message(str(event["text"])))
            continue
        records.extend(
            _tool(
                f"{session_id}-{index}",
                str(event["command"]),
                success=bool(event["success"]),
                output=str(event["output"]),
            )
        )
    return records


def _write_jsonl(
    path: Path,
    records: list[dict[str, Any]],
    timestamp: datetime,
    *,
    malformed: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        if malformed:
            handle.write('{"type":"response_item","payload":\n')
    stamp = timestamp.timestamp()
    os.utime(path, (stamp, stamp))


def _write_old_skill(skill_root: Path) -> Path:
    skill = skill_root / "old-unused" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        "---\n"
        "name: old-unused\n"
        "description: A deliberately stale-looking synthetic skill\n"
        "---\n\n"
        "# Old unused\n",
        encoding="utf-8",
    )
    old_stamp = (REVIEW_AT - timedelta(days=60)).timestamp()
    os.utime(skill, (old_stamp, old_stamp))
    os.utime(skill.parent, (old_stamp, old_stamp))
    return skill


def _action_events(correction: str) -> list[dict[str, Any]]:
    return [
        {
            "kind": "tool",
            "command": ACTION_SIGNATURE,
            "success": False,
            "output": "started a parallel viewer without checking reviewed tools",
        },
        {"kind": "message", "text": correction},
        {
            "kind": "tool",
            "command": "git status --short",
            "success": True,
            "output": "unrelated repository status collected",
        },
        {
            "kind": "message",
            "text": "Keep any exported evidence bounded and free of private prompt text.",
        },
        {
            "kind": "tool",
            "command": "review codlogs provenance and privacy",
            "success": True,
            "output": "license and bounded-export behavior reviewed",
        },
        {
            "kind": "tool",
            "command": ACTION_SIGNATURE,
            "success": True,
            "output": "bounded read-only exploration completed with codlogs",
        },
    ]


def _seed_fixture(codex_home: Path, skill_root: Path) -> None:
    _write_old_skill(skill_root)
    sessions: list[tuple[str, str, list[dict[str, Any]], bool]] = [
        (
            "action-one",
            "Find the useful parts of recent Codex history without exporting private text.",
            _action_events(
                "No - do not build another log viewer. Evaluate the reviewed codlogs project instead."
            ),
            False,
        ),
        (
            "action-two",
            "I need a bounded way to inspect recent Codex history, not a new analytics product.",
            _action_events(
                "Wrong direction. Reuse the reviewed codlogs tool; the task is not to implement a new explorer."
            ),
            True,
        ),
        (
            "single-recovery",
            "Publish the package when it is ready.",
            [
                {
                    "kind": "tool",
                    "command": SINGLE_RECOVERY_SIGNATURE,
                    "success": False,
                    "output": "package metadata has not been checked",
                },
                {
                    "kind": "message",
                    "text": "No. Check package metadata before publishing.",
                },
                {
                    "kind": "tool",
                    "command": "check package metadata",
                    "success": True,
                    "output": "metadata is valid",
                },
                {
                    "kind": "tool",
                    "command": SINGLE_RECOVERY_SIGNATURE,
                    "success": True,
                    "output": "package published",
                },
            ],
            False,
        ),
        (
            "no-recovery-one",
            "Review the flaky test report and tell me what failed.",
            [
                {
                    "kind": "tool",
                    "command": NO_RECOVERY_SIGNATURE,
                    "success": False,
                    "output": "mixed product and infrastructure failures",
                },
                {
                    "kind": "message",
                    "text": "No. Separate product failures from CI infrastructure noise before concluding.",
                },
                {
                    "kind": "tool",
                    "command": "run focused unit tests",
                    "success": True,
                    "output": "focused tests passed",
                },
            ],
            False,
        ),
        (
            "no-recovery-two",
            "Re-check the flaky test report after the CI retry.",
            [
                {
                    "kind": "tool",
                    "command": NO_RECOVERY_SIGNATURE,
                    "success": False,
                    "output": "runner disconnected before classification",
                },
                {
                    "kind": "message",
                    "text": "Do not call this a product regression until the runner failure is isolated.",
                },
                {
                    "kind": "tool",
                    "command": "inspect runner health",
                    "success": True,
                    "output": "transient runner outage confirmed",
                },
            ],
            False,
        ),
        (
            "unrelated-success",
            "Summarize the already-clean retry result.",
            [
                {
                    "kind": "tool",
                    "command": NO_RECOVERY_SIGNATURE,
                    "success": True,
                    "output": "retry report contained no failing tests",
                }
            ],
            False,
        ),
    ]
    for index, (session_id, prompt, events, malformed) in enumerate(sessions, start=1):
        timestamp = REVIEW_AT - timedelta(minutes=index * 17)
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
                prompt=prompt,
                events=events,
            ),
            timestamp,
            malformed=malformed,
        )


def _catalog() -> list[dict[str, Any]]:
    reviewed = json.loads(
        (REPO_ROOT / "examples" / "reviewed-catalog.json").read_text(
            encoding="utf-8"
        )
    )
    codlogs = next(
        entry for entry in reviewed if entry.get("name") == "tobitege/codlogs"
    )
    return [
        codlogs,
        {
            "kind": "oss",
            "name": "popular/codex-console",
            "description": "A popular Codex dashboard and general automation toolkit.",
            "url": "https://example.invalid/popular/codex-console",
            "license": "MIT",
            "updated_at": "2026-07-20",
            "stars": 50000,
            "source": "synthetic-distractor",
        },
    ]


def _signature(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def _outcome_counts(
    observation: Observation,
    signature: str,
) -> dict[str, int]:
    wanted = _signature(signature)
    failure_sessions: set[str] = set()
    recovered_sessions: set[str] = set()
    success_only_sessions: set[str] = set()
    for session in observation.sessions:
        matching = [
            tool
            for tool in session.tool_executions
            if _signature(tool.command) == wanted
        ]
        failures = [tool for tool in matching if tool.status == "failure"]
        successes = [tool for tool in matching if tool.status == "success"]
        if failures:
            failure_sessions.add(session.session_id)
        if successes and not failures:
            success_only_sessions.add(session.session_id)
        if any(
            success.sequence > failure.sequence
            for failure in failures
            for success in successes
        ):
            recovered_sessions.add(session.session_id)
    return {
        "failure_sessions": len(failure_sessions),
        "verified_recovery_sessions": len(recovered_sessions),
        "success_only_sessions": len(success_only_sessions),
    }


def _decision_for(decisions: list[Any], signature: str) -> Any | None:
    wanted = _signature(signature)
    return next(
        (
            decision
            for decision in decisions
            if _signature(str(decision.metadata.get("signature") or "")) == wanted
        ),
        None,
    )


def _abstention(
    observation: Observation,
    decisions: list[Any],
    signature: str,
) -> dict[str, Any]:
    if _decision_for(decisions, signature) is not None:
        raise RuntimeError(f"expected the noisy case to be left without action: {signature}")
    counts = _outcome_counts(observation, signature)
    recovered = counts["verified_recovery_sessions"]
    reason = (
        "only_one_verified_recovery_session"
        if recovered == 1
        else "no_verified_recovery_path"
    )
    return {"signature": signature, "reason": reason, **counts}


def run(output_root: Path) -> int:
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"demo output directory must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    codex_home = output_root / "demo-home" / ".codex"
    skill_root = output_root / "demo-home" / ".agents" / "skills"
    project_root = output_root / "demo-project"
    project_root.mkdir(parents=True)
    _seed_fixture(codex_home, skill_root)
    catalog = _catalog()

    snapshot = observe(
        codex_home,
        [skill_root],
        days=7,
        now=REVIEW_AT,
        project_root=project_root,
        catalog_entries=catalog,
        catalog_checked=True,
    )
    lifecycle = parse_skillreaper_report(
        {
            "GeneratedAt": REVIEW_AT.isoformat(),
            "Sessions": 12,
            "MalformedLines": 1,
            "Warnings": [
                {
                    "Path": "synthetic-session-window",
                    "Msg": "incomplete lifecycle evidence",
                }
            ],
            "Rows": [
                {
                    "Category": "skill",
                    "Name": "old-unused",
                    "Platform": "codex",
                    "Path": str(skill_root / "old-unused"),
                    "Removable": True,
                    "Uses": 0,
                    "Verdict": "REAP",
                    "Reason": "no use observed in the incomplete window",
                }
            ],
        }
    )
    snapshot.lifecycle_evidence = lifecycle.evidence
    snapshot.coverage.skill_lifecycle_source = "skillreaper"
    snapshot.coverage.skill_lifecycle_complete = lifecycle.complete

    decisions = decide(snapshot, now=REVIEW_AT)
    staging = output_root / ".codex-metabolism"
    stage_review(snapshot, decisions, staging, generated_at=REVIEW_AT)

    action = _decision_for(decisions, ACTION_SIGNATURE)
    if action is None or len(decisions) != 1:
        raise RuntimeError(
            f"expected exactly one evidence-backed decision, observed {len(decisions)}"
        )
    abstentions = [
        _abstention(snapshot, decisions, SINGLE_RECOVERY_SIGNATURE),
        _abstention(snapshot, decisions, NO_RECOVERY_SIGNATURE),
    ]
    unsafe_retirements = [
        decision for decision in decisions if decision.decision == "RETIRE_CANDIDATE"
    ]
    coverage_warning = (
        f"{snapshot.coverage.parse_errors} malformed JSONL line; skill invocation "
        "evidence is partial and lifecycle evidence is incomplete"
    )
    result = {
        "summary": {
            "decision_count": len(decisions),
            "abstention_count": len(abstentions),
            "coverage_warning_count": 1,
            "unsafe_retirement_decision_count": len(unsafe_retirements),
        },
        "fixture": {
            "session_count": len(snapshot.sessions),
            "catalog_candidate_count": len(catalog),
            "synthetic": True,
            "known_limit": (
                "This challenge does not test semantic clustering; recurring commands use "
                "normalized exact signatures."
            ),
        },
        "actioned": [
            {
                "signature": ACTION_SIGNATURE,
                "decision": action.decision,
                "target_kind": action.target_kind,
                "target": action.target,
                **_outcome_counts(snapshot, ACTION_SIGNATURE),
            }
        ],
        "abstentions": abstentions,
        "coverage_warnings": [coverage_warning],
        "coverage": snapshot.coverage.to_dict(),
        "retirement": {
            "target": "old-unused",
            "candidate_count": len(unsafe_retirements),
            "blocked_by": "incomplete_lifecycle_evidence",
        },
    }
    (output_root / "challenge-results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"Messy evidence: {len(decisions)} decision, "
        f"{len(abstentions)} abstentions"
    )
    print(f"Actioned: {action.decision} {action.target_kind} -> {action.target}")
    print("Abstained: publish package -> only 1 verified recovery session")
    print(
        "Abstained: review flaky tests -> repeated failures but no verified recovery path"
    )
    print(f"Coverage warning: {coverage_warning}")
    print(f"Unsafe retirement decisions: {len(unsafe_retirements)}")
    print(f"Inspect the retained challenge artifacts at: {output_root.resolve()}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay noisy synthetic evidence and conservative non-decisions"
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Empty directory for the isolated challenge; defaults to a retained temporary directory",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output_root or Path(
        tempfile.mkdtemp(prefix="codex-metabolism-messy-")
    )
    try:
        return run(output)
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
