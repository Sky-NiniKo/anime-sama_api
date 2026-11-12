"""Inline episode references and Anime-Sama link API. No JavaScript execution."""

import asyncio
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


class LinkError(RuntimeError):
    pass


class BddScriptParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            attributes = dict(attrs)
            self.active = attributes.get("data-source") == "bdd"

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            self.active = False


def extract_bdd_script(html):
    parser = BddScriptParser()
    parser.feed(html)

    source = "\n".join(parser.parts)

    if not source.strip():
        raise LinkError('Script <script data-source="bdd"> introuvable.')

    return source


class RateLimitedError(LinkError):
    pass


@dataclass
class PageData:
    token: str
    players: dict[int, list[str]]
    final_order: bool


def parse_page(html):
    source = extract_bdd_script(html)
    token = re.search(
        r"\b(?:var|let|const)\s+epsJeton\s*=\s*([\"'])(.*?)\1", source, re.DOTALL
    )
    players = {}
    for match in re.finditer(
        r"\b(?:var|let|const)\s+eps(\d+)\s*=\s*(\[[^;]*?\])\s*;", source, re.DOTALL
    ):
        try:
            values = json.loads(match[2])
        except ValueError as exc:
            raise LinkError("Unsupported episode array syntax (expected JSON)") from exc
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise LinkError("Invalid episode array")
        players[int(match[1])] = values
    if not players:
        raise LinkError(
            "No inline epsN arrays found; page unavailable or format changed"
        )
    needs_token = any(v.startswith("lien:") for a in players.values() for v in a)
    if needs_token and not token:
        raise LinkError("epsJeton missing")
    final = bool(re.search(r"\bepsOrdreFinal\s*=\s*true\b", source))
    return PageData(token[2] if token else "", players, final)


def validate_url(value):
    if not isinstance(value, str):
        raise LinkError("API field u must be a string")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("https", "http")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise LinkError("Invalid player URL")
    return value


class LinkResolver:
    def __init__(self, client, page_url):
        self.client = client
        self.page_url = page_url
        self.data = None
        self.cache = {}
        self.min_interval = 0.0
        self._last_request = 0.0
        self._refresh_lock = asyncio.Lock()

    async def load(self):
        response = await self.client.get(self.page_url, follow_redirects=True)
        response.raise_for_status()
        self.page_url = str(response.url)
        self.data = parse_page(response.text)
        self.cache.clear()
        return response.text

    async def resolve(self, reference):
        if not reference:
            return ""
        if not reference.startswith("lien:"):
            return validate_url(reference)
        identifier = reference[5:]
        if not identifier.isdecimal():
            raise LinkError("Invalid lien ID")
        if self.data is None:
            await self.load()
        refreshed = False
        for attempt in range(3):
            key = (self.data.token, identifier)
            if key in self.cache:
                return self.cache[key]
            try:
                loop = asyncio.get_running_loop()
                wait = self.min_interval - (loop.time() - self._last_request)
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last_request = loop.time()
                response = await self.client.get(
                    urljoin(self.page_url, "/api/lien.php"),
                    params={"j": self.data.token, "l": identifier},
                    headers={"Referer": self.page_url},
                    follow_redirects=False,
                )
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")

                    detail = (
                        f"Retry-After reçu : {retry_after}."
                        if retry_after
                        else "Aucun délai Retry-After fourni par le serveur."
                    )

                    raise RateLimitedError(
                        "Anime-Sama limite actuellement les requêtes. " + detail
                    )

                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise LinkError(
                        "API did not return JSON (possibly a verification page)"
                    ) from exc
                if not isinstance(payload, dict):
                    raise LinkError("API response must be an object")
                if payload.get("u"):
                    value = validate_url(payload["u"])
                    self.cache[key] = value
                    return value
                error = payload.get("erreur", "missing u")
                if error == "expire" and not refreshed:
                    refreshed = True
                    async with self._refresh_lock:
                        if self.data.token == key[0]:
                            await self.load()
                    continue
                if error in ("absent", "expire"):
                    raise LinkError("Terminal API error: " + str(error))
                if attempt == 2:
                    raise LinkError("API error: " + str(error))
            except LinkError:
                raise
            except Exception:
                if attempt == 2:
                    raise
            await asyncio.sleep((1, 3)[min(attempt, 1)])
        raise LinkError("Resolution failed after token refresh")
