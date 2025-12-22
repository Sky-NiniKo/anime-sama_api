import pytest

from anime_sama_api.top_level import AnimeSama
from .data import catalogue_data

pytest_plugins = ("pytest_asyncio",)
anime_sama = AnimeSama(site_url="https://anime-sama.eu/")


@pytest.mark.asyncio(loop_scope="session")
async def test_search():
    assert catalogue_data.one_piece in await anime_sama.search("one piece")
    assert catalogue_data.mha in await anime_sama.search("mha")
    assert catalogue_data.gumball in await anime_sama.search("gumball")


@pytest.mark.asyncio(loop_scope="session")
async def test_all_catalogues():
    async for catalogue in anime_sama.catalogues_iter():
        if catalogue_data.gumball == catalogue:
            break
    else:
        assert 1 == 0
