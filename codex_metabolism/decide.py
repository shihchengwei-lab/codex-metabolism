from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents_review import agents_review_decisions, new_rule_suggestion
from .interventions import latest_interventions
from .models import (
    Decision,
    InstalledSkill,
    Observation,
    SessionObservation,
    SkillLifecycleEvidence,
    ToolExecution,
)


DECISIONS = {"CREATE", "PATCH", "KEEP", "RETIRE_CANDIDATE"}
TARGET_KINDS = {"HARNESS", "TOOL", "SKILL", "RULE"}
CONFIDENCE = {"low", "medium", "high"}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:64] or "workflow"


def _signature(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip()).lower()


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"met-{digest}"


def _evidence_id(session_id: str, kind: str, summary: str) -> str:
    return f"ev-{hashlib.sha256(f'{session_id}|{kind}|{summary}'.encode()).hexdigest()[:10]}"


def _evidence(session: SessionObservation, kind: str, summary: str, *, hard: bool) -> dict[str, Any]:
    return {
        "id": _evidence_id(session.session_id, kind, summary),
        "session_id": session.session_id,
        "kind": kind,
        "summary": summary,
        "source": session.source_file,
        "hard": hard,
    }


def _first_later_success(
    failed: ToolExecution, session: SessionObservation, signature: str
) -> ToolExecution | None:
    for tool in session.tool_executions:
        if tool.sequence <= failed.sequence:
            continue
        if tool.status == "success" and _signature(tool.command) == signature:
            return tool
    return None


def _correction_between(
    failed: ToolExecution, success: ToolExecution, session: SessionObservation
) -> str | None:
    for message in session.corrections:
        if failed.output_sequence < message.sequence < success.sequence:
            return message.text
    return None


def friction_funnel(observation: Observation) -> dict[str, int]:
    """Summarize conservative detector gates without exposing session content."""
    failures = 0
    recoveries = 0
    corrected_recoveries = 0
    corrected_signatures: dict[str, set[str]] = defaultdict(set)
    for session in observation.sessions:
        for tool in session.tool_executions:
            if tool.status != "failure" or not tool.command:
                continue
            failures += 1
            signature = _signature(tool.command)
            success = _first_later_success(tool, session, signature)
            if success is None:
                continue
            recoveries += 1
            if _correction_between(tool, success, session) is None:
                continue
            corrected_recoveries += 1
            corrected_signatures[signature].add(session.session_id)
    return {
        "observed_user_feedback_candidates": sum(
            len(session.feedback_candidates) for session in observation.sessions
        ),
        "interrupted_turns": sum(
            session.interrupted_turns for session in observation.sessions
        ),
        "tool_failures_with_command": failures,
        "same_command_recoveries": recoveries,
        "recoveries_with_recognized_correction": corrected_recoveries,
        "recurring_patterns_meeting_threshold": sum(
            len(session_ids) >= 2 for session_ids in corrected_signatures.values()
        ),
    }


def _preflight_pair(correction: str, signature: str) -> tuple[str, str] | None:
    spans = [span.strip() for span in re.findall(r"`([^`]{1,160})`", correction)]
    lowered = correction.lower()
    if len(spans) >= 2 and ("before" in lowered or "first" in lowered):
        required, protected = spans[0], spans[1]
        if _signature(protected) == signature:
            return required, protected
    if len(spans) >= 2 and "先" in correction:
        for candidate in spans:
            if _signature(candidate) != signature:
                return candidate, next((s for s in spans if _signature(s) == signature), signature)
    return None


def _rule_like_correction(correction: str) -> bool:
    return bool(
        re.search(
            r"(?i)\b(?:always|never|must|must not|do not|don't|should not)\b|永遠|一律|不得|不要|必須",
            correction,
        )
    )


def _tokens(*values: str) -> set[str]:
    ignored = {"the", "and", "for", "with", "this", "that", "project", "production"}
    return {
        token
        for value in values
        for token in re.findall(r"[a-z][a-z0-9_-]{2,}", value.lower())
        if token not in ignored
    }


