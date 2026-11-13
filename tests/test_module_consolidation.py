"""Regression checks for the three-module consolidation."""

import ast
import unittest
from pathlib import Path

from anime_sama_api import episode
from anime_sama_api.cli import downloader, utils


class ConsolidationTests(unittest.TestCase):
    def test_new_locations(self):
        self.assertTrue(callable(episode.iter_resolved_players))
        self.assertTrue(callable(downloader.download_episodes))
        self.assertTrue(callable(utils.install_clean_prompts))

    def test_removed_files(self):
        root = Path(__file__).resolve().parents[1]
        for name in [
            "anime_sama_api/episode_sources.py",
            "anime_sama_api/cli/lazy_downloader.py",
            "anime_sama_api/cli/console_fix.py",
        ]:
            self.assertFalse((root / name).exists(), name)

    def test_sync_urls_not_repeated(self):
        a = episode.Players([])
        a.extend(["https://vo.test/a", "https://vo.test/a"])
        b = episode.Players([])
        b.extend(["https://vo.test/a", "https://vf.test/b"])
        languages = episode.Languages({"vostfr": a, "vf": b})
        self.assertEqual(
            list(languages.consume_player(["VOSTFR"], [], [])),
            ["https://vo.test/a", "https://vf.test/b"],
        )

    def test_source_syntax_and_imports(self):
        root = Path(__file__).resolve().parents[1] / "anime_sama_api"
        removed = {
            "anime_sama_api.episode_sources",
            "anime_sama_api.cli.lazy_downloader",
            "anime_sama_api.cli.console_fix",
        }
        for path in root.rglob("*.py"):
            tree = ast.parse(
                path.read_text(encoding="utf-8-sig"),
                filename=str(path),
                feature_version=(3, 11),
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn(node.module, removed)
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name, removed)


if __name__ == "__main__":
    unittest.main()
