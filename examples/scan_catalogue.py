import asyncio

from anime_sama_api import AnimeSama, find_site_url

semaphore = asyncio.Semaphore(100)

async def scan(catalogue):
    async with semaphore:
        return await catalogue.state()


async def async_main() -> None:
    url = await find_site_url()

    if url is None:
        raise RuntimeError

    catalogues = await AnimeSama(url).all_catalogues()
    a = await asyncio.gather(*(scan(catalogue) for catalogue in catalogues))
    print(a)

asyncio.run(async_main())
