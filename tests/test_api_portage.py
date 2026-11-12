"""Offline tests of the ported production path (no real API or download)."""

import ast
import unittest
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from anime_sama_api.cli import downloader
from anime_sama_api.cli.lazy_downloader import download_episodes
from anime_sama_api.episode import Episode, Languages
from anime_sama_api.episode_sources import DeferredPlayers
from anime_sama_api.link_resolver import LinkResolver, RateLimitedError, parse_page
from anime_sama_api.season import Season

HTML = '<script data-source="bdd">var eps1=["lien:11","lien:12"]; var eps2=["lien:21","lien:22"]; var epsJeton="token"; var epsOrdreFinal=true;</script>'


class Response:
    def __init__(
        self, payload=None, status=200, url="https://example.test/saison1/vostfr/"
    ):
        self.payload = payload
        self.status_code = status
        self.url = url
        self.text = HTML
        self.headers = {"Retry-After": "60"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP " + str(self.status_code))

    def json(self):
        return self.payload


class Client:
    def __init__(self, api_failure=False, limited=False):
        self.calls = []
        self.api_failure = api_failure
        self.limited = limited

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "/api/lien.php" not in url:
            return Response(status=200 if url.endswith("/vostfr/") else 404, url=url)
        identifier = kwargs["params"]["l"]
        if self.limited:
            return Response(status=429)
        if self.api_failure and identifier == "11":
            return Response({"erreur": "absent"})
        return Response({"u": "https://video.test/" + identifier})


class PortTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(
        self, api_failure=False, download_failure=False, limited=False, all_fail=False
    ):
        client = Client(api_failure, limited)
        resolver = LinkResolver(client, "https://example.test/saison1/vostfr/")
        resolver.data = parse_page(HTML)
        episode = Episode(
            Languages({"vostfr": DeferredPlayers(["lien:11", "lien:21"], resolver)}),
            series_name="Test",
            season_name="Saison 1",
            _name="Episode 1",
        )
        attempts = []
        options_seen = []

        class FakeYDL:
            def __init__(self, options):
                self.options = options
                options_seen.append(options)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def download(self, urls):
                attempts.extend(urls)
                if all_fail or (download_failure and urls[0].endswith("/11")):
                    raise downloader.DownloadError("simulated failure")
                for hook in self.options["progress_hooks"]:
                    hook(
                        {
                            "status": "downloading",
                            "downloaded_bytes": 10,
                            "total_bytes": 20,
                        }
                    )
                return 0

        with TemporaryDirectory() as folder:
            config = SimpleNamespace(
                download_path=Path(folder),
                episode_path="{series}/{episode}{release_year_parentheses}",
                prefer_languages=["VOSTFR"],
                concurrent_downloads={"video": 1, "fragment": 1},
                players_config=SimpleNamespace(prefers=[], bans=[]),
                max_retry_time=1,
                format="",
                format_sort="",
            )
            original = downloader.download
            with (
                patch.object(downloader, "YoutubeDL", FakeYDL),
                patch.object(downloader, "Live", lambda *a, **k: nullcontext()),
                patch.object(downloader, "reaction_to", lambda message: "continue"),
            ):
                result = await download_episodes([episode], config, 2026)
            self.assertIs(downloader.download, original)
        ids = [kw["params"]["l"] for url, kw in client.calls if "/api/lien.php" in url]
        return result, ids, attempts, options_seen

    async def test_first_success_resolves_only_one(self):
        result, ids, attempts, options = await self.run_case()
        self.assertTrue(result)
        self.assertEqual(ids, ["11"])
        self.assertEqual(len(attempts), 1)
        self.assertIn("2026", options[0]["outtmpl"])

    async def test_api_failure_moves_to_next(self):
        result, ids, attempts, _ = await self.run_case(api_failure=True)
        self.assertTrue(result)
        self.assertEqual(ids, ["11", "21"])
        self.assertEqual(attempts, ["https://video.test/21"])

    async def test_download_failure_moves_to_next(self):
        result, ids, attempts, _ = await self.run_case(download_failure=True)
        self.assertTrue(result)
        self.assertEqual(ids, ["11", "21"])
        self.assertEqual(len(attempts), 2)

    async def test_all_fail_returns_false(self):
        result, ids, _, _ = await self.run_case(all_fail=True)
        self.assertFalse(result)
        self.assertEqual(ids, ["11", "21"])

    async def test_429_is_propagated(self):
        with self.assertRaises(RateLimitedError):
            await self.run_case(limited=True)

    async def test_listing_does_not_resolve(self):
        client = Client()
        pages = await Season(
            "https://example.test/saison1/", client=client
        ).get_all_pages()
        self.assertTrue(pages)
        self.assertFalse(any("/api/lien.php" in url for url, _ in client.calls))

    async def test_public_async_api_is_lazy(self):
        client = Client()
        resolver = LinkResolver(client, "https://example.test/vostfr/")
        resolver.data = parse_page(HTML)
        episode = Episode(
            Languages({"vostfr": DeferredPlayers(["lien:11", "lien:21"], resolver)})
        )
        stream = episode.aconsume_player(["VOSTFR"])
        self.assertEqual(await anext(stream), "https://video.test/11")
        await stream.aclose()
        self.assertEqual(len(client.calls), 1)

    def test_production_has_no_core_update_imports(self):
        base = Path(__file__).resolve().parents[1] / "anime_sama_api"
        for path in base.rglob("*.py"):
            tree = ast.parse(
                path.read_text(encoding="utf-8-sig"), feature_version=(3, 11)
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(
                        (node.module or "").startswith("Core_Update"), str(path)
                    )
                if isinstance(node, ast.Import):
                    self.assertFalse(
                        any(a.name.startswith("Core_Update") for a in node.names),
                        str(path),
                    )


if __name__ == "__main__":
    unittest.main()
