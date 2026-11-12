"""Dependency-light, sequential candidate fallback for one episode."""

from .resolver import RateLimitedError


async def try_candidates(
    candidates, resolve, download, *, recoverable, stopped, report=None
):
    seen_urls = set()
    for candidate in candidates:
        if stopped():
            return False
        try:
            url = await resolve(candidate)
        except RateLimitedError:
            raise
        except recoverable:
            if report:
                report("api_failure", candidate)
            continue
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        if stopped():
            return False
        if await download(url, candidate):
            return True
        if report:
            report("download_failure", candidate)
    return False
