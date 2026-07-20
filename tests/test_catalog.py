from __future__ import annotations

import json
import unittest

from codex_metabolism.catalog import build_oss_query, parse_github_search


class CatalogTests(unittest.TestCase):
    def test_query_is_bounded_and_does_not_send_paths_or_secret_like_values(self) -> None:
        query = build_oss_query(
            signature=r"C:\private\client-x\deploy production --token sk-secret-value",
            required_command="preflight",
        )

        self.assertLessEqual(len(query.split()), 6)
        self.assertIn("deploy", query)
        self.assertIn("preflight", query)
        self.assertNotIn("client-x", query)
        self.assertNotIn("secret", query)
        self.assertNotIn("C:", query)

    def test_github_results_keep_provenance_license_and_freshness(self) -> None:
        payload = {
            "items": [
                {
                    "full_name": "acme/preflight-guard",
                    "html_url": "https://github.com/acme/preflight-guard",
                    "description": "Guard deploy commands with a preflight check",
                    "stargazers_count": 12,
                    "updated_at": "2026-07-18T00:00:00Z",
                    "license": {"spdx_id": "MIT"},
                    "archived": False,
                }
            ]
        }

        entries = parse_github_search(json.dumps(payload).encode("utf-8"))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["kind"], "oss")
        self.assertEqual(entries[0]["license"], "MIT")
        self.assertEqual(entries[0]["stars"], 12)
        self.assertEqual(entries[0]["updated_at"], "2026-07-18T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
