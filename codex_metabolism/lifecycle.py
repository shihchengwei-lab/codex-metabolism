from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .interventions import (
    append_intervention,
    intervention_identity,
    latest_interventions,
    load_interventions,
)
from .models import InterventionReceipt
from .names import safe_name
from .proposals import proposal_approval_digest


class LifecycleError(RuntimeError):
    pass


def _atomic_json(path: Path, payload: object) -> None:
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


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    approved = root.resolve()
    try:
        resolved.relative_to(approved)
    except ValueError as exc:
        raise LifecycleError(f"path escapes approved root: {resolved}") from exc
    return resolved


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest(staging: Path) -> dict[str, Any]:
    path = staging / "proposals.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"invalid staged Agent proposals: {path}") from exc
    if not isinstance(payload, dict) or payload.get("source") != "codex_agent":
        raise LifecycleError("staged proposals were not produced by the Agent-first validator")
    return payload


def _find(payload: dict[str, Any], proposal_id: str) -> dict[str, Any]:
    for proposal in payload.get("proposals", []):
        if proposal.get("proposal_id") == proposal_id:
            return proposal
    raise LifecycleError(f"proposal not found: {proposal_id}")


def _verify_approval(
    payload: dict[str, Any],
    proposal: dict[str, Any],
    approved_digest: str | None,
) -> str:
    if not approved_digest:
        raise LifecycleError("explicit approval of the staged digest is required")
    stored = str(proposal.get("approval_digest") or "")
    actual = proposal_approval_digest(str(payload.get("review_id") or ""), proposal)
    if not stored or not hmac.compare_digest(stored, actual):
        raise LifecycleError("staged proposal no longer matches the approved digest")
    if not hmac.compare_digest(approved_digest, actual):
        raise LifecycleError("approved digest does not match the staged proposal")
    return actual


def _mark(
    staging: Path,
    payload: dict[str, Any],
    proposal: dict[str, Any],
    status: str,
    when: datetime,
) -> None:
    proposal["status"] = status
    proposal["status_changed_at"] = when.isoformat()
    _atomic_json(staging / "proposals.json", payload)


def _active_receipt(staging: Path, identifier: str) -> InterventionReceipt:
    records = latest_interventions(load_interventions(staging / "interventions.jsonl"))
    record = next(
        (
            item
            for item in records
            if item.intervention_id == identifier or item.proposal_id == identifier
        ),
        None,
    )
    if record is None or record.status != "ACTIVE":
        raise LifecycleError("an active Agent intervention receipt is required")
    return record


