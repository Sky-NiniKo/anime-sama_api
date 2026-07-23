import asyncio
import logging
import re
from collections.abc import AsyncIterator, Generator
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Any, cast

from httpx import AsyncClient

from .catalogue import Catalogue, Type
from .episode import Episode
from .langs import Lang, flagid2lang, flags
from .season import Season
from .utils import filter_literal, is_Literal

logger = logging.getLogger(__name__)


async def find_site_url(
    client: AsyncClient | None = None, provider_url="https://anime-sama.pw/"
) -> str | None:
    client = client or AsyncClient()

    response = await client.get(provider_url)

    if response.is_error:
        return None

    # * Sometimes need to check for the great word "anime-sama" in lowercase or uppercase but if add re.IGNORECASE it will work
    match = re.search(
        r"href=\"(.+?)\">Accéder à Anime-Sama", response.text, re.IGNORECASE
    )

    # * Ajouter un suive de redirection d'url au match au cas ou le site n'est pas a jour et redirige vers une autre url, puis garder l'url finale

    if match:
        redirected = await client.get(match.group(1), follow_redirects=True)
        return str(redirected.url) + "/"


@dataclass(frozen=True)
class EpisodeRelease:
    page_url: str
    image_url: str
    serie_name: str
    types: tuple[Type]
    language: Lang
    episode_name: str
    timestamp: datetime

    def get_real_episodes(self) -> list[Episode]:
        raise NotImplementedError

    @property
    def fancy_name(self) -> str:
        return f"{self.serie_name} - {self.episode_name} {flags.get(self.language, '')}"


