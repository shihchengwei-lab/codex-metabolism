from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from codex_metabolism.decide import decide
from codex_metabolism.observe import observe
from examples.run_messy_evidence_demo import REVIEW_AT, _records, _write_jsonl


def _tool(command: str, *, success: bool) -> dict[str, Any]:
    return {
        "kind": "tool",
        "command": command,
        "success": success,
        "output": "completed" if success else "failed",
    }


def _message(text: str) -> dict[str, Any]:
    return {"kind": "message", "text": text}


def _recovery(
    command: str,
    *,
    correction: str | None,
    success_command: str | None = None,
    correction_position: str = "between",
) -> list[dict[str, Any]]:
    success = success_command or command
    events: list[dict[str, Any]] = []
    if correction and correction_position == "before":
        events.append(_message(correction))
    events.append(_tool(command, success=False))
    if correction and correction_position == "between":
        events.append(_message(correction))
    events.append(_tool(success, success=True))
    if correction and correction_position == "after":
        events.append(_message(correction))
    return events


def _pair(
    identifier: str,
    *,
    category: str,
    expected_detected: bool,
    commands: tuple[str, str],
    corrections: tuple[str | None, str | None],
    success_commands: tuple[str | None, str | None] | None = None,
    positions: tuple[str, str] = ("between", "between"),
    note: str,
) -> dict[str, Any]:
    successes = success_commands or (None, None)
    return {
        "id": identifier,
        "category": category,
        "expected_detected": expected_detected,
        "note": note,
        "sessions": [
            _recovery(
                commands[index],
                correction=corrections[index],
                success_command=successes[index],
                correction_position=positions[index],
            )
            for index in range(2)
        ],
    }


