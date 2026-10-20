import asyncio
import logging
import re
from collections.abc import AsyncIterator, Generator
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any, cast, get_args
from urllib.parse import urljoin

from httpx import AsyncClient

from .catalogue import Catalogue, Type
from .episode import Episode
from .langs import Lang, flagid2lang, flags
from .season import Season
from .utils import filter_literal, is_Literal

logger = logging.getLogger(__name__)


class _CatalogueCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict[str, Any]] = []
        self._card: dict[str, Any] | None = None
        self._div_depth = 0
        self._title_active = False
        self._title_text = ""
        self._badge_active = False
        self._badge_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()

        if tag == "div" and self._card is None and "as-carte" in classes:
            self._card = {
                "url": attributes.get("data-url") or "",
                "name": attributes.get("data-nom") or "",
                "image_url": attributes.get("data-img") or "",
                "types": [],
                "languages": [],
            }
            self._div_depth = 1
            return

        if self._card is None:
            return

        if tag == "div":
            self._div_depth += 1
        elif tag == "h3":
            self._title_active = True
            self._title_text = ""
        elif tag == "span" and any(name.startswith("as-badge") for name in classes):
            self._badge_active = True
            self._badge_text = ""
        elif tag == "img":
            language_name = (attributes.get("title") or "").strip().casefold()
            language_by_name = {
                language.casefold(): language for language in get_args(Lang)
            }
            language = language_by_name.get(language_name)
            if language is None:
                language = next(
                    (
                        value
                        for flag_id, value in flagid2lang.items()
                        if flag_id.casefold() == language_name
                    ),
                    None,
                )
            if language is not None:
                self._card["languages"].append(language)

    def handle_data(self, data: str) -> None:
        if self._title_active:
            self._title_text += data
        if self._badge_active:
            self._badge_text += data

    def handle_endtag(self, tag: str) -> None:
        if self._card is None:
            return

        if tag == "h3" and self._title_active:
            if self._title_text.strip():
                self._card["name"] = self._title_text.strip()
            self._title_active = False
        elif tag == "span" and self._badge_active:
            badge = self._badge_text.strip()
            if badge:
                self._card["types"].append(badge)
            self._badge_active = False
        elif tag == "div":
            self._div_depth -= 1
            if self._div_depth == 0:
                if self._card["name"] and self._card["url"]:
                    self.cards.append(self._card)
                self._card = None


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
    series_name: str
    types: tuple[Type]
    language: Lang
    episode_name: str
    timestamp: datetime

    def get_real_episodes(self) -> list[Episode]:
        raise NotImplementedError

    @property
    def fancy_name(self) -> str:
        return f"{self.series_name} - {self.episode_name} {flags.get(self.language, '')}"


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
        parser = _CatalogueCardParser()
        parser.feed(html)
        if parser.cards:
            for card in parser.cards:
                url = urljoin(self.site_url, card["url"])

                def not_in_literal(value: Any, url=url) -> None:
                    logger.warning(
                        "Error while parsing '%s'. Please report this with URL: %s",
                        value,
                        url,
                    )

                card_types = cast(
                    set[Type],
                    set(filter_literal(card["types"], Type, not_in_literal)),
                )
                yield Catalogue(
                    url=url,
                    name=card["name"],
                    types=card_types,
                    languages=set(card["languages"]),
                    image_url=card["image_url"],
                    client=self.client,
                )
            return

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

            def not_in_literal(value: Any, url=url) -> None:
                logger.warning(
                    f"Error while parsing '{value}'. \nPlease report this to the developer with URL: {url}"
                )

            types_checked = cast(
                set[Type], set(filter_literal(types, Type, not_in_literal))
            )
            languages = {
                flagid2lang[flag.lower()]
                for flag in flags
                if flag.lower() in flagid2lang
            }

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
                series_name,
                episode_name,
                timestamp,
            ) = match.groups()
            season_url = self.site_url + season_url

            types = types.split(", ") if types else ["Anime"]

            def not_in_literal(value: Any, season_url=season_url) -> None:
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
                series_name=series_name,
                types=types_checked,
                language=language,
                episode_name=episode_name,
                timestamp=datetime.strptime(timestamp, "%d/%m/%Y %H:%M"),
            )

    async def search(self, query: str) -> list[Catalogue]:
        response = (
            await self.client.get(
                f"{self.site_url}catalogue/", params={"search": query}
            )
        ).raise_for_status()

        pages_regex = re.findall(r"page=(\d+)", response.text)

        last_page = max((int(page) for page in pages_regex), default=1)

        responses = [response] + await asyncio.gather(
            *(
                self.client.get(
                    f"{self.site_url}catalogue/",
                    params={"search": query, "page": num},
                )
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
            await self.client.get(
                f"{self.site_url}catalogue/", params={"search": query}
            )
        ).raise_for_status()

        pages_regex = re.findall(r"page=(\d+)", response.text)

        last_page = max((int(page) for page in pages_regex), default=1)

        for catalogue in self._yield_catalogues_from(response.text):
            yield catalogue

        for number in range(2, last_page + 1):
            response = await self.client.get(
                f"{self.site_url}catalogue/",
                params={"search": query, "page": number},
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
