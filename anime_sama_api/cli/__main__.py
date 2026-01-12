import asyncio
import logging
from urllib.error import URLError

from httpx import AsyncClient
from rich import get_console
from rich.logging import RichHandler
from rich.status import Status

from anime_sama_api.cli import downloader, internal_player
from anime_sama_api.cli.config import config
from anime_sama_api.cli.episode_extra_info import convert_with_extra_info
from anime_sama_api.cli.utils import safe_input, select_one, select_range
from anime_sama_api.top_level import AnimeSama, find_site_url

console = get_console()
console._highlight = False
logging.basicConfig(format="%(message)s", datefmt="[%X]", handlers=[RichHandler()])


def spinner(text: str) -> Status:
    return console.status(text, spinner_style="cyan")


async def async_main() -> None:
    query = safe_input("Anime name: \033[0;34m", str)

    client = AsyncClient()
    url = config.url or await find_site_url(client, config.provider_url)

    if url is None:
        raise URLError("Failed to get AnimeSama url")

    with spinner(f"Searching for [blue]{query}"):
        catalogues = await AnimeSama(url, client).search(query)
    catalogue = select_one(catalogues)

    with spinner(f"Getting season list for [blue]{catalogue.name}"):
        seasons_list = await catalogue.seasons()

    selected_seasons = select_range(seasons_list, msg="Choose season(s)")

    if len(selected_seasons) > 1:
        # Multi-season automatic download
        selected_episodes = []
        for s in selected_seasons:
            with spinner(f"Getting episode list for [blue]{s.name}"):
                episodes = await s.episodes()
                selected_episodes.extend(episodes)
    else:
        # Single season behavior (manual episode selection)
        season = selected_seasons[0]
        with spinner(f"Getting episode list for [blue]{season.name}"):
            episodes = await season.episodes()

        console.print(f"\n[cyan bold underline]{season.serie_name} - {season.name}")
        selected_episodes = select_range(
            episodes, msg="Choose episode(s)", print_choices=True
        )

    if config.download:
        downloader.multi_download(
            [
                convert_with_extra_info(episode, catalogue)
                for episode in selected_episodes
            ],
            config.download_path,
            config.episode_path,
            config.concurrent_downloads,
            config.prefer_languages,
            config.players_config,
            config.max_retry_time,
            config.format,
            config.format_sort,
        )
    else:
        command = internal_player.play_episode(
            selected_episodes[0], config.prefer_languages
        )
        if command is not None:
            command.wait()


def main() -> int:
    try:
        asyncio.run(async_main())
    except (KeyboardInterrupt, asyncio.exceptions.CancelledError, EOFError):
        console.print("\n[red]Exiting...")

    return 0


if __name__ == "__main__":
    main()
