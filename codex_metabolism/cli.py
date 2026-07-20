from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .advisor import AdvisorError, CodexAdvisor
from .catalog import build_oss_query, search_github
from .codex_command import build_codex_command
from .decide import decide
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
    ]


def _review(args: argparse.Namespace) -> int:
    now = datetime.fromisoformat(args.now) if args.now else None
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
    if args.advisor == "codex" and decisions:
        candidates = _advisor_candidates(decisions)
        suggestions = CodexAdvisor(model=args.advisor_model).advise(
            candidates,
            cwd=args.project_root,
        )
        by_id = {item["candidate_id"]: item for item in suggestions}
        for decision in decisions:
            suggestion = by_id.get(decision.id)
            if suggestion is not None:
                decision.metadata["codex_advisor"] = suggestion
                decision.metadata["advisor_role"] = "non_authoritative"
    output = stage_review(snapshot, decisions, args.output_dir, generated_at=now)
    ready = sum(1 for item in decisions if item.readiness == "ready")
    blocked = len(decisions) - ready
    print(
        f"Staged {len(decisions)} decisions ({ready} ready, {blocked} needs research) at {output}"
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
            "Optional second opinion. `codex` sends bounded decision and evidence summaries "
            "to an ephemeral, read-only Codex run; it never changes authoritative decisions"
        ),
    )
    review.add_argument("--advisor-model", default="gpt-5.6-sol", help=argparse.SUPPRESS)
    review.add_argument("--now", help=argparse.SUPPRESS)

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
    except (AdvisorError, InterventionError, LifecycleError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
