import logging
import re
from ast import literal_eval
from dataclasses import dataclass, replace
from functools import reduce
from typing import get_args

from httpx import AsyncClient

from .episode import Episode, Languages, Players
from .episode_sources import DeferredPlayers
from .langs import LangId, flagid2lang, lang2ids
from .link_resolver import LinkError, LinkResolver, RateLimitedError, parse_page
from .utils import remove_some_js_comments, split_and_strip

logger = logging.getLogger(__name__)


class EpisodeDataUnavailableError(RuntimeError):
    pass


@dataclass
class SeasonLangPage:
    lang_id: LangId
    html: str = ""
    episodes_js: str = ""


class Season:
    def __init__(
        self,
        url: str,
        name: str = "",
        series_name: str = "",
        client: AsyncClient | None = None,
    ) -> None:
        self.url = url
        self.site_url = "/".join(url.split("/")[:3]) + "/"

        self.name = name or url.split("/")[-2]
        self.series_name = series_name or url.split("/")[-3]

        self.client = client or AsyncClient()

    async def get_all_pages(self):
        pages = []
        self._api_rows = {}
        for lang_id in get_args(LangId):
            page_url = self.url.rstrip("/") + "/" + lang_id + "/"
            response = await self.client.get(page_url, follow_redirects=True)
            if response.status_code == 404:
                continue
            if response.status_code == 429:
                delay = response.headers.get("Retry-After", "non fourni")
                raise RateLimitedError(
                    "Limitation lors du chargement HTML. Retry-After : " + delay
                )
            response.raise_for_status()
            try:
                data = parse_page(response.text)
            except LinkError as exc:
                logger.warning("Page langue ignorée (%s) : %s", page_url, exc)
                continue
            resolver = LinkResolver(self.client, str(response.url))
            resolver.data = data
            arrays = [data.players[n] for n in sorted(data.players)]
            rows = []
            for index in range(max(map(len, arrays), default=0)):
                refs = [a[index] if index < len(a) else "" for a in arrays]
                if not data.final_order and len(refs) > 1:
                    refs[0], refs[1] = (refs[1], refs[0])
                rows.append(DeferredPlayers([r for r in refs if r], resolver))
            self._api_rows[lang_id] = rows
            pages.append(SeasonLangPage(lang_id=lang_id, html=response.text))
        mapping = {p.lang_id: p for p in pages}
        if "vostfr" in mapping:
            matches = re.findall(
                'src="[^"]*flag_([^"]+?)\\.png".*?<span[^>]*>\\s*VOSTFR\\s*</span>',
                remove_some_js_comments(mapping["vostfr"].html),
                re.DOTALL | re.IGNORECASE,
            )
            if matches and matches[0] in flagid2lang:
                for target in lang2ids[flagid2lang[matches[0]]]:
                    if target not in mapping:
                        pages.append(replace(mapping["vostfr"], lang_id=target))
                        self._api_rows[target] = self._api_rows["vostfr"]
                        break
        if not pages:
            raise EpisodeDataUnavailableError(
                "Aucune page avec données bdd exploitable : " + self.url
            )
        return pages

    # TODO: Refactor
    def _get_players_from(self, page):
        return self._api_rows[page.lang_id]

    def _get_episodes_names(
        self, page: SeasonLangPage, number_of_episodes: int, number_of_episodes_max: int
    ) -> list[str]:
        functions = re.findall(
            r"resetListe\(\); *[\n\r]+\t*(.*?)}",
            remove_some_js_comments(page.html),
            re.DOTALL,
        )
        if not functions:
            raise EpisodeDataUnavailableError(
                f"Could not find episode names for {self.series_name} - {self.name} "
                f"({self.url + page.lang_id}/)."
            )
        functions = functions[-1]
        functions_list = split_and_strip(functions, (";", "\n"))[:-1]

        def padding(n: int) -> str:
            return " " * (len(str(number_of_episodes_max)) - len(str(n)))

        def episode_name_range(*args) -> list[str]:
            return [f"Episode {n}{padding(n)}" for n in range(*args)]

        episodes_name: list[str] = []
        for function in functions_list:
            if function.startswith("//"):
                continue

            call_start = function.find("(")
            function, args_sting = function[:call_start], function[call_start + 1 : -1]
            if args_sting:
                # Warning literal_eval: Can crash
                args = literal_eval(node_or_string=args_sting + ",")
                if type(args) is not tuple:
                    continue
            else:
                args = ()

            match function:
                case "":
                    continue
                case "creerListe":
                    if len(args) < 2:
                        # Only seen on Dragon Ball GT (Film), Junji Ito Collection (Saison 1) and Orange (Film)
                        # Surely a small oversight in anime-sama
                        # So it is undefined but do nothing is generally the good reaction
                        continue

                    episodes_name += episode_name_range(int(args[0]), int(args[1]) + 1)
                case "finirListe" | "finirListeOP":
                    if not args:
                        break

                    episodes_name += episode_name_range(
                        int(args[0]),
                        int(args[0]) + number_of_episodes - len(episodes_name),
                    )
                    break
                case "newSP":
                    if not args:
                        raise NotImplementedError(
                            f"Error while parsing 'newSP'.\nPlease report this to the developer with URL: {self.url + page.lang_id}/"
                        )
                    episodes_name.append(f"Episode {args[0]}")
                case "newSPF":
                    if not args:
                        raise NotImplementedError(
                            f"Error while parsing 'newSPF'.\nPlease report this to the developer with URL: {self.url + page.lang_id}/"
                        )
                    episodes_name.append(args[0])
                case name:
                    raise NotImplementedError(
                        f"Error cannot parse '{name}'.\nPlease report this to the developer with URL: {self.url + page.lang_id}/"
                    )

        return episodes_name

    @staticmethod
    def _extend_episodes(
        current: list[tuple[str, Languages]],
        new: tuple[SeasonLangPage, list[str], list[Players]],
    ) -> list[tuple[str, Languages]]:
        """
        Extend a list of episodes AKA (name, languages) from a list names and players corresponding
        to a language while preserving the relative order of names.
        This function is intended to be used with reduce.
        """
        page, names, players_list = new  # Unpack args. This is due to reduce

        fusion = []
        curr_done = 0
        for name_new, players in zip(names, players_list):
            for pos, (name_current, languages) in enumerate(current[curr_done:]):
                if name_new == name_current:
                    languages[page.lang_id] = players
                    fusion.extend(current[curr_done : curr_done + pos + 1])
                    curr_done += pos + 1
                    break
            else:
                fusion.append((name_new, Languages({page.lang_id: players})))
        fusion.extend(current[curr_done:])
        return fusion

    async def episodes(self) -> list[Episode]:
        pages = await self.get_all_pages()
        if not pages:
            raise EpisodeDataUnavailableError(
                f"Could not retrieve episode data for {self.series_name} - {self.name} "
                f"({self.url}). The season may be unavailable or Anime-Sama's page "
                "structure may have changed."
            )

        players_list = [self._get_players_from(page) for page in pages]
        if not any(players_list):
            raise EpisodeDataUnavailableError(
                f"Could not parse episode players for {self.series_name} - {self.name} "
                f"({self.url}). Anime-Sama's page structure may have changed."
            )

        number_of_episodes_max = max(
            len(episodes_page) for episodes_page in players_list
        )

        episodes_names = [
            self._get_episodes_names(page, len(episodes_page), number_of_episodes_max)
            for page, episodes_page in zip(pages, players_list)
        ]

        episodes: list[tuple[str, Languages]] = reduce(
            self._extend_episodes, zip(pages, episodes_names, players_list), []
        )

        return [
            Episode(
                languages,
                self.series_name,
                self.name,
                name,
                index,
            )
            for index, (name, languages) in enumerate(episodes, start=1)
        ]

    def __repr__(self) -> str:
        return f"Season({self.name!r}, {self.series_name!r})"

    def __str__(self) -> str:
        return self.name

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Season):
            return False
        return self.url == value.url