def apply_agent_proposal(
    staging_dir: Path | str,
    proposal_id: str,
    skill_root: Path | str,
    *,
    approved_digest: str | None,
    changed_at: datetime | None = None,
) -> Path:
    staging = Path(staging_dir)
    payload = _load_manifest(staging)
    proposal = _find(payload, proposal_id)
    if proposal.get("status") != "awaiting_human_approval":
        raise LifecycleError(f"proposal is already {proposal.get('status')}")
    approval_digest = _verify_approval(payload, proposal, approved_digest)
    if proposal.get("layer") != "SKILL":
        raise LifecycleError(
            "repository, rule, harness, and tool changes use the normal Codex workflow; "
            "record them after approved implementation"
        )
    action = str(proposal.get("action") or "")
    when = changed_at or datetime.now(timezone.utc)
    target = safe_name(str(proposal.get("target") or ""))
    root = Path(skill_root)
    destination = _inside(root / target / "SKILL.md", root)
    identity = intervention_identity("SKILL", target, "user")

    if action == "RETIRE_CANDIDATE":
        expected = str(proposal.get("base_sha256") or "")
        if not destination.is_file() or not expected or _sha256(destination) != expected:
            raise LifecycleError("live skill changed after observation; stage a new proposal")
        archive = _inside(staging / "archive" / proposal_id / target, staging)
        if archive.exists():
            raise LifecycleError(f"retirement archive already exists: {archive}")
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(destination.parent), str(archive))
        try:
            append_intervention(
                staging / "interventions.jsonl",
                InterventionReceipt(
                    intervention_id=identity,
                    target_kind="SKILL",
                    target=target,
                    mechanism="agent_approved_archive",
                    scope="user",
                    status="RETIRED",
                    activated_at=when.isoformat(),
                    artifact_path=str((archive / "SKILL.md").resolve()),
                    proposal_id=proposal_id,
                    reasoning=str(proposal.get("reasoning") or ""),
                    expected_effect=str(proposal.get("expected_effect") or ""),
                    rollback_when=str(proposal.get("rollback_when") or ""),
                    evidence_ids=list(proposal.get("evidence_ids") or []),
                    metadata={
                        "source": "codex_agent",
                        "action": action,
                        "original_path": str(destination.resolve()),
                        "base_sha256": expected,
                        "review_id": payload.get("review_id"),
                        "approval_digest": approval_digest,
                        "execution_mode": "runtime_managed",
                    },
                ),
            )
        except Exception:
            destination.parent.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(archive), str(destination.parent))
            raise
        _mark(staging, payload, proposal, "retired", when)
        return archive / "SKILL.md"

    if action not in {"CREATE", "PATCH"}:
        raise LifecycleError(f"unsupported Agent proposal action: {action}")
    staged_relative = proposal.get("staged_artifact")
    if not staged_relative:
        raise LifecycleError("proposal has no sealed artifact")
    source = _inside(staging / str(staged_relative), staging)
    if not source.is_file():
        raise LifecycleError("sealed artifact is missing")
    expected_artifact = str(proposal.get("artifact_sha256") or "")
    if not expected_artifact or _sha256(source) != expected_artifact:
        raise LifecycleError("sealed artifact changed after staging")

    prior: bytes | None = None
    backup: Path | None = None
    if action == "CREATE":
        if destination.exists() or destination.parent.exists():
            raise LifecycleError(f"skill target already exists: {destination.parent}")
    else:
        base_sha = str(proposal.get("base_sha256") or "")
        if not destination.is_file() or not base_sha or _sha256(destination) != base_sha:
            raise LifecycleError("live skill changed after observation; stage a new proposal")
        prior = destination.read_bytes()
        backup = _inside(staging / "backups" / proposal_id / "SKILL.md", staging)
        _atomic_bytes(backup, prior)

    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_bytes(destination, source.read_bytes())
    try:
        append_intervention(
            staging / "interventions.jsonl",
            InterventionReceipt(
                intervention_id=identity,
                target_kind="SKILL",
                target=target,
                mechanism="agent_authored_skill",
                scope="user",
                status="ACTIVE",
                activated_at=when.isoformat(),
                artifact_path=str(destination.resolve()),
                proposal_id=proposal_id,
                reasoning=str(proposal.get("reasoning") or ""),
                expected_effect=str(proposal.get("expected_effect") or ""),
                rollback_when=str(proposal.get("rollback_when") or ""),
                evidence_ids=list(proposal.get("evidence_ids") or []),
                metadata={
                    "source": "codex_agent",
                    "action": action,
                    "review_id": payload.get("review_id"),
                    "base_sha256": proposal.get("base_sha256"),
                    "applied_sha256": _sha256(destination),
                    "backup_path": str(backup.resolve()) if backup is not None else None,
                    "approval_digest": approval_digest,
                    "execution_mode": "runtime_managed",
                    "approved_artifact_sha256": expected_artifact,
                    "implementation_evidence_sha256": _sha256(destination),
                },
            ),
        )
    except Exception:
        if action == "CREATE":
            try:
                destination.unlink()
                destination.parent.rmdir()
            except OSError:
                pass
        elif prior is not None:
            _atomic_bytes(destination, prior)
        raise
    _mark(staging, payload, proposal, "applied", when)
    return destination


