import asyncio
from html import escape
from datetime import datetime, timezone

from anime_sama_api import AnimeSama, find_site_url


async def main():
    url = await find_site_url()

    if url is None:
        raise

    anime_sama = AnimeSama(url)
    new_releases = await anime_sama.new_episodes()

    print(
        f'<rss version="2.0">\n<channel>\n'
        f"<title>{url} new episodes</title>\n"
        f"<link>{url}/</link>\n"
        f"<lastBuildDate>{datetime.now(timezone.utc).isoformat(timespec='seconds')}</lastBuildDate>\n"
    )

    for release in reversed(new_releases):
        print(
            f"<item>\n"
            f"<title>New release for {escape(release.serie_name)}</title>\n"
            f"<description>{escape(release.fancy_name)}</description>\n"
            f"<link>{release.page_url}</link>\n"
            f'<guid isPermaLink="false">{release.__hash__()}</guid>\n'
            f'<enclosure url="{release.image_url}" length="0" type="image/jpeg"/>\n'
            f"</item>"
        )

    print("\n</channel>\n</rss>")


if __name__ == "__main__":
    asyncio.run(main())
