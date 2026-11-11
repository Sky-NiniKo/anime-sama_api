import httpx
import pytest

from anime_sama_api.season import EpisodeDataUnavailableError, Season

from .data import episode_data, season_data

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_episodes():
    assert episode_data.one_piece_season1 == await season_data.one_piece[0].episodes()
    assert episode_data.gumball_season1 == await season_data.gumball[0].episodes()
    assert episode_data.mha_season1 == await season_data.mha[0].episodes()


@pytest.mark.asyncio
async def test_episodes_with_inline_player_data():
    expected_episodes = episode_data.one_piece_season1[:2]
    first_player_links = [
        episode.languages["vostfr"][1] for episode in expected_episodes
    ]
    second_player_links = [
        episode.languages["vostfr"][0] for episode in expected_episodes
    ]
    html = (
        '<script data-source="bdd">'
        f'var eps1 = ["{first_player_links[0]}", "{first_player_links[1]}"];'
        f'var eps2 = ["{second_player_links[0]}", "{second_player_links[1]}"];'
        "</script>"
        "<script>resetListe();\n\tfinirListe(1);\n}</script>"
    )

    def handler(request):
        if request.url.path.endswith("/vostfr/"):
            return httpx.Response(200, text=html)
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        season = Season(season_data.one_piece[0].url, client=client)
        episodes = await season.episodes()

    assert [episode.name for episode in episodes] == [
        episode.name for episode in expected_episodes
    ]
    assert [list(episode.languages["vostfr"]) for episode in episodes] == [
        list(episode.languages["vostfr"]) for episode in expected_episodes
    ]


@pytest.mark.asyncio
async def test_episodes_without_pages_raise_clear_error():
    class EmptySeason(Season):
        async def get_all_pages(self):
            return []

    with pytest.raises(
        EpisodeDataUnavailableError, match="Could not retrieve episode data"
    ):
        await EmptySeason(season_data.one_piece[0].url).episodes()
