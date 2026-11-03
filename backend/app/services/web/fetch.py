"""Fetch user-supplied URLs without letting them reach our own network (SSRF protection).

Every hop (including each redirect) must be http(s) on a standard port and resolve only to
public IP addresses; localhost, private ranges, link-local (cloud metadata) and reserved
addresses are refused. Responses are size- and time-limited.
"""

import asyncio
import contextlib
import ipaddress
import socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import httpx

MAX_BYTES = 512 * 1024
MAX_REDIRECTS = 5
TIMEOUT = 10.0
ALLOWED_PORTS = {None, 80, 443}
USER_AGENT = "ResumeForge-ProofCheck/1.0 (+verification of user-submitted links)"

Resolver = Callable[[str], Awaitable[list[str]]]


class BlockedUrlError(Exception):
    """The URL points somewhere we won't fetch. `str(exc)` is safe to show."""


class FetchFailedError(Exception):
    """The site couldn't be reached (DNS, timeout, TLS, connection)."""


@dataclass(frozen=True)
class FetchResult:
    url: str  # as requested
    final_url: str  # after redirects
    status_code: int
    content_type: str
    text: str  # decoded body, truncated to MAX_BYTES
    elapsed_ms: int


async def system_resolver(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return list({info[4][0] for info in infos})


def _is_public(ip: str) -> bool:
    address = ipaddress.ip_address(ip.split("%")[0])
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast


def normalize_url(raw: str) -> str:
    text = raw.strip()
    if text and "://" not in text:
        text = f"https://{text}"
    return text


async def check_url(url: str, resolver: Resolver) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise BlockedUrlError("Only http and https links can be checked.")
    if parts.username or parts.password:
        raise BlockedUrlError("Links with embedded credentials aren't allowed.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise BlockedUrlError("That link points to a private address.")
    if parts.port not in ALLOWED_PORTS:
        raise BlockedUrlError("Only links on the standard web ports can be checked.")
    try:
        addresses = [host] if _looks_like_ip(host) else await resolver(host)
    except OSError as exc:
        raise FetchFailedError(f"The domain {host} doesn't resolve.") from exc
    if not addresses or not all(_is_public(a) for a in addresses):
        raise BlockedUrlError("That link points to a private address.")


def _looks_like_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


class Fetcher(Protocol):
    async def fetch(self, url: str) -> FetchResult: ...


class SafeFetcher:
    def __init__(
        self,
        resolver: Resolver = system_resolver,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._resolver = resolver
        self._client = httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=False,  # we follow manually so every hop is checked
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.5",
            },
            transport=transport,
        )

    async def fetch(self, url: str) -> FetchResult:
        started = time.perf_counter()
        current = normalize_url(url)
        for _ in range(MAX_REDIRECTS + 1):
            await check_url(current, self._resolver)
            try:
                async with self._client.stream("GET", current) as response:
                    if response.is_redirect and "location" in response.headers:
                        current = urljoin(current, response.headers["location"])
                        continue
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) >= MAX_BYTES:
                            break
                    encoding = response.encoding or "utf-8"
                    return FetchResult(
                        url=url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type", ""),
                        text=bytes(body[:MAX_BYTES]).decode(encoding, errors="replace"),
                        elapsed_ms=round((time.perf_counter() - started) * 1000),
                    )
            except httpx.TimeoutException as exc:
                raise FetchFailedError("The site didn't respond within 10 seconds.") from exc
            except httpx.HTTPError as exc:
                raise FetchFailedError("The site couldn't be reached.") from exc
        raise FetchFailedError("The link redirects too many times.")


@lru_cache
def _default_fetcher() -> SafeFetcher:
    return SafeFetcher()


def get_fetcher() -> Fetcher:
    """FastAPI dependency; tests override it."""
    return _default_fetcher()


# --- HTML metadata ------------------------------------------------------------------------


@dataclass
class PageMeta:
    title: str = ""
    description: str = ""
    site_name: str = ""
    text: str = ""  # visible text, for looking up names / credential IDs
    links: tuple[str, ...] = ()
    # Authors publishers declare for indexers (citation_author, dc.creator), in order.
    authors: tuple[str, ...] = ()


AUTHOR_META = {"citation_author", "dc.creator", "dcterms.creator", "prism.author"}


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.authors: list[str] = []
        self.title = ""
        self.text: list[str] = []
        self.links: list[str] = []
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag in {"script", "style", "noscript", "template"}:
            self._skip += 1
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"].strip())
                if key in AUTHOR_META and a["content"].strip():
                    self.authors.append(" ".join(a["content"].split())[:200])
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in {"script", "style", "noscript", "template"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.text.append(data.strip())


def parse_page(html: str) -> PageMeta:
    parser = _MetaParser()
    with contextlib.suppress(Exception):  # malformed HTML: keep whatever was parsed
        parser.feed(html)
    m = parser.meta
    return PageMeta(
        title=" ".join((m.get("og:title") or parser.title).split())[:300],
        description=" ".join((m.get("og:description") or m.get("description") or "").split())[:500],
        site_name=m.get("og:site_name", "")[:120],
        text=" ".join(parser.text)[:100_000],
        links=tuple(parser.links[:500]),
        authors=tuple(dict.fromkeys(parser.authors))[:100],
    )
