from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from codex_metabolism.automation import (
    AutomationError,
    LaunchdScheduler,
    SystemdScheduler,
    WindowsTaskScheduler,
    build_config,
    disable_automation,
    due_state,
    enable_automation,
    get_automation_status,
    run_scheduled_review,
)
from codex_metabolism.cli import main
from tests.helpers import make_deploy_home


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def write_session(codex_home: Path, name: str, *, modified_at: datetime) -> Path:
    path = codex_home / "sessions" / "2026" / "07" / "20" / f"rollout-{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")
    stamp = modified_at.timestamp()
    os.utime(path, (stamp, stamp))
    return path


class FakeScheduler:
    kind = "fake"

    def __init__(self) -> None:
        self.installed = False
        self.install_calls: list[dict] = []
        self.uninstall_calls: list[dict] = []

    def install(self, config: dict) -> None:
        self.installed = True
        self.install_calls.append(config)

    def uninstall(self, config: dict) -> None:
        self.installed = False
        self.uninstall_calls.append(config)

    def is_registered(self, config: dict) -> bool:
        return self.installed


class AutomationTests(unittest.TestCase):
    def _config(self, root: Path, **overrides) -> dict:
        values = {
            "output_dir": root / ".codex-metabolism",
            "project_root": root,
            "codex_home": root / ".codex",
            "skill_roots": [root / ".agents" / "skills"],
            "review_days": 7,
            "every_days": 7,
            "after_sessions": 10,
            "search_oss": False,
            "catalog_file": None,
            "no_skillreaper": True,
            "enabled_at": NOW,
            "python_executable": Path("C:/Python312/python.exe"),
            "platform_name": "win32",
        }
        values.update(overrides)
        return build_config(**values)

    def test_due_requires_new_sessions_even_after_time_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root, enabled_at=NOW - timedelta(days=8))
            heartbeat = {
                "last_successful_review_at": (NOW - timedelta(days=8)).isoformat(),
            }

            state = due_state(config, heartbeat, now=NOW)

            self.assertFalse(state["due"])
            self.assertEqual(state["reason"], "waiting_for_sessions")
            self.assertEqual(state["pending_sessions"], 0)

    def test_sessions_from_before_enable_are_not_counted_as_new(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root, enabled_at=NOW, after_sessions=1)
            write_session(
                config["codex_home"],
                "before-enable",
                modified_at=NOW - timedelta(minutes=1),
            )

            state = due_state(config, {}, now=NOW + timedelta(hours=1))

            self.assertFalse(state["due"])
            self.assertEqual(state["reason"], "waiting_for_sessions")
            self.assertEqual(state["pending_sessions"], 0)

    def test_session_or_time_threshold_triggers_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            last_review = NOW - timedelta(days=2)
            config = self._config(root, after_sessions=2)
            write_session(config["codex_home"], "one", modified_at=NOW - timedelta(hours=2))
            write_session(config["codex_home"], "two", modified_at=NOW - timedelta(hours=1))

            by_count = due_state(
                config,
                {"last_successful_review_at": last_review.isoformat()},
                now=NOW,
            )
            self.assertTrue(by_count["due"])
            self.assertEqual(by_count["reason"], "session_threshold")

            config = self._config(root, after_sessions=10)
            by_time = due_state(
                config,
                {"last_successful_review_at": (NOW - timedelta(days=8)).isoformat()},
                now=NOW,
            )
            self.assertTrue(by_time["due"])
            self.assertEqual(by_time["reason"], "time_threshold")

    def test_scheduled_review_is_stage_only_local_by_default_and_updates_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root, after_sessions=1)
            backend = FakeScheduler()
            config_path = enable_automation(config, backend=backend)
            write_session(config["codex_home"], "new", modified_at=NOW + timedelta(minutes=1))
            calls: list[list[str]] = []
            notices: list[tuple[str, str]] = []

            def review_runner(argv: list[str]) -> int:
                calls.append(argv)
                output = Path(config["output_dir"])
                (output / "decisions.json").write_text(
                    json.dumps({"decisions": [{"id": "met-demo"}]}),
                    encoding="utf-8",
                )
                return 0

            result = run_scheduled_review(
                config_path,
                now=NOW + timedelta(minutes=2),
                review_runner=review_runner,
                notifier=lambda title, message: notices.append((title, message)),
            )

            self.assertTrue(result["ran_review"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "review")
            self.assertNotIn("--search-oss", calls[0])
            self.assertFalse({"apply", "archive", "activate-harness"} & set(calls[0]))
            heartbeat = json.loads(
                (Path(config["automation_dir"]) / "heartbeat.json").read_text(encoding="utf-8")
            )
            self.assertEqual(heartbeat["last_status"], "review_staged")
            self.assertEqual(heartbeat["last_successful_review_at"], (NOW + timedelta(minutes=2)).isoformat())
            self.assertEqual(heartbeat["pending_decisions"], 1)
            self.assertEqual(len(notices), 1)

    def test_scheduled_failure_is_visible_and_does_not_advance_success_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root, after_sessions=1)
            backend = FakeScheduler()
            config_path = enable_automation(config, backend=backend)
            write_session(config["codex_home"], "new", modified_at=NOW + timedelta(minutes=1))

            with self.assertRaises(AutomationError):
                run_scheduled_review(
                    config_path,
                    now=NOW + timedelta(minutes=2),
                    review_runner=lambda argv: 2,
                    notifier=lambda title, message: None,
                )

            heartbeat = json.loads(
                (Path(config["automation_dir"]) / "heartbeat.json").read_text(encoding="utf-8")
            )
            self.assertEqual(heartbeat["last_status"], "error")
            self.assertIsNone(heartbeat["last_successful_review_at"])
            self.assertIn("exit code 2", heartbeat["last_error"])

    def test_due_schedule_runs_the_real_review_cli_and_stages_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skill_root = make_deploy_home(root)
            catalog = root / "catalog.json"
            catalog.write_text("[]", encoding="utf-8")
            config = self._config(
                root,
                codex_home=codex_home,
                skill_roots=[skill_root],
                after_sessions=1,
                catalog_file=catalog,
                enabled_at=NOW - timedelta(hours=1),
            )
            backend = FakeScheduler()
            config_path = enable_automation(config, backend=backend)

            with patch("codex_metabolism.cli._plugin_catalog", return_value=[]):
                result = run_scheduled_review(
                    config_path,
                    now=NOW + timedelta(minutes=1),
                    review_runner=main,
                    notifier=lambda title, message: None,
                )

            output = Path(config["output_dir"])
            self.assertTrue(result["ran_review"])
            self.assertTrue((output / "report.md").is_file())
            self.assertTrue((output / "decisions.json").is_file())
            heartbeat = json.loads(
                (Path(config["automation_dir"]) / "heartbeat.json").read_text(encoding="utf-8")
            )
            self.assertEqual(heartbeat["last_review_source"], "scheduled")
            self.assertEqual(heartbeat["last_successful_review_at"], (NOW + timedelta(minutes=1)).isoformat())

    def test_enable_status_disable_is_explicit_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            backend = FakeScheduler()

            config_path = enable_automation(config, backend=backend)
            status = get_automation_status(config_path, now=NOW, backend=backend)

            self.assertTrue(config_path.is_file())
            self.assertEqual(len(backend.install_calls), 1)
            self.assertTrue(status["enabled"])
            self.assertTrue(status["registered"])
            self.assertEqual(status["health"], "waiting_for_sessions")

            disable_automation(config_path, backend=backend, now=NOW + timedelta(hours=1))
            disabled = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertFalse(disabled["enabled"])
            self.assertEqual(len(backend.uninstall_calls), 1)

    def test_status_marks_a_missed_scheduler_heartbeat_overdue(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root, enabled_at=NOW - timedelta(days=3))
            backend = FakeScheduler()
            config_path = enable_automation(config, backend=backend)

            status = get_automation_status(config_path, now=NOW, backend=backend)

            self.assertTrue(status["overdue"])
            self.assertEqual(status["health"], "overdue")

    def test_native_scheduler_backends_create_user_level_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            completed = SimpleNamespace(returncode=0, stdout="", stderr="")

            windows_run = Mock(return_value=completed)
            windows = WindowsTaskScheduler(run=windows_run)
            windows.install(config)
            self.assertTrue((Path(config["automation_dir"]) / "run-scheduled-review.cmd").is_file())
            self.assertEqual(windows_run.call_args.args[0][0].casefold(), "schtasks")
            self.assertIn("/Create", windows_run.call_args.args[0])

            launchd_run = Mock(return_value=completed)
            launchd = LaunchdScheduler(home=root / "mac-home", uid=501, run=launchd_run)
            launchd.install(config)
            plist = root / "mac-home" / "Library" / "LaunchAgents" / f"{config['schedule_id']}.plist"
            self.assertTrue(plist.is_file())
            self.assertEqual(launchd_run.call_args.args[0][:2], ["launchctl", "bootstrap"])

            systemd_run = Mock(return_value=completed)
            systemd = SystemdScheduler(home=root / "linux-home", run=systemd_run)
            systemd.install(config)
            unit_root = root / "linux-home" / ".config" / "systemd" / "user"
            self.assertTrue((unit_root / f"{config['schedule_id']}.service").is_file())
            self.assertTrue((unit_root / f"{config['schedule_id']}.timer").is_file())
            commands = [call.args[0] for call in systemd_run.call_args_list]
            self.assertIn(["systemctl", "--user", "daemon-reload"], commands)

            spaced_project = root / "project with spaces"
            spaced_project.mkdir()
            spaced_config = self._config(root / "spaced", project_root=spaced_project)
            systemd.install(spaced_config)
            service = (
                unit_root / f"{spaced_config['schedule_id']}.service"
            ).read_text(encoding="utf-8")
            self.assertIn(f'WorkingDirectory="{spaced_project.resolve()}"', service)


if __name__ == "__main__":
    unittest.main()
