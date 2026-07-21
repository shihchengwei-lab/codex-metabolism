from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "anonymized-real-session-evaluation.json"
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
FORBIDDEN_MARKERS = ("C:\\Users", "/Users/", "github.com/")


def load_and_validate() -> dict:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported real-session evaluation schema")
    provenance = payload.get("provenance")
    coverage = payload.get("coverage")
    cases = payload.get("cases")
    if not isinstance(provenance, dict) or provenance.get("source") != "real_codex_sessions":
        raise ValueError("fixture provenance must identify real Codex sessions")
    if provenance.get("raw_logs_committed") is not False:
        raise ValueError("raw logs must not be committed")
    if not isinstance(coverage, dict) or not isinstance(cases, list) or len(cases) < 2:
        raise ValueError("fixture requires coverage and at least two reviewed cases")
    if coverage.get("files_parsed") != coverage.get("files_selected"):
        raise ValueError("public fixture must disclose incomplete parser coverage")
    for case in cases:
        if not all(case.get(field) for field in ("id", "evidence", "agent_judgment", "recommended_outcome")):
            raise ValueError("every case requires evidence, Agent judgment, and an outcome")
    serialized = json.dumps(payload, ensure_ascii=False)
    if any(marker.casefold() in serialized.casefold() for marker in FORBIDDEN_MARKERS):
        raise ValueError("fixture contains a forbidden path or account marker")
    if UUID_RE.search(serialized):
        raise ValueError("fixture contains a raw session identifier")
    return payload


def main() -> int:
    payload = load_and_validate()
    coverage = payload["coverage"]
    print("REAL SESSION EVALUATION")
    print(f"Coverage: {coverage['files_parsed']}/{coverage['files_selected']} files parsed")
    print(
        f"Identity: {coverage['unique_sessions']} unique sessions; "
        f"{coverage['duplicate_session_files']} duplicate/fork files collapsed"
    )
    print(f"Duplicate user events collapsed: {coverage['duplicate_user_events']}")
    print("Raw logs committed: no")
    for case in payload["cases"]:
        print(f"- {case['title']}: {case['recommended_outcome']}")
    print("Claim boundary: small real-session case study; no causal-impact claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
