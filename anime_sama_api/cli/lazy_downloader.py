"""Bridge between the async resolver and the original threaded downloader.

No Progress, no yt-dlp implementation and no monkey-patching in this module.
"""

import asyncio
import threading
from contextlib import suppress

from ..episode_sources import DeferredPlayers, iter_resolved_players, resolve_reference
from ..link_resolver import RateLimitedError
from . import downloader


class LazyEpisode:
    def __init__(self, episode, loop, resolve, stopped):
        self._episode = episode
        self._loop = loop
        self._resolve = resolve
        self._stopped = stopped
        self.streams = []

    def __getattr__(self, name):
        return getattr(self._episode, name)

    def consume_player(self, prefer_languages, prefer_players=None, ban_players=None):
        stream = iter_resolved_players(
            self._episode, prefer_languages, ban_players or (), self._resolve
        )
        self.streams.append(stream)

        async def next_url():
            if self._stopped.is_set():
                raise StopAsyncIteration
            return await anext(stream)

        while not self._stopped.is_set():
            future = asyncio.run_coroutine_threadsafe(next_url(), self._loop)
            try:
                url = future.result()
            except StopAsyncIteration:
                return
            except RateLimitedError:
                self._stopped.set()
                raise
            if self._stopped.is_set():
                return
            yield url


async def download_episodes(episodes, config, year=None):
    episodes = list(episodes)
    if not episodes:
        return True
    loop = asyncio.get_running_loop()
    stopped = threading.Event()
    api_slots = asyncio.Semaphore(3)
    locks = {}

    async def resolve(players, reference):
        async with api_slots:
            if stopped.is_set():
                return ""
            if not isinstance(players, DeferredPlayers):
                return await resolve_reference(players, reference)
            lock = locks.setdefault(id(players.resolver), asyncio.Lock())
            async with lock:
                if stopped.is_set():
                    return ""
                try:
                    return await resolve_reference(players, reference)
                except RateLimitedError:
                    stopped.set()
                    raise

    proxies = [LazyEpisode(ep, loop, resolve, stopped) for ep in episodes]

    def run():
        return downloader.multi_download(
            proxies,
            config.download_path,
            config.episode_path,
            config.concurrent_downloads,
            config.prefer_languages,
            config.players_config,
            config.max_retry_time,
            config.format,
            config.format_sort,
            [year] * len(proxies),
        )

    worker = asyncio.create_task(asyncio.to_thread(run))
    try:
        results = await asyncio.shield(worker)
        return all(results)
    except asyncio.CancelledError:
        stopped.set()
        with suppress(Exception):
            await asyncio.shield(worker)
        raise
    finally:
        # Workers have finished before closing their async iterators/client.
        for proxy in proxies:
            for stream in proxy.streams:
                await stream.aclose()
