"""CLI isolated in Core_Update. No modification of the installed package."""

import asyncio
import logging
from urllib.error import URLError

from httpx import AsyncClient, HTTPError
from rich import get_console
from rich.logging import RichHandler

from anime_sama_api.cli.config import config
from anime_sama_api.cli.utils import safe_input, select_one, select_range
from anime_sama_api.season import EpisodeDataUnavailableError
from anime_sama_api.top_level import AnimeSama, find_site_url

from .console_fix import install_clean_prompts
from .resolver import LinkError, RateLimitedError
from .season_api import ApiSeason

console = get_console()


def as_api_season(season):
    return ApiSeason(
        season.url,
        name=season.name,
        series_name=season.series_name,
        client=season.client,
    )


async def async_main():
    query = safe_input("Anime name: ", str)
    async with AsyncClient(timeout=30, follow_redirects=True) as client:
        url = config.url or await find_site_url(client, config.provider_url)
        if not url:
            raise URLError("Impossible de trouver le domaine Anime-Sama")
        with console.status("Recherche..."):
            catalogues = await AnimeSama(url, client).search(query)
        if not catalogues:
            console.print("Aucun résultat.")
            return
        catalogue = select_one(catalogues)
        with console.status("Chargement des saisons..."):
            seasons = [as_api_season(s) for s in await catalogue.seasons()]
        if not seasons:
            console.print("Aucune saison.")
            return
        selected_seasons = select_range(seasons, msg="Choose season(s)")
        if not selected_seasons:
            return
        selected_episodes = []
        for season in selected_seasons:
            with console.status("Lecture des métadonnées : " + season.name):
                episodes = await season.episodes()
            if len(selected_seasons) == 1:
                console.print(season.series_name + " - " + season.name)
                selected_episodes = select_range(
                    episodes, msg="Choose episode(s)", print_choices=True
                )
            else:
                # Preserve original CLI multi-season semantics: all episodes.
                selected_episodes.extend(episodes)
        if not selected_episodes:
            return
        if not config.download:
            raise LinkError(
                "Ce lanceur lazy cible le téléchargement : activer download dans la configuration."
            )
        from .lazy_downloader import download_episodes

        year = await catalogue.year()
        return await download_episodes(selected_episodes, config, year)


def main():
    install_clean_prompts()

    logging.basicConfig(
        level=logging.INFO, format="%(message)s", handlers=[RichHandler()]
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        outcome = asyncio.run(async_main())
        if outcome is False:
            return 1
    except (KeyboardInterrupt, asyncio.CancelledError, EOFError):
        console.print("Arrêt demandé.")
        return 130
    except RateLimitedError as exc:
        console.print("Limitation serveur : " + str(exc), markup=False)
        console.print(
            "Aucune nouvelle tentative automatique. Respecte le délai serveur avant de relancer."
        )
        return 2
    except (LinkError, EpisodeDataUnavailableError, HTTPError, URLError) as exc:
        console.print("Erreur : " + str(exc), markup=False)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
