"""Offline season tests for the HTML/API contract."""

import json

import httpx
import pytest

from anime_sama_api.season import EpisodeDataUnavailableError, Season

pytest_plugins = ("pytest_asyncio",)


def make_html(players, final_order=True):
    declarations = [
        f"var eps{n} = {json.dumps(values)};"
        for n, values in enumerate(players, start=1)
    ]
    declarations.append('var epsJeton = "fixture-token";')
    if final_order:
        declarations.append("var epsOrdreFinal = true;")
    return (
        '<script data-source="bdd">'
        + "".join(declarations)
        + "</script>"
        + "<script>resetListe();\n\tfinirListe(1);\n}</script>"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "series_name",
    ["one-piece", "le-monde-incroyable-de-gumball", "my-hero-academia"],
)
async def test_episodes(series_name):
    sources = {
        "vf": [["lien:301", "lien:302"]],
        "vostfr": [["lien:101", "lien:102"], ["lien:201", ""]],
    }
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/lien.php":
            pytest.fail("Episode listing must not resolve API links")
        language = request.url.path.rstrip("/").rsplit("/", 1)[-1]
        if language in sources:
            return httpx.Response(200, text=make_html(sources[language]))
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        season = Season(
            f"https://example.test/catalogue/{series_name}/saison1/",
            name="saison1",
            series_name=series_name,
            client=client,
        )
        episodes = await season.episodes()
        assert len(episodes) == 2
        assert [e.name for e in episodes] == ["Episode 1", "Episode 2"]
        assert [e.index for e in episodes] == [1, 2]
        assert [e.series_name for e in episodes] == [series_name, series_name]
        assert [e.season_name for e in episodes] == ["saison1", "saison1"]
        assert [set(e.languages) for e in episodes] == [
            {"vf", "vostfr"},
            {"vf", "vostfr"},
        ]
        assert list(episodes[0].languages["vostfr"]) == ["lien:101", "lien:201"]
        assert list(episodes[1].languages["vostfr"]) == ["lien:102"]
        assert list(episodes[0].languages["vf"]) == ["lien:301"]
        assert list(episodes[1].languages["vf"]) == ["lien:302"]
        for episode in episodes:
            for players in episode.languages.values():
                assert players.resolver.client is client
                assert players.resolver.data.token == "fixture-token"
                assert players.resolver.cache == {}

    assert requests
    assert all(r.url.host == "example.test" for r in requests)
    assert not any(
        "episodes.js" in r.url.path or r.url.path == "/api/lien.php" for r in requests
    )


@pytest.mark.asyncio
async def test_episodes_with_inline_player_data():
    primary = ["https://video.test/primary-1", "https://video.test/primary-2"]
    secondary = ["https://video.test/secondary-1", "https://video.test/secondary-2"]
    html = make_html([secondary, primary], final_order=False)
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/vostfr/"):
            return httpx.Response(200, text=html)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        episodes = await Season(
            "https://example.test/catalogue/test/saison1/", client=client
        ).episodes()
    assert [e.name for e in episodes] == ["Episode 1", "Episode 2"]
    assert [list(e.languages["vostfr"]) for e in episodes] == [
        [primary[0], secondary[0]],
        [primary[1], secondary[1]],
    ]
    assert not any(r.url.path == "/api/lien.php" for r in requests)


@pytest.mark.asyncio
async def test_episodes_without_pages_raise_clear_error():
    class EmptySeason(Season):
        async def get_all_pages(self):
            return []

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(404))
    ) as client:
        with pytest.raises(
            EpisodeDataUnavailableError, match="Could not retrieve episode data"
        ):
            await EmptySeason(
                "https://example.test/catalogue/test/saison1/", client=client
            ).episodes()
