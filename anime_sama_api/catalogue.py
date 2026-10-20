import logging
import re
from collections.abc import Sequence
from datetime import date
from html import unescape
from typing import Literal, get_args

from httpx import AsyncClient

from .langs import Lang, flags
from .season import Season
from .utils import remove_some_js_comments

Type = Literal["Anime", "Film", "Scans", "Webtoon", "Autres"]
State = Literal["À venir", "En cours", "Terminé", "Annulé", "En pause"]

logger = logging.getLogger(__name__)


class Catalogue:
    def __init__(
        self,
        url: str,
        name: str = "",
        alternative_names: Sequence[str] | None = None,
        genres: Sequence[str] | None = None,
        types: set[Type] | None = None,
        languages: set[Lang] | None = None,
        image_url: str = "",
        client: AsyncClient | None = None,
    ) -> None:
        if alternative_names is None:
            alternative_names = []
        if genres is None:
            genres = []
        if types is None:
            types = set()
        if languages is None:
            languages = set()

        self.url = url + "/" if url[-1] != "/" else url
        self.site_url = "/".join(url.split("/")[:3]) + "/"
        self.client = client or AsyncClient()

        self.name = name or url.split("/")[-2]

        self._page: str | None = None
        self.alternative_names = alternative_names
        self.genres = genres
        self.types = types
        self.languages = languages
        self.image_url = image_url

    async def page(self) -> str:
        if self._page is not None:
            return self._page

        response = await self.client.get(self.url)

        if response.is_error:
            self._page = ""
        else:
            self._page = response.text

        return self._page

    async def seasons(self) -> list[Season]:
        page_without_comments = remove_some_js_comments(string=await self.page())

        seasons = re.findall(
            r'panneauAnime\("(.+?)", *"(.+?)(?:vostfr|vf)"\);', page_without_comments
        )

        seasons = [
            Season(
                url=self.url + link,
                name=name,
                series_name=self.name,
                client=self.client,
            )
            for name, link in seasons
        ]

        return seasons

    async def _info_values(self) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}
        page = await self.page()
        info_blocks = re.findall(
            r"""<dl\b[^>]*class=["'][^"']*\boe-infos\b[^"']*["'][^>]*>(.*?)</dl\s*>""",
            page,
            re.IGNORECASE | re.DOTALL,
        )
        for block in info_blocks:
            for label, value in re.findall(
                r"<dt\b[^>]*>(.*?)</dt\s*>\s*<dd\b[^>]*>(.*?)</dd\s*>",
                block,
                re.IGNORECASE | re.DOTALL,
            ):
                clean_label = self._clean_html(label).casefold()
                values.setdefault(clean_label, []).append(self._clean_html(value))
        return values

    # TODO: move to utils
    @staticmethod
    def _clean_html(value: str) -> str:
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", value))).strip()

    async def news(self) -> str:
        search = re.findall(r"Actualité.+?>(.+?)<", await self.page())

        if not search:
            return ""

        return search[0].lstrip()

    async def state(self) -> str:
        info = await self._info_values()
        states = info.get("statut", [])
        if states:
            if states[0] in get_args(State):
                return states[0]
            logger.warning(
                f"Error while parsing '{states[0]}'. \nPlease report this to the developer with URL: {self.url}",
            )
        return ""

    async def broadcasting_date(self) -> date | None:
        raise NotImplementedError

        info = await self._info_values()
        diffusions = info.get("diffusion", [])

        if not diffusions:
            return

        import time

        return date(
            *(time.strptime(diffusions[0], "%d %b. %Y")[0:3])
        )  # issue with local: %b should be interpreted with french local

    async def year(self) -> int | None:
        info = await self._info_values()
        for label in ("diffusion", "année", "année de sortie", "début"):
            for value in info.get(label, []):
                match = re.search(r"\b(?:19|20)\d{2}\b", value)
                if match:
                    return int(match.group(0))

    async def episode_count(self) -> int | None:
        info = await self._info_values()
        for value in info.get("épisodes", []):
            match = re.search(r"\d+", value)
            if match:
                return int(match.group(0))

    # Currently not provided by Anime Sama. We consider this as deprecated: TODO add a warning
    async def chapter_count(self) -> int | None:
        info = await self._info_values()
        for value in info.get("chapitres", []):
            match = re.search(r"\d+", value)
            if match:
                return int(match.group(0))

    async def creator(self) -> str:
        info = await self._info_values()
        creators = info.get("auteur", [])

        if not creators:
            return ""

        return creators[0]

    async def studio(self) -> str:
        info = await self._info_values()
        studios = info.get("studio", [])

        if not studios:
            return ""

        return studios[0]

    async def correspondence(self) -> str:
        page = await self.page()
        match = re.search(
            r"Correspondance\s*:.*?</strong>\s*(.*?)</span>",
            page,
            re.IGNORECASE | re.DOTALL,
        )

        if not match:
            return ""

        return self._clean_html(match.group(1))

    async def synopsis(self) -> str:
        page = await self.page()
        synopsis = re.search(
            r"""<p\b[^>]*id=["'][^"']*\bsynopsisText\b[^"']*["'][^>]*>(.*?)</p\s*>""",
            page,
            re.IGNORECASE | re.DOTALL,
        )

        if not synopsis:
            return ""

        return self._clean_html(synopsis.group(1))

    async def is_mature(self) -> bool:
        """Return True if the catalogue contain a warning about adult content"""
        return (
            re.search(
                r'<div class=".*?yellow.*?">[\W\w]+?public averti', await self.page()
            )
            is not None
        )

    @property
    def is_anime(self) -> bool:
        return "Anime" in self.types

    @property
    def is_manga(self) -> bool:
        return "Scans" in self.types

    @property
    def is_film(self) -> bool:
        return "Film" in self.types

    @property
    def is_other(self) -> bool:
        return "Autres" in self.types

    @property
    def fancy_name(self) -> str:
        names = [""] + list(self.alternative_names) if self.alternative_names else []
        return f"{self.name}[bright_black]{' - '.join(names)} {' '.join(flags[lang] for lang in self.languages if lang != 'VOSTFR')}"

    def __repr__(self) -> str:
        return f"Catalogue({self.url!r}, {self.name!r})"

    def __str__(self) -> str:
        return self.fancy_name

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Catalogue):
            return False
        return self.url == value.url

    def __hash__(self) -> int:
        return hash(self.url + self.name + "".join(self.alternative_names))