def record_agent_intervention(
    staging_dir: Path | str,
    proposal_id: str,
    artifact_path: Path | str,
    *,
    approved_digest: str | None,
    changed_at: datetime | None = None,
) -> Path:
    """Preserve evidence from an approved change made through an existing mechanism."""
    staging = Path(staging_dir)
    payload = _load_manifest(staging)
    proposal = _find(payload, proposal_id)
    if proposal.get("status") != "awaiting_human_approval":
        raise LifecycleError(f"proposal is already {proposal.get('status')}")
    approval_digest = _verify_approval(payload, proposal, approved_digest)
    if proposal.get("layer") == "SKILL":
        raise LifecycleError("skills must use the sealed apply path")
    artifact = Path(artifact_path).resolve()
    if not artifact.is_file():
        raise LifecycleError("implementation evidence must be an existing regular file")
    content = artifact.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    when = changed_at or datetime.now(timezone.utc)
    layer = str(proposal.get("layer"))
    target = str(proposal.get("target"))
    identity = intervention_identity(layer, target, "project")
    durable = _inside(
        staging
        / "implementation-evidence"
        / identity
        / proposal_id
        / artifact.name,
        staging,
    )
    if durable.exists():
        raise LifecycleError(f"implementation evidence already exists: {durable}")
    _atomic_bytes(durable, content)
    action = str(proposal.get("action") or "")
    status = "RETIRED" if action == "RETIRE_CANDIDATE" else "ACTIVE"
    try:
        append_intervention(
            staging / "interventions.jsonl",
            InterventionReceipt(
                intervention_id=identity,
                target_kind=layer,
                target=target,
                mechanism="agent_implemented_via_existing_mechanism",
                scope="project",
                status=status,
                activated_at=when.isoformat(),
                artifact_path=str(durable),
                proposal_id=proposal_id,
                reasoning=str(proposal.get("reasoning") or ""),
                expected_effect=str(proposal.get("expected_effect") or ""),
                rollback_when=str(proposal.get("rollback_when") or ""),
                evidence_ids=list(proposal.get("evidence_ids") or []),
                metadata={
                    "source": "codex_agent",
                    "action": action,
                    "review_id": payload.get("review_id"),
                    "execution_mode": "existing_mechanism",
                    "approval_digest": approval_digest,
                    "approved_artifact_sha256": proposal.get("artifact_sha256"),
                    "implementation_evidence_sha256": digest,
                },
            ),
        )
    except Exception:
        try:
            durable.unlink()
        except OSError:
            pass
        raise
    _mark(staging, payload, proposal, "recorded", when)
    return durable