def _repo_match(observation: Observation, signature: str, required: str | None) -> str | None:
    wanted = _tokens(signature, required or "")
    if not wanted:
        return None
    ranked: list[tuple[int, str]] = []
    for asset in observation.repo_assets:
        matched = sum(1 for token in wanted if token in asset.searchable_text)
        threshold = min(2, len(wanted))
        if matched >= threshold:
            ranked.append((matched, asset.path))
    return max(ranked, default=(0, ""))[1] or None


def _catalog_entry_is_installed(entry: dict[str, Any]) -> bool:
    kind = str(entry.get("kind") or "").casefold()
    source = str(entry.get("source") or "").casefold()
    status = str(entry.get("status") or "").casefold()
    return kind in {"installed-command", "installed-tool", "plugin", "dependency"} and (
        kind.startswith("installed")
        or source == "codex-plugin-list"
        or any(word in status for word in ("active", "available", "enabled", "installed"))
    )


def _installed_tool_match(
    observation: Observation,
    signature: str,
    required: str | None,
) -> dict[str, Any] | None:
    candidates = list(observation.installed_tools) + [
        entry for entry in observation.catalog_entries if _catalog_entry_is_installed(entry)
    ]
    wanted = _tokens(signature, required or "")
    required_parts = (required or "").strip().split(maxsplit=1)
    required_name = required_parts[0].strip("\"'").casefold() if required_parts else ""
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for entry in candidates:
        name = str(entry.get("name") or "").casefold()
        path_name = Path(str(entry.get("path") or name)).stem.casefold()
        text = (
            f"{entry.get('name', '')} {entry.get('description', '')} "
            f"{entry.get('path', '')}"
        ).casefold()
        exact = int(bool(required_name) and required_name in {name, path_name})
        matched = sum(1 for token in wanted if token in text)
        if exact or matched >= min(2, len(wanted)):
            ranked.append((exact, matched, entry))
    return max(ranked, key=lambda item: (item[0], item[1]))[2] if ranked else None


def _catalog_match(
    observation: Observation, signature: str, required: str | None
) -> dict[str, Any] | None:
    wanted = _tokens(signature, required or "")
    if not wanted:
        return None
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for entry in observation.catalog_entries:
        if _catalog_entry_is_installed(entry):
            continue
        text = f"{entry.get('name', '')} {entry.get('description', '')}".lower()
        matched = sum(1 for token in wanted if token in text)
        if matched >= min(2, len(wanted)):
            ranked.append((matched, int(entry.get("stars") or 0), entry))
    return max(ranked, key=lambda item: (item[0], item[1]))[2] if ranked else None


def _installed_match(
    observation: Observation, session_ids: set[str], signature: str
) -> InstalledSkill | None:
    signaled = {
        name
        for session in observation.sessions
        if session.session_id in session_ids
        for name in session.skill_signals
    }
    corrected = {
        name.casefold()
        for session in observation.sessions
        if session.session_id in session_ids
        for message in session.corrections
        for name in re.findall(r"\$([a-z0-9][a-z0-9:_-]{1,80})", message.text, re.IGNORECASE)
    }
    for skill in observation.skills:
        if skill.name.casefold() in corrected:
            return skill
    wanted = _tokens(signature)
    ranked: list[tuple[int, int, InstalledSkill]] = []
    for skill in observation.skills:
        text = f"{skill.name} {skill.description}".lower()
        matched = sum(1 for token in wanted if token in text)
        if wanted and matched >= min(2, len(wanted)):
            ranked.append((matched, int(skill.name.casefold() in signaled), skill))
    return max(ranked, key=lambda item: (item[0], item[1]))[2] if ranked else None


