from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .advisor import AdvisorError, CodexAdvisor
from .automation import (
    AutomationError,
    build_config,
    disable_automation,
    enable_automation,
    get_automation_status,
    record_review_success,
    run_scheduled_review,
)
from .catalog import build_oss_query, search_github
from .codex_command import build_codex_command
from .decide import decide
from .evidence_export import export_evidence_csv
from .integrations.skillreaper import (
    collect_skillreaper,
    find_skillreaper,
    load_skillreaper_report,
)
from .interventions import InterventionError, load_interventions
from .lifecycle import (
    LifecycleError,
    activate_harness,
    activate_tool,
    apply_decision,
    archive_decision,
    reject_decision,
    restore_archived_skill,
    retire_tool,
    rollback_intervention,
)
from .observe import observe
from .stage import stage_review


def _default_codex_home() -> Path:
    return Path.home() / ".codex"


def _default_skill_roots() -> list[Path]:
    return [Path.home() / ".agents" / "skills", Path.home() / ".codex" / "skills"]


def _plugin_catalog() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            build_codex_command(["plugin", "list"]),
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    entries: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if not parts or "@" not in parts[0] or parts[0] == "PLUGIN":
            continue
        if len(parts) < 3 or parts[1].rstrip(",").casefold() != "installed":
            continue
        entries.append(
            {
                "kind": "plugin",
                "name": parts[0],
                "description": "Configured Codex marketplace plugin",
                "status": " ".join(parts[1:3]),
                "url": "",
                "license": "UNKNOWN",
                "updated_at": None,
                "stars": 0,
                "source": "codex-plugin-list",
            }
        )
    return entries


def _load_catalog(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("catalog file must contain a JSON array of objects")
    return payload


def _advisor_candidates(decisions: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": decision.id,
            "decision": decision.decision,
            "target_kind": decision.target_kind,
            "target": decision.target,
            "mechanism": decision.mechanism,
            "mechanical": decision.mechanism == "pretool_guard",
            "readiness": decision.readiness,
            "confidence": decision.confidence,
            "proposed_change": decision.proposed_change,
            "evidence_ids": [item["id"] for item in decision.evidence],
            "evidence": [
                {
                    "id": item["id"],
                    "kind": item["kind"],
                    "summary": item["summary"],
                    "hard": bool(item.get("hard")),
                }
                for item in decision.evidence
            ],
            "adoption_ladder": [
                {"name": rung["name"], "result": rung["result"]}
                for rung in decision.adoption_ladder
            ],
        }
        for decision in decisions
        if decision.decision != "KEEP"
    ]