def rollback_agent_intervention(
    staging_dir: Path | str,
    proposal_id: str,
    skill_root: Path | str,
    *,
    human_approved: bool,
    changed_at: datetime | None = None,
) -> Path:
    if not human_approved:
        raise LifecycleError("explicit human approval is required before rollback")
    staging = Path(staging_dir)
    record = _active_receipt(staging, proposal_id)
    if record.target_kind != "SKILL":
        raise LifecycleError("non-skill rollback must use the normal Codex workflow")
    root = Path(skill_root)
    destination = _inside(root / safe_name(record.target) / "SKILL.md", root)
    expected = str(record.metadata.get("applied_sha256") or "")
    if not destination.is_file() or not expected or _sha256(destination) != expected:
        raise LifecycleError("live skill changed after apply; refusing rollback overwrite")
    when = changed_at or datetime.now(timezone.utc)
    action = record.metadata.get("action")
    rollback_archive: Path | None = None
    current_bytes: bytes | None = None
    if action == "CREATE":
        archive = _inside(staging / "archive" / proposal_id / safe_name(record.target), staging)
        if archive.exists():
            raise LifecycleError(f"rollback archive already exists: {archive}")
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(destination.parent), str(archive))
        rollback_archive = archive
        result = archive / "SKILL.md"
    elif action == "PATCH":
        backup_value = record.metadata.get("backup_path")
        if not backup_value:
            raise LifecycleError("patch receipt has no reviewed backup")
        backup = _inside(Path(str(backup_value)), staging)
        if not backup.is_file():
            raise LifecycleError("patch backup is missing")
        current_archive = _inside(staging / "archive" / proposal_id / "patched.SKILL.md", staging)
        current_bytes = destination.read_bytes()
        _atomic_bytes(current_archive, current_bytes)
        rollback_archive = current_archive
        _atomic_bytes(destination, backup.read_bytes())
        result = destination
    else:
        raise LifecycleError(f"unsupported Agent intervention action: {action}")
    try:
        append_intervention(
            staging / "interventions.jsonl",
            InterventionReceipt(
                intervention_id=record.intervention_id,
                target_kind=record.target_kind,
                target=record.target,
                mechanism=record.mechanism,
                scope=record.scope,
                status="ROLLED_BACK",
                activated_at=record.activated_at,
                artifact_path=str(result.resolve()),
                proposal_id=record.proposal_id,
                reasoning=record.reasoning,
                expected_effect=record.expected_effect,
                rollback_when=record.rollback_when,
                evidence_ids=list(record.evidence_ids),
                metadata={**record.metadata, "rolled_back_at": when.isoformat()},
            ),
        )
    except Exception:
        if action == "CREATE" and rollback_archive is not None:
            destination.parent.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(rollback_archive), str(destination.parent))
        elif action == "PATCH" and current_bytes is not None:
            _atomic_bytes(destination, current_bytes)
            if rollback_archive is not None:
                try:
                    rollback_archive.unlink()
                except OSError:
                    pass
        raise
    return result


def restore_retired_skill(
    staging_dir: Path | str,
    proposal_id: str,
    skill_root: Path | str,
    *,
    human_approved: bool,
    changed_at: datetime | None = None,
) -> Path:
    if not human_approved:
        raise LifecycleError("explicit human approval is required before restore")
    staging = Path(staging_dir)
    records = latest_interventions(load_interventions(staging / "interventions.jsonl"))
    record = next(
        (
            item
            for item in records
            if item.intervention_id == proposal_id or item.proposal_id == proposal_id
        ),
        None,
    )
    if record is None or record.status != "RETIRED":
        raise LifecycleError("a retired skill receipt is required for restore")
    archive = _inside(Path(record.artifact_path).parent, staging)
    root = Path(skill_root)
    destination = _inside(root / safe_name(record.target), root)
    if destination.exists():
        raise LifecycleError(f"restore target already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(archive), str(destination))
    when = changed_at or datetime.now(timezone.utc)
    try:
        append_intervention(
            staging / "interventions.jsonl",
            InterventionReceipt(
                intervention_id=record.intervention_id,
                target_kind=record.target_kind,
                target=record.target,
                mechanism=record.mechanism,
                scope=record.scope,
                status="RESTORED",
                activated_at=record.activated_at,
                artifact_path=str((destination / "SKILL.md").resolve()),
                proposal_id=record.proposal_id,
                reasoning=record.reasoning,
                expected_effect=record.expected_effect,
                rollback_when=record.rollback_when,
                evidence_ids=list(record.evidence_ids),
                metadata={**record.metadata, "restored_at": when.isoformat()},
            ),
        )
    except Exception:
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(destination), str(archive))
        raise
    return destination / "SKILL.md"


def reject_agent_proposal(
    staging_dir: Path | str,
    proposal_id: str,
    *,
    changed_at: datetime | None = None,
) -> None:
    staging = Path(staging_dir)
    payload = _load_manifest(staging)
    proposal = _find(payload, proposal_id)
    if proposal.get("status") != "awaiting_human_approval":
        raise LifecycleError(f"proposal is already {proposal.get('status')}")
    _mark(
        staging,
        payload,
        proposal,
        "rejected",
        changed_at or datetime.now(timezone.utc),
    )
