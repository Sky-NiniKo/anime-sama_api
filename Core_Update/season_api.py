"""Lazy season backend: listing episodes never resolves API links."""

import logging
import re
from dataclasses import replace
from typing import get_args

from anime_sama_api.episode import Players
from anime_sama_api.langs import LangId, flagid2lang, lang2ids
from anime_sama_api.season import EpisodeDataUnavailableError, Season, SeasonLangPage
from anime_sama_api.utils import remove_some_js_comments

from .lang_fix import make_resolved_languages
from .resolver import LinkError, LinkResolver, RateLimitedError, parse_page

logger = logging.getLogger(__name__)


class DeferredPlayers(Players):
    def __init__(self, references, resolver):
        # Deliberately bypass Players.__init__: it swaps legacy readers.
        list.__init__(self, references)
        self.resolver = resolver


class ApiSeason(Season):
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
                # Some unavailable language URLs return 200 without episode data.
                # Warn instead of silently interpreting them as valid pages.
                logger.warning("Page langue ignorée (%s) : %s", page_url, exc)
                continue
            resolver = LinkResolver(self.client, str(response.url))
            resolver.data = data
            arrays = [data.players[n] for n in sorted(data.players)]
            rows = []
            for index in range(max(map(len, arrays), default=0)):
                refs = [a[index] if index < len(a) else "" for a in arrays]
                if not data.final_order and len(refs) > 1:
                    refs[0], refs[1] = refs[1], refs[0]
                rows.append(DeferredPlayers([r for r in refs if r], resolver))
            self._api_rows[lang_id] = rows
            pages.append(SeasonLangPage(lang_id=lang_id, html=response.text))
        mapping = {p.lang_id: p for p in pages}
        if "vostfr" in mapping:
            matches = re.findall(
                r'src="[^"]*flag_([^"]+?)\.png".*?<span[^>]*>\s*VOSTFR\s*</span>',
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

    def _get_players_from(self, page):
        return self._api_rows[page.lang_id]


async def prepare_selected_episodes(episodes, progress=None):
    """Resolve only selected episodes, sequentially, sharing page caches.

    Returns new Episode instances. Never give the deferred originals to yt-dlp.
    A 429 interrupts the entire preparation immediately.
    """
    prepared = []
    for position, episode in enumerate(episodes, 1):
        if progress:
            progress(position, len(episodes), episode)
        languages = {}
        for lang_id, players in episode.languages.items():
            urls = []
            for reference in players:
                if not reference:
                    continue
                try:
                    if isinstance(players, DeferredPlayers):
                        url = await players.resolver.resolve(reference)
                    else:
                        if reference.startswith("lien:"):
                            raise LinkError("Référence sans contexte de résolution")
                        url = reference
                except RateLimitedError:
                    raise
                except LinkError as exc:
                    logger.warning(
                        "Lecteur indisponible (%s / %s) : %s",
                        episode.name,
                        lang_id,
                        exc,
                    )
                    continue
                if url not in urls:
                    urls.append(url)
            if urls:
                # No legacy swap and no hostname rewriting: preserve API URLs.
                resolved_players = Players([])
                resolved_players.extend(urls)
                languages[lang_id] = resolved_players
        if not languages:
            raise EpisodeDataUnavailableError(
                "Aucun lecteur résolu pour " + episode.name
            )

        prepared.append(
            replace(
                episode,
                languages=make_resolved_languages(languages),
            )
        )
    return prepared
