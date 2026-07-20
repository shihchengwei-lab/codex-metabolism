from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents_review import MANAGED_END, MANAGED_START
from .interventions import append_intervention, latest_interventions, load_interventions
from .models import InterventionReceipt
from .names import safe_name


class LifecycleError(RuntimeError):
    pass


def _load(staging: Path) -> dict[str, Any]:
    path = staging / "decisions.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"invalid staging decisions: {path}") from exc


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _find(payload: dict[str, Any], decision_id: str) -> dict[str, Any]:
    for decision in payload.get("decisions", []):
        if decision.get("id") == decision_id:
            return decision
    raise LifecycleError(f"decision not found: {decision_id}")


def _require_proposed(decision: dict[str, Any]) -> None:
    if decision.get("status") != "proposed":
        raise LifecycleError(f"decision is already {decision.get('status')}")
    if decision.get("readiness") != "ready":
        raise LifecycleError("adoption ladder is incomplete; research must finish before apply")


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise LifecycleError(f"path escapes approved root: {resolved}") from exc
    return resolved


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _managed_byte_region(payload: bytes) -> tuple[int, int]:
    start_marker = MANAGED_START.encode("ascii")
    end_marker = MANAGED_END.encode("ascii")
    if payload.count(start_marker) != 1 or payload.count(end_marker) != 1:
        raise LifecycleError("AGENTS.md must contain exactly one managed marker pair")
    start = payload.index(start_marker)
    content_start = start + len(start_marker)
    content_end = payload.index(end_marker)
    if content_end <= content_start:
        raise LifecycleError("AGENTS.md managed markers are out of order")

    def standalone(offset: int, marker: bytes) -> bool:
        line_start = payload.rfind(b"\n", 0, offset) + 1
        line_end = payload.find(b"\n", offset)
        if line_end < 0:
            line_end = len(payload)
        return payload[line_start:line_end].strip(b" \t\r") == marker

    if not standalone(start, start_marker) or not standalone(content_end, end_marker):
        raise LifecycleError("AGENTS.md managed markers must be on standalone lines")
    return content_start, content_end


def _mark(
    staging: Path,
    payload: dict[str, Any],
    decision: dict[str, Any],
    status: str,
    *,
    changed_at: datetime | None = None,
) -> None:
    decision["status"] = status
    decision["status_changed_at"] = (changed_at or datetime.now(timezone.utc)).isoformat()
    _atomic_json(staging / "decisions.json", payload)


