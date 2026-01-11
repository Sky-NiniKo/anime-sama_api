from pathlib import Path
from anime_sama_api.cli.downloader import multi_download, download
from anime_sama_api.cli.episode_extra_info import convert_with_extra_info
from anime_sama_api.episode import Episode, Languages, Players


def test_multi_download():
    multi_download([Episode({})], Path())


def test_download():
    download(
        convert_with_extra_info(
            Episode(
                Languages(
                    vf=Players(),
                    vostfr=Players(
                        [
                            "https://s22.anime-sama.si/s2/",
                        ]
                    ),
                ),
            )
        ),
        Path(),
        prefer_languages=["VF", "VOSTFR"],
    )
