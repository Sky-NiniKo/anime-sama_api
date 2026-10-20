import asyncio
from pprint import pprint

import season_data


async def async_main():
    pprint(await season_data.mha[0].episodes())


asyncio.run(async_main())
