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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    interrupted_turns: int = 0
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
class AgentsDocument:
    path: str
    scope: str
    depth: int
    content_sha256: str
    byte_count: int
    line_count: int
    whole_document_available: bool


@dataclass(slots=True)
class InterventionReceipt:
    intervention_id: str
    target_kind: str
    target: str
    mechanism: str
    scope: str
    status: str
    activated_at: str
    artifact_path: str
    proposal_id: str = ""
    reasoning: str = ""
    expected_effect: str = ""
    rollback_when: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Observation:
    codex_home: str
    project_root: str
    skill_roots: list[str]
    days: float
    sessions: list[SessionObservation]
    skills: list[InstalledSkill]
    coverage: Coverage
    agents_documents: list[AgentsDocument] = field(default_factory=list)
    intervention_records: list[InterventionReceipt] = field(default_factory=list)
