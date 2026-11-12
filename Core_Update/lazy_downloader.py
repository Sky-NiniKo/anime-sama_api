"""Adaptateur lazy pour le downloader original.

Aucune barre de progression et aucun téléchargement yt-dlp ici.

Le downloader original conserve :
- l'affichage ;
- les hooks de progression ;
- les options yt-dlp ;
- les reprises ;
- le fallback entre les URL proposées.

Cet adaptateur résout une référence API uniquement lorsque
le downloader demande le candidat suivant.
"""

import asyncio
import logging
import threading
from urllib.parse import urlsplit

from httpx import HTTPError

from anime_sama_api.cli import downloader
from anime_sama_api.langs import id2lang, lang2ids

from .profiling import measure
from .resolver import LinkError, RateLimitedError, validate_url
from .season_api import DeferredPlayers

logger = logging.getLogger(__name__)

# La référence downloader.download est remplacée temporairement
# pour récupérer les exceptions des workers du downloader original.
# Une seule session de cet adaptateur peut être active à la fois.
_session_lock = threading.Lock()


def candidates_for(episode, prefer_languages):
    """Langues configurées, puis replis, dans l'ordre du site."""

    language_order = list(
        dict.fromkeys(
            [
                *prefer_languages,
                *lang2ids,
            ]
        )
    )

    seen = set()

    for language in language_order:
        for lang_id, players in episode.languages.items():
            if id2lang[lang_id] != language:
                continue

            for reference in players:
                if not reference:
                    continue

                owner = (
                    id(players.resolver)
                    if isinstance(players, DeferredPlayers)
                    else None
                )

                key = (owner, reference)

                if key in seen:
                    continue

                seen.add(key)

                yield players, reference


class LazyEpisode:
    """Présenter un épisode au downloader sans résoudre ses URL."""

    def __init__(
        self,
        episode,
        loop,
        resolve_candidate,
        stopped,
    ):
        self._episode = episode
        self._loop = loop
        self._resolve_candidate = resolve_candidate
        self._stopped = stopped

        self.yielded_url = False
        self.exhausted = False
        self.completed = False
        self.succeeded = False

    def __getattr__(self, name):
        return getattr(self._episode, name)

    def consume_player(
        self,
        prefer_languages,
        prefer_players=None,
        ban_players=None,
    ):
        """Générateur synchrone consommé dans un worker.

        La résolution HTTP reste exécutée sur la boucle asyncio
        d'origine, avec son client HTTP partagé.
        """

        bans = set(ban_players or [])
        seen_urls = set()

        # Le classement prefer_players n'est volontairement
        # pas appliqué : l'ordre des lecteurs du site prime.
        for players, reference in candidates_for(
            self._episode,
            prefer_languages,
        ):
            if self._stopped.is_set():
                self.exhausted = True
                return

            future = asyncio.run_coroutine_threadsafe(
                self._resolve_candidate(
                    players,
                    reference,
                ),
                self._loop,
            )

            try:
                url = future.result()

            except RateLimitedError:
                self._stopped.set()
                raise

            except LinkError, HTTPError:
                logger.warning(
                    "%s : résolution API échouée ; passage au lecteur suivant",
                    self._episode.name,
                )
                continue

            if self._stopped.is_set():
                self.exhausted = True
                return

            if not url or url in seen_urls:
                continue

            if urlsplit(url).hostname in bans:
                continue

            seen_urls.add(url)
            self.yielded_url = True

            # downloader.download() reçoit cette URL.
            #
            # S'il réussit, il sort de sa boucle : le
            # générateur ne résout aucun autre lecteur.
            #
            # S'il passe au candidat suivant, l'exécution
            # reprend ici et résout la prochaine référence.
            yield url

        self.exhausted = True


async def download_episodes(
    episodes,
    config,
    year=None,
):
    """Déléguer le téléchargement au module original."""

    episodes = list(episodes)

    if not episodes:
        return True

    if not _session_lock.acquire(blocking=False):
        raise RuntimeError("Une session de téléchargement lazy est déjà active.")

    loop = asyncio.get_running_loop()
    stopped = threading.Event()

    api_slots = asyncio.Semaphore(3)
    resolver_locks = {}

    failures = []
    failures_lock = threading.Lock()

    original_download = downloader.download

    async def resolve_candidate(players, reference):
        async with api_slots:
            if stopped.is_set():
                return ""

            if not isinstance(players, DeferredPlayers):
                if reference.startswith("lien:"):
                    raise LinkError("Référence sans contexte de résolution")

                return validate_url(reference)

            resolver = players.resolver

            lock = resolver_locks.setdefault(
                id(resolver),
                asyncio.Lock(),
            )

            async with lock:
                if stopped.is_set():
                    return ""

                try:
                    with measure("API résolution à la demande"):
                        return await resolver.resolve(reference)

                except RateLimitedError:
                    stopped.set()
                    raise

    lazy_episodes = [
        LazyEpisode(
            episode,
            loop,
            resolve_candidate,
            stopped,
        )
        for episode in episodes
    ]

    def tracked_download(episode, *args, **kwargs):
        """Conserver le downloader, mais observer ses workers."""

        if stopped.is_set():
            return

        try:
            # Dans la version actuelle du downloader original,
            # multi_download ne transmet pas ep_year au worker.
            # Préserver l'année sans la fournir deux fois.
            if len(args) < 9:
                kwargs.setdefault("ep_year", year)

            result = original_download(
                episode,
                *args,
                **kwargs,
            )

            if isinstance(episode, LazyEpisode):
                episode.completed = True

                # Dans le downloader original inspecté,
                # la boucle des lecteurs s'arrête avant
                # épuisement uniquement après un succès.
                episode.succeeded = (
                    episode.yielded_url
                    and not episode.exhausted
                    and not stopped.is_set()
                )

            return result

        except Exception as error:
            if isinstance(error, RateLimitedError):
                stopped.set()

            with failures_lock:
                failures.append(error)

            # Le downloader original soumet des futures sans
            # consulter leur résultat. L'exception est également
            # conservée ci-dessus pour être remontée à la CLI.
            raise

    def run_original_downloader():
        downloader.download = tracked_download

        try:
            with measure("Downloader original (API lazy + téléchargements)"):
                return downloader.multi_download(
                    lazy_episodes,
                    config.download_path,
                    config.episode_path,
                    config.concurrent_downloads,
                    config.prefer_languages,
                    config.players_config,
                    config.max_retry_time,
                    config.format,
                    config.format_sort,
                    [year] * len(lazy_episodes),
                )

        finally:
            downloader.download = original_download

    worker = None

    try:
        worker = asyncio.create_task(asyncio.to_thread(run_original_downloader))

        # Le thread du downloader demande ses résolutions à
        # cette boucle asyncio : elle doit rester disponible.
        await asyncio.shield(worker)

        if failures:
            raise failures[0]

        return all(episode.completed and episode.succeeded for episode in lazy_episodes)

    except asyncio.CancelledError:
        stopped.set()

        # Ne pas fermer la boucle HTTP pendant que le
        # downloader original utilise encore ses workers.
        #
        # Les téléchargements déjà engagés peuvent donc
        # terminer avant que l'annulation soit propagée.
        if worker is not None:
            try:
                await asyncio.shield(worker)
            except Exception:
                pass

        raise

    finally:
        _session_lock.release()
