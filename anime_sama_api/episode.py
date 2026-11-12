import logging
import re
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlsplit

from httpx import HTTPError

from .langs import Lang, LangId, flags, id2lang, lang2ids
from .link_resolver import LinkError, RateLimitedError, validate_url

logger = logging.getLogger(__name__)


class Players(list[str]):
    def __init__(self, *args: Sequence[Any], **kwargs: dict[Any, Any]):
        super().__init__(*args, **kwargs)
        self.swapPlayers()
        for index, _ in enumerate(self):
            self[index] = self[index].replace("vidmoly.to", "vidmoly.net")

    def swapPlayers(self) -> None:
        if len(self) < 2:
            return
        self[0], self[1] = (self[1], self[0])

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
    def __init__(self, *args: dict[LangId, Players], **kargs: Players) -> None:
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

    def consume_player(self, prefer_languages, prefer_players, ban_players):
        available = self.availables
        seen_urls = set()
        for language in ordered_languages(prefer_languages, available):
            for players in available.get(language, []):
                for url in players.sort_and_filter(prefer_players, ban_players):
                    if url not in seen_urls:
                        seen_urls.add(url)
                        yield url


@dataclass(frozen=True)
class Episode:
    languages: Languages
    series_name: str = ""
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
        match_season_number = re.search("\\d+", self.season_name)
        return int(match_season_number.group(0)) if match_season_number else 0

    @property
    def long_name(self) -> str:
        return f"{self.season_name} - {self.name}"

    @property
    def short_name(self) -> str:
        return f"{self.series_name} S{self.season_number:02}E{self.index:02}"

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

    async def aconsume_player(self, prefer_languages=None, ban_players=None):
        """Yield resolved URLs on demand, suitable for the current HTML/API backend."""
        async for url in iter_resolved_players(
            self,
            ["VOSTFR"] if prefer_languages is None else prefer_languages,
            ban_players or [],
        ):
            yield url


class DeferredPlayers(Players):
    def __init__(self, references, resolver):
        list.__init__(self, references)
        self.resolver = resolver

    def sort_and_filter(self, prefer_players, ban_players):
        raise RuntimeError(
            "Liens différés : utiliser Episode.aconsume_player() ou la CLI."
        )


def candidates_for(episode, prefer_languages):
    order = ordered_languages(prefer_languages)
    seen = set()
    for language in order:
        for lang_id, players in episode.languages.items():
            if id2lang[lang_id] != language:
                continue
            for ref in players:
                owner = (
                    id(players.resolver)
                    if isinstance(players, DeferredPlayers)
                    else None
                )
                key = (owner, ref)
                if ref and key not in seen:
                    seen.add(key)
                    yield (language, players, ref)


async def resolve_reference(players, reference):
    if isinstance(players, DeferredPlayers):
        return await players.resolver.resolve(reference)
    if reference.startswith("lien:"):
        raise LinkError("Référence sans contexte de résolution")
    return validate_url(reference)


async def iter_resolved_players(
    episode, prefer_languages, ban_players=(), resolve=None
):
    resolver = resolve or resolve_reference
    seen_urls = set()
    bans = set(ban_players)
    for language, players, reference in candidates_for(episode, prefer_languages):
        try:
            url = await resolver(players, reference)
        except RateLimitedError:
            raise
        except (LinkError, HTTPError) as exc:
            logger.warning(
                "%s / %s : résolution échouée (%s), candidat suivant",
                episode.name,
                language,
                type(exc).__name__,
            )
            continue
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        if urlsplit(url).hostname in bans:
            continue
        yield url


def ordered_languages(prefer_languages, available=()):
    """Preserve configured priorities, then append fallback languages once."""
    return list(dict.fromkeys([*prefer_languages, *lang2ids, *available]))
