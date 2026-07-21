from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .names import safe_name


class ProposalError(RuntimeError):
    pass


_ACTIONS = {"CREATE", "PATCH", "RETIRE_CANDIDATE"}
_LAYERS = {"HARNESS", "TOOL", "SKILL", "RULE"}
_LADDER = {"builtin", "installed", "repository", "ecosystem"}
_ENVELOPE_FIELDS = {"schema_version", "review_id", "proposals"}
_PROPOSAL_FIELDS = {
    "proposal_id",
    "action",
    "layer",
    "target",
    "target_evidence_id",
    "evidence_ids",
    "reasoning",
    "expected_effect",
    "rollback_when",
    "alternatives_checked",
    "artifact",
}
_ARTIFACT_FIELDS = {"path"}
_ALTERNATIVE_FIELDS = {"level", "result", "details", "source"}
_MAX_ARTIFACT_BYTES = 128_000
_MUTABLE_STAGED_FIELDS = {"approval_digest", "status", "status_changed_at"}


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProposalError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise ProposalError(f"{label} must be a JSON object")
    return payload


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


def _inside_draft(path: Path, draft: Path) -> Path:
    resolved = path.resolve()
    root = draft.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ProposalError("artifact path must stay inside the draft directory") from exc
    return resolved


def _text(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ProposalError(f"proposal requires non-empty {field}")
    return result


def _validate_skill(content: str, target: str) -> None:
    content = content.replace("\r\n", "\n")
    if not content.startswith("---\n"):
        raise ProposalError("skill artifact requires YAML frontmatter")
    end = content.find("\n---\n", 4)
    if end < 0:
        raise ProposalError("skill artifact has incomplete YAML frontmatter")
    frontmatter = content[4:end]
    keys: list[str] = []
    for line in frontmatter.splitlines():
        key, separator, _ = line.partition(":")
        if not separator or not key.strip():
            raise ProposalError("skill frontmatter must contain simple name and description fields")
        keys.append(key.strip())
    if set(keys) != {"name", "description"} or len(keys) != 2:
        raise ProposalError("skill frontmatter may contain only name and description")
    name_match = re.search(r"(?m)^name:\s*([^\n]+?)\s*$", frontmatter)
    description_match = re.search(r"(?m)^description:\s*([^\n]+?)\s*$", frontmatter)
    if name_match is None or description_match is None:
        raise ProposalError("skill artifact requires name and description frontmatter")
    if name_match.group(1).strip() != safe_name(target):
        raise ProposalError("skill frontmatter name must match the proposal target")


def proposal_approval_digest(review_id: str, proposal: dict[str, Any]) -> str:
    """Bind approval to every immutable proposal field, including artifact hashes."""
    immutable = {
        key: value
        for key, value in proposal.items()
        if key not in _MUTABLE_STAGED_FIELDS
    }
    canonical = json.dumps(
        {"review_id": review_id, "proposal": immutable},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _evidence_ids(packet: dict[str, Any]) -> set[str]:
    portfolio = packet.get("portfolio") or {}
    sessions = packet.get("sessions") or []
    groups = [sessions]
    groups.extend(portfolio.get(name) or [] for name in ("skills", "agents_documents", "interventions"))
    identifiers = {
        str(item.get("id"))
        for group in groups
        for item in group
        if isinstance(item, dict) and item.get("id")
    }
    identifiers.update(
        str(event.get("id"))
        for session in sessions
        if isinstance(session, dict)
        for event in session.get("events", [])
        if isinstance(event, dict) and event.get("id")
    )
    return identifiers


def stage_agent_proposals(
    evidence_path: Path | str,
    proposal_path: Path | str,
    output_dir: Path | str,
) -> Path:
    evidence_file = Path(evidence_path)
    draft_file = Path(proposal_path)
    packet = _load_object(evidence_file, "evidence packet")
    draft = _load_object(draft_file, "agent proposal")
    if packet.get("schema_version") != 2 or packet.get("authority") != "evidence_only":
        raise ProposalError("unsupported evidence packet")
    if draft.get("schema_version") != 1:
        raise ProposalError("unsupported proposal schema")
    unknown_envelope = set(draft) - _ENVELOPE_FIELDS
    if unknown_envelope:
        raise ProposalError(f"unknown proposal envelope field: {sorted(unknown_envelope)[0]}")
    if draft.get("review_id") != packet.get("review_id"):
        raise ProposalError("proposal review_id does not match the evidence packet")
    proposals = draft.get("proposals")
    if not isinstance(proposals, list) or len(proposals) > 3:
        raise ProposalError("agent proposal must contain between zero and three proposals")

    supplied_evidence = _evidence_ids(packet)
    skill_evidence = {
        str(item.get("id")): item
        for item in (packet.get("portfolio") or {}).get("skills", [])
        if isinstance(item, dict) and item.get("id")
    }
    observed_skill_names = {
        safe_name(str(item.get("name") or ""))
        for item in skill_evidence.values()
        if item.get("name")
    }
    seen_ids: set[str] = set()
    seen_targets: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    copies: list[tuple[Path, Path]] = []
    draft_root = draft_file.parent
    for raw in proposals:
        if not isinstance(raw, dict):
            raise ProposalError("each proposal must be a JSON object")
        unknown_fields = set(raw) - _PROPOSAL_FIELDS
        if unknown_fields:
            raise ProposalError(f"unknown proposal field: {sorted(unknown_fields)[0]}")
        proposal_id = _text(raw.get("proposal_id"), "proposal_id")
        if proposal_id in seen_ids:
            raise ProposalError("proposal IDs must be unique")
        if safe_name(proposal_id) != proposal_id:
            raise ProposalError("proposal_id must use lowercase safe-name syntax")
        seen_ids.add(proposal_id)
        action = str(raw.get("action") or "")
        layer = str(raw.get("layer") or "")
        if action not in _ACTIONS:
            raise ProposalError("proposal action is unsupported")
        if layer not in _LAYERS:
            raise ProposalError("proposal layer is unsupported")
        cited_list = raw.get("evidence_ids")
        if not isinstance(cited_list, list) or not cited_list:
            raise ProposalError("proposal must cite evidence")
        cited = {str(item) for item in cited_list}
        if len(cited) != len(cited_list):
            raise ProposalError("proposal contains duplicate evidence IDs")
        unknown = cited - supplied_evidence
        if unknown:
            raise ProposalError(f"proposal cited unknown evidence: {sorted(unknown)[0]}")
        raw_target = _text(raw.get("target"), "target")
        target = safe_name(raw_target)
        if target != raw_target:
            raise ProposalError("target must use lowercase safe-name syntax")
        if layer == "SKILL" and action == "CREATE" and target in observed_skill_names:
            raise ProposalError("an observed skill with this name already exists; use PATCH")
        target_key = (layer, target)
        if target_key in seen_targets:
            raise ProposalError("proposal targets must be unique within each layer")
        seen_targets.add(target_key)
        reasoning = _text(raw.get("reasoning"), "reasoning")
        expected_effect = _text(raw.get("expected_effect"), "expected_effect")
        rollback_when = _text(raw.get("rollback_when"), "rollback_when")
        alternatives = raw.get("alternatives_checked")
        levels: list[str] = []
        if alternatives is not None:
            if not isinstance(alternatives, list) or not alternatives:
                raise ProposalError("alternatives_checked must be a non-empty list")
            levels: list[str] = []
            for item in alternatives:
                if (
                    not isinstance(item, dict)
                    or set(item) - _ALTERNATIVE_FIELDS
                    or str(item.get("level") or "") not in _LADDER
                    or not str(item.get("result") or "").strip()
                ):
                    raise ProposalError("alternatives_checked contains unsupported fields")
                levels.append(str(item["level"]))
            if len(set(levels)) != len(levels):
                raise ProposalError("alternatives_checked levels must be unique")
        elif action == "CREATE":
            raise ProposalError("CREATE requires alternatives_checked")
        if action == "CREATE" and (
            set(levels) != _LADDER or len(levels) != len(_LADDER)
        ):
            raise ProposalError(
                "CREATE must check builtin, installed, repository, and ecosystem exactly once"
            )

        base_sha256: str | None = None
        if layer == "SKILL" and action in {"PATCH", "RETIRE_CANDIDATE"}:
            target_evidence_id = str(raw.get("target_evidence_id") or "")
            target_evidence = skill_evidence.get(target_evidence_id)
            if target_evidence is None:
                raise ProposalError("SKILL PATCH/RETIRE requires observed target evidence")
            if safe_name(str(target_evidence.get("name") or "")) != target:
                raise ProposalError("observed target evidence does not match the proposal target")
            if target_evidence.get("protected"):
                raise ProposalError("protected skills cannot be managed by this lifecycle")
            base_sha256 = str(target_evidence.get("content_sha256") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", base_sha256):
                raise ProposalError("observed skill target has no valid content hash")

        artifact_sha256: str | None = None
        staged_relative: str | None = None
        artifact = raw.get("artifact")
        artifact_required = action in {"CREATE", "PATCH"} or (
            action == "RETIRE_CANDIDATE" and layer != "SKILL"
        )
        if action == "RETIRE_CANDIDATE" and layer == "SKILL" and artifact is not None:
            raise ProposalError("SKILL RETIRE proposals cannot include an artifact")
        if artifact_required and (
            not isinstance(artifact, dict) or not artifact.get("path")
        ):
            raise ProposalError("this proposal requires a complete reviewed artifact")
        if isinstance(artifact, dict) and set(artifact) - _ARTIFACT_FIELDS:
            raise ProposalError("artifact contains unsupported fields")
        if layer == "SKILL" and action in {"CREATE", "PATCH"}:
            source = _inside_draft(draft_root / str(artifact["path"]), draft_root)
            if source.name != "SKILL.md" or not source.is_file():
                raise ProposalError("skill artifact must be an existing SKILL.md")
            content_bytes = source.read_bytes()
            if len(content_bytes) > _MAX_ARTIFACT_BYTES:
                raise ProposalError(f"artifact exceeds {_MAX_ARTIFACT_BYTES} bytes")
            try:
                content = content_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ProposalError("skill artifact must be valid UTF-8") from exc
            _validate_skill(content, target)
            artifact_sha256 = hashlib.sha256(content_bytes).hexdigest()
            destination = Path("proposed-skills") / target / "SKILL.md"
            staged_relative = destination.as_posix()
            copies.append((source, destination))
        elif isinstance(artifact, dict) and artifact.get("path"):
            source = _inside_draft(draft_root / str(artifact["path"]), draft_root)
            if not source.is_file():
                raise ProposalError("artifact path must reference an existing file")
            content = source.read_bytes()
            if len(content) > _MAX_ARTIFACT_BYTES:
                raise ProposalError(f"artifact exceeds {_MAX_ARTIFACT_BYTES} bytes")
            artifact_sha256 = hashlib.sha256(content).hexdigest()
            destination = Path("proposed-artifacts") / proposal_id / source.name
            staged_relative = destination.as_posix()
            copies.append((source, destination))

        normalized.append(
            {
                **raw,
                "proposal_id": proposal_id,
                "action": action,
                "layer": layer,
                "target": target,
                "reasoning": reasoning,
                "expected_effect": expected_effect,
                "rollback_when": rollback_when,
                "evidence_ids": list(cited_list),
                "status": "awaiting_human_approval",
                "artifact_sha256": artifact_sha256,
                "base_sha256": base_sha256,
                "staged_artifact": staged_relative,
            }
        )

    for item in normalized:
        item["approval_digest"] = proposal_approval_digest(packet["review_id"], item)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for source, relative in copies:
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    manifest = {
        "schema_version": 2,
        "review_id": packet["review_id"],
        "source": "codex_agent",
        "status": "awaiting_human_approval" if normalized else "no_change",
        "proposals": normalized,
    }
    _atomic_json(output / "proposals.json", manifest)
    lines = [
        "# Codex Metabolism proposals",
        "",
        "> Codex authored these proposals. The runtime validated evidence references and sealed exact artifacts; it made no semantic decision.",
        "",
    ]
    if not normalized:
        lines.extend(
            [
                "## No changes proposed",
                "",
                "Codex found no evidence-supported intervention worth staging in this review.",
                "",
            ]
        )
    for item in normalized:
        lines.extend(
            [
                f"## {item['action']} {item['layer']}: {item['target']}",
                "",
                item["reasoning"],
                "",
                f"Expected effect: {item['expected_effect']}",
                f"Rollback when: {item['rollback_when']}",
                "Evidence: " + ", ".join(f"`{value}`" for value in item["evidence_ids"]),
                f"Sealed artifact: `{item['staged_artifact'] or 'none'}`",
                f"Approval digest: `{item['approval_digest']}`",
                "",
            ]
        )
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return output
