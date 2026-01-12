import re
from collections.abc import Sequence
from typing import Any, Literal, cast

from httpx import AsyncClient

from .langs import Lang, flags
from .season import Season
from .utils import remove_some_js_comments

# Oversight from anime-sama that we should handle
# 'Animes' instead of 'Anime' seen in Cyberpunk: Edgerunners and Valkyrie Apocalypse
# 'Autre' instead of 'Autres' seen in Hazbin Hotel
# 'Scans' is in the language section for Watamote (harder to handle)
Category = Literal["Anime", "Scans", "Film", "Autres"]


class Catalogue:
    def __init__(
        self,
        url: str,
        name: str = "",
        alternative_names: Sequence[str] | None = None,
        genres: Sequence[str] | None = None,
        categories: set[Category] | None = None,
        languages: set[Lang] | None = None,
        image_url: str = "",
        client: AsyncClient | None = None,
    ) -> None:
        if alternative_names is None:
            alternative_names = []
        if genres is None:
            genres = []
        if categories is None:
            categories = set()
        if languages is None:
            languages = set()

        self.url = url + "/" if url[-1] != "/" else url
        self.site_url = "/".join(url.split("/")[:3]) + "/"
        self.client = client or AsyncClient()

        self.name = name or url.split("/")[-2]

        self._page: str | None = None
        self.alternative_names = alternative_names
        self.genres = genres
        self.categories = categories
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
                serie_name=self.name,
                client=self.client,
            )
            for name, link in seasons
        ]

        return seasons

    async def advancement(self) -> str:
        search = cast(list[str], re.findall(r"Actualité.+?>(.+?)<", await self.page()))

        if not search:
            return ""

        return search[0]

    async def correspondence(self) -> str:
        search = cast(
            list[str], re.findall(r"Correspondance.+?>(.+?)<", await self.page())
        )

        if not search:
            return ""

        return search[0]

    async def synopsis(self) -> str:
        search = cast(
            list[str], re.findall(r"Synopsis[\W\w]+?>(.+)<", await self.page())
        )

        if not search:
            return ""

        return search[0]

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
        return "Anime" in self.categories

    @property
    def is_manga(self) -> bool:
        return "Scans" in self.categories

    @property
    def is_film(self) -> bool:
        return "Film" in self.categories

    @property
    def is_other(self) -> bool:
        return "Autres" in self.categories

    @property
    def fancy_name(self) -> str:
        names = [""] + list(self.alternative_names) if self.alternative_names else []
        return f"{self.name}[bright_black]{' - '.join(names)} {' '.join(flags[lang] for lang in self.languages if lang != 'VOSTFR')}"

    def __repr__(self) -> str:
        return f"Catalogue({self.url!r}, {self.name!r})"

    def __str__(self) -> str:
        return self.fancy_name

    def __eq__(self, value: Any) -> bool:
        if not isinstance(value, Catalogue):
            return False
        return self.url == value.url

    def __hash__(self) -> int:
        return hash(self.url + self.name + "".join(self.alternative_names))
