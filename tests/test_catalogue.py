import pytest

from .data import catalogue_data, season_data

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_seasons():
    assert season_data.one_piece == await catalogue_data.one_piece.seasons()
    assert season_data.mha == await catalogue_data.mha.seasons()
    assert season_data.gumball == await catalogue_data.gumball.seasons()


@pytest.mark.asyncio
async def test_avancement():
    assert await catalogue_data.one_piece.news() == ""
    assert await catalogue_data.gumball.news() == ""
    assert await catalogue_data.mha.news() == ""


@pytest.mark.asyncio
async def test_correspondance():
    assert (
        await catalogue_data.one_piece.correspondence()
        == "Episode 1155 -> Chapitre 1125"
    )
    assert await catalogue_data.gumball.correspondence() == ""
    assert (
        await catalogue_data.mha.correspondence()
        == "Saison 8 Épisode 2 -> Chapitre 403"
    )
