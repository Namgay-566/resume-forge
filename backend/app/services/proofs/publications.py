"""Publication metadata: the DOI registry (Crossref) for DOIs, the page's own citation
metadata for plain links."""

import json
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from app.services.web.fetch import Fetcher, FetchFailedError, parse_page

CROSSREF = "https://api.crossref.org/works/{doi}"
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class PublicationMeta:
    title: str | None = None
    venue: str | None = None
    published: str | None = None
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None


def _first(value: object) -> str | None:
    if isinstance(value, list) and value and isinstance(value[0], str):
        return " ".join(value[0].split()) or None
    return None


def parse_crossref(body: str) -> PublicationMeta:
    message = json.loads(body).get("message") or {}
    authors = []
    for author in message.get("author") or []:
        name = " ".join(
            p for p in (author.get("given"), author.get("family")) if isinstance(p, str)
        ) or author.get("name")
        if isinstance(name, str) and name.strip():
            authors.append(" ".join(name.split()))
    parts = ((message.get("published") or message.get("issued") or {}).get("date-parts") or [[]])[0]
    published = "-".join(f"{int(p):02d}" if i else str(int(p)) for i, p in enumerate(parts[:3]))
    abstract = message.get("abstract")
    return PublicationMeta(
        title=_first(message.get("title")),
        venue=_first(message.get("container-title")) or message.get("publisher"),
        published=published or None,
        authors=authors,
        abstract=" ".join(_TAGS.sub(" ", abstract).split())[:4000]
        if isinstance(abstract, str)
        else None,
    )


async def lookup_doi(fetcher: Fetcher, doi: str) -> PublicationMeta | None:
    """None if the DOI isn't registered. Raises FetchFailedError if the registry is down."""
    result = await fetcher.fetch(CROSSREF.format(doi=quote(doi, safe="/")))
    if result.status_code == 404:
        return None
    if result.status_code >= 400:
        raise FetchFailedError(f"The DOI registry returned HTTP {result.status_code}.")
    try:
        return parse_crossref(result.text)
    except (ValueError, TypeError, AttributeError) as exc:
        raise FetchFailedError("The DOI registry's answer couldn't be read.") from exc


def page_publication(html: str) -> tuple[PublicationMeta, str]:
    """Metadata from a publication's web page, plus its visible text."""
    page = parse_page(html)
    meta = PublicationMeta(title=page.title or None, venue=page.site_name or None)
    meta.authors = list(page.authors)
    return meta, page.text