def _ladder(
    observation: Observation,
    *,
    mechanical: bool,
    installed: InstalledSkill | None,
    installed_tool: dict[str, Any] | None,
    repo_path: str | None,
    external: dict[str, Any] | None,
    session_count: int,
) -> list[dict[str, Any]]:
    return [
        {
            "name": "necessity",
            "checked": True,
            "result": "needed",
            "details": f"Repeated in {session_count} sessions with a verified recovery path.",
        },
        {
            "name": "builtin",
            "checked": True,
            "result": "foundation",
            "details": "Codex PreToolUse hooks" if mechanical else "Codex Agent Skills",
        },
        {
            "name": "installed",
            "checked": True,
            "result": "reuse" if installed or installed_tool else "none",
            "details": (
                installed.name
                if installed
                else (
                    str(installed_tool.get("path") or installed_tool.get("name"))
                    if installed_tool
                    else "No matching installed skill, plugin, command, or harness."
                )
            ),
        },
        {
            "name": "repo",
            "checked": True,
            "result": "reuse" if repo_path else "none",
            "details": repo_path or "No matching repo-local hook, script, or tool.",
        },
        {
            "name": "ecosystem",
            "checked": observation.coverage.catalog_checked,
            "result": "adopt" if external else ("none" if observation.coverage.catalog_checked else "not_checked"),
            "details": external.get("url") if external else (
                "No matching configured plugin or OSS catalog entry."
                if observation.coverage.catalog_checked
                else "External OSS search has not been authorized or completed."
            ),
        },
    ]