def _collaboration_advisor_candidates(
    observation: Any, *, limit: int = 24
) -> list[dict[str, Any]]:
    friction: list[dict[str, Any]] = []
    workflows: list[dict[str, Any]] = []
    for session in reversed(observation.sessions):
        session_identity = f"{session.session_id}|{session.source_file}"
        session_key = hashlib.sha256(session_identity.encode("utf-8")).hexdigest()[:12]
        project_key = hashlib.sha256(
            str(session.cwd or "unknown").casefold().encode("utf-8")
        ).hexdigest()[:12]
        if session.feedback_candidates or session.interrupted_turns:
            context_id = hashlib.sha256(
                f"{session_identity}|context".encode("utf-8")
            ).hexdigest()[:12]
            friction.append(
                {
                    "id": f"signal-{context_id}",
                    "session_key": session_key,
                    "project_key": project_key,
                    "kind": "collaboration_context",
                    "user_inputs_sample": [
                        message.text[:200] for message in session.messages[:2]
                    ],
                }
            )
            for message in reversed(session.feedback_candidates[-2:]):
                signal_id = hashlib.sha256(
                    f"{session_identity}|feedback|{message.sequence}".encode("utf-8")
                ).hexdigest()[:12]
                friction.append(
                    {
                        "id": f"signal-{signal_id}",
                        "session_key": session_key,
                        "project_key": project_key,
                        "kind": "user_feedback",
                        "excerpt": message.text[:200],
                    }
                )
            if session.interrupted_turns:
                signal_id = hashlib.sha256(
                    f"{session_identity}|interruptions".encode("utf-8")
                ).hexdigest()[:12]
                friction.append(
                    {
                        "id": f"signal-{signal_id}",
                        "session_key": session_key,
                        "project_key": project_key,
                        "kind": "interrupted_turns",
                        "occurrence_count": session.interrupted_turns,
                    }
                )

        successful = sum(tool.status == "success" for tool in session.tool_executions)
        failed = sum(tool.status == "failure" for tool in session.tool_executions)
        if len(session.tool_executions) >= 4 and successful >= 2 and session.messages:
            signal_id = hashlib.sha256(
                f"{session_identity}|workflow".encode("utf-8")
            ).hexdigest()[:12]
            verification_like_successes = sum(
                tool.status == "success"
                and bool(
                    re.search(
                        r"(?i)(?:^|\s)(?:test|tests|pytest|unittest|build|lint|check)(?:\s|$)",
                        tool.command,
                    )
                )
                for tool in session.tool_executions
            )
            workflows.append(
                {
                    "id": f"signal-{signal_id}",
                    "session_key": session_key,
                    "project_key": project_key,
                    "kind": "workflow_candidate",
                    "user_inputs_sample": [
                        message.text[:200] for message in session.messages[:2]
                    ],
                    "tool_activity": {
                        "total": len(session.tool_executions),
                        "successful": successful,
                        "failed": failed,
                        "verification_like_successes": verification_like_successes,
                    },
                    "tool_trace": [
                        {"tool_name": tool.tool_name, "status": tool.status}
                        for tool in session.tool_executions[:8]
                    ],
                    "completion_verified": False,
                    "candidate_reason": (
                        "Substantial tool activity may contain a reusable workflow; "
                        "absence of later correction is not proof of task success."
                    ),
                }
            )

    friction_budget = min(len(friction), (limit + 1) // 2)
    selected = friction[:friction_budget]
    selected.extend(workflows[: limit - len(selected)])
    if len(selected) < limit:
        selected.extend(friction[friction_budget : friction_budget + limit - len(selected)])
    return selected[:limit]


# Kept for API compatibility with the first MVP.
_semantic_advisor_candidates = _collaboration_advisor_candidates


def _review(args: argparse.Namespace) -> int:
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    skill_roots = args.skill_root or _default_skill_roots()
    catalog: list[dict[str, Any]] = _plugin_catalog()
    checked = False
    if args.catalog_file:
        catalog.extend(_load_catalog(args.catalog_file))
        checked = True
    intervention_records = load_interventions(args.output_dir / "interventions.jsonl")

    snapshot = observe(
        args.codex_home,
        skill_roots,
        days=args.days,
        now=now,
        project_root=args.project_root,
        catalog_entries=catalog,
        catalog_checked=checked,
        intervention_records=intervention_records,
    )
    lifecycle_import = None
    if args.skillreaper_report:
        lifecycle_import = load_skillreaper_report(args.skillreaper_report)
    elif not args.no_skillreaper:
        executable = find_skillreaper()
        if executable:
            try:
                lifecycle_import = collect_skillreaper(args.days, executable=executable)
            except (OSError, RuntimeError, ValueError) as exc:
                print(f"SkillReaper evidence unavailable; retirement stays disabled: {exc}", file=sys.stderr)
    if lifecycle_import is not None:
        snapshot.lifecycle_evidence = lifecycle_import.evidence
        snapshot.coverage.skill_lifecycle_source = "skillreaper"
        snapshot.coverage.skill_lifecycle_complete = lifecycle_import.complete

    provisional = decide(snapshot, now=now)
    if args.search_oss:
        queries = {
            build_oss_query(
                item.metadata.get("signature", ""),
                item.metadata.get("required_command"),
            )
            for item in provisional
            if item.decision == "CREATE" and item.metadata.get("signature")
        }
        try:
            for query in sorted(queries):
                print(f"OSS search sends sanitized public keywords: {query}", file=sys.stderr)
                catalog.extend(search_github(query))
            checked = True
        except Exception as exc:
            print(f"OSS search incomplete: {exc}", file=sys.stderr)
            checked = False
        snapshot.catalog_entries = catalog
        snapshot.coverage.catalog_checked = checked

    decisions = decide(snapshot, now=now)
    semantic_suggestions: list[dict[str, Any]] = []
    semantic_candidates: list[dict[str, Any]] = []
    if args.advisor == "codex":
        advisor = CodexAdvisor(model=args.advisor_model)
        if decisions:
            candidates = _advisor_candidates(decisions)
            suggestions = (
                advisor.advise(candidates, cwd=args.project_root) if candidates else []
            )
            by_id = {item["candidate_id"]: item for item in suggestions}
            for decision in decisions:
                suggestion = by_id.get(decision.id)
                if suggestion is not None:
                    decision.metadata["codex_advisor"] = suggestion
                    decision.metadata["advisor_role"] = "non_authoritative"
        semantic_candidates = _collaboration_advisor_candidates(snapshot)
        if semantic_candidates:
            excerpt_count = sum(
                int("excerpt" in item) + len(item.get("user_inputs_sample", []))
                for item in semantic_candidates
            )
            print(
                "GPT-5.6 collaboration-layer review sends "
                f"{len(semantic_candidates)} pseudonymous candidates "
                f"({excerpt_count} bounded user excerpts) to OpenAI; "
                "results remain non-authoritative and human-reviewed.",
                file=sys.stderr,
            )
            semantic_suggestions = advisor.advise_collaboration(
                semantic_candidates, cwd=args.project_root
            )
    output = stage_review(
        snapshot,
        decisions,
        args.output_dir,
        generated_at=now,
        semantic_suggestions=semantic_suggestions,
        semantic_candidate_count=len(semantic_candidates),
        advisor_model=args.advisor_model if args.advisor == "codex" else None,
    )
    if args.export_evidence:
        exported = export_evidence_csv(snapshot, decisions, args.export_evidence)
        print(f"Exported structured evidence CSV to {exported}")
    ready = sum(1 for item in decisions if item.readiness == "ready")
    blocked = len(decisions) - ready
    proposed_changes = sum(1 for item in decisions if item.decision != "KEEP")
    kept = len(decisions) - proposed_changes
    print(
        f"Staged {len(decisions)} review items "
        f"({proposed_changes} proposed change{'s' if proposed_changes != 1 else ''}, "
        f"{kept} KEEP; {ready} ready, {blocked} needs research) at {output}"
    )
    record_review_success(args.output_dir, reviewed_at=now, source="manual")
    return 0


def _automation_config_path(output_dir: Path) -> Path:
    return output_dir / "automation" / "config.json"


def _enable(args: argparse.Namespace) -> int:
    enabled_at = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    config = build_config(
        output_dir=args.output_dir,
        project_root=args.project_root,
        codex_home=args.codex_home,
        skill_roots=args.skill_root or _default_skill_roots(),
        review_days=args.days,
        every_days=args.every_days,
        after_sessions=args.after_sessions,
        search_oss=args.search_oss,
        catalog_file=args.catalog_file,
        no_skillreaper=args.no_skillreaper,
        enabled_at=enabled_at,
        notify=not args.no_notify,
    )
    config_path = enable_automation(config)
    print(
        "Enabled staged review automation: "
        f"check daily; review after {args.after_sessions} new sessions or {args.every_days:g} days."
    )
    print(f"Config: {config_path}")
    print("Background reviews never apply, install, activate, archive, or delete anything.")
    if not args.search_oss:
        print("Background open-source search: disabled")
    return 0


def _status(args: argparse.Namespace) -> int:
    current = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    status = get_automation_status(
        _automation_config_path(args.output_dir),
        now=current,
    )
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(f"Automation: {'enabled' if status['enabled'] else 'disabled'}")
        print(f"Health: {status['health']}")
        print(f"Scheduler: {status['scheduler_kind']} · registered={status['registered']}")
        print(f"Pending sessions: {status['pending_sessions']}")
        print(f"Pending decisions: {status['pending_decisions']}")
        print(f"Last check: {status['last_check_at'] or 'never'}")
        print(f"Last successful review: {status['last_successful_review_at'] or 'never'}")
        print(f"Next time threshold: {status['next_due_at']}")
        if status["last_error"]:
            print(f"Last error: {status['last_error']}")
        print(f"Notice: {status['notice_path']}")
    return 1 if status["health"] in {"unregistered", "error", "overdue"} else 0


def _disable(args: argparse.Namespace) -> int:
    current = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    config_path = _automation_config_path(args.output_dir)
    disable_automation(config_path, now=current)
    print(f"Disabled scheduled reviews. Audit state retained at {config_path}")
    return 0


def _scheduled_review(args: argparse.Namespace) -> int:
    current = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    result = run_scheduled_review(
        args.config,
        now=current,
        review_runner=lambda argv: main(argv),
    )
    if result["ran_review"]:
        print(f"Scheduled review staged {result.get('decisions', 0)} decisions.")
    else:
        print(
            "Scheduled review skipped: "
            f"{result['reason']} ({result.get('pending_sessions', 0)} new sessions)."
        )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-metabolism")
    subparsers = parser.add_subparsers(dest="command", required=True)
    review = subparsers.add_parser("review", help="Observe, decide, and stage proposals")
    review.add_argument("--days", type=float, default=7)
    review.add_argument("--codex-home", type=Path, default=_default_codex_home())
    review.add_argument("--skill-root", type=Path, action="append")
    review.add_argument("--project-root", type=Path, default=Path.cwd())
    review.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    review.add_argument(
        "--export-evidence",
        type=Path,
        help=(
            "Write a deterministic CSV of structured evidence and coverage; "
            "raw prompts, evidence summaries, session IDs, and paths are excluded"
        ),
    )
    review.add_argument(
        "--catalog-file",
        type=Path,
        help="Reviewed JSON catalog; supplying it marks the external-tool rung checked",
    )
    review.add_argument(
        "--search-oss",
        action="store_true",
        help="Send sanitized keywords (never prompts or paths) to GitHub public repository search",
    )
    skillreaper = review.add_mutually_exclusive_group()
    skillreaper.add_argument(
        "--skillreaper-report",
        type=Path,
        help="Import an existing `reap --json` report without running the external tool",
    )
    skillreaper.add_argument(
        "--no-skillreaper",
        action="store_true",
        help="Do not auto-detect the optional read-only SkillReaper integration",
    )
    review.add_argument(
        "--advisor",
        choices=("none", "codex"),
        default="none",
        help=(
            "Use `codex` for the recommended model-assisted review: bounded, pseudonymous "
            "evidence is sent to OpenAI for GPT-5.6 semantic interpretation. `none` is the "
            "local deterministic fallback. Neither mode applies changes automatically"
        ),
    )
    review.add_argument("--advisor-model", default="gpt-5.6-sol", help=argparse.SUPPRESS)
    review.add_argument("--now", help=argparse.SUPPRESS)

    enable = subparsers.add_parser(
        "enable",
        help="Opt in to automatic local, stage-only reviews",
    )
    enable.add_argument("--days", type=float, default=7, help="Session window for each review")
    enable.add_argument("--every-days", type=float, default=7)
    enable.add_argument("--after-sessions", type=int, default=10)
    enable.add_argument("--codex-home", type=Path, default=_default_codex_home())
    enable.add_argument("--skill-root", type=Path, action="append")
    enable.add_argument("--project-root", type=Path, default=Path.cwd())
    enable.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    enable.add_argument(
        "--catalog-file",
        type=Path,
        help="Optional reviewed JSON catalog used by scheduled reviews",
    )
    enable.add_argument(
        "--search-oss",
        action="store_true",
        help="Opt in to sanitized GitHub public search during background reviews",
    )
    enable.add_argument(
        "--no-skillreaper",
        action="store_true",
        help="Disable optional read-only SkillReaper collection in background reviews",
    )
    enable.add_argument(
        "--no-notify",
        action="store_true",
        help="Do not attempt a local OS notification when decisions are staged or review fails",
    )
    enable.add_argument("--now", help=argparse.SUPPRESS)

    status = subparsers.add_parser("status", help="Show scheduler heartbeat and review backlog")
    status.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    status.add_argument("--json", action="store_true")
    status.add_argument("--now", help=argparse.SUPPRESS)

    disable = subparsers.add_parser("disable", help="Remove the native review schedule")
    disable.add_argument("--output-dir", type=Path, default=Path(".codex-metabolism"))
    disable.add_argument("--now", help=argparse.SUPPRESS)

    scheduled = subparsers.add_parser(
        "scheduled-review",
        help="Internal stage-only scheduler entrypoint",
    )
    scheduled.add_argument("--config", type=Path, required=True)
    scheduled.add_argument("--now", help=argparse.SUPPRESS)

    for name in ("apply", "archive", "reject"):
        command = subparsers.add_parser(name)
        command.add_argument("decision_id")
        command.add_argument("--staging", type=Path, default=Path(".codex-metabolism"))
        command.add_argument("--skill-root", type=Path, default=Path.home() / ".agents" / "skills")
        if name == "apply":
            command.add_argument("--project-root", type=Path, default=Path.cwd())
            command.add_argument("--codex-home", type=Path, default=_default_codex_home())
    activate = subparsers.add_parser(
        "activate-tool",
        help="Record a reviewed tool that the user already installed or enabled",
    )
    activate.add_argument("decision_id")
    activate.add_argument("--artifact", required=True, help="Existing path or executable name")
    activate.add_argument("--staging", type=Path, default=Path(".codex-metabolism"))
    trust = subparsers.add_parser(
        "activate-harness",
        help="Record a project hook as active after the user trusts it in Codex /hooks",
    )
    trust.add_argument("decision_id")
    trust.add_argument("--confirmed-trusted", action="store_true")
    trust.add_argument("--staging", type=Path, default=Path(".codex-metabolism"))
    retire = subparsers.add_parser(
        "retire-tool",
        help="Record an idle external tool as inactive without uninstalling it",
    )
    retire.add_argument("decision_id", help="RETIRE_CANDIDATE review decision ID")
    retire.add_argument("--confirmed-inactive", action="store_true")
    retire.add_argument("--staging", type=Path, default=Path(".codex-metabolism"))
    restore = subparsers.add_parser("restore", help="Restore a previously archived skill")
    restore.add_argument("decision_id")
    restore.add_argument("--staging", type=Path, default=Path(".codex-metabolism"))
    restore.add_argument("--skill-root", type=Path, default=Path.home() / ".agents" / "skills")
    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("decision_id", help="Original active intervention decision ID")
    rollback.add_argument("--staging", type=Path, default=Path(".codex-metabolism"))
    rollback.add_argument("--project-root", type=Path, default=Path.cwd())
    rollback.add_argument("--skill-root", type=Path, default=Path.home() / ".agents" / "skills")
    rollback.add_argument("--codex-home", type=Path, default=_default_codex_home())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "review":
            return _review(args)
        if args.command == "enable":
            return _enable(args)
        if args.command == "status":
            return _status(args)
        if args.command == "disable":
            return _disable(args)
        if args.command == "scheduled-review":
            return _scheduled_review(args)
        if args.command == "apply":
            apply_decision(
                args.staging,
                args.decision_id,
                project_root=args.project_root,
                skill_root=args.skill_root,
                codex_home=args.codex_home,
            )
        elif args.command == "archive":
            archive_decision(args.staging, args.decision_id, skill_root=args.skill_root)
        elif args.command == "reject":
            reject_decision(args.staging, args.decision_id)
        elif args.command == "activate-tool":
            activate_tool(args.staging, args.decision_id, artifact=args.artifact)
        elif args.command == "activate-harness":
            activate_harness(
                args.staging,
                args.decision_id,
                confirmed_trusted=args.confirmed_trusted,
            )
        elif args.command == "retire-tool":
            retire_tool(
                args.staging,
                args.decision_id,
                confirmed_inactive=args.confirmed_inactive,
            )
        elif args.command == "restore":
            restore_archived_skill(
                args.staging,
                args.decision_id,
                skill_root=args.skill_root,
            )
        elif args.command == "rollback":
            rollback_intervention(
                args.staging,
                args.decision_id,
                project_root=args.project_root,
                skill_root=args.skill_root,
                codex_home=args.codex_home,
            )
        return 0
    except (
        AdvisorError,
        AutomationError,
        InterventionError,
        LifecycleError,
        OSError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
