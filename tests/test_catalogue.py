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
    assert await catalogue_data.one_piece.news() == "La suite est prévue pour 2027."
    assert await catalogue_data.gumball.news() == ""
    assert await catalogue_data.mha.news() == ""


@pytest.mark.asyncio
async def test_correspondence():
    assert (
        await catalogue_data.one_piece.correspondence()
        == "Episode 1155 -> Chapitre 1125"
    )
    assert await catalogue_data.gumball.correspondence() == ""
    assert (
        await catalogue_data.mha.correspondence()
        == "Saison 8 Épisode 2 -> Chapitre 403"
    )


@pytest.mark.asyncio
async def test_state():
    assert await catalogue_data.one_piece.state() == "En cours"
    assert await catalogue_data.gumball.state() == ""
    assert await catalogue_data.mha.state() == "Terminé"


@pytest.mark.asyncio
async def test_year():
    assert await catalogue_data.one_piece.year() == 1999
    assert await catalogue_data.gumball.year() == 2011
    assert await catalogue_data.mha.year() == 2016


@pytest.mark.asyncio
async def test_episode_count():
    assert await catalogue_data.one_piece.episode_count() == 1180
    assert await catalogue_data.gumball.episode_count() == 240
    assert await catalogue_data.mha.episode_count() == 170


@pytest.mark.asyncio
async def test_creator():
    assert await catalogue_data.one_piece.creator() == "Eiichirou Oda"
    assert await catalogue_data.gumball.creator() == ""
    assert await catalogue_data.mha.creator() == "Kouhei Horikoshi"


@pytest.mark.asyncio
async def test_studio():
    assert await catalogue_data.one_piece.studio() == "Toei Animation"
    assert await catalogue_data.gumball.studio() == ""
    assert await catalogue_data.mha.studio() == "bones"


@pytest.mark.asyncio
async def test_synopsis():
    assert (
        await catalogue_data.one_piece.synopsis()
        == """Il fut un temps où Gold Roger était le plus grand de tous les pirates, le "Roi des Pirates" était son surnom. A sa mort, son trésor d'une valeur inestimable connu sous le nom de "One Piece" fut caché quelque part sur "Grand Line". De nombreux pirates sont partis à la recherche de ce trésor mais tous sont morts avant même de l'atteindre. Monkey D. Luffy rêve de retrouver ce trésor légendaire et de devenir le nouveau "Roi des Pirates". Après avoir mangé un fruit du démon, il possède un pouvoir lui permettant de réaliser son rêve. Il lui faut maintenant trouver un équipage pour partir à l'aventure !"""
    )
    assert (
        await catalogue_data.gumball.synopsis()
        == """Le quotidien de Gumball, un chaton bleu âgé 12 ans, ainsi que son compagnon Darwin, un poisson rouge domestique, devenu son frère adoptif après que des bras et des jambes lui aient poussé. Gumball et sa famille vivent à Elmore, une ville imaginaire, semblant appartenir au monde réel, mais qui est habitée par toutes sortes de créatures animées."""
    )
    assert (
        await catalogue_data.mha.synopsis()
        == """Dans un futur proche suite à une mutation génétique, 80% de la population mondiale possède des super pouvoirs appelés "Alters". Les super-héros protègent la population mondiale face aux super-vilains qui utilisent leur Alter à des fins maléfiques. Le plus célèbre des super-héro se nomme All Might. Izuku Midoriya en est fan, et rêve d'intégrer la filière super-héroïque du lycée Yuei pour suivre les traces de son idole ainsi devenir le plus grand des super-héros. Malheureusement, Izuku ne possède pas de pouvoir."""
    )