def _friction_decisions(observation: Observation) -> list[Decision]:
    groups: dict[str, list[tuple[SessionObservation, ToolExecution, ToolExecution, str | None]]] = defaultdict(list)
    for session in observation.sessions:
        for tool in session.tool_executions:
            if tool.status != "failure" or not tool.command:
                continue
            signature = _signature(tool.command)
            success = _first_later_success(tool, session, signature)
            if success:
                correction = _correction_between(tool, success, session)
                if correction:
                    groups[signature].append((session, tool, success, correction))

    decisions: list[Decision] = []
    for signature, occurrences in groups.items():
        session_ids = {item[0].session_id for item in occurrences}
        if len(session_ids) < 2:
            continue
        pair: tuple[str, str] | None = None
        for _, _, _, correction in occurrences:
            if correction:
                pair = _preflight_pair(correction, signature)
                if pair:
                    break
        mechanical = pair is not None
        required = pair[0] if pair else None
        installed = _installed_match(observation, session_ids, signature)
        installed_tool = _installed_tool_match(observation, signature, required)
        repo_path = _repo_match(observation, signature, required)
        external = _catalog_match(observation, signature, required)
        ladder = _ladder(
            observation,
            mechanical=mechanical,
            installed=installed,
            installed_tool=installed_tool,
            repo_path=repo_path,
            external=external,
            session_count=len(session_ids),
        )

        evidence: list[dict[str, Any]] = []
        for session, failed, success, correction in occurrences:
            evidence.append(
                _evidence(
                    session,
                    "verified_recovery",
                    f"`{failed.command}` failed and later exited successfully in the same session.",
                    hard=True,
                )
            )
            if correction:
                evidence.append(
                    _evidence(
                        session,
                        "user_correction",
                        correction,
                        hard=False,
                    )
                )

        metadata: dict[str, Any] = {
            "signature": signature,
            "session_ids": sorted(session_ids),
            "creates_new_tool": False,
        }
        if required:
            metadata.update({"required_command": required, "protected_command": pair[1]})

        if installed and not mechanical:
            decision = "PATCH"
            target_kind = "SKILL"
            target = installed.name
            mechanism = "workflow_instruction"
            proposed = "Patch the installed skill with the repeated correction and verified recovery path."
            metadata.update({"existing_path": installed.path, "expected_sha256": installed.sha256})
        elif installed_tool:
            decision = "PATCH"
            target_kind = "TOOL"
            target = str(installed_tool.get("name") or "installed-tool")
            mechanism = "configure_installed"
            proposed = (
                f"Configure or extend the installed tool at "
                f"{installed_tool.get('path') or installed_tool.get('name')}; do not build or install "
                "a parallel implementation."
            )
            metadata["installed_tool"] = installed_tool
        elif repo_path:
            decision = "PATCH"
            target_kind = "HARNESS" if mechanical else "SKILL"
            target = Path(repo_path).stem
            mechanism = "extend_existing_harness" if mechanical else "extend_existing_workflow"
            proposed = f"Extend the existing repo asset at {repo_path}; do not create a parallel implementation."
            metadata["existing_path"] = repo_path
        elif external:
            decision = "PATCH"
            target_kind = "TOOL"
            target = str(external.get("name") or "external-tool")
            mechanism = "adopt_external"
            proposed = (
                f"Review and configure {target} instead of reimplementing it. "
                "Installation remains manual until license and source review are approved."
            )
            metadata["external_tool"] = external
        elif mechanical:
            decision = "CREATE"
            target_kind = "HARNESS"
            target = f"{_slug(required or 'preflight')}-before-{_slug(signature)}"
            mechanism = "pretool_guard"
            proposed = (
                f"Stage a Codex PreToolUse guard that denies `{signature}` unless the shell "
                f"command exactly matches the reviewed `{required} && {signature}` sequence."
            )
            metadata["creates_new_tool"] = True
        elif any(correction and _rule_like_correction(correction) for _, _, _, correction in occurrences):
            evidence_for_rule = evidence
            correction = next(
                correction
                for _, _, _, correction in occurrences
                if correction and _rule_like_correction(correction)
            )
            decision, source_path, rule_metadata = new_rule_suggestion(
                observation,
                correction,
                evidence_for_rule,
            )
            target_kind = "RULE"
            target = f"project-agents-{_slug(signature)}"
            mechanism = "agents_recommendation"
            proposed = (
                "Stage the new rule only inside the existing managed region; the user reviews and "
                "approves the exact diff."
                if rule_metadata.get("managed_region", {}).get("applyable")
                else f"Suggestion only for {source_path}; the user decides whether and how to edit AGENTS.md."
            )
            metadata.update(rule_metadata)
        else:
            decision = "CREATE"
            target_kind = "SKILL"
            target = f"{_slug(signature)}-workflow"
            mechanism = "workflow_instruction"
            proposed = "Stage a reusable workflow skill grounded in the repeated correction and recovery evidence."
            metadata["creates_new_tool"] = True

        readiness = (
            "needs_research"
            if decision == "CREATE" and not observation.coverage.catalog_checked
            else "ready"
        )
        identifier = _stable_id(decision, target_kind, target, signature)
        decisions.append(
            Decision(
                id=identifier,
                decision=decision,
                target_kind=target_kind,
                target=target,
                mechanism=mechanism,
                evidence=evidence,
                confidence="high" if mechanical and len(session_ids) >= 2 else "medium",
                proposed_change=proposed,
                coverage=observation.coverage.to_dict(),
                adoption_ladder=ladder,
                readiness=readiness,
                metadata=metadata,
            )
        )
    return decisions


