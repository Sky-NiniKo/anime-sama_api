import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from rich import get_console
from rich.console import Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TotalFileSizeColumn,
    TransferSpeedColumn,
)
from rich.table import Column
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from anime_sama_api.langs import Lang
from anime_sama_api.cli.config import PlayersConfig, config
from anime_sama_api.cli.episode_extra_info import EpisodeWithExtraInfo
from anime_sama_api.cli.error_handeling import YDL_log_filter, reaction_to

logger = logging.getLogger(__name__)
logger.addFilter(YDL_log_filter)

console = get_console()
download_progress_list: list[str | ProgressColumn] = [
    "[bold blue]{task.fields[episode_name]}",
    BarColumn(bar_width=None),
    "[progress.percentage]{task.percentage:>3.1f}%",  # TODO: should disappear if the console is not wide enough
    TransferSpeedColumn(),
    TotalFileSizeColumn(),
    TimeRemainingColumn(compact=True, elapsed_when_finished=True),
]
if config.show_players:
    download_progress_list.insert(
        1,
        TextColumn(
            "[green]{task.fields[site]}",
            table_column=Column(max_width=12),
            justify="right",
        ),
    )

download_progress = Progress(*download_progress_list, console=console)

total_progress = Progress(
    TextColumn("[bold cyan]{task.description}"),
    BarColumn(bar_width=None),
    MofNCompleteColumn(),
    TimeRemainingColumn(elapsed_when_finished=True),
    console=console,
)
progress = Group(total_progress, download_progress)


def download(
    episode: EpisodeWithExtraInfo,
    path: Path,
    episode_path: str = "{episode}",
    prefer_languages: list[Lang] | None = None,
    players_config: PlayersConfig | None = None,
    concurrent_fragment_downloads: int = 3,
    max_retry_time: int = 1024,
    video_format: str = "",
    format_sort: str = "",
) -> None:
    if prefer_languages is None:
        prefer_languages = ["VOSTFR"]
    if players_config is None:
        players_config = PlayersConfig([], [])

    if not any(episode.warpped.languages.values()):
        logger.error("No player available")
        return

    me = download_progress.add_task(
        "download", episode_name=episode.warpped.name, site="", total=None
    )
    task = next(t for t in download_progress.tasks if t.id == me)

    full_path = (
        path
        / episode_path.format(
            serie=episode.warpped.serie_name,
            season=episode.warpped.season_name,
            episode=episode.warpped.name,
            release_year_parentheses=episode.release_year_parentheses(),
        )
    ).expanduser()

    def hook(data: dict) -> None:
        if data.get("status") != "downloading":
            return

        # Directly accessing .total is needed to not reset the speed
        task.total = data.get("total_bytes") or data.get("total_bytes_estimate")
        download_progress.update(me, completed=data.get("downloaded_bytes", 0))

    option = {
        "outtmpl": f"{full_path}.%(ext)s",
        "concurrent_fragment_downloads": concurrent_fragment_downloads,
        "progress_hooks": [hook],
        "logger": logger,
        "format": video_format,
        "format_sort": format_sort.split(","),
    }

    for player in episode.warpped.consume_player(
        prefer_languages, players_config.prefers, players_config.bans
    ):
        retry_time = 1
        sucess = False
        download_progress.update(me, site=urlparse(player).hostname)

        while True:
            try:
                with YoutubeDL(option) as ydl:  # type: ignore
                    error_code = cast(int, ydl.download([player]))

                    if not error_code:
                        sucess = True
                    else:
                        logger.fatal(
                            "The download encountered an error code %s. Please report this to the developer with URL: %s",
                            error_code,
                            player,
                        )

                    break

            except DownloadError as exception:
                match reaction_to(exception.msg):
                    case "continue":
                        break

                    case "retry":
                        if retry_time >= max_retry_time:
                            break

                        logger.warning(
                            "%s interrupted (%s). Retrying in %ss.",
                            episode.warpped.name,
                            exception.msg,
                            retry_time,
                        )
                        # random is used to spread the resume time and so mitigate deadlock when multiple downloads resume at the same time
                        time.sleep(retry_time * random.uniform(0.8, 1.2))
                        retry_time *= 2

                    case "crash":
                        raise exception

                    case "":
                        logger.fatal(
                            "The above error wasn't handle. Please report it to the developer with URL: %s",
                            player,
                        )
                        break

        if sucess:
            break

    download_progress.update(me, visible=False)
    if total_progress.tasks:
        total_progress.update(TaskID(0), advance=1)


def multi_download(
    episodes: list[EpisodeWithExtraInfo],
    path: Path,
    episode_path: str = "{episode}",
    concurrent_downloads: dict[str, int] | None = None,
    prefer_languages: list[Lang] | None = None,
    players_config: PlayersConfig | None = None,
    max_retry_time: int = 1024,
    video_format: str = "",
    format_sort: str = "",
) -> None:
    if concurrent_downloads is None:
        concurrent_downloads = {}
    if prefer_languages is None:
        prefer_languages = ["VOSTFR"]
    if players_config is None:
        players_config = PlayersConfig([], [])

    """
    Not sure if you can use this function multiple times
    """
    total_progress.add_task("Downloaded", total=len(episodes))
    with Live(progress, console=console):
        with ThreadPoolExecutor(
            max_workers=concurrent_downloads.get("video", 1)
        ) as executor:
            for episode in episodes:
                executor.submit(
                    download,
                    episode,
                    path,
                    episode_path,
                    prefer_languages,
                    players_config,
                    concurrent_downloads.get("fragment", 1),
                    max_retry_time,
                    video_format,
                    format_sort,
                )
