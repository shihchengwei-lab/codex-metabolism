from __future__ import annotations

import re


def safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-")[:80] or "proposal"