def _skill_lifecycle_decisions(
    observation: Observation,
    existing: list[Decision],
    *,
    grace_days: int,
) -> list[Decision]:
    del grace_days  # Grace and minimum-session policy belong to the lifecycle analyzer.
    decisions: list[Decision] = []
    touched = {decision.target.lower() for decision in existing if decision.target_kind == "SKILL"}

    def matched_evidence(skill: InstalledSkill) -> SkillLifecycleEvidence | None:
        skill_file = str(Path(skill.path).resolve()).casefold()
        skill_dir = str(Path(skill.path).parent.resolve()).casefold()
        by_name: list[SkillLifecycleEvidence] = []
        for item in observation.lifecycle_evidence:
            item_path = str(Path(item.skill_path).resolve()).casefold()
            if item_path in {skill_file, skill_dir}:
                return item
            item_name = item.skill_name.casefold()
            if item_name == skill.name.casefold() or item_name.rsplit(":", 1)[-1] == skill.name.casefold():
                by_name.append(item)
        return by_name[0] if len(by_name) == 1 else None

    for skill in observation.skills:
        if skill.protected or skill.name.lower() in touched:
            continue
        lifecycle = matched_evidence(skill)
        external_keep = lifecycle is not None and lifecycle.verdict == "KEEP"
        if external_keep or skill.usage_signals > 0:
            if external_keep:
                summary = (
                    f"SkillReaper reported KEEP ({lifecycle.reason or 'used'}) from "
                    f"{lifecycle.sessions} sessions with {lifecycle.uses} use(s)."
                )
                source = lifecycle.skill_path
                confidence = "high" if lifecycle.uses > 0 else "medium"
                analyzer = "skillreaper"
            else:
                summary = f"Observed {skill.usage_signals} explicit mention or SKILL.md read signal(s)."
                source = skill.path
                confidence = "medium"
                analyzer = "local-positive-only"
            decisions.append(
                Decision(
                    id=_stable_id("KEEP", "SKILL", skill.name, skill.path),
                    decision="KEEP",
                    target_kind="SKILL",
                    target=skill.name,
                    mechanism="retain_used_skill",
                    evidence=[
                        {
                            "id": _evidence_id("inventory", "usage_signal", summary),
                            "session_id": None,
                            "kind": "usage_signal",
                            "summary": summary,
                            "source": source,
                            "hard": False,
                        }
                    ],
                    confidence=confidence,
                    proposed_change="Keep the skill; recent use evidence exists.",
                    coverage=observation.coverage.to_dict(),
                    adoption_ladder=[
                        {"name": "necessity", "checked": True, "result": "used", "details": summary},
                        {"name": "builtin", "checked": True, "result": "not_applicable", "details": "Lifecycle review."},
                        {"name": "installed", "checked": True, "result": "reuse", "details": skill.path},
                        {"name": "repo", "checked": True, "result": "not_applicable", "details": "Lifecycle review."},
                        {"name": "ecosystem", "checked": True, "result": "not_applicable", "details": "No creation proposed."},
                    ],
                    metadata={
                        "existing_path": skill.path,
                        "expected_sha256": skill.sha256,
                        "lifecycle_analyzer": analyzer,
                    },
                )
            )
        elif (
            lifecycle is not None
            and lifecycle.verdict == "REAP"
            and lifecycle.removable
            and lifecycle.complete
            and observation.coverage.retirement_safe
        ):
            summary = (
                f"SkillReaper reported REAP ({lifecycle.reason or 'unused'}) from "
                f"{lifecycle.sessions} sessions; its Codex evidence report was complete."
            )
            decisions.append(
                Decision(
                    id=_stable_id("RETIRE_CANDIDATE", "SKILL", skill.name, skill.path),
                    decision="RETIRE_CANDIDATE",
                    target_kind="SKILL",
                    target=skill.name,
                    mechanism="archive_skill",
                    evidence=[
                        {
                            "id": _evidence_id("inventory", "non_use_candidate", summary),
                            "session_id": None,
                            "kind": "non_use_candidate",
                            "summary": summary,
                            "source": skill.path,
                            "hard": False,
                        }
                    ],
                    confidence="high",
                    proposed_change=(
                        "Archive, do not delete. SkillReaper supplies the lifecycle verdict; "
                        "Codex Metabolism keeps human approval as the trust boundary."
                    ),
                    coverage=observation.coverage.to_dict(),
                    adoption_ladder=[
                        {"name": "necessity", "checked": True, "result": "candidate", "details": summary},
                        {"name": "builtin", "checked": True, "result": "not_applicable", "details": "Lifecycle review."},
                        {"name": "installed", "checked": True, "result": "unused_candidate", "details": skill.path},
                        {"name": "repo", "checked": True, "result": "not_applicable", "details": "Lifecycle review."},
                        {"name": "ecosystem", "checked": True, "result": "not_applicable", "details": "No creation proposed."},
                    ],
                    metadata={
                        "existing_path": skill.path,
                        "expected_sha256": skill.sha256,
                        "age_days": skill.age_days,
                        "lifecycle_analyzer": "skillreaper",
                        "lifecycle_verdict": lifecycle.verdict,
                        "lifecycle_reason": lifecycle.reason,
                    },
                )
            )
    return decisions


