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
    assert (
        await catalogue_data.one_piece.advancement()
        == "La Saga 12 (Elbaf) est prévue pour le 5 avril 2026."
    )
    assert await catalogue_data.gumball.advancement() == "Aucune donnée."
    assert await catalogue_data.mha.advancement() == "Aucune donnée."


@pytest.mark.asyncio
async def test_correspondance():
    assert (
        await catalogue_data.one_piece.correspondence()
        == "Episode 1155 -> Chapitre 1125"
    )
    assert await catalogue_data.gumball.correspondence() == "Aucune donnée."
    assert (
        await catalogue_data.mha.correspondence()
        == "Saison 8 Épisode 2 -> Chapitre 403"
    )
