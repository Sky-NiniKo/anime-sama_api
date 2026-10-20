import asyncio

from httpx import AsyncClient

from anime_sama_api import AnimeSama, find_site_url

semaphore = asyncio.Semaphore(10)


async def scan(catalogue):
    async with semaphore:
        return await catalogue.state()


async def async_main() -> None:

    client = AsyncClient()
    url = await find_site_url(client)

    if url is None:
        raise RuntimeError

    catalogues = await AnimeSama(url, client).all_catalogues()
    await asyncio.gather(*(scan(catalogue) for catalogue in catalogues))


asyncio.run(async_main())