def _cases() -> list[dict[str, Any]]:
    default = "No. Run `preflight` before `deploy production`."
    cases = [
        _pair(
            "canonical-sequence",
            category="supported-positive",
            expected_detected=True,
            commands=("deploy production", "deploy production"),
            corrections=(default, default),
            note="Exact repeated command with an explicit correction in both sessions.",
        ),
        _pair(
            "case-whitespace-normalization",
            category="supported-positive",
            expected_detected=True,
            commands=("Deploy   Production", "deploy production"),
            corrections=(default, default),
            note="Case and repeated whitespace are normalized.",
        ),
        _pair(
            "different-correction-wording",
            category="supported-positive",
            expected_detected=True,
            commands=("publish package", "publish package"),
            corrections=(
                "No. Run `check metadata` before `publish package`.",
                "Wrong. Check metadata first, then retry the command.",
            ),
            note="Correction wording may differ when both messages carry correction markers.",
        ),
        _pair(
            "traditional-chinese-correction",
            category="supported-positive",
            expected_detected=True,
            commands=("deploy production", "deploy production"),
            corrections=(
                "不對，先執行 `preflight` 再執行 `deploy production`。",
                "不要直接部署，應該先完成 preflight。",
            ),
            note="The bounded correction lexicon includes Traditional Chinese markers.",
        ),
        _pair(
            "exact-command-with-arguments",
            category="supported-positive",
            expected_detected=True,
            commands=("pytest tests/unit -q", "pytest tests/unit -q"),
            corrections=("No. Inspect the failure first.", "Wrong. Inspect the failure first."),
            note="Arguments are supported when the complete normalized command repeats exactly.",
        ),
        _pair(
            "exact-path",
            category="supported-positive",
            expected_detected=True,
            commands=(
                "python C:/repo/scripts/check.py",
                "python C:/repo/scripts/check.py",
            ),
            corrections=("No. Check configuration first.", "Wrong. Check configuration first."),
            note="Paths are supported only when they repeat exactly.",
        ),
        _pair(
            "rule-like-correction",
            category="supported-positive",
            expected_detected=True,
            commands=("review release", "review release"),
            corrections=(
                "No. Always review release notes before publishing.",
                "Wrong. You must review release notes first.",
            ),
            note="Recognized durable-language markers can support a bounded rule proposal.",
        ),
        _pair(
            "contextual-skill-correction",
            category="supported-positive",
            expected_detected=True,
            commands=("design dashboard", "design dashboard"),
            corrections=(
                "No. Use $ui-verification before declaring it complete.",
                "Wrong. Use $ui-verification first.",
            ),
            note="Explicit skill redirection remains detectable without semantic clustering.",
        ),
        _pair(
            "path-variation",
            category="known-positive-miss",
            expected_detected=True,
            commands=(
                "python C:/repo-a/scripts/check.py",
                "python C:/repo-b/scripts/check.py",
            ),
            corrections=("No. Check config first.", "No. Check config first."),
            note="Equivalent workflow with different repository paths is not clustered.",
        ),
        _pair(
            "argument-variation",
            category="known-positive-miss",
            expected_detected=True,
            commands=("deploy --build 101", "deploy --build 102"),
            corrections=("No. Run preflight first.", "No. Run preflight first."),
            note="Dynamic argument values remain distinct signatures.",
        ),
        _pair(
            "command-alias",
            category="known-positive-miss",
            expected_detected=True,
            commands=("pytest tests/unit", "python -m pytest tests/unit"),
            corrections=("No. Inspect the failure first.", "No. Inspect the failure first."),
            note="Command aliases are not treated as semantically equivalent.",
        ),
        _pair(
            "quoted-path-variation",
            category="known-positive-miss",
            expected_detected=True,
            commands=(
                'python "C:/repo/scripts/check.py"',
                "python C:/repo/scripts/check.py",
            ),
            corrections=("No. Check config first.", "No. Check config first."),
            note="Quoted and unquoted path forms remain distinct.",
        ),
        _pair(
            "unmarked-correction",
            category="known-positive-miss",
            expected_detected=True,
            commands=("design dashboard", "design dashboard"),
            corrections=(
                "Use the existing visual verification workflow.",
                "Reuse the visual verification workflow.",
            ),
            note="Imperatives without a bounded correction marker are conservatively ignored.",
        ),
        _pair(
            "equivalent-recovery-command",
            category="known-positive-miss",
            expected_detected=True,
            commands=("pytest tests/unit", "pytest tests/unit"),
            success_commands=(
                "python -m pytest tests/unit",
                "python -m pytest tests/unit",
            ),
            corrections=("No. Retry with the module form.", "No. Retry with the module form."),
            note="A semantically equivalent recovery command does not verify the failed signature.",
        ),
        _pair(
            "flag-order-variation",
            category="known-positive-miss",
            expected_detected=True,
            commands=("tool --fast --safe", "tool --safe --fast"),
            corrections=("No. Check config first.", "No. Check config first."),
            note="Flag order is not canonicalized.",
        ),
        _pair(
            "shell-variant",
            category="known-positive-miss",
            expected_detected=True,
            commands=("make test", "& make test"),
            corrections=("No. Inspect the failure first.", "No. Inspect the failure first."),
            note="Shell invocation variants remain separate signatures.",
        ),
        _pair(
            "normal-retry",
            category="negative",
            expected_detected=False,
            commands=("deploy production", "deploy production"),
            corrections=(None, None),
            note="A normal retry without user correction is not collaboration friction.",
        ),
        _pair(
            "one-corrected-session",
            category="negative",
            expected_detected=False,
            commands=("deploy production", "deploy production"),
            corrections=(default, None),
            note="One corrected session does not cross the recurrence threshold.",
        ),
        _pair(
            "correction-before-failure",
            category="negative",
            expected_detected=False,
            commands=("deploy production", "deploy production"),
            corrections=(default, default),
            positions=("before", "before"),
            note="A message before the failure is not evidence of correction for that failure.",
        ),
        _pair(
            "correction-after-success",
            category="negative",
            expected_detected=False,
            commands=("deploy production", "deploy production"),
            corrections=(default, default),
            positions=("after", "after"),
            note="A later message cannot be attached retroactively to an earlier recovery.",
        ),
        {
            "id": "single-session-only",
            "category": "negative",
            "expected_detected": False,
            "note": "One corrected recovery is below the two-session threshold.",
            "sessions": [_recovery("deploy production", correction=default)],
        },
        {
            "id": "cross-session-outcome",
            "category": "negative",
            "expected_detected": False,
            "note": "Failure and success in different sessions do not form a verified recovery.",
            "sessions": [
                [_tool("deploy production", success=False), _message(default)],
                [_tool("deploy production", success=True)],
            ],
        },
        {
            "id": "failures-without-recovery",
            "category": "negative",
            "expected_detected": False,
            "note": "Repeated failures without later success must abstain.",
            "sessions": [
                [_tool("deploy production", success=False), _message(default)],
                [_tool("deploy production", success=False), _message(default)],
            ],
        },
        {
            "id": "unrelated-success",
            "category": "negative",
            "expected_detected": False,
            "note": "Success of a prerequisite is not success of the failed command.",
            "sessions": [
                [
                    _tool("deploy production", success=False),
                    _message(default),
                    _tool("preflight", success=True),
                ],
                [
                    _tool("deploy production", success=False),
                    _message(default),
                    _tool("preflight", success=True),
                ],
            ],
        },
    ]
    if len(cases) != 24:
        raise RuntimeError(f"detector evaluation must contain 24 cases, observed {len(cases)}")
    return cases