def _as_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _intervention_decisions(
    observation: Observation,
    *,
    now: datetime,
) -> list[Decision]:
    decisions: list[Decision] = []
    for receipt in latest_interventions(observation.intervention_records):
        if receipt.status == "PENDING_TRUST":
            summary = (
                "The project hook files were applied, but Codex hook trust has not been "
                "confirmed. No outcome evaluation has started."
            )
            decisions.append(
                Decision(
                    id=_stable_id(
                        "KEEP",
                        receipt.target_kind,
                        receipt.target,
                        receipt.decision_id,
                        "PENDING_TRUST",
                    ),
                    decision="KEEP",
                    target_kind=receipt.target_kind,
                    target=receipt.target,
                    mechanism="intervention_pending_trust",
                    evidence=[
                        {
                            "id": _evidence_id(
                                receipt.decision_id,
                                "hook_trust_pending",
                                summary,
                            ),
                            "session_id": None,
                            "kind": "hook_trust_pending",
                            "summary": summary,
                            "source": receipt.artifact_path,
                            "hard": True,
                        }
                    ],
                    confidence="high",
                    proposed_change=(
                        "Review the hook with Codex `/hooks`, then explicitly activate it or roll "
                        "it back. Do not create a duplicate intervention."
                    ),
                    coverage=observation.coverage.to_dict(),
                    adoption_ladder=[
                        {
                            "name": "necessity",
                            "checked": True,
                            "result": "pending_trust",
                            "details": summary,
                        },
                        {
                            "name": "builtin",
                            "checked": True,
                            "result": "trust_review_required",
                            "details": "Codex `/hooks` controls trust for new project hooks.",
                        },
                        {
                            "name": "installed",
                            "checked": True,
                            "result": "pending",
                            "details": receipt.artifact_path,
                        },
                        {
                            "name": "repo",
                            "checked": True,
                            "result": "installed",
                            "details": receipt.scope,
                        },
                        {
                            "name": "ecosystem",
                            "checked": True,
                            "result": "not_applicable",
                            "details": "No new build is proposed.",
                        },
                    ],
                    metadata={
                        "intervention_id": receipt.decision_id,
                        "lifecycle_verdict": "PENDING_TRUST",
                        "artifact_path": receipt.artifact_path,
                        "signature": receipt.signature,
                        "post_session_count": 0,
                    },
                )
            )
            continue
        if receipt.status != "ACTIVE" or not receipt.signature:
            continue
        activated = _as_datetime(receipt.activated_at)
        if activated is None:
            continue
        signature = _signature(receipt.signature)
        post_sessions: list[SessionObservation] = []
        failures: list[SessionObservation] = []
        successes: list[SessionObservation] = []
        for session in observation.sessions:
            if session.session_id in receipt.baseline_session_ids:
                continue
            timestamp = _as_datetime(session.timestamp)
            if timestamp is None or timestamp <= activated:
                continue
            post_sessions.append(session)
            matched = [
                tool
                for tool in session.tool_executions
                if signature and signature in _signature(tool.command)
            ]
            if any(tool.status == "failure" for tool in matched):
                failures.append(session)
            elif any(tool.status == "success" for tool in matched):
                successes.append(session)

        verdict: str | None = None
        decision_name: str | None = None
        confidence = "medium"
        summary = ""
        evidence_sessions: list[SessionObservation] = []
        if len({session.session_id for session in failures}) >= 2:
            verdict = "INEFFECTIVE"
            decision_name = "PATCH"
            confidence = "high"
            evidence_sessions = failures
            summary = (
                f"The protected workflow failed again in {len(failures)} post-activation sessions."
            )
        elif len({session.session_id for session in successes}) >= 2 and not failures:
            verdict = "VALIDATED"
            decision_name = "KEEP"
            confidence = "medium"
            evidence_sessions = successes
            summary = (
                f"The workflow completed successfully in {len(successes)} post-activation sessions "
                "without an observed matching failure."
            )
        elif (
            len(post_sessions) >= 10
            and not failures
            and not successes
            and (now - activated).days >= 28
        ):
            verdict = "IDLE_CANDIDATE"
            decision_name = "RETIRE_CANDIDATE"
            confidence = "low"
            evidence_sessions = post_sessions[:3]
            summary = (
                f"No matching opportunity was observed across {len(post_sessions)} sessions and "
                f"{(now - activated).days} days; review whether this intervention is still worth maintaining."
            )
        if verdict is None or decision_name is None:
            continue

        evidence = [
            _evidence(
                session,
                "post_intervention_outcome",
                summary,
                hard=verdict in {"INEFFECTIVE", "VALIDATED"},
            )
            for session in evidence_sessions[:5]
        ]
        identifier = _stable_id(
            decision_name,
            receipt.target_kind,
            receipt.target,
            receipt.decision_id,
            verdict,
        )
        decisions.append(
            Decision(
                id=identifier,
                decision=decision_name,
                target_kind=receipt.target_kind,
                target=receipt.target,
                mechanism="intervention_reevaluation",
                evidence=evidence,
                confidence=confidence,
                proposed_change=(
                    "Keep the active intervention and continue evaluation."
                    if verdict == "VALIDATED"
                    else (
                        "Review and patch the intervention; the expected friction recurred after activation."
                        if verdict == "INEFFECTIVE"
                        else "Consider rollback or retirement; this remains a human decision."
                    )
                ),
                coverage=observation.coverage.to_dict(),
                adoption_ladder=[
                    {"name": "necessity", "checked": True, "result": verdict.casefold(), "details": summary},
                    {"name": "builtin", "checked": True, "result": "not_applicable", "details": "Active intervention review."},
                    {"name": "installed", "checked": True, "result": "active", "details": receipt.artifact_path},
                    {"name": "repo", "checked": True, "result": "observed", "details": receipt.scope},
                    {"name": "ecosystem", "checked": True, "result": "not_applicable", "details": "No new build proposed."},
                ],
                metadata={
                    "intervention_id": receipt.decision_id,
                    "lifecycle_verdict": verdict,
                    "activated_at": receipt.activated_at,
                    "artifact_path": receipt.artifact_path,
                    "signature": receipt.signature,
                    "post_session_count": len(post_sessions),
                    "post_failure_sessions": len(failures),
                    "post_success_sessions": len(successes),
                },
            )
        )
    return decisions


def decide(
    observation: Observation,
    *,
    now: datetime | None = None,
    grace_days: int = 28,
) -> list[Decision]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    friction = _friction_decisions(observation)
    active_signatures = {
        _signature(receipt.signature)
        for receipt in latest_interventions(observation.intervention_records)
        if receipt.status in {"ACTIVE", "PENDING_TRUST"} and receipt.signature
    }
    friction = [
        decision
        for decision in friction
        if _signature(str(decision.metadata.get("signature") or "")) not in active_signatures
    ]
    lifecycle = _skill_lifecycle_decisions(observation, friction, grace_days=grace_days)
    agents = agents_review_decisions(observation, friction)
    interventions = _intervention_decisions(observation, now=now)
    decisions = friction + lifecycle + agents + interventions
    for decision in decisions:
        if decision.decision not in DECISIONS:
            raise ValueError(f"unsupported decision: {decision.decision}")
        if decision.target_kind not in TARGET_KINDS:
            raise ValueError(f"unsupported target kind: {decision.target_kind}")
        if decision.confidence not in CONFIDENCE:
            raise ValueError(f"unsupported confidence: {decision.confidence}")
    return sorted(decisions, key=lambda item: (item.target_kind, item.target.lower(), item.decision))
