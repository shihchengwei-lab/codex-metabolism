from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_metabolism.decide import decide
from codex_metabolism.lifecycle import LifecycleError, apply_decision
from codex_metabolism.observe import observe
from codex_metabolism.stage import stage_review

from tests.helpers import NOW, make_deploy_home, session_records, write_jsonl, write_skill


class AdoptionLadderTests(unittest.TestCase):
    def test_existing_repo_harness_is_extended_instead_of_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            existing = root / ".codex" / "hooks" / "deploy_guard.py"
            existing.parent.mkdir(parents=True)
            existing.write_text("# preflight guard for deploy production\n", encoding="utf-8")

            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=True,
            )
            decision = next(
                item
                for item in decide(snapshot, now=NOW)
                if item.metadata.get("signature") == "deploy production"
            )

            self.assertEqual(decision.decision, "PATCH")
            self.assertEqual(decision.target_kind, "HARNESS")
            self.assertEqual(Path(decision.metadata["existing_path"]).name, "deploy_guard.py")
            repo_rung = next(rung for rung in decision.adoption_ladder if rung["name"] == "repo")
            self.assertEqual(repo_rung["result"], "reuse")

    def test_unchecked_ecosystem_blocks_create_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=[],
                catalog_checked=False,
            )
            decisions = decide(snapshot, now=NOW)
            decision = next(
                item
                for item in decisions
                if item.metadata.get("signature") == "deploy production"
            )
            staging = stage_review(snapshot, decisions, root / ".codex-metabolism", generated_at=NOW)

            self.assertEqual(decision.decision, "CREATE")
            self.assertEqual(decision.readiness, "needs_research")
            self.assertFalse((staging / "proposed-harness" / decision.id / "guard.py").exists())
            with self.assertRaises(LifecycleError):
                apply_decision(staging, decision.id, project_root=root, skill_root=skills_root)

    def test_matching_external_oss_is_adopted_instead_of_reimplemented(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home, skills_root = make_deploy_home(root)
            catalog = [
                {
                    "kind": "oss",
                    "name": "acme/codex-deploy-preflight-guard",
                    "description": "A Codex hook that requires preflight before deploy commands",
                    "url": "https://github.com/acme/codex-deploy-preflight-guard",
                    "license": "MIT",
                    "updated_at": "2026-07-18T00:00:00Z",
                    "stars": 42,
                }
            ]
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=catalog,
                catalog_checked=True,
            )
            decision = next(
                item
                for item in decide(snapshot, now=NOW)
                if item.metadata.get("signature") == "deploy production"
            )

            self.assertEqual(decision.decision, "PATCH")
            self.assertEqual(decision.target_kind, "TOOL")
            self.assertEqual(decision.mechanism, "adopt_external")
            self.assertEqual(decision.metadata["external_tool"]["license"], "MIT")
            self.assertEqual(decision.metadata["external_tool"]["url"], catalog[0]["url"])
            self.assertFalse(decision.metadata.get("creates_new_tool", True))

    def test_matching_installed_skill_wins_before_external_catalog_for_contextual_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / ".codex"
            skills_root = root / ".agents" / "skills"
            write_skill(
                skills_root,
                "release-workflow",
                description="Guide a contextual release review",
            )
            for index in (1, 2):
                write_jsonl(
                    codex_home / "sessions" / "2026" / "07" / "20" / f"rollout-{index}.jsonl",
                    session_records(
                        f"release-{index}",
                        failed_command="release project",
                        correction="No, use $release-workflow and verify the contextual checklist.",
                        skill_name="release-workflow",
                    ),
                )
            catalog = [
                {
                    "kind": "oss",
                    "name": "acme/release-workflow",
                    "description": "A contextual release workflow review tool",
                    "url": "https://github.com/acme/release-workflow",
                    "license": "MIT",
                    "stars": 100,
                }
            ]
            snapshot = observe(
                codex_home,
                [skills_root],
                days=7,
                now=NOW,
                project_root=root,
                catalog_entries=catalog,
                catalog_checked=True,
            )
            decision = next(
                item
                for item in decide(snapshot, now=NOW)
                if item.metadata.get("signature") == "release project"
            )

            self.assertEqual(decision.target, "release-workflow")
            self.assertEqual(decision.mechanism, "workflow_instruction")
            self.assertNotIn("external_tool", decision.metadata)

    def test_installed_path_tool_wins_before_external_catalog_or_new_harness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            executable = bin_dir / ("preflight.EXE" if os.name == "nt" else "preflight")
            executable.write_text("already installed", encoding="utf-8")
            if os.name != "nt":
                executable.chmod(0o755)
            codex_home, skills_root = make_deploy_home(root)
            catalog = [
                {
                    "kind": "oss",
                    "name": "acme/codex-deploy-preflight-guard",
                    "description": "A Codex hook that requires preflight before deploy commands",
                    "url": "https://github.com/acme/codex-deploy-preflight-guard",
                    "license": "MIT",
                    "stars": 500,
                }
            ]
            environment = {
                "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                "PATHEXT": ".EXE;.CMD;.BAT;.COM",
            }

            with patch.dict(os.environ, environment, clear=False):
                snapshot = observe(
                    codex_home,
                    [skills_root],
                    days=7,
                    now=NOW,
                    project_root=root,
                    catalog_entries=catalog,
                    catalog_checked=True,
                )
                decision = next(
                    item
                    for item in decide(snapshot, now=NOW)
                    if item.metadata.get("signature") == "deploy production"
                )

            self.assertEqual(decision.decision, "PATCH")
            self.assertEqual(decision.target_kind, "TOOL")
            self.assertEqual(decision.mechanism, "configure_installed")
            self.assertEqual(Path(decision.metadata["installed_tool"]["path"]), executable.resolve())
            self.assertNotIn("external_tool", decision.metadata)
            installed_rung = next(
                rung for rung in decision.adoption_ladder if rung["name"] == "installed"
            )
            self.assertEqual(installed_rung["result"], "reuse")


if __name__ == "__main__":
    unittest.main()
