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
    TextColumn,
    TimeRemainingColumn,
    TotalFileSizeColumn,
    TransferSpeedColumn,
)
from rich.table import Column
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from anime_sama_api.cli.config import PlayersConfig, config
from anime_sama_api.cli.error_handling import YDL_log_filter, reaction_to
from anime_sama_api.episode import Episode
from anime_sama_api.langs import Lang

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
    episode: Episode,
    path: Path,
    episode_path: str = "{episode}",
    prefer_languages: list[Lang] | None = None,
    players_config: PlayersConfig | None = None,
    concurrent_fragment_downloads: int = 3,
    max_retry_time: int = 1024,
    video_format: str = "",
    format_sort: str = "",
    ep_year: int | None = None,
    *,
    _total_task_id=None,
) -> bool:
    if prefer_languages is None:
        prefer_languages = ["VOSTFR"]
    if players_config is None:
        players_config = PlayersConfig([], [])
    if not any(episode.languages.values()):
        logger.error("No player available")
        return False
    me = download_progress.add_task(
        "download", episode_name=episode.name, site="", total=None
    )
    task = next(t for t in download_progress.tasks if t.id == me)
    try:
        full_path = (
            path
            / episode_path.format(
                series=episode.series_name,
                season=episode.season_name,
                episode=episode.name,
                release_year_parentheses="" if ep_year is None else f" {ep_year}",
            )
        ).expanduser()

        def hook(data: dict) -> None:
            if data.get("status") != "downloading":
                return
            task.total = data.get("total_bytes") or data.get("total_bytes_estimate")
            download_progress.update(me, completed=data.get("downloaded_bytes", 0))

        option = {
            "outtmpl": f"{full_path}.%(ext)s",
            "concurrent_fragment_downloads": concurrent_fragment_downloads,
            "progress_hooks": [hook],
            "logger": logger,
            "format": video_format,
            "format_sort": format_sort.split(","),
            "continuedl": False,
        }
        success = False
        for player in episode.consume_player(
            prefer_languages, players_config.prefers, players_config.bans
        ):
            download_progress.reset(
                me,
                total=0,
                completed=0,
                episode_name=episode.name,
                site=urlparse(player).hostname,
            )
            retry_time = 1
            success = False
            download_progress.update(me, site=urlparse(player).hostname)
            while True:
                try:
                    with YoutubeDL(option) as ydl:
                        error_code = cast(int, ydl.download([player]))
                        if not error_code:
                            success = True
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
                                episode.name,
                                exception.msg,
                                retry_time,
                            )
                            time.sleep(retry_time * random.uniform(0.8, 1.2))
                            retry_time *= 2
                        case "crash":
                            raise
                        case "":
                            logger.fatal(
                                "The above error wasn't handle. Please report it to the developer with URL: %s",
                                player,
                            )
                            break
            if success:
                break
        return success
    finally:
        download_progress.update(me, visible=False)
        if _total_task_id is not None:
            total_progress.update(_total_task_id, advance=1)


def multi_download(
    episodes,
    path,
    episode_path="{episode}",
    concurrent_downloads=None,
    prefer_languages=None,
    players_config=None,
    max_retry_time=1024,
    video_format="",
    format_sort="",
    eps_years=None,
) -> list[bool]:
    if not episodes:
        return []
    concurrent_downloads = concurrent_downloads or {}
    if prefer_languages is None:
        prefer_languages = ["VOSTFR"]
    if players_config is None:
        players_config = PlayersConfig([], [])
    years = list(eps_years or [])
    years += [None] * max(0, len(episodes) - len(years))
    batch = total_progress.add_task("Épisodes traités", total=len(episodes))
    with (
        Live(progress, console=console),
        ThreadPoolExecutor(
            max_workers=max(1, concurrent_downloads.get("video", 1))
        ) as executor,
    ):
        futures = [
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
                ep_year=year,
                _total_task_id=batch,
            )
            for episode, year in zip(episodes, years)
        ]
        # Propagate worker exceptions and preserve episode ordering.
        return [future.result() for future in futures]
