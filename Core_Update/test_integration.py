"""Offline integration against the actual package and yt-dlp imports."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from .test_resolver import Response

try:
    import anime_sama_api
except ModuleNotFoundError:
    HAS_PACKAGE = False
else:
    HAS_PACKAGE = True


class SiteClient:
    def __init__(self, api_failure=False, limited=False):
        self.calls = []
        self.api_failure = api_failure
        self.limited = limited

    async def get(self, url, **kw):
        self.calls.append((url, kw))
        if "/api/lien.php" in url:
            if self.limited:
                return Response(status=429, headers={"Retry-After": "60"})
            identifier = kw["params"]["l"]
            if self.api_failure and identifier == "11":
                return Response({"erreur": "absent"})
            return Response({"u": "https://video.test/" + identifier})
        if url.endswith("/vostfr/"):
            return Response(url=url)
        return Response(status=404, url=url)


@unittest.skipUnless(HAS_PACKAGE, "Requires actual anime_sama_api + CLI dependencies")
class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, api_failure=False, download_failure=False, limited=False):
        from .lazy_downloader import download_episodes
        from .season_api import ApiSeason

        client = SiteClient(api_failure, limited)
        episodes = await ApiSeason(
            "https://example.test/saison1/", client=client
        ).episodes()
        self.assertFalse(any("/api/lien.php" in u for u, _ in client.calls))
        attempts = []

        def attempt(url, *args):
            attempts.append(url)
            return not (download_failure and url.endswith("/11"))

        config = SimpleNamespace(
            prefer_languages=["VOSTFR"],
            concurrent_downloads={"video": 1},
            players_config=SimpleNamespace(bans=[]),
        )
        with patch("Core_Update.lazy_downloader.attempt_download", side_effect=attempt):
            result = await download_episodes([episodes[0]], config)
        ids = [kw["params"]["l"] for url, kw in client.calls if "/api/lien.php" in url]
        return result, ids, attempts

    async def test_one_api_on_first_success(self):
        result, ids, attempts = await self.run_case()
        self.assertTrue(result)
        self.assertEqual(ids, ["11"])
        self.assertEqual(len(attempts), 1)

    async def test_api_failure_uses_second(self):
        result, ids, attempts = await self.run_case(api_failure=True)
        self.assertTrue(result)
        self.assertEqual(ids, ["11", "21"])
        self.assertEqual(attempts, ["https://video.test/21"])

    async def test_download_failure_uses_second(self):
        result, ids, attempts = await self.run_case(download_failure=True)
        self.assertTrue(result)
        self.assertEqual(ids, ["11", "21"])
        self.assertEqual(len(attempts), 2)

    async def test_429_is_terminal(self):
        from .resolver import RateLimitedError

        with self.assertRaises(RateLimitedError):
            await self.run_case(limited=True)


if __name__ == "__main__":
    unittest.main()
