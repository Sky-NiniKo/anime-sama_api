from collections.abc import Sequence
import re
from typing import Any, Literal, cast
import aiohttp
from httpx import AsyncClient

from .utils import remove_some_js_comments
from .season import Season
from .langs import flags, Lang



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
        self._raw_name = self.name  # conserve l'ancien nom de base

        if alternative_names:
            self.name = alternative_names[0] 

        self._page: str | None = None
        self._name_with_year = None  # Cache pour �viter les appels r�p�t�s
        self.alternative_names = alternative_names
        self.genres = genres
        self.categories = categories
        self.languages = languages
        self.image_url = image_url

    async def page(self) -> str:
        if self._page is not None:
            return self._page

        response = await self.client.get(self.url)

        if not response.is_success:
            self._page = ""
        else:
            self._page = response.text

        return self._page

    async def seasons(self) -> list[Season]:
        page_without_comments = remove_some_js_comments(string=await self.page())

        seasons = re.findall(
            r'panneauAnime\("(.+?)", *"(.+?)(?:vostfr|vf)"\);', page_without_comments
        )
        full = await self.get_name_with_year()

        seasons = [
            Season(
                url=self.url + link,
                name=name,
                serie_name=full,  # Utilise le nom avec l'ann�e
                client=self.client,
            )
            for name, link in seasons
        ]

        return seasons

    async def advancement(self) -> str:
        search = cast(list[str], re.findall(r"Avancement.+?>(.+?)<", await self.page()))

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

    async def get_name_with_year(self) -> str:
        # Utilise le cache si disponible
        if self._name_with_year is not None:
            return self._name_with_year
            
        # Essaie d'abord avec le nom principal, puis avec les noms alternatifs
        names_to_try = [self.name] + (self.alternative_names or [])
        
        for name_to_search in names_to_try:
            try:
                query = name_to_search.replace(" ", "+")
                url = f"https://api.jikan.moe/v4/anime?q={query}&limit=3"

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            animes = data.get("data", [])
                            
                            # Cherche une correspondance exacte ou proche
                            for anime in animes:
                                anime_title = anime.get("title", "")
                                anime_title_english = anime.get("title_english", "")
                                anime_title_japanese = anime.get("title_japanese", "")
                                
                                # V�rifie si le titre correspond
                                if (self._titles_match(name_to_search, anime_title) or
                                    self._titles_match(name_to_search, anime_title_english) or
                                    self._titles_match(name_to_search, anime_title_japanese)):
                                    
                                    title = anime_title
                                    year = anime.get("year") or (
                                        anime.get("aired", {}).get("from", "")[:4] if 
                                        anime.get("aired", {}).get("from") else ""
                                    )
                                    
                                    if year:
                                        self._name_with_year = f"{title} ({year})"
                                    else:
                                        self._name_with_year = title
                                    
                                    return self._name_with_year
            except Exception as e:
                print(f"[DEBUG catalogue] Error searching for {name_to_search}: {e}")
                continue
        
        # Si aucune correspondance trouv�e, utilise le nom original
        self._name_with_year = self.name
        print(f"[DEBUG catalogue] No match found, using original: {self._name_with_year!r}")
        return self._name_with_year

    def _titles_match(self, search_title: str, api_title: str) -> bool:
        """Verifie si deux titres correspondent (insensible a la casse et aux caracteres speciaux)"""
        if not api_title:
            return False
            
        # Normalise les titres (minuscules, supprime caract�res sp�ciaux)
        def normalize(title: str) -> str:
            return re.sub(r'[^\w\s]', '', title.lower().strip())
        
        normalized_search = normalize(search_title)
        normalized_api = normalize(api_title)
        
        # Correspondance exacte ou contient
        return (normalized_search == normalized_api or 
                normalized_search in normalized_api or 
                normalized_api in normalized_search)

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
