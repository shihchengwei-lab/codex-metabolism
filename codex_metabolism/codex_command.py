from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, Sequence


def build_codex_command(
    arguments: Sequence[str],
    *,
    executable: str = "codex",
    os_name: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    comspec: str | None = None,
) -> list[str]:
    """Build a subprocess-safe Codex CLI command on Windows and POSIX."""

    platform = os.name if os_name is None else os_name
    if platform != "nt":
        return [executable, *arguments]

    resolved = which(executable)
    if resolved is None and executable.casefold() == "codex":
        resolved = which("codex.exe")
    resolved = resolved or executable
    if Path(resolved).suffix.casefold() in {".cmd", ".bat"}:
        command_processor = comspec or os.environ.get("COMSPEC") or "cmd.exe"
        return [command_processor, "/d", "/s", "/c", resolved, *arguments]
    return [resolved, *arguments]
