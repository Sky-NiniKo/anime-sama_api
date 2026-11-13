"""CLI using the package's HTML backend and lazy API resolution."""

import asyncio
import logging
from urllib.error import URLError

from httpx import AsyncClient, HTTPError
from rich import get_console
from rich.logging import RichHandler

from anime_sama_api.cli.downloader import download_episodes
from anime_sama_api.cli.utils import install_clean_prompts
from anime_sama_api.link_resolver import LinkError, RateLimitedError
from anime_sama_api.season import EpisodeDataUnavailableError
from anime_sama_api.top_level import AnimeSama, find_site_url

from . import utils as cli_utils
from .config import config

console = get_console()


async def async_main():
    query = cli_utils.safe_input("Anime name: ", str)
    async with AsyncClient(timeout=30, follow_redirects=True) as client:
        url = config.url or await find_site_url(client, config.provider_url)
        if not url:
            raise URLError("Could not find the Anime-Sama domain")
        with console.status("Searching..."):
            catalogues = await AnimeSama(url, client).search(query)
        if not catalogues:
            console.print("No results found.")
            return True
        catalogue = cli_utils.select_one(catalogues)
        with console.status("Loading seasons..."):
            seasons = await catalogue.seasons()
        if not seasons:
            console.print("No seasons found.")
            return True
        selected = cli_utils.select_range(seasons, msg="Choose season(s)")
        if not selected:
            return True
        episodes = []
        for season in selected:
            with console.status("Loading episodes: " + season.name):
                available = await season.episodes()
            if len(selected) == 1:
                console.print(season.series_name + " - " + season.name, markup=False)
                episodes = cli_utils.select_range(
                    available, msg="Choose episode(s)", print_choices=True
                )
            else:
                episodes.extend(available)
        if not episodes:
            return True
        if config.download:
            return await download_episodes(episodes, config, await catalogue.year())


def main():
    install_clean_prompts()
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", handlers=[RichHandler()]
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        return 0 if asyncio.run(async_main()) else 1
    except (KeyboardInterrupt, asyncio.CancelledError, EOFError):
        console.print("Interrupted.", style="red", markup=False)
        return 130
    except RateLimitedError as exc:
        console.print("Server rate limit: " + str(exc), style="red", markup=False)
        return 2
    except (LinkError, EpisodeDataUnavailableError, HTTPError, URLError) as exc:
        console.print("Error: " + str(exc), style="red", markup=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