class AnimeSama:
    def __init__(self, site_url: str, client: AsyncClient | None = None) -> None:
        self.site_url = site_url
        self.client = client or AsyncClient()

    async def _get_homepage_section(self, section_name: str, how_many: int = 1) -> str:
        homepage = await self.client.get(self.site_url)

        if homepage.is_error:
            return ""

        sections = homepage.text.split("<!--")
        for index, section in enumerate(sections):
            comment_end_pos = section.find("-->")
            if section_name in section[:comment_end_pos]:
                return "<!--" + "<!--".join(sections[index : index + how_many])

        return ""

    def _yield_catalogues_from(self, html: str) -> Generator[Catalogue]:
        text_without_script = re.sub(r"<script[\W\w]+?</script>", "", html)
        for match in re.finditer(
            rf"href=\"({self.site_url}catalogue/.+)\"[\W\w]+?src=\"(.+?)\"[\W\w]+?<h2.+?>(.*)\n?<[\W\w]+?<p.+?>(.*)\n?<[\W\w]+?<div class=\"genre-tags\">([\W\w]*?)</div[\W\w]+?<p.+?>(.*)\n?<[\W\w]+?<div class=\"lang-flags\">([\W\w]*?)</div",
            text_without_script,
        ):
            (
                url,
                image_url,
                name,
                alternative_names_str,
                genres_str,
                types_str,
                flags_str,
            ) = (unescape(item) for item in match.groups())

            alternative_names = (
                alternative_names_str.split(", ") if alternative_names_str else []
            )

            genres = re.findall(r">(.+?)<", genres_str)
            types = types_str.split(", ") if types_str else []
            flags = re.findall(r"title=\"(.+?)\"", flags_str)

            def not_in_literal(value: Any) -> None:
                logger.warning(
                    f"Error while parsing '{value}'. \nPlease report this to the developer with URL: {url}"
                )

            types_checked = cast(
                set[Type], set(filter_literal(types, Type, not_in_literal))
            )
            languages = set(
                flagid2lang[flag.lower()]
                for flag in flags
                if flag.lower() in flagid2lang
            )

            yield Catalogue(
                url=url,
                name=name,
                alternative_names=alternative_names,
                genres=genres,
                types=types_checked,
                languages=languages,
                image_url=image_url,
                client=self.client,
            )

    def _yield_release_episodes_from(self, html: str) -> Generator[EpisodeRelease]:
        for match in re.finditer(
            r"href=\"/(catalogue\/.+)\"[\W\w]+?src=\"(.+?)\"[\W\w]+?>.*\n?<[\W\w]+?>.*\n?<[\W\w]+?>(.*)\n?<[\W\w]+?>.*\n?<[\W\w]+?\">([\W\w]*?)\n?</[\W\w]+?>(.*)\n?<[\W\w]+?>.*\n?<[\W\w]+?>(.*)\n?<[\W\w]+?>(.*)\n?<",
            html,
        ):
            (
                season_url,
                image_url,
                types,
                language_str,
                serie_name,
                episode_name,
                timestamp,
            ) = match.groups()
            season_url = self.site_url + season_url

            types = types.split(", ") if types else ["Anime"]

            def not_in_literal(value: Any) -> None:
                logger.warning(
                    f"Error while parsing '{value}'. \nPlease report this to the developer with URL: {season_url} (from homepage)"
                )

            types_checked = cast(
                tuple[Type],
                tuple(filter_literal(types, Type, not_in_literal)),
            )

            language = re.findall(r"title=\"(.+?)\"", language_str)[0]
            is_Literal(language, Lang, not_in_literal)

            yield EpisodeRelease(
                page_url=season_url,
                image_url=image_url,
                serie_name=serie_name,
                types=types_checked,
                language=language,
                episode_name=episode_name,
                timestamp=datetime.strptime(timestamp, "%d/%m/%Y %H:%M"),
            )

    async def search(self, query: str) -> list[Catalogue]:
        response = (
            await self.client.get(f"{self.site_url}catalogue/?search={query}")
        ).raise_for_status()

        pages_regex = re.findall(r"page=(\d+)", response.text)

        if not pages_regex:
            last_page = 1
        else:
            last_page = int(pages_regex[-1])

        responses = [response] + await asyncio.gather(
            *(
                self.client.get(f"{self.site_url}catalogue/?search={query}&page={num}")
                for num in range(2, last_page + 1)
            )
        )

        catalogues = []
        for response in responses:
            if response.is_error:
                continue

            catalogues += list(self._yield_catalogues_from(response.text))

        return catalogues

    async def search_iter(self, query: str) -> AsyncIterator[Catalogue]:
        response = (
            await self.client.get(f"{self.site_url}catalogue/?search={query}")
        ).raise_for_status()

        pages_regex = re.findall(r"page=(\d+)", response.text)

        if not pages_regex:
            raise StopAsyncIteration

        last_page = int(pages_regex[-1])

        for catalogue in self._yield_catalogues_from(response.text):
            yield catalogue

        for number in range(2, last_page + 1):
            response = await self.client.get(
                f"{self.site_url}catalogue/?search={query}&page={number}"
            )

            if response.is_error:
                continue

            for catalogue in self._yield_catalogues_from(response.text):
                yield catalogue

    async def catalogues_iter(self) -> AsyncIterator[Catalogue]:
        async for catalogue in self.search_iter(""):
            yield catalogue

    async def all_catalogues(self) -> list[Catalogue]:
        return await self.search("")

    async def planning(self) -> list[list[Season]]:
        # Get from homepage, return value should be change
        raise NotImplementedError

    async def new_episodes(self) -> list[EpisodeRelease]:
        """
        Return the new available episodes on anime-sama using the homepage sorted from oldest to newest.
        """
        section = await self._get_homepage_section("ajouts animes", 4)
        release_episodes = list(self._yield_release_episodes_from(section))
        return release_episodes[::-1]

    """async def new_scans(self) -> list[Scan]:
        raise NotImplementedError"""

    async def new_content(self) -> list[Catalogue]:
        raise NotImplementedError

    async def classics(self) -> list[Catalogue]:
        raise NotImplementedError

    async def highlights(self) -> list[Catalogue]:
        raise NotImplementedError
