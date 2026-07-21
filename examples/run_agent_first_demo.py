from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codex_metabolism.evidence import build_evidence_packet, write_evidence_packet
from codex_metabolism.interventions import load_interventions
from codex_metabolism.lifecycle import apply_agent_proposal, rollback_agent_intervention
from codex_metabolism.observe import observe
from codex_metabolism.proposals import stage_agent_proposals


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _records(session_id: str, *, command: str, correction: str, cwd: str) -> list[dict]:
    return [
        {
            "type": "session_meta",
            "payload": {
                "session_id": session_id,
                "timestamp": NOW.isoformat(),
                "cwd": cwd,
                "cli_version": "demo",
            },
        },
        {
            "type": "turn_context",
            "payload": {"model": "gpt-5.6", "cwd": cwd},
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Ship this to production."}],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "call_id": f"{session_id}-failed",
                "name": "functions.exec",
                "input": json.dumps({"command": command}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": f"{session_id}-failed",
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
                "input": json.dumps({"command": "python tools/preflight.py --production"}),
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": f"{session_id}-preflight",
                "output": "Script completed\nExit code: 0\nOutput:\nchecks passed",
            },
        },
    ]


def _write_session(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    stamp = NOW.timestamp()
    os.utime(path, (stamp, stamp))


def _observe(codex_home: Path, skills: Path, project: Path, staging: Path) -> dict:
    snapshot = observe(
        codex_home,
        [skills],
        days=7,
        now=NOW,
        project_root=project,
        intervention_records=load_interventions(staging / "interventions.jsonl"),
    )
    packet = build_evidence_packet(snapshot, generated_at=NOW)
    write_evidence_packet(packet, staging)
    return packet


def _write_recorded_agent_draft(packet: dict, draft: Path) -> Path:
    """Write a fixed Codex-authored fixture; the public demo makes no model call."""
    skill = draft / "artifacts" / "deploy-safely" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        "---\n"
        "name: deploy-safely\n"
        "description: Use when deploying this service to production; verify the target and run repository preflight before any deployment.\n"
        "---\n\n"
        "# Deploy safely\n\n"
        "1. Confirm the requested environment and stop if it is ambiguous.\n"
        "2. Run `python tools/preflight.py --production`.\n"
        "3. Stop on any failed check; do not hide or bypass it.\n"
        "4. Run the repository deployment command only after preflight succeeds.\n"
        "5. Report the preflight and deployment results separately.\n",
        encoding="utf-8",
        newline="\n",
    )
    evidence_ids = [
        event["id"]
        for session in packet["sessions"]
        for event in session["events"]
        if event["kind"] in {"user_message", "tool_execution"}
    ]
    proposal = {
        "schema_version": 1,
        "review_id": packet["review_id"],
        "proposals": [
            {
                "proposal_id": "agent-deploy-safely",
                "action": "CREATE",
                "layer": "SKILL",
                "target": "deploy-safely",
                "evidence_ids": evidence_ids,
                "reasoning": (
                    "A recorded Codex review grouped two differently worded deployment "
                    "sessions into one reusable preflight workflow."
                ),
                "expected_effect": "Make the verified deployment path reusable in later sessions.",
                "rollback_when": "The skill adds ceremony without preventing deployment recovery.",
                "alternatives_checked": [
                    {"level": "builtin", "result": "no repository-specific deployment workflow"},
                    {"level": "installed", "result": "no matching installed skill"},
                    {"level": "repository", "result": "preflight script exists and is reused"},
                    {"level": "ecosystem", "result": "generic tools lack this repository contract"},
                ],
                "artifact": {"path": "artifacts/deploy-safely/SKILL.md"},
            }
        ],
    }
    path = draft / "proposal.json"
    path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run(output_root: Path, *, prepare_only: bool = False) -> int:
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"demo output directory must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    codex_home = output_root / "codex-home"
    skills = output_root / "skills"
    project = output_root / "project"
    staging = output_root / ".codex-metabolism"
    project.mkdir()
    tools = project / "tools"
    tools.mkdir()
    (tools / "preflight.py").write_text(
        "from __future__ import annotations\n\n"
        "import sys\n\n"
        "if '--production' not in sys.argv:\n"
        "    raise SystemExit('expected --production')\n"
        "print('checks passed')\n",
        encoding="utf-8",
        newline="\n",
    )
    (tools / "release.py").write_text(
        "from __future__ import annotations\n\n"
        "import sys\n\n"
        "environment = sys.argv[1] if len(sys.argv) > 1 else 'development'\n"
        "print(f'deploy:{environment}')\n",
        encoding="utf-8",
        newline="\n",
    )
    (project / "release.ps1").write_text(
        "param([string]$Environment = 'development')\n"
        "Write-Output \"deploy:$Environment\"\n",
        encoding="utf-8",
        newline="\n",
    )
    synthetic_cwd = str(project.resolve())

    _write_session(
        codex_home / "sessions" / "2026" / "07" / "20" / "rollout-one.jsonl",
        _records(
            "synthetic-one",
            command="python tools/release.py production",
            correction="Run our production preflight first, then retry.",
            cwd=synthetic_cwd,
        ),
    )
    _write_session(
        codex_home / "sessions" / "2026" / "07" / "20" / "rollout-two.jsonl",
        _records(
            "synthetic-two",
            command="./release.ps1 -Environment prod",
            correction="You skipped tools/preflight.py again. Check production before release.",
            cwd=synthetic_cwd,
        ),
    )

    packet = _observe(codex_home, skills, project, staging)
    print("Runtime interpretation: 0 semantic decisions")
    print(f"Neutral evidence: {len(packet['sessions'])} session capsules")
    if prepare_only:
        print("Synthetic evidence is ready for a live Codex review.")
        print(f"Target project (inspect read-only before approval): {project.resolve()}")
        print(
            "Prompt: Use $codex-metabolism to interpret the existing synthetic evidence at "
            f"{(staging / 'evidence.json').resolve()}. Do not re-observe. Check existing "
            f"capabilities, including the target project at {project.resolve()}, without "
            "modifying it. Author zero to three complete proposals, stage them, show every "
            "diff, and wait for approval."
        )
        return 0

    proposal_path = _write_recorded_agent_draft(packet, output_root / "recorded-codex-draft")
    stage_agent_proposals(staging / "evidence.json", proposal_path, staging)
    manifest = json.loads((staging / "proposals.json").read_text(encoding="utf-8"))
    approved_digest = manifest["proposals"][0]["approval_digest"]
    print("Recorded Codex fixture: CREATE SKILL deploy-safely")
    print("Runtime gate: evidence references and exact artifact sealed")

    apply_agent_proposal(
        staging,
        "agent-deploy-safely",
        skills,
        approved_digest=approved_digest,
        changed_at=NOW,
    )
    print("Human gate fixture: the exact displayed digest was approved in this isolated demo")

    later = _observe(codex_home, skills, project, staging)
    receipt = later["portfolio"]["interventions"][0]
    print(f"Receipt visible to the next review: {receipt['status']}")

    rollback_agent_intervention(
        staging,
        "agent-deploy-safely",
        skills,
        human_approved=True,
        changed_at=NOW,
    )
    print("Rollback: live skill archived, not deleted")
    print(f"Inspect the isolated artifacts at: {output_root.resolve()}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the isolated Agent-first metabolism demo")
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Empty directory for retained demo artifacts; defaults to a temporary directory",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Stop after creating neutral synthetic evidence for a live Codex review",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output_root or Path(tempfile.mkdtemp(prefix="codex-metabolism-agent-first-"))
    try:
        return run(output, prepare_only=args.prepare_only)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
