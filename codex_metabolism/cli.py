from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .evidence import build_evidence_packet, write_evidence_packet
from .interventions import InterventionError, load_interventions
from .lifecycle import (
    LifecycleError,
    apply_agent_proposal,
    record_agent_intervention,
    reject_agent_proposal,
    restore_retired_skill,
    rollback_agent_intervention,
)
from .observe import observe
from .proposals import ProposalError, stage_agent_proposals


def _default_codex_home() -> Path:
    return Path.home() / ".codex"


def _default_skill_roots() -> list[Path]:
    return [Path.home() / ".agents" / "skills", Path.home() / ".codex" / "skills"]


def _now(value: str | None) -> datetime:
    parsed = datetime.fromisoformat(value) if value else datetime.now(timezone.utc)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _observe(args: argparse.Namespace) -> int:
    output = args.output_dir
    snapshot = observe(
        args.codex_home,
        args.skill_root or _default_skill_roots(),
        days=args.days,
        now=_now(args.now),
        project_root=args.project_root,
        intervention_records=load_interventions(output / "interventions.jsonl"),
    )
    packet = build_evidence_packet(snapshot, generated_at=_now(args.now))
    destination = write_evidence_packet(packet, output)
    coverage = packet["coverage"]
    print(
        f"Prepared {len(packet['sessions'])} neutral session capsules at {destination} "
        f"({coverage['files_parsed']}/{coverage['files_selected']} files parsed; "
        f"{coverage['duplicate_session_files']} duplicate/fork files collapsed; "
        f"{coverage['duplicate_user_events']} duplicate user events collapsed; "
        f"{coverage['parse_errors']} malformed lines)."
    )
    print("Codex must interpret the evidence and author proposals; the runtime made no decision.")
    return 0


def _stage(args: argparse.Namespace) -> int:
    evidence = args.evidence or args.output_dir / "evidence.json"
    output = stage_agent_proposals(evidence, args.proposal, args.output_dir)
    print(f"Validated and sealed Agent-authored proposals at {output}")
    manifest = json.loads((output / "proposals.json").read_text(encoding="utf-8"))
    if not manifest["proposals"]:
        print("No changes proposed. Live state is unchanged and no approval is needed.")
        return 0
    for proposal in manifest["proposals"]:
        print(f"Approval digest for {proposal['proposal_id']}: {proposal['approval_digest']}")
    print("Live state is unchanged. Show report.md, exact artifacts, and digests before approval.")
    return 0


def _apply(args: argparse.Namespace) -> int:
    destination = apply_agent_proposal(
        args.output_dir,
        args.proposal_id,
        args.skill_root,
        approved_digest=args.approved_digest,
    )
    print(f"Applied approved Agent proposal to {destination}")
    return 0


def _reject(args: argparse.Namespace) -> int:
    reject_agent_proposal(args.output_dir, args.proposal_id)
    print(f"Rejected proposal {args.proposal_id}; live state was unchanged.")
    return 0


def _record(args: argparse.Namespace) -> int:
    artifact = record_agent_intervention(
        args.output_dir,
        args.proposal_id,
        args.artifact,
        approved_digest=args.approved_digest,
    )
    print(f"Recorded approved Agent intervention at {artifact}")
    return 0


def _rollback(args: argparse.Namespace) -> int:
    destination = rollback_agent_intervention(
        args.output_dir,
        args.proposal_id,
        args.skill_root,
        human_approved=args.human_approved,
    )
    print(f"Rolled back intervention {args.proposal_id}; retained artifact at {destination}")
    return 0


def _restore(args: argparse.Namespace) -> int:
    destination = restore_retired_skill(
        args.output_dir,
        args.proposal_id,
        args.skill_root,
        human_approved=args.human_approved,
    )
    print(f"Restored retired skill to {destination}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-metabolism",
        description=(
            "Deterministic evidence, persistence, and safe-mutation substrate for the "
            "$codex-metabolism skill. Codex performs semantic interpretation."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    observe_parser = subparsers.add_parser(
        "observe",
        help="Prepare neutral, bounded collaboration evidence without making decisions",
    )
    observe_parser.add_argument("--days", type=float, default=7)
    observe_parser.add_argument("--codex-home", type=Path, default=_default_codex_home())
    observe_parser.add_argument("--skill-root", type=Path, action="append")
    observe_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    observe_parser.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    observe_parser.add_argument("--now", help=argparse.SUPPRESS)
    observe_parser.set_defaults(handler=_observe)

    stage_parser = subparsers.add_parser(
        "stage",
        help="Validate evidence references and seal exact Agent-authored artifacts",
    )
    stage_parser.add_argument("proposal", type=Path)
    stage_parser.add_argument("--evidence", type=Path)
    stage_parser.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    stage_parser.set_defaults(handler=_stage)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply one sealed skill proposal matching the reviewed approval digest",
    )
    apply_parser.add_argument("proposal_id")
    apply_parser.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    apply_parser.add_argument("--skill-root", type=Path, default=Path.home() / ".agents" / "skills")
    apply_parser.add_argument(
        "--approved-digest",
        required=True,
        help="Exact approval digest shown with the reviewed proposal",
    )
    apply_parser.set_defaults(handler=_apply)

    reject_parser = subparsers.add_parser(
        "reject",
        help="Reject a staged proposal without changing live state",
    )
    reject_parser.add_argument("proposal_id")
    reject_parser.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    reject_parser.set_defaults(handler=_reject)

    record_parser = subparsers.add_parser(
        "record",
        help="Preserve evidence from a non-skill change made through an existing mechanism",
    )
    record_parser.add_argument("proposal_id")
    record_parser.add_argument("--artifact", type=Path, required=True)
    record_parser.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    record_parser.add_argument(
        "--approved-digest",
        required=True,
        help="Exact approval digest shown with the reviewed proposal",
    )
    record_parser.set_defaults(handler=_record)

    rollback_parser = subparsers.add_parser(
        "rollback",
        help="Rollback an active Agent-authored skill while preserving an archive",
    )
    rollback_parser.add_argument("proposal_id")
    rollback_parser.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    rollback_parser.add_argument("--skill-root", type=Path, default=Path.home() / ".agents" / "skills")
    rollback_parser.add_argument("--human-approved", action="store_true")
    rollback_parser.set_defaults(handler=_rollback)

    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore a human-approved retired skill from its archive",
    )
    restore_parser.add_argument("proposal_id")
    restore_parser.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    restore_parser.add_argument("--skill-root", type=Path, default=Path.home() / ".agents" / "skills")
    restore_parser.add_argument("--human-approved", action="store_true")
    restore_parser.set_defaults(handler=_restore)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (InterventionError, LifecycleError, ProposalError, ValueError) as exc:
        print(f"codex-metabolism: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
