from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Callable


GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
SAFE_TERMS = {
    "agent",
    "automation",
    "build",
    "check",
    "ci",
    "cli",
    "codex",
    "command",
    "deploy",
    "deployment",
    "guard",
    "hook",
    "lint",
    "preflight",
    "release",
    "review",
    "skill",
    "test",
    "workflow",
}


def build_oss_query(signature: str, required_command: str | None = None) -> str:
    """Build a small public query without paths, values, prompts, or secrets."""
    combined = f"{signature} {required_command or ''}".lower()
    combined = re.sub(r"(?:sk|ghp|github_pat)-?[a-z0-9_-]+", " ", combined)
    words = re.findall(r"[a-z][a-z0-9-]{2,}", combined)
    selected: list[str] = []
    for word in words:
        if word in SAFE_TERMS and word not in selected:
            selected.append(word)
    for fallback in ("codex", "hook", "workflow"):
        if fallback not in selected:
            selected.append(fallback)
    return " ".join(selected[:6])


def parse_github_search(raw: bytes) -> list[dict[str, Any]]:
    payload = json.loads(raw.decode("utf-8"))
    entries: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        if item.get("archived"):
            continue
        license_obj = item.get("license") or {}
        entries.append(
            {
                "kind": "oss",
                "name": item.get("full_name") or item.get("name") or "unknown",
                "description": item.get("description") or "",
                "url": item.get("html_url") or "",
                "license": license_obj.get("spdx_id") or "UNKNOWN",
                "updated_at": item.get("updated_at"),
                "stars": int(item.get("stargazers_count") or 0),
                "source": "github-rest-search",
            }
        )
    return entries


def search_github(
    query: str,
    *,
    token: str | None = None,
    timeout: float = 10.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {"q": query, "sort": "stars", "order": "desc", "per_page": 5}
    )
    request = urllib.request.Request(
        f"{GITHUB_SEARCH_URL}?{params}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "codex-metabolism/0.1",
        },
    )
    auth = token or os.environ.get("GITHUB_TOKEN")
    if auth:
        request.add_header("Authorization", f"Bearer {auth}")
    with opener(request, timeout=timeout) as response:
        return parse_github_search(response.read())