def _apply_harness(staging: Path, decision: dict[str, Any], project_root: Path) -> Path:
    if decision.get("mechanism") == "adopt_external":
        raise LifecycleError("external tools require manual source and license review; automatic install is disabled")
    if decision.get("mechanism") != "pretool_guard":
        raise LifecycleError("this harness proposal is review-only in the MVP")
    source = staging / "proposed-harness" / decision["id"]
    if not (source / "guard.py").is_file() or not (source / "rule.json").is_file():
        raise LifecycleError("staged harness files are missing")
    codex_dir = _inside(project_root / ".codex", project_root)
    destination = _inside(
        codex_dir / "hooks" / f"codex-metabolism-{decision['id']}", project_root
    )
    if destination.exists():
        raise LifecycleError(f"harness destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)

    hooks_path = _inside(codex_dir / "hooks.json", project_root)
    if hooks_path.exists():
        try:
            hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            shutil.rmtree(destination)
            raise LifecycleError(f"existing hooks.json is invalid: {hooks_path}") from exc
    else:
        hooks = {"description": "Project hooks reviewed and installed by the user.", "hooks": {}}
    hooks.setdefault("hooks", {})
    groups = hooks["hooks"].setdefault("PreToolUse", [])
    command = f'"{sys.executable}" "{destination / "guard.py"}"'
    group = {
        "matcher": "^Bash$",
        "hooks": [
            {
                "type": "command",
                "command": command,
                "commandWindows": command,
                "timeout": 10,
                "statusMessage": "Checking evidence-backed preflight guard",
                "codexMetabolismDecision": decision["id"],
            }
        ],
    }
    groups.append(group)
    try:
        _atomic_json(hooks_path, hooks)
    except Exception:
        shutil.rmtree(destination)
        raise
    return destination


def _apply_skill(staging: Path, decision: dict[str, Any], skill_root: Path) -> Path:
    proposed = staging / "proposed-skills" / safe_name(decision["target"]) / "SKILL.md"
    if not proposed.is_file():
        raise LifecycleError(f"staged skill is missing: {proposed}")
    destination = _inside(skill_root / safe_name(decision["target"]) / "SKILL.md", skill_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if decision["decision"] == "CREATE":
        if destination.exists():
            raise LifecycleError(f"skill already exists: {destination}")
    elif decision["decision"] == "PATCH":
        existing = _inside(Path(decision["metadata"]["existing_path"]), skill_root)
        expected = decision["metadata"].get("expected_sha256")
        if not existing.is_file() or (expected and _sha256(existing) != expected):
            raise LifecycleError("live skill changed after review; rerun review before applying")
        destination = existing
    descriptor, temporary = tempfile.mkstemp(prefix=".SKILL.md.", dir=destination.parent)
    os.close(descriptor)
    try:
        shutil.copyfile(proposed, temporary)
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return destination


def _apply_rule(
    staging: Path,
    decision: dict[str, Any],
    *,
    project_root: Path,
    codex_home: Path,
) -> Path:
    managed = decision.get("metadata", {}).get("managed_region", {})
    if not managed.get("applyable"):
        raise LifecycleError(
            "AGENTS.md recommendations are suggestion-only without a valid staged managed-region edit"
        )
    scope = decision.get("metadata", {}).get("scope")
    root = codex_home if scope == "user" else project_root
    source = _inside(Path(decision["metadata"]["source_path"]), root)
    expected = decision["metadata"].get("content_sha256")
    if not source.is_file() or (expected and _sha256(source) != expected):
        raise LifecycleError("AGENTS.md changed after review; rerun review before applying")
    proposal = staging / "proposed-rules" / decision["id"] / "managed-block.proposed.txt"
    backup = staging / "proposed-rules" / decision["id"] / "managed-block.original.txt"
    if not proposal.is_file() or not backup.is_file():
        raise LifecycleError("staged AGENTS.md managed-region files are missing")
    current = source.read_bytes()
    content_start, content_end = _managed_byte_region(current)
    original = current[content_start:content_end]
    original_hash = managed.get("original_content_sha256")
    if original_hash and hashlib.sha256(original).hexdigest() != original_hash:
        raise LifecycleError("AGENTS.md managed region changed after review")
    reviewed_backup = backup.read_bytes()
    if reviewed_backup != original:
        raise LifecycleError("staged AGENTS.md backup does not match the live managed region")
    replacement = proposal.read_bytes()
    _atomic_bytes(source, current[:content_start] + replacement + current[content_end:])
    return source


def apply_decision(
    staging_dir: Path | str,
    decision_id: str,
    *,
    project_root: Path | str,
    skill_root: Path | str,
    codex_home: Path | str | None = None,
    changed_at: datetime | None = None,
) -> None:
    staging = Path(staging_dir)
    payload = _load(staging)
    decision = _find(payload, decision_id)
    _require_proposed(decision)
    if decision.get("decision") not in {"CREATE", "PATCH"}:
        raise LifecycleError(f"{decision.get('decision')} is not an apply action")
    if decision.get("target_kind") == "HARNESS":
        artifact = _apply_harness(staging, decision, Path(project_root))
        scope = "project"
    elif decision.get("target_kind") == "SKILL":
        artifact = _apply_skill(staging, decision, Path(skill_root))
        scope = "user"
    elif decision.get("target_kind") == "RULE":
        artifact = _apply_rule(
            staging,
            decision,
            project_root=Path(project_root),
            codex_home=Path(codex_home) if codex_home is not None else Path.home() / ".codex",
        )
        scope = str(decision.get("metadata", {}).get("scope") or "project")
    elif decision.get("target_kind") == "TOOL":
        raise LifecycleError(
            "external tools are never installed by apply; install after review, then record activation"
        )
    else:
        raise LifecycleError(f"unsupported apply target: {decision.get('target_kind')}")
    when = changed_at or datetime.now(timezone.utc)
    receipt_metadata: dict[str, Any] = {
        "decision_type": decision.get("decision"),
        "hooks_path": str((Path(project_root) / ".codex" / "hooks.json").resolve())
        if decision.get("target_kind") == "HARNESS"
        else None,
    }
    if decision.get("target_kind") == "SKILL":
        original = staging / "proposed-skills" / safe_name(decision["target"]) / "original.SKILL.md"
        receipt_metadata.update(
            {
                "original_path": str(artifact.resolve()),
                "applied_sha256": _sha256(artifact),
                "backup_path": str(original.resolve()) if original.is_file() else None,
            }
        )
    elif decision.get("target_kind") == "RULE":
        original = staging / "proposed-rules" / decision["id"] / "managed-block.original.txt"
        receipt_metadata.update(
            {
                "original_path": str(artifact.resolve()),
                "applied_sha256": _sha256(artifact),
                "backup_path": str(original.resolve()),
                "managed_region_only": True,
            }
        )
    pending_trust = decision.get("target_kind") == "HARNESS"
    append_intervention(
        staging / "interventions.jsonl",
        InterventionReceipt(
            decision_id=decision["id"],
            target_kind=decision["target_kind"],
            target=decision["target"],
            mechanism=decision["mechanism"],
            scope=scope,
            status="PENDING_TRUST" if pending_trust else "ACTIVE",
            activated_at=when.isoformat(),
            artifact_path=str(artifact.resolve()),
            signature=decision.get("metadata", {}).get("signature"),
            expected_effect=decision.get("proposed_change", ""),
            baseline_session_ids=list(decision.get("metadata", {}).get("session_ids", [])),
            metadata={
                **receipt_metadata,
                "requires_codex_hook_trust": pending_trust,
            },
        ),
    )
    _mark(
        staging,
        payload,
        decision,
        "pending_trust" if pending_trust else "applied",
        changed_at=when,
    )


def activate_harness(
    staging_dir: Path | str,
    decision_id: str,
    *,
    confirmed_trusted: bool,
    activated_at: datetime | None = None,
) -> InterventionReceipt:
    """Activate a staged hook only after the user confirms Codex hook trust review."""
    if not confirmed_trusted:
        raise LifecycleError("open `/hooks`, review the hook, and confirm trust before activation")
    staging = Path(staging_dir)
    records = load_interventions(staging / "interventions.jsonl")
    pending = next(
        (
            item
            for item in latest_interventions(records)
            if item.decision_id == decision_id
            and item.target_kind == "HARNESS"
            and item.status == "PENDING_TRUST"
        ),
        None,
    )
    if pending is None:
        raise LifecycleError(f"pending-trust harness intervention not found: {decision_id}")
    if not Path(pending.artifact_path).is_dir():
        raise LifecycleError("installed harness artifact is missing")
    hooks_value = pending.metadata.get("hooks_path")
    if not hooks_value:
        raise LifecycleError("installed harness receipt has no hooks path")
    try:
        hooks = json.loads(Path(hooks_value).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("installed harness hooks file cannot be verified") from exc
    if not any(
        hook.get("codexMetabolismDecision") == decision_id
        for group in hooks.get("hooks", {}).get("PreToolUse", [])
        for hook in group.get("hooks", [])
    ):
        raise LifecycleError("installed harness hook entry is missing")
    when = activated_at or datetime.now(timezone.utc)
    active = InterventionReceipt(
        decision_id=pending.decision_id,
        target_kind=pending.target_kind,
        target=pending.target,
        mechanism=pending.mechanism,
        scope=pending.scope,
        status="ACTIVE",
        activated_at=when.isoformat(),
        artifact_path=pending.artifact_path,
        signature=pending.signature,
        expected_effect=pending.expected_effect,
        baseline_session_ids=pending.baseline_session_ids,
        metadata={
            **pending.metadata,
            "user_confirmed_codex_hook_trust": True,
            "trust_confirmed_at": when.isoformat(),
        },
    )
    append_intervention(staging / "interventions.jsonl", active)
    try:
        payload = _load(staging)
        decision = _find(payload, decision_id)
    except LifecycleError:
        pass
    else:
        _mark(staging, payload, decision, "activated", changed_at=when)
    return active


def activate_tool(
    staging_dir: Path | str,
    decision_id: str,
    *,
    artifact: Path | str,
    activated_at: datetime | None = None,
) -> InterventionReceipt:
    """Record a user-installed external tool without downloading or modifying it."""
    staging = Path(staging_dir)
    payload = _load(staging)
    decision = _find(payload, decision_id)
    _require_proposed(decision)
    if decision.get("target_kind") != "TOOL" or decision.get("mechanism") not in {
        "adopt_external",
        "configure_installed",
    }:
        raise LifecycleError("only reviewed installed or external TOOL decisions can be activated")
    candidate = Path(artifact).expanduser()
    if candidate.exists():
        resolved = candidate.resolve()
    else:
        located = shutil.which(str(artifact))
        if not located:
            raise LifecycleError(
                "tool artifact was not found; install and review it before recording activation"
            )
        resolved = Path(located).resolve()
    records = load_interventions(staging / "interventions.jsonl")
    if any(
        item.decision_id == decision_id and item.status == "ACTIVE"
        for item in latest_interventions(records)
    ):
        raise LifecycleError(f"tool intervention is already active: {decision_id}")
    when = activated_at or datetime.now(timezone.utc)
    external = decision.get("metadata", {}).get("external_tool", {})
    installed = decision.get("metadata", {}).get("installed_tool", {})
    receipt = InterventionReceipt(
        decision_id=decision["id"],
        target_kind="TOOL",
        target=decision["target"],
        mechanism=decision["mechanism"],
        scope="user",
        status="ACTIVE",
        activated_at=when.isoformat(),
        artifact_path=str(resolved),
        signature=decision.get("metadata", {}).get("signature"),
        expected_effect=decision.get("proposed_change", ""),
        baseline_session_ids=list(decision.get("metadata", {}).get("session_ids", [])),
        metadata={
            "activation_evidence": "artifact_exists",
            "source_url": external.get("url"),
            "reported_license": external.get("license"),
            "observed_installed_path": installed.get("path"),
            "installed_or_enabled_by_user": True,
        },
    )
    append_intervention(staging / "interventions.jsonl", receipt)
    _mark(staging, payload, decision, "activated", changed_at=when)
    return receipt


def retire_tool(
    staging_dir: Path | str,
    decision_id: str,
    *,
    confirmed_inactive: bool,
    retired_at: datetime | None = None,
) -> InterventionReceipt:
    """Record a reviewed tool as inactive; never uninstall or delete the external artifact."""
    if not confirmed_inactive:
        raise LifecycleError(
            "external-tool retirement must be confirmed after the user disables or uninstalls it"
        )
    staging = Path(staging_dir)
    payload = _load(staging)
    decision = _find(payload, decision_id)
    _require_proposed(decision)
    if (
        decision.get("target_kind") != "TOOL"
        or decision.get("decision") != "RETIRE_CANDIDATE"
        or decision.get("mechanism") != "intervention_reevaluation"
    ):
        raise LifecycleError("only a reviewed idle TOOL intervention can be recorded retired")
    original_id = decision.get("metadata", {}).get("intervention_id")
    records = load_interventions(staging / "interventions.jsonl")
    active = next(
        (
            item
            for item in latest_interventions(records)
            if item.decision_id == original_id
            and item.target_kind == "TOOL"
            and item.status == "ACTIVE"
        ),
        None,
    )
    if active is None:
        raise LifecycleError(f"active external-tool intervention not found: {original_id}")
    when = retired_at or datetime.now(timezone.utc)
    receipt = InterventionReceipt(
        decision_id=active.decision_id,
        target_kind="TOOL",
        target=active.target,
        mechanism=active.mechanism,
        scope=active.scope,
        status="RETIRED",
        activated_at=active.activated_at,
        artifact_path=active.artifact_path,
        signature=active.signature,
        expected_effect=active.expected_effect,
        baseline_session_ids=active.baseline_session_ids,
        metadata={
            **active.metadata,
            "lifecycle_event": "USER_CONFIRMED_INACTIVE",
            "retired_at": when.isoformat(),
            "retirement_decision_id": decision_id,
            "external_artifact_deleted_by_metabolism": False,
        },
    )
    append_intervention(staging / "interventions.jsonl", receipt)
    _mark(staging, payload, decision, "retired", changed_at=when)
    return receipt


def archive_decision(
    staging_dir: Path | str,
    decision_id: str,
    *,
    skill_root: Path | str,
    archived_at: datetime | None = None,
) -> Path:
    staging = Path(staging_dir)
    root = Path(skill_root)
    payload = _load(staging)
    decision = _find(payload, decision_id)
    _require_proposed(decision)
    if decision.get("decision") != "RETIRE_CANDIDATE" or decision.get("target_kind") != "SKILL":
        raise LifecycleError("only RETIRE_CANDIDATE skills can be archived")
    source_md = _inside(Path(decision["metadata"]["existing_path"]), root)
    source = source_md.parent
    expected = decision["metadata"].get("expected_sha256")
    if not source_md.is_file() or (expected and _sha256(source_md) != expected):
        raise LifecycleError("live skill changed after review; rerun review before archiving")
    when = archived_at or datetime.now(timezone.utc)
    stamp = when.strftime("%Y%m%dT%H%M%SZ")
    archive_root = _inside(root / ".codex-metabolism-archive", root)
    archive_root.mkdir(parents=True, exist_ok=True)
    destination = _inside(archive_root / f"{safe_name(decision['target'])}-{stamp}", root)
    if destination.exists():
        raise LifecycleError(f"archive destination already exists: {destination}")
    shutil.move(str(source), str(destination))
    append_intervention(
        staging / "interventions.jsonl",
        InterventionReceipt(
            decision_id=decision["id"],
            target_kind="SKILL",
            target=decision["target"],
            mechanism="archive_skill",
            scope="user",
            status="ARCHIVED",
            activated_at=when.isoformat(),
            artifact_path=str(destination.resolve()),
            expected_effect=decision.get("proposed_change", ""),
            metadata={"original_path": str(source.resolve())},
        ),
    )
    _mark(staging, payload, decision, "archived", changed_at=when)
    return destination


def restore_archived_skill(
    staging_dir: Path | str,
    decision_id: str,
    *,
    skill_root: Path | str,
    restored_at: datetime | None = None,
) -> Path:
    staging = Path(staging_dir)
    root = Path(skill_root)
    records = load_interventions(staging / "interventions.jsonl")
    record = next(
        (
            item
            for item in latest_interventions(records)
            if item.decision_id == decision_id and item.status == "ARCHIVED"
        ),
        None,
    )
    if record is None or record.target_kind != "SKILL":
        raise LifecycleError(f"archived skill intervention not found: {decision_id}")
    source = _inside(Path(record.artifact_path), root)
    destination_value = record.metadata.get("original_path")
    if not destination_value:
        raise LifecycleError("archived skill has no reviewed restore path")
    destination = _inside(Path(destination_value), root)
    if not (source / "SKILL.md").is_file():
        raise LifecycleError("archived skill payload is missing")
    if destination.exists():
        raise LifecycleError(f"skill restore destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    when = restored_at or datetime.now(timezone.utc)
    restored = InterventionReceipt(
        decision_id=record.decision_id,
        target_kind="SKILL",
        target=record.target,
        mechanism="archive_skill",
        scope=record.scope,
        status="ACTIVE",
        activated_at=when.isoformat(),
        artifact_path=str(destination.resolve()),
        signature=record.signature,
        expected_effect="Restore the archived skill after explicit human approval.",
        baseline_session_ids=record.baseline_session_ids,
        metadata={
            **record.metadata,
            "lifecycle_event": "RESTORED",
            "restored_from": str(source.resolve()),
        },
    )
    try:
        append_intervention(staging / "interventions.jsonl", restored)
    except Exception:
        shutil.move(str(destination), str(source))
        raise
    try:
        payload = _load(staging)
        decision = _find(payload, decision_id)
    except LifecycleError:
        pass
    else:
        _mark(staging, payload, decision, "restored", changed_at=when)
    return destination.resolve()


def rollback_intervention(
    staging_dir: Path | str,
    decision_id: str,
    *,
    project_root: Path | str,
    skill_root: Path | str,
    codex_home: Path | str | None = None,
    rolled_back_at: datetime | None = None,
) -> Path:
    staging = Path(staging_dir)
    records = load_interventions(staging / "interventions.jsonl")
    record = next(
        (
            item
            for item in reversed(latest_interventions(records))
            if item.decision_id == decision_id
        ),
        None,
    )
    if record is None or record.status not in {"ACTIVE", "PENDING_TRUST"}:
        raise LifecycleError(f"active or pending-trust intervention not found: {decision_id}")
    when = rolled_back_at or datetime.now(timezone.utc)

    if record.target_kind == "HARNESS":
        root = Path(project_root)
        artifact = _inside(Path(record.artifact_path), root)
        hooks_path = _inside(root / ".codex" / "hooks.json", root)
        try:
            hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LifecycleError(f"cannot safely read hooks file: {hooks_path}") from exc
        groups = hooks.get("hooks", {}).get("PreToolUse", [])
        retained_groups = []
        for group in groups:
            retained_hooks = [
                hook
                for hook in group.get("hooks", [])
                if hook.get("codexMetabolismDecision") != decision_id
            ]
            if retained_hooks:
                updated = dict(group)
                updated["hooks"] = retained_hooks
                retained_groups.append(updated)
        hooks.setdefault("hooks", {})["PreToolUse"] = retained_groups
        archive_root = _inside(root / ".codex" / "metabolism-archive", root)
        archive_root.mkdir(parents=True, exist_ok=True)
        destination = _inside(
            archive_root / f"{safe_name(record.target)}-{when.strftime('%Y%m%dT%H%M%SZ')}",
            root,
        )
        if destination.exists():
            raise LifecycleError(f"rollback archive already exists: {destination}")
        shutil.move(str(artifact), str(destination))
        try:
            _atomic_json(hooks_path, hooks)
        except Exception:
            shutil.move(str(destination), str(artifact))
            raise
    elif record.target_kind == "SKILL":
        root = Path(skill_root)
        artifact = _inside(Path(record.artifact_path), root)
        decision_type = record.metadata.get("decision_type")
        archive_root = _inside(root / ".codex-metabolism-archive", root)
        archive_root.mkdir(parents=True, exist_ok=True)
        destination = _inside(
            archive_root / f"rollback-{safe_name(record.target)}-{when.strftime('%Y%m%dT%H%M%SZ')}",
            root,
        )
        if destination.exists():
            raise LifecycleError(f"rollback archive already exists: {destination}")
        if decision_type == "PATCH":
            backup_value = record.metadata.get("backup_path")
            if not backup_value:
                raise LifecycleError("reviewed skill backup is unavailable")
            backup = _inside(Path(backup_value), staging)
            expected = record.metadata.get("applied_sha256")
            if not artifact.is_file() or (expected and _sha256(artifact) != expected):
                raise LifecycleError("live skill changed after apply; automatic rollback is unsafe")
            destination.mkdir(parents=True)
            shutil.copyfile(artifact, destination / "SKILL.md")
            descriptor, temporary = tempfile.mkstemp(prefix=".SKILL.md.rollback.", dir=artifact.parent)
            os.close(descriptor)
            try:
                shutil.copyfile(backup, temporary)
                os.replace(temporary, artifact)
            except Exception:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise
        elif decision_type == "CREATE":
            source = artifact.parent
            if not artifact.is_file():
                raise LifecycleError("created skill is missing")
            shutil.move(str(source), str(destination))
        else:
            raise LifecycleError(f"unsupported skill rollback type: {decision_type}")
    elif record.target_kind == "RULE":
        root = (
            Path(codex_home) if record.scope == "user" and codex_home is not None
            else (Path.home() / ".codex" if record.scope == "user" else Path(project_root))
        )
        artifact = _inside(Path(record.artifact_path), root)
        backup_value = record.metadata.get("backup_path")
        if not backup_value:
            raise LifecycleError("reviewed AGENTS.md managed-region backup is unavailable")
        backup = _inside(Path(backup_value), staging)
        expected = record.metadata.get("applied_sha256")
        if not artifact.is_file() or (expected and _sha256(artifact) != expected):
            raise LifecycleError("AGENTS.md changed after apply; automatic rollback is unsafe")
        current = artifact.read_bytes()
        content_start, content_end = _managed_byte_region(current)
        archive_root = _inside(root / "metabolism-archive", root)
        archive_root.mkdir(parents=True, exist_ok=True)
        destination = _inside(
            archive_root
            / f"rollback-{safe_name(record.target)}-{when.strftime('%Y%m%dT%H%M%SZ')}.txt",
            root,
        )
        if destination.exists():
            raise LifecycleError(f"rollback archive already exists: {destination}")
        _atomic_bytes(destination, current[content_start:content_end])
        try:
            _atomic_bytes(
                artifact,
                current[:content_start] + backup.read_bytes() + current[content_end:],
            )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    else:
        raise LifecycleError(f"rollback is unsupported for {record.target_kind}")

    append_intervention(
        staging / "interventions.jsonl",
        InterventionReceipt(
            decision_id=record.decision_id,
            target_kind=record.target_kind,
            target=record.target,
            mechanism=record.mechanism,
            scope=record.scope,
            status="ROLLED_BACK",
            activated_at=record.activated_at,
            artifact_path=str(destination.resolve()),
            signature=record.signature,
            expected_effect=record.expected_effect,
            baseline_session_ids=record.baseline_session_ids,
            metadata={**record.metadata, "rolled_back_at": when.isoformat()},
        ),
    )
    return destination


def reject_decision(staging_dir: Path | str, decision_id: str) -> None:
    staging = Path(staging_dir)
    payload = _load(staging)
    decision = _find(payload, decision_id)
    _require_proposed(decision)
    _mark(staging, payload, decision, "rejected")
