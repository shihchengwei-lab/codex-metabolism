from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence


class AutomationError(RuntimeError):
    """Raised when scheduled review configuration or execution is unsafe."""


class SchedulerBackend(Protocol):
    kind: str

    def install(self, config: dict[str, Any]) -> None: ...

    def uninstall(self, config: dict[str, Any]) -> None: ...

    def is_registered(self, config: dict[str, Any]) -> bool: ...


Runner = Callable[..., Any]
Notifier = Callable[[str, str], None]


def _aware(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current if current.tzinfo else current.replace(tzinfo=timezone.utc)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return _aware(parsed)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(_jsonable(payload), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AutomationError(f"automation is not configured: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AutomationError(f"automation state is unreadable: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AutomationError(f"automation state must be a JSON object: {path}")
    return payload


def _number(value: float) -> str:
    return f"{value:g}"


def build_config(
    *,
    output_dir: Path,
    project_root: Path,
    codex_home: Path,
    skill_roots: Sequence[Path],
    review_days: float = 7,
    every_days: float = 7,
    after_sessions: int = 10,
    search_oss: bool = False,
    catalog_file: Path | None = None,
    no_skillreaper: bool = False,
    enabled_at: datetime | None = None,
    python_executable: Path | None = None,
    platform_name: str | None = None,
    notify: bool = True,
) -> dict[str, Any]:
    if review_days <= 0:
        raise ValueError("review_days must be positive")
    if every_days <= 0:
        raise ValueError("every_days must be positive")
    if after_sessions <= 0:
        raise ValueError("after_sessions must be positive")

    output = output_dir.expanduser().resolve()
    project = project_root.expanduser().resolve()
    codex = codex_home.expanduser().resolve()
    roots = [root.expanduser().resolve() for root in skill_roots]
    automation_dir = output / "automation"
    config_path = automation_dir / "config.json"
    identity = f"{project}\0{output}".encode("utf-8")
    schedule_id = f"codex-metabolism-{hashlib.sha256(identity).hexdigest()[:12]}"
    executable = (python_executable or Path(sys.executable)).expanduser().resolve()
    enabled = _aware(enabled_at)

    review_argv = [
        "--days",
        _number(review_days),
        "--codex-home",
        str(codex),
        "--project-root",
        str(project),
        "--output-dir",
        str(output),
    ]
    for root in roots:
        review_argv.extend(["--skill-root", str(root)])
    if catalog_file is not None:
        review_argv.extend(["--catalog-file", str(catalog_file.expanduser().resolve())])
    if search_oss:
        review_argv.append("--search-oss")
    if no_skillreaper:
        review_argv.append("--no-skillreaper")

    return {
        "schema_version": 1,
        "enabled": True,
        "enabled_at": enabled.isoformat(),
        "disabled_at": None,
        "platform": platform_name or sys.platform,
        "schedule_id": schedule_id,
        "scheduler_kind": None,
        "check_interval_hours": 24,
        "every_days": every_days,
        "after_sessions": after_sessions,
        "review_days": review_days,
        "search_oss": search_oss,
        "notify": notify,
        "project_root": project,
        "output_dir": output,
        "automation_dir": automation_dir,
        "config_path": config_path,
        "heartbeat_path": automation_dir / "heartbeat.json",
        "notice_path": automation_dir / "NOTICE.md",
        "codex_home": codex,
        "skill_roots": roots,
        "python_executable": executable,
        "review_argv": review_argv,
        "scheduled_command": [
            str(executable),
            "-m",
            "codex_metabolism",
            "scheduled-review",
            "--config",
            str(config_path),
        ],
    }


def _completed(result: Any, action: str) -> None:
    if getattr(result, "returncode", 1) == 0:
        return
    detail = str(getattr(result, "stderr", "") or getattr(result, "stdout", "")).strip()
    raise AutomationError(f"{action} failed{f': {detail}' if detail else ''}")


class WindowsTaskScheduler:
    kind = "windows-task-scheduler"

    def __init__(self, *, run: Runner = subprocess.run) -> None:
        self.run = run

    def install(self, config: dict[str, Any]) -> None:
        automation_dir = Path(config["automation_dir"])
        automation_dir.mkdir(parents=True, exist_ok=True)
        runner = automation_dir / "run-scheduled-review.cmd"
        command = subprocess.list2cmdline([str(item) for item in config["scheduled_command"]])
        project = str(config["project_root"])
        runner.write_text(
            f"@echo off\r\ncd /d \"{project}\"\r\n{command}\r\nexit /b %errorlevel%\r\n",
            encoding="utf-8",
        )
        result = self.run(
            [
                "schtasks",
                "/Create",
                "/TN",
                str(config["schedule_id"]),
                "/TR",
                str(runner),
                "/SC",
                "DAILY",
                "/ST",
                "09:00",
                "/F",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        _completed(result, "Windows Task Scheduler registration")

    def uninstall(self, config: dict[str, Any]) -> None:
        result = self.run(
            ["schtasks", "/Delete", "/TN", str(config["schedule_id"]), "/F"],
            text=True,
            capture_output=True,
            check=False,
        )
        if getattr(result, "returncode", 1) not in {0, 1}:
            _completed(result, "Windows Task Scheduler removal")

    def is_registered(self, config: dict[str, Any]) -> bool:
        result = self.run(
            ["schtasks", "/Query", "/TN", str(config["schedule_id"])],
            text=True,
            capture_output=True,
            check=False,
        )
        return getattr(result, "returncode", 1) == 0


class LaunchdScheduler:
    kind = "launchd"

    def __init__(
        self,
        *,
        home: Path | None = None,
        uid: int | None = None,
        run: Runner = subprocess.run,
    ) -> None:
        self.home = (home or Path.home()).expanduser()
        self.uid = os.getuid() if uid is None else uid
        self.run = run

    def _plist(self, config: dict[str, Any]) -> Path:
        return self.home / "Library" / "LaunchAgents" / f"{config['schedule_id']}.plist"

    def install(self, config: dict[str, Any]) -> None:
        plist = self._plist(config)
        plist.parent.mkdir(parents=True, exist_ok=True)
        automation_dir = Path(config["automation_dir"])
        automation_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "Label": str(config["schedule_id"]),
            "ProgramArguments": [str(item) for item in config["scheduled_command"]],
            "WorkingDirectory": str(config["project_root"]),
            "StartInterval": int(config["check_interval_hours"] * 3600),
            "RunAtLoad": False,
            "StandardOutPath": str(automation_dir / "scheduler.stdout.log"),
            "StandardErrorPath": str(automation_dir / "scheduler.stderr.log"),
        }
        plist.write_bytes(plistlib.dumps(payload, sort_keys=True))
        domain = f"gui/{self.uid}"
        self.run(
            ["launchctl", "bootout", domain, str(plist)],
            text=True,
            capture_output=True,
            check=False,
        )
        result = self.run(
            ["launchctl", "bootstrap", domain, str(plist)],
            text=True,
            capture_output=True,
            check=False,
        )
        _completed(result, "launchd registration")

    def uninstall(self, config: dict[str, Any]) -> None:
        plist = self._plist(config)
        result = self.run(
            ["launchctl", "bootout", f"gui/{self.uid}", str(plist)],
            text=True,
            capture_output=True,
            check=False,
        )
        if getattr(result, "returncode", 1) not in {0, 3}:
            _completed(result, "launchd removal")
        plist.unlink(missing_ok=True)

    def is_registered(self, config: dict[str, Any]) -> bool:
        result = self.run(
            ["launchctl", "print", f"gui/{self.uid}/{config['schedule_id']}"],
            text=True,
            capture_output=True,
            check=False,
        )
        return getattr(result, "returncode", 1) == 0


class SystemdScheduler:
    kind = "systemd-user-timer"

    def __init__(self, *, home: Path | None = None, run: Runner = subprocess.run) -> None:
        self.home = (home or Path.home()).expanduser()
        self.run = run

    def _unit_root(self) -> Path:
        return self.home / ".config" / "systemd" / "user"

    def install(self, config: dict[str, Any]) -> None:
        unit_root = self._unit_root()
        unit_root.mkdir(parents=True, exist_ok=True)
        schedule_id = str(config["schedule_id"])
        service = unit_root / f"{schedule_id}.service"
        timer = unit_root / f"{schedule_id}.timer"
        command = shlex.join([str(item) for item in config["scheduled_command"]])
        working_directory = str(config["project_root"]).replace('"', '\\"')
        service.write_text(
            "[Unit]\n"
            "Description=Codex Metabolism staged review\n\n"
            "[Service]\n"
            "Type=oneshot\n"
            f'WorkingDirectory="{working_directory}"\n'
            f"ExecStart={command}\n",
            encoding="utf-8",
        )
        timer.write_text(
            "[Unit]\n"
            "Description=Check whether Codex Metabolism review is due\n\n"
            "[Timer]\n"
            "OnBootSec=10m\n"
            f"OnUnitActiveSec={int(config['check_interval_hours'])}h\n"
            "Persistent=true\n\n"
            "[Install]\n"
            "WantedBy=timers.target\n",
            encoding="utf-8",
        )
        reload_result = self.run(
            ["systemctl", "--user", "daemon-reload"],
            text=True,
            capture_output=True,
            check=False,
        )
        _completed(reload_result, "systemd user daemon reload")
        result = self.run(
            ["systemctl", "--user", "enable", "--now", f"{schedule_id}.timer"],
            text=True,
            capture_output=True,
            check=False,
        )
        _completed(result, "systemd user timer registration")

    def uninstall(self, config: dict[str, Any]) -> None:
        schedule_id = str(config["schedule_id"])
        result = self.run(
            ["systemctl", "--user", "disable", "--now", f"{schedule_id}.timer"],
            text=True,
            capture_output=True,
            check=False,
        )
        if getattr(result, "returncode", 1) not in {0, 1, 5}:
            _completed(result, "systemd user timer removal")
        unit_root = self._unit_root()
        (unit_root / f"{schedule_id}.service").unlink(missing_ok=True)
        (unit_root / f"{schedule_id}.timer").unlink(missing_ok=True)
        self.run(
            ["systemctl", "--user", "daemon-reload"],
            text=True,
            capture_output=True,
            check=False,
        )

    def is_registered(self, config: dict[str, Any]) -> bool:
        result = self.run(
            ["systemctl", "--user", "is-enabled", f"{config['schedule_id']}.timer"],
            text=True,
            capture_output=True,
            check=False,
        )
        return getattr(result, "returncode", 1) == 0


def scheduler_backend(platform_name: str | None = None) -> SchedulerBackend:
    platform = platform_name or sys.platform
    if platform.startswith("win"):
        return WindowsTaskScheduler()
    if platform == "darwin":
        return LaunchdScheduler()
    if platform.startswith("linux"):
        return SystemdScheduler()
    raise AutomationError(f"unsupported scheduler platform: {platform}")


def _initial_review_time(config: dict[str, Any]) -> str | None:
    decisions = Path(config["output_dir"]) / "decisions.json"
    if not decisions.is_file():
        return None
    try:
        payload = json.loads(decisions.read_text(encoding="utf-8"))
        generated = payload.get("generated_at")
        return _parse_time(generated).isoformat() if generated else None
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None


def enable_automation(
    config: dict[str, Any],
    *,
    backend: SchedulerBackend | None = None,
) -> Path:
    selected = backend or scheduler_backend(str(config["platform"]))
    config["enabled"] = True
    config["scheduler_kind"] = selected.kind
    config_path = Path(config["config_path"])
    heartbeat_path = Path(config["heartbeat_path"])
    heartbeat = {
        "schema_version": 1,
        "last_check_at": None,
        "last_successful_review_at": _initial_review_time(config),
        "last_status": "enabled",
        "last_error": None,
        "last_reason": None,
        "pending_sessions": 0,
        "pending_decisions": 0,
        "last_review_source": None,
    }
    _atomic_json(config_path, config)
    _atomic_json(heartbeat_path, heartbeat)
    try:
        selected.install(config)
    except Exception as exc:
        config["enabled"] = False
        heartbeat["last_status"] = "error"
        heartbeat["last_error"] = str(exc)
        _atomic_json(config_path, config)
        _atomic_json(heartbeat_path, heartbeat)
        if isinstance(exc, AutomationError):
            raise
        raise AutomationError(f"scheduler registration failed: {exc}") from exc
    return config_path


def _session_files(config: dict[str, Any], *, now: datetime, since: datetime | None) -> list[Path]:
    sessions_root = Path(config["codex_home"]) / "sessions"
    if not sessions_root.is_dir():
        return []
    cutoff = (
        since.timestamp()
        if since is not None
        else (now - timedelta(days=float(config["review_days"]))).timestamp()
    )
    selected = []
    for path in sessions_root.rglob("rollout-*.jsonl"):
        try:
            if path.stat().st_mtime > cutoff:
                selected.append(path)
        except OSError:
            continue
    return sorted(selected)


def due_state(
    config: dict[str, Any],
    heartbeat: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = _aware(now)
    last_review = _parse_time(heartbeat.get("last_successful_review_at"))
    enabled_at = _parse_time(str(config["enabled_at"])) or current
    pending = len(_session_files(config, now=current, since=last_review or enabled_at))
    anchor = last_review or enabled_at
    next_due = anchor + timedelta(days=float(config["every_days"]))
    if pending == 0:
        due = False
        reason = "waiting_for_sessions"
    elif pending >= int(config["after_sessions"]):
        due = True
        reason = "session_threshold"
    elif current >= next_due:
        due = True
        reason = "time_threshold"
    else:
        due = False
        reason = "waiting_for_threshold"
    return {
        "due": due,
        "reason": reason,
        "pending_sessions": pending,
        "next_due_at": next_due.isoformat(),
        "last_successful_review_at": last_review.isoformat() if last_review else None,
    }


def _load_heartbeat(config: dict[str, Any]) -> dict[str, Any]:
    path = Path(config["heartbeat_path"])
    if path.is_file():
        return _load_json(path)
    return {
        "schema_version": 1,
        "last_check_at": None,
        "last_successful_review_at": None,
        "last_status": "unknown",
        "last_error": None,
        "last_reason": None,
        "pending_sessions": 0,
        "pending_decisions": 0,
        "last_review_source": None,
    }


def _decision_count(output_dir: Path) -> int:
    try:
        payload = json.loads((output_dir / "decisions.json").read_text(encoding="utf-8"))
        decisions = payload.get("decisions", [])
        return len(decisions) if isinstance(decisions, list) else 0
    except (OSError, UnicodeError, json.JSONDecodeError):
        return 0


def _write_notice(config: dict[str, Any], *, now: datetime, decisions: int) -> None:
    path = Path(config["notice_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Codex Metabolism review ready\n\n"
        f"Generated: {now.isoformat()}\n\n"
        f"Pending decisions in the latest staged review: {decisions}\n\n"
        f"Open `{Path(config['output_dir']) / 'report.md'}` and approve or reject each change. "
        "No live state was changed by the scheduled review.\n",
        encoding="utf-8",
    )


def _default_notifier(title: str, message: str) -> None:
    try:
        if sys.platform.startswith("win"):
            user = os.environ.get("USERNAME") or "*"
            command = ["msg", user, f"{title}: {message}"]
        elif sys.platform == "darwin":
            escaped = message.replace('"', "'")
            command = ["osascript", "-e", f'display notification "{escaped}" with title "{title}"']
        else:
            command = ["notify-send", title, message]
        subprocess.run(command, text=True, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return


def run_scheduled_review(
    config_path: Path,
    *,
    now: datetime | None = None,
    review_runner: Callable[[list[str]], int],
    notifier: Notifier | None = None,
) -> dict[str, Any]:
    current = _aware(now)
    config = _load_json(config_path)
    if not config.get("enabled"):
        return {"ran_review": False, "reason": "disabled", "pending_sessions": 0}
    heartbeat = _load_heartbeat(config)
    state = due_state(config, heartbeat, now=current)
    heartbeat.update(
        {
            "last_check_at": current.isoformat(),
            "last_reason": state["reason"],
            "pending_sessions": state["pending_sessions"],
            "last_error": None,
        }
    )
    if not state["due"]:
        heartbeat["last_status"] = state["reason"]
        _atomic_json(Path(config["heartbeat_path"]), heartbeat)
        return {"ran_review": False, **state}

    notify = notifier or _default_notifier
    argv = ["review", *[str(item) for item in config["review_argv"]]]
    try:
        code = review_runner(argv)
        if code != 0:
            raise AutomationError(f"scheduled review exited with exit code {code}")
    except Exception as exc:
        message = str(exc)
        heartbeat.update(
            {
                "last_status": "error",
                "last_error": message,
                "last_review_source": "scheduled",
            }
        )
        _atomic_json(Path(config["heartbeat_path"]), heartbeat)
        if config.get("notify", True):
            notify("Codex Metabolism review failed", message)
        if isinstance(exc, AutomationError):
            raise
        raise AutomationError(f"scheduled review failed: {message}") from exc

    decisions = _decision_count(Path(config["output_dir"]))
    heartbeat.update(
        {
            "last_successful_review_at": current.isoformat(),
            "last_status": "review_staged" if decisions else "review_complete_no_decisions",
            "last_error": None,
            "last_review_source": "scheduled",
            "pending_sessions": 0,
            "pending_decisions": decisions,
        }
    )
    _atomic_json(Path(config["heartbeat_path"]), heartbeat)
    _write_notice(config, now=current, decisions=decisions)
    if decisions and config.get("notify", True):
        notify(
            "Codex Metabolism review ready",
            f"{decisions} staged decision{'s' if decisions != 1 else ''}; no live state changed.",
        )
    return {"ran_review": True, "decisions": decisions, **state}


def record_review_success(
    output_dir: Path,
    *,
    reviewed_at: datetime | None = None,
    source: str = "manual",
) -> None:
    config_path = output_dir / "automation" / "config.json"
    if not config_path.is_file():
        return
    config = _load_json(config_path)
    if not config.get("enabled"):
        return
    current = _aware(reviewed_at)
    heartbeat = _load_heartbeat(config)
    heartbeat.update(
        {
            "last_check_at": current.isoformat(),
            "last_successful_review_at": current.isoformat(),
            "last_status": "review_staged",
            "last_error": None,
            "last_review_source": source,
            "pending_sessions": 0,
            "pending_decisions": _decision_count(output_dir),
        }
    )
    _atomic_json(Path(config["heartbeat_path"]), heartbeat)


def get_automation_status(
    config_path: Path,
    *,
    now: datetime | None = None,
    backend: SchedulerBackend | None = None,
) -> dict[str, Any]:
    current = _aware(now)
    config = _load_json(config_path)
    heartbeat = _load_heartbeat(config)
    enabled = bool(config.get("enabled"))
    selected = backend or scheduler_backend(str(config.get("platform") or sys.platform))
    registered = selected.is_registered(config) if enabled else False
    state = due_state(config, heartbeat, now=current)
    last_check = _parse_time(heartbeat.get("last_check_at"))
    enabled_at = _parse_time(str(config["enabled_at"])) or current
    stale_anchor = last_check or enabled_at
    stale_after = timedelta(hours=max(48, int(config.get("check_interval_hours", 24)) * 2))
    overdue = enabled and current - stale_anchor > stale_after

    if not enabled:
        health = "disabled"
    elif not registered:
        health = "unregistered"
    elif heartbeat.get("last_error"):
        health = "error"
    elif overdue:
        health = "overdue"
    elif state["due"]:
        health = "review_due"
    else:
        health = state["reason"]
    return {
        "enabled": enabled,
        "registered": registered,
        "health": health,
        "overdue": overdue,
        "pending_sessions": state["pending_sessions"],
        "pending_decisions": int(heartbeat.get("pending_decisions") or 0),
        "last_check_at": heartbeat.get("last_check_at"),
        "last_successful_review_at": heartbeat.get("last_successful_review_at"),
        "next_due_at": state["next_due_at"],
        "last_error": heartbeat.get("last_error"),
        "notice_path": str(config["notice_path"]),
        "scheduler_kind": config.get("scheduler_kind"),
    }


def disable_automation(
    config_path: Path,
    *,
    backend: SchedulerBackend | None = None,
    now: datetime | None = None,
) -> None:
    current = _aware(now)
    config = _load_json(config_path)
    selected = backend or scheduler_backend(str(config.get("platform") or sys.platform))
    selected.uninstall(config)
    config["enabled"] = False
    config["disabled_at"] = current.isoformat()
    _atomic_json(config_path, config)
    heartbeat = _load_heartbeat(config)
    heartbeat.update(
        {
            "last_check_at": current.isoformat(),
            "last_status": "disabled",
            "last_error": None,
        }
    )
    _atomic_json(Path(config["heartbeat_path"]), heartbeat)
