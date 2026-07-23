from pathlib import Path

from anime_sama_api.cli.downloader import download, multi_download
from anime_sama_api.episode import Episode, Languages, Players


def test_multi_download():
    multi_download([Episode({})], Path())


def test_download():
    download(
        Episode(
            Languages(
                vf=Players(),
                vostfr=Players(
                    [
                        "https://s22.anime-sama.to/s2/",
                    ]
                ),
            ),
        ),
        Path(),
        prefer_languages=["VF", "VOSTFR"],
    )
