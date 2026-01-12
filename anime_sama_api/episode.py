import logging
import re
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .langs import Lang, LangId, flags, id2lang, lang2ids

logger = logging.getLogger(__name__)


class Players(list[str]):
    def __init__(self, *args: Sequence[Any], **kwargs: dict[Any, Any]):
        ret = super().__init__(*args, **kwargs)
        self.swapPlayers()  # seem to exist on all pages but that could be false, to be sure check script_videos.js

        # Autofix old links
        for index, _ in enumerate(self):
            self[index] = self[index].replace("vidmoly.to", "vidmoly.net")

        return ret

    def swapPlayers(self) -> None:
        if len(self) < 2:
            return
        self[0], self[1] = self[1], self[0]

    def sort_and_filter(
        self, prefer_players: list[str], ban_players: list[str]
    ) -> list[str]:
        def ban_filter(player: str) -> bool:
            player_hostname = urlparse(player).hostname
            if player_hostname is None:
                return False
            return player_hostname in ban_players

        def key(player: str) -> int:
            player_hostname = urlparse(player).hostname
            if player_hostname is None:
                return 0

            try:
                return prefer_players.index(player_hostname) - len(prefer_players)
            except ValueError:
                return 0

        return sorted([player for player in self if not ban_filter(player)], key=key)


class Languages(dict[LangId, Players]):
    def __init__(self, *args: Sequence[Any], **kargs: dict[Any, Any]) -> None:
        super().__init__(*args, **kargs)
        if not self:
            logger.warning("No player available for %s", self)

    @property
    def availables(self) -> dict[Lang, list[Players]]:
        availables: dict[Lang, list[Players]] = {}
        for lang_id, players in self.items():
            if availables.get(id2lang[lang_id]) is None:
                availables[id2lang[lang_id]] = []
            availables[id2lang[lang_id]].append(players)
        return availables

    def consume_player(
        self,
        prefer_languages: list[Lang],
        prefer_players: list[str],
        ban_players: list[str],
    ) -> Generator[str]:
        for prefer_language in prefer_languages:
            for players in self.availables.get(prefer_language, []):
                if players:
                    yield from players.sort_and_filter(
                        prefer_players=prefer_players, ban_players=ban_players
                    )

        for language in lang2ids:
            for players in self.availables.get(language, []):
                if players:
                    logger.warning(
                        "Language preference not respected. Using %s", language
                    )
                    yield from players.sort_and_filter(
                        prefer_players=prefer_players, ban_players=ban_players
                    )


@dataclass(frozen=True)
class Episode:
    languages: Languages
    serie_name: str = ""
    season_name: str = ""
    _name: str = ""
    index: int = 1

    @property
    def name(self) -> str:
        return self._name.strip()

    @property
    def fancy_name(self) -> str:
        return f"{self._name.lstrip()} " + " ".join(
            flags[lang] for lang in self.languages.availables if lang != "VOSTFR"
        )

    @property
    def season_number(self) -> int:
        match_season_number = re.search(r"\d+", self.season_name)
        return int(match_season_number.group(0)) if match_season_number else 0

    @property
    def long_name(self) -> str:
        return f"{self.season_name} - {self.name}"

    @property
    def short_name(self) -> str:
        return f"{self.serie_name} S{self.season_number:02}E{self.index:02}"

    def __str__(self) -> str:
        return self.fancy_name

    def consume_player(
        self,
        prefer_languages: list[Lang],
        prefer_players: list[str] | None = None,
        ban_players: list[str] | None = None,
    ) -> Generator[str]:
        if prefer_players is None:
            prefer_players = []
        if ban_players is None:
            ban_players = []
        yield from self.languages.consume_player(
            prefer_languages, prefer_players, ban_players
        )

    def best(self, prefer_languages: list[Lang]) -> str | None:
        try:
            return next(self.consume_player(prefer_languages))
        except StopIteration:
            return None
