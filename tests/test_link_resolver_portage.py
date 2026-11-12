import ast
import unittest
from pathlib import Path

from anime_sama_api.link_resolver import (
    LinkError,
    LinkResolver,
    RateLimitedError,
    parse_page,
)

HTML = """<script>var eps1 = ["wrong"];</script>
<script data-source="bdd">var eps1 = ["lien:11", "lien:12", ""];
var eps2 = ["lien:21", "lien:22"];
var eps10 = ["lien:101", "lien:102"];
var epsJeton = "fresh-token"; var epsOrdreFinal = true;</script>
<script>function noms(){resetListe();
finirListe(1);
}</script>"""


class Response:
    def __init__(
        self,
        payload=None,
        status=200,
        text=HTML,
        url="https://example.test/saison1/vostfr/",
        headers=None,
    ):
        self.payload, self.status_code, self.text = payload, status, text
        self.url, self.headers = url, headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP " + str(self.status_code))

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class Client:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class Tests(unittest.IsolatedAsyncioTestCase):
    def resolver(self, responses):
        client = Client(responses)
        resolver = LinkResolver(client, "https://example.test/saison1/vostfr/")
        resolver.data, resolver.min_interval = parse_page(HTML), 0
        return resolver, client

    def test_parse(self):
        data = parse_page(HTML)
        self.assertEqual(data.players[1], ["lien:11", "lien:12", ""])
        self.assertEqual(data.token, "fresh-token")
        self.assertTrue(data.final_order)
        self.assertEqual(sorted(data.players), [1, 2, 10])

    def test_missing_token(self):
        with self.assertRaises(LinkError):
            parse_page(HTML.replace('var epsJeton = "fresh-token";', ""))

    def test_missing_bdd(self):
        with self.assertRaises(LinkError):
            parse_page("<script>var eps1=[];</script>")

    async def test_absent(self):
        resolver, client = self.resolver([Response({"erreur": "absent"})])
        with self.assertRaises(LinkError):
            await resolver.resolve("lien:12")
        self.assertEqual(len(client.calls), 1)

    async def test_bad_url(self):
        resolver, _ = self.resolver([Response({"u": "javascript:bad"})])
        with self.assertRaises(LinkError):
            await resolver.resolve("lien:12")

    async def test_expired(self):
        new_html = HTML.replace("fresh-token", "renewed-token")
        resolver, client = self.resolver(
            [
                Response({"erreur": "expire"}),
                Response(text=new_html),
                Response({"u": "https://video.test/2"}),
            ]
        )
        self.assertEqual(await resolver.resolve("lien:12"), "https://video.test/2")
        self.assertEqual(client.calls[-1][1]["params"]["j"], "renewed-token")

    async def test_resolve_cache(self):
        resolver, client = self.resolver([Response({"u": "https://video.test/2"})])
        await resolver.resolve("lien:12")
        await resolver.resolve("lien:12")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][1]["params"], {"j": "fresh-token", "l": "12"})

    async def test_429_no_retry(self):
        resolver, client = self.resolver(
            [Response(status=429, headers={"Retry-After": "60"})]
        )
        with self.assertRaisesRegex(RateLimitedError, "60"):
            await resolver.resolve("lien:12")
        self.assertEqual(len(client.calls), 1)

    async def test_non_json(self):
        resolver, _ = self.resolver([Response(ValueError("HTML"))])
        with self.assertRaises(LinkError):
            await resolver.resolve("lien:12")

    async def test_direct_url_no_api(self):
        resolver, client = self.resolver([])
        self.assertEqual(
            await resolver.resolve("https://video.test/x"), "https://video.test/x"
        )
        self.assertEqual(client.calls, [])

    def test_listing_contains_no_resolve_call(self):
        tree = ast.parse(
            (
                Path(__file__).resolve().parents[1] / "anime_sama_api" / "season.py"
            ).read_text(encoding="utf-8")
        )
        method = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_all_pages"
        )
        self.assertFalse(
            any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "resolve"
                for n in ast.walk(method)
            )
        )


if __name__ == "__main__":
    unittest.main()
