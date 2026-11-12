"""Deferred episode references and public async URL iteration."""

import logging
from urllib.parse import urlsplit

from httpx import HTTPError

from .episode import Players
from .langs import id2lang, lang2ids
from .link_resolver import LinkError, RateLimitedError, validate_url

logger = logging.getLogger(__name__)


class DeferredPlayers(Players):
    def __init__(self, references, resolver):
        list.__init__(self, references)
        self.resolver = resolver

    def sort_and_filter(self, prefer_players, ban_players):
        raise RuntimeError(
            "Liens différés : utiliser Episode.aconsume_player() ou la CLI."
        )


def candidates_for(episode, prefer_languages):
    order = list(dict.fromkeys([*prefer_languages, *lang2ids]))
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
                    yield language, players, ref


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
