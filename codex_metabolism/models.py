from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Coverage:
    files_selected: int = 0
    files_parsed: int = 0
    parse_errors: int = 0
    skill_invocation: str = "unavailable"
    structured_skill_events: int = 0
    heuristic_skill_events: int = 0
    catalog_checked: bool = False
    skill_lifecycle_source: str = "local-positive-only"
    skill_lifecycle_complete: bool = False

    @property
    def retirement_safe(self) -> bool:
        return self.skill_lifecycle_source == "skillreaper" and self.skill_lifecycle_complete

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["retirement_safe"] = self.retirement_safe
        return payload


@dataclass(slots=True)
class UserMessage:
    sequence: int
    text: str


@dataclass(slots=True)
class ToolExecution:
    sequence: int
    output_sequence: int
    call_id: str
    tool_name: str
    command: str
    status: str
    output_excerpt: str


@dataclass(slots=True)
class SessionObservation:
    session_id: str
    timestamp: str | None
    cwd: str | None
    cli_version: str | None
    model: str | None
    source_file: str
    messages: list[UserMessage] = field(default_factory=list)
    corrections: list[UserMessage] = field(default_factory=list)
    tool_executions: list[ToolExecution] = field(default_factory=list)
    skill_signals: set[str] = field(default_factory=set)
    parse_errors: int = 0


@dataclass(slots=True)
class InstalledSkill:
    name: str
    description: str
    path: str
    root: str
    sha256: str
    age_days: float
    protected: bool
    usage_signals: int = 0


@dataclass(slots=True)
class RepoAsset:
    path: str
    kind: str
    searchable_text: str


@dataclass(slots=True)
class AgentsDocument:
    path: str
    scope: str
    depth: int
    content_sha256: str
    byte_count: int
    line_count: int
    codex_context_limit: int
    whole_document_evaluated: bool
    content: str = field(repr=False)
    decode_errors: int = 0


@dataclass(slots=True)
class SkillLifecycleEvidence:
    source: str
    skill_name: str
    skill_path: str
    verdict: str
    reason: str
    uses: int
    sessions: int
    removable: bool
    complete: bool
    generated_at: str | None = None


@dataclass(slots=True)
class InterventionReceipt:
    decision_id: str
    target_kind: str
    target: str
    mechanism: str
    scope: str
    status: str
    activated_at: str
    artifact_path: str
    signature: str | None = None
    expected_effect: str = ""
    baseline_session_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Observation:
    codex_home: str
    project_root: str
    days: float
    sessions: list[SessionObservation]
    skills: list[InstalledSkill]
    repo_assets: list[RepoAsset]
    catalog_entries: list[dict[str, Any]]
    coverage: Coverage
    installed_tools: list[dict[str, Any]] = field(default_factory=list)
    agents_documents: list[AgentsDocument] = field(default_factory=list)
    lifecycle_evidence: list[SkillLifecycleEvidence] = field(default_factory=list)
    intervention_records: list[InterventionReceipt] = field(default_factory=list)


@dataclass(slots=True)
class Decision:
    id: str
    decision: str
    target_kind: str
    target: str
    mechanism: str
    evidence: list[dict[str, Any]]
    confidence: str
    proposed_change: str
    coverage: dict[str, Any]
    adoption_ladder: list[dict[str, Any]]
    readiness: str = "ready"
    status: str = "proposed"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