def _evaluate_case(case: dict[str, Any], output_root: Path, index: int) -> dict[str, Any]:
    case_root = output_root / "cases" / str(case["id"])
    codex_home = case_root / ".codex"
    project_root = case_root / "project"
    skill_root = case_root / ".agents" / "skills"
    project_root.mkdir(parents=True, exist_ok=True)
    for session_index, events in enumerate(case["sessions"], start=1):
        timestamp = REVIEW_AT - timedelta(minutes=index * 5 + session_index)
        _write_jsonl(
            codex_home
            / "sessions"
            / "2026"
            / "07"
            / "20"
            / f"rollout-{case['id']}-{session_index}.jsonl",
            _records(
                f"{case['id']}-{session_index}",
                timestamp=timestamp,
                prompt="Complete the requested coding task.",
                events=events,
            ),
            timestamp,
        )
    observation = observe(
        codex_home,
        [skill_root],
        days=7,
        now=REVIEW_AT,
        project_root=project_root,
        catalog_entries=[],
        catalog_checked=True,
    )
    friction = [
        decision
        for decision in decide(observation, now=REVIEW_AT)
        if decision.metadata.get("signature")
    ]
    return {
        "id": case["id"],
        "category": case["category"],
        "expected_detected": bool(case["expected_detected"]),
        "observed_detected": bool(friction),
        "note": case["note"],
        "observed_signatures": sorted(
            str(decision.metadata["signature"]) for decision in friction
        ),
    }


def run(output_root: Path) -> int:
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"evaluation output directory must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    results = [
        _evaluate_case(case, output_root, index)
        for index, case in enumerate(_cases(), start=1)
    ]
    true_positive = sum(
        item["expected_detected"] and item["observed_detected"] for item in results
    )
    false_positive = sum(
        not item["expected_detected"] and item["observed_detected"] for item in results
    )
    false_negative = sum(
        item["expected_detected"] and not item["observed_detected"] for item in results
    )
    true_negative = sum(
        not item["expected_detected"] and not item["observed_detected"] for item in results
    )
    detected = true_positive + false_positive
    positives = true_positive + false_negative
    abstained = false_negative + true_negative
    payload = {
        "schema_version": 1,
        "summary": {
            "case_count": len(results),
            "labeled_positive_count": positives,
            "labeled_negative_count": false_positive + true_negative,
        },
        "confusion_matrix": {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "true_negative": true_negative,
        },
        "metrics": {
            "precision": true_positive / detected if detected else 0.0,
            "recall": true_positive / positives if positives else 0.0,
            "abstention_rate": abstained / len(results),
        },
        "methodology": {
            "synthetic": True,
            "labels": "author-defined capability expectations fixed before detector execution",
            "claim": (
                "This is a deterministic boundary evaluation, not a real-world quality benchmark "
                "or evidence of causal friction reduction."
            ),
            "detector_scope": (
                "Two sessions must each contain the same normalized failed command, a recognized "
                "user correction between failure and recovery, and a later successful execution "
                "of that same normalized command."
            ),
        },
        "cases": results,
    }
    result_path = output_root / "detector-evaluation.json"
    result_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Detector boundary: {len(results)} cases")
    print(f"Precision: {payload['metrics']['precision']:.3f}")
    print(f"Recall: {payload['metrics']['recall']:.3f}")
    print(f"False positives: {false_positive}")
    print(f"Abstentions: {abstained}")
    print(f"Inspect the retained evaluation at: {result_path.resolve()}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the synthetic detector capability-boundary evaluation"
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Empty output directory; defaults to a retained temporary directory",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = args.output_root or Path(
        tempfile.mkdtemp(prefix="codex-metabolism-detector-eval-")
    )
    try:
        return run(output)
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
