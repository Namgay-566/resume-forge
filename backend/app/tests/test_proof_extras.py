"""Certificates, live links, storage, SSRF protection and verification levels."""

import io
import json
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.ai.certificate_reader import CertificateFields
from app.ai.client import AIClient, get_ai_client
from app.ai.providers.anthropic_provider import _content
from app.ai.types import AIRequest, AIResponse, ImageInput
from app.main import app
from app.models import Proof, Skill, User, UserSkill
from app.models.enums import ProofStatus, ProofType
from app.schemas.proof_report import (
    CertificateInfo,
    LiveLinkInfo,
    NameMatch,
    ProofReport,
    RepoFacts,
    UrlCheck,
)
from app.services.proofs.certificates import (
    CertificateFileError,
    decide_certificate,
    detect_file,
    match_name,
    prepare_image,
    read_pdf,
    trusted_host,
)
from app.services.proofs.live_links import decide_live, find_connection
from app.services.storage.files import LocalFileStorage, StorageError, get_file_storage, new_key
from app.services.web.fetch import (
    BlockedUrlError,
    FetchFailedError,
    FetchResult,
    SafeFetcher,
    check_url,
    get_fetcher,
    parse_page,
)

# --- storage ----------


async def test_local_storage_round_trip_and_rejects_unsafe_keys(tmp_path: Any) -> None:
    storage = LocalFileStorage(tmp_path)
    key = new_key("proofs/abc-123", "pdf")

    await storage.save(key, b"%PDF-1.7 data", "application/pdf")

    assert await storage.read(key) == b"%PDF-1.7 data"
    for bad in ["../etc/passwd", "proofs/../../x.pdf", "/abs/x.pdf", "proofs/x.exe", "a/B.pdf"]:
        with pytest.raises(StorageError):
            await storage.read(bad)
    await storage.delete(key)
    with pytest.raises(StorageError):
        await storage.read(key)


# --- uploads ----------


def png_bytes(size: tuple[int, int] = (40, 30), exif: bool = False) -> bytes:
    image = Image.new("RGB", size, (200, 30, 30))
    out = io.BytesIO()
    if exif:
        data = Image.Exif()
        data[0x010F] = "SecretCamera"  # Make
        image.save(out, format="JPEG", exif=data)
    else:
        image.save(out, format="PNG")
    return out.getvalue()


def text_pdf(body: str) -> bytes:
    return HTML(string=f"<html><body>{body}</body></html>").write_pdf()  # type: ignore[return-value]


@pytest.mark.parametrize(
    ("content_type", "data", "kind"),
    [
        ("application/pdf", b"%PDF-1.7 x", "pdf"),
        ("image/png", b"\x89PNG\r\n\x1a\n" + b"0" * 10, "png"),
        ("image/jpeg", b"\xff\xd8\xff" + b"0" * 10, "jpg"),
        ("application/octet-stream", b"%PDF-1.7 x", "pdf"),
    ],
)
def test_detect_file_by_signature(content_type: str, data: bytes, kind: str) -> None:
    assert detect_file(content_type, data) == kind


@pytest.mark.parametrize(
    ("content_type", "data"),
    [
        ("image/png", b"%PDF-1.7 pretending"),  # declared type disagrees with the bytes
        ("application/pdf", b"MZ\x90\x00 an exe"),
        ("image/gif", b"GIF89a"),
        ("application/pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024)),  # over 5 MB
    ],
)
def test_detect_file_rejects(content_type: str, data: bytes) -> None:
    with pytest.raises(CertificateFileError):
        detect_file(content_type, data)


def test_prepare_image_downscales_and_strips_metadata() -> None:
    original = png_bytes((3200, 1800), exif=True)
    assert b"SecretCamera" in original

    cleaned = prepare_image(original)

    with Image.open(io.BytesIO(cleaned)) as image:
        assert image.format == "JPEG" and max(image.size) == 1568
        assert not image.getexif()
    assert b"SecretCamera" not in cleaned


def test_printed_links_without_scheme_still_count() -> None:
    from app.services.proofs.certificates import url_appears_in

    text = "Verify at coursera.org/verify/ABC123 . Credential ID ABC123"
    assert url_appears_in("https://coursera.org/verify/ABC123", text)
    assert url_appears_in("https://www.coursera.org/verify/ABC123/", text)
    assert not url_appears_in("https://coursera.org/verify/MADEUP", text)


def test_read_pdf_text_and_scanned() -> None:
    text = read_pdf(text_pdf("<h1>Certificate of Completion</h1><p>Awarded to Ada Lovelace</p>"))
    assert "Ada Lovelace" in text.text and text.first_page_image is None

    scanned = read_pdf(
        text_pdf(
            '<img style="width:500px;height:350px" src="data:image/png;base64,'
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGA"
            'WjR9awAAAABJRU5ErkJggg==">'
        )
    )
    assert scanned.first_page_image is not None and scanned.first_page_image.startswith(b"\xff\xd8")


# --- name and domain matching ----------


@pytest.mark.parametrize(
    ("on_certificate", "account", "status"),
    [
        ("Ada Lovelace", "Ada Lovelace", "match"),
        ("ADA KING LOVELACE", "Ada Lovelace", "match"),  # middle name
        ("José García", "Jose Garcia", "match"),  # accents
        ("Ada Lovelase", "Ada Lovelace", "match"),  # typo
        ("Samuel Smith", "Sam Smith", "partial"),  # nickname
        ("Ada", "Ada Lovelace", "partial"),  # first name only
        ("John Doe", "Ada Lovelace", "mismatch"),
        (None, "Ada Lovelace", "missing"),
    ],
)
def test_name_matching(on_certificate: str | None, account: str, status: str) -> None:
    assert match_name(on_certificate, account).status == status


@pytest.mark.parametrize(
    ("url", "issuer", "trusted"),
    [
        ("https://coursera.org/verify/ABC", "Coursera", True),
        ("https://www.credly.com/badges/x", "Amazon Web Services", True),  # credential platform
        ("https://verify.acme.io/x", "Acme Academy", True),  # issuer word is the domain
        ("https://coursera.org.evil.com/x", "Coursera", False),
        ("https://evilcoursera.org/x", "Coursera", False),
        ("https://example.com/x", "Coursera", False),
    ],
)
def test_trusted_hosts(url: str, issuer: str, trusted: bool) -> None:
    assert trusted_host(url, issuer) is trusted


def cert(**overrides: Any) -> CertificateInfo:
    base: dict[str, Any] = dict(
        filename="c.pdf",
        content_type="application/pdf",
        text_source="pdf_text",
        issuer="Coursera",
        recipient_name="Ada Lovelace",
        credential_id="ABC123",
        name_match=NameMatch(status="match", detail="ok"),
    )
    return CertificateInfo(**{**base, **overrides})


def url_check(**overrides: Any) -> UrlCheck:
    base: dict[str, Any] = dict(
        url="https://coursera.org/verify/ABC123",
        reachable=True,
        on_trusted_domain=True,
        details_on_page=True,
    )
    return UrlCheck(**{**base, **overrides})


@pytest.mark.parametrize(
    ("info", "level"),
    [
        (cert(url_check=url_check()), "verified"),
        (cert(url_check=url_check(details_on_page=False)), "partially_verified"),
        (
            cert(url_check=url_check(), name_match=NameMatch(status="partial", detail="")),
            "partially_verified",
        ),
        (cert(url_check=url_check(on_trusted_domain=False)), "self_reported"),
        (cert(url_check=url_check(reachable=False, detail="timed out")), "self_reported"),
        (cert(), "self_reported"),  # credential ID but no link
        (cert(credential_id=None), "self_reported"),  # nothing: recorded, not rejected
        (cert(is_certificate=False), None),
        (cert(name_match=NameMatch(status="mismatch", detail="someone else")), None),
    ],
)
def test_certificate_levels(info: CertificateInfo, level: str | None) -> None:
    assert decide_certificate(info).level == level


# --- SSRF protection ----------


def resolver(mapping: dict[str, list[str]]):  # type: ignore[no-untyped-def]
    async def resolve(host: str) -> list[str]:
        if host not in mapping:
            raise OSError("no such host")
        return mapping[host]

    return resolve


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "http://10.1.2.3/",
        "http://[::ffff:127.0.0.1]/",
        "file:///etc/passwd",
        "http://user:pass@example.com/",
        "https://example.com:8443/",
        "http://internal.corp/",
    ],
)
async def test_check_url_blocks_private_targets(url: str) -> None:
    fake = resolver({"example.com": ["93.184.215.14"], "internal.corp": ["192.168.1.10"]})
    with pytest.raises(BlockedUrlError):
        await check_url(url, fake)


async def test_fetcher_rechecks_every_redirect_hop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
        return httpx.Response(200, text="secret")

    fetcher = SafeFetcher(
        resolver({"example.com": ["93.184.215.14"]}), transport=httpx.MockTransport(handler)
    )

    with pytest.raises(BlockedUrlError):
        await fetcher.fetch("https://example.com/r")


async def test_fetcher_follows_safe_redirects_and_caps_size() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(301, headers={"location": "/final"})
        return httpx.Response(
            200, text="<title>Hi</title>" + "x" * 2_000_000, headers={"content-type": "text/html"}
        )

    fetcher = SafeFetcher(
        resolver({"example.com": ["93.184.215.14"]}), transport=httpx.MockTransport(handler)
    )

    result = await fetcher.fetch("example.com/start")

    assert result.final_url == "https://example.com/final" and result.status_code == 200
    assert len(result.text) <= 512 * 1024


async def test_unresolvable_domain_is_a_fetch_failure() -> None:
    with pytest.raises(FetchFailedError):
        await check_url("https://nope.invalid/", resolver({}))


def test_parse_page_reads_meta_and_ignores_scripts() -> None:
    page = parse_page(
        '<html><head><title>Old</title><meta property="og:title" content="Habit Tracker">'
        '<meta name="description" content="Track habits"><script>var name="Hidden"</script></head>'
        '<body><a href="https://github.com/ada/tracker">Code</a><p>Built by Ada</p></body></html>'
    )

    assert (page.title, page.description) == ("Habit Tracker", "Track habits")
    assert "Built by Ada" in page.text and "Hidden" not in page.text
    assert page.links == ("https://github.com/ada/tracker",)


# --- live links ----------


def repo_facts(**overrides: Any) -> RepoFacts:
    base: dict[str, Any] = dict(
        full_name="ada/tracker",
        url="https://github.com/ada/tracker",
        description=None,
        default_branch="main",
        fork=False,
        stars=0,
        created_at=None,
        pushed_at=None,
        languages={},
        commit_count=10,
        commit_days=3,
        contributors=[],
        file_count=5,
        tree_truncated=False,
        has_readme=True,
        has_tests=False,
        has_ci=False,
        has_docker=False,
        key_files=[],
        sampled_files=[],
    )
    return RepoFacts(**{**base, **overrides})


def test_live_link_connection_to_repo() -> None:
    linked = parse_page('<a href="https://github.com/Ada/Tracker">source</a>')

    assert (
        find_connection("https://tracker.dev", linked, repo_facts())
        == "The site links to ada/tracker."
    )
    via_homepage = find_connection(
        "https://www.tracker.dev/app", parse_page(""), repo_facts(homepage="https://tracker.dev")
    )
    assert via_homepage and "website" in via_homepage
    assert find_connection("https://tracker.dev", parse_page(""), repo_facts()) is None


@pytest.mark.parametrize(
    ("info", "level"),
    [
        (
            LiveLinkInfo(
                url="x",
                reachable=True,
                linked_repo="a/b",
                linked_repo_verified=True,
                connection="links",
            ),
            "verified",
        ),
        (
            LiveLinkInfo(url="x", reachable=True, linked_repo="a/b", linked_repo_verified=True),
            "partially_verified",
        ),
        (
            LiveLinkInfo(url="x", reachable=True, linked_repo="a/b", connection="links"),
            "partially_verified",
        ),
        (LiveLinkInfo(url="x", reachable=True, linked_repo="a/b"), "self_reported"),
        (LiveLinkInfo(url="x", reachable=True), "self_reported"),
        (LiveLinkInfo(url="x", reachable=False), None),
    ],
)
def test_live_link_levels(info: LiveLinkInfo, level: str | None) -> None:
    assert decide_live(info).level == level


# --- providers send images ----------


def test_anthropic_request_includes_image_blocks() -> None:
    request = AIRequest(
        prompt="read",
        response_model=CertificateFields,
        images=(ImageInput(data=b"\xff\xd8\xffabc", media_type="image/jpeg"),),
    )

    content = _content(request)

    assert isinstance(content, list)
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/jpeg"  # type: ignore[index]
    assert content[-1] == {"type": "text", "text": "read"}
    assert _content(AIRequest(prompt="plain", response_model=CertificateFields)) == "plain"


# --- endpoints ----------


class MemoryStorage:
    def __init__(self) -> None:
        self.files: dict[str, tuple[bytes, str]] = {}

    async def save(self, key: str, data: bytes, content_type: str) -> None:
        self.files[key] = (data, content_type)

    async def read(self, key: str) -> bytes:
        if key not in self.files:
            raise StorageError("file not found")
        return self.files[key][0]

    async def delete(self, key: str) -> None:
        self.files.pop(key, None)


class FakeFetcher:
    def __init__(self, pages: dict[str, FetchResult | Exception]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    async def fetch(self, url: str) -> FetchResult:
        self.urls.append(url)
        page = self.pages.get(url, FetchFailedError("The site couldn't be reached."))
        if isinstance(page, Exception):
            raise page
        return page


def page(url: str, html: str, status: int = 200) -> FetchResult:
    return FetchResult(
        url=url,
        final_url=url,
        status_code=status,
        content_type="text/html",
        text=html,
        elapsed_ms=40,
    )


class CertAI:
    name, model = "fake", "fake-1"

    def __init__(self, answer: dict[str, Any]) -> None:
        self.answer = answer
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        return AIResponse(text=json.dumps(self.answer), model=self.model)


FIELDS = {
    "is_certificate": True,
    "issuer": "Coursera",
    "recipient_name": "Ada Lovelace",
    "course_name": "Python for Everybody",
    "issue_date": "2024-05",
    "credential_id": "ABC123XYZ",
    "verification_url": "https://coursera.org/verify/ABC123XYZ",
    "skills": ["Python", "Kubernetes"],
}
CERT_PDF_BODY = (
    "<h1>Certificate of Completion</h1><p>Ada Lovelace</p><p>Python for Everybody</p>"
    "<p>Verify at coursera.org/verify/ABC123XYZ</p><p>Credential ID ABC123XYZ</p>"
)


def wire(
    answer: dict[str, Any], pages: dict[str, FetchResult | Exception]
) -> tuple[CertAI, FakeFetcher, MemoryStorage]:
    ai, fetcher, storage = CertAI(answer), FakeFetcher(pages), MemoryStorage()
    app.dependency_overrides[get_ai_client] = lambda: AIClient(ai)
    app.dependency_overrides[get_fetcher] = lambda: fetcher
    app.dependency_overrides[get_file_storage] = lambda: storage
    return ai, fetcher, storage


@pytest.fixture
async def catalog(db_session: AsyncSession) -> dict[str, Skill]:
    skills = {
        "python": Skill(name="Python", slug="python", category="language", aliases=["python"]),
        "sql": Skill(name="SQL", slug="sql", category="database", aliases=["sql"]),
    }
    db_session.add_all(skills.values())
    await db_session.commit()
    return skills


async def signup(
    client: AsyncClient, email: str = "certs@example.com", name: str = "Ada Lovelace"
) -> dict[str, str]:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123", "name": name}
    )
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def upload(
    client: AsyncClient,
    headers: dict[str, str],
    data: bytes,
    content_type: str,
    name: str = "cert.pdf",
    skill_ids: list[str] | None = None,
) -> httpx.Response:
    return await client.post(
        "/api/proofs/certificate",
        files={"file": (name, data, content_type)},
        data={"skill_ids": skill_ids or []},
        headers=headers,
    )


async def detail(client: AsyncClient, headers: dict[str, str], proof_id: str) -> dict[str, Any]:
    return (await client.get(f"/api/proofs/{proof_id}", headers=headers)).json()


async def test_certificate_verified_on_issuer_site(
    client: AsyncClient, db_session: AsyncSession, catalog: dict[str, Skill]
) -> None:
    url = "https://coursera.org/verify/ABC123XYZ"
    ai, fetcher, storage = wire(
        FIELDS,
        {url: page(url, "<title>Coursera</title><p>Ada Lovelace completed ... ABC123XYZ</p>")},
    )
    headers = await signup(client)

    response = await upload(client, headers, text_pdf(CERT_PDF_BODY), "application/pdf")

    assert response.status_code == 202, response.text
    body = await detail(client, headers, response.json()["id"])
    assert body["status"] == "verified" and body["verification_level"] == "verified"
    info = body["report"]["certificate"]
    assert (info["issuer"], info["course_name"], info["credential_id"]) == (
        "Coursera",
        "Python for Everybody",
        "ABC123XYZ",
    )
    assert info["name_match"]["status"] == "match" and info["text_source"] == "pdf_text"
    assert info["url_check"]["on_trusted_domain"] and info["url_check"]["details_on_page"]
    assert info["mapped_skills"] == ["Python"]  # "Kubernetes" isn't in the catalog
    assert [s["name"] for s in body["skills"]] == ["Python"]
    row = await db_session.scalar(
        select(UserSkill).where(UserSkill.skill_id == catalog["python"].id)
    )
    assert row and row.verification_status.value == "verified"
    assert "Ada Lovelace" in ai.requests[0].prompt and ai.requests[0].images == ()
    assert fetcher.urls == [url]
    # Stored under a generated key, never the user's filename; served only via the API.
    (key,) = storage.files
    assert key.startswith("proofs/") and "cert" not in key
    assert "file_path" not in json.dumps(body) and key not in json.dumps(body)
    file = await client.get(f"/api/proofs/{body['id']}/file", headers=headers)
    assert file.status_code == 200 and file.content.startswith(b"%PDF")
    assert file.headers["x-content-type-options"] == "nosniff"
    other = await signup(client, "other-cert@example.com", "Bob")
    assert (await client.get(f"/api/proofs/{body['id']}/file", headers=other)).status_code == 404


async def test_invented_verification_link_is_discarded(
    client: AsyncClient, catalog: dict[str, Skill]
) -> None:
    hallucinated = {
        **FIELDS,
        "verification_url": "https://coursera.org/verify/MADEUP",
        "credential_id": "MADEUP",
    }
    _, fetcher, _ = wire(hallucinated, {})
    headers = await signup(client)

    body = await detail(
        client,
        headers,
        (
            await upload(
                client,
                headers,
                text_pdf(
                    "<h1>Certificate of Completion</h1><p>Awarded to Ada Lovelace for "
                    "completing Python for Everybody on Coursera.</p>"
                ),
                "application/pdf",
            )
        ).json()["id"],
    )

    info = body["report"]["certificate"]
    assert info["verification_url"] is None and info["credential_id"] is None  # not on the page
    assert fetcher.urls == []
    assert body["verification_level"] == "self_reported" and body["status"] == "needs_more"
    assert "self-reported" in body["decision"]


@pytest.mark.parametrize(
    ("html", "status", "level"),
    [
        ("<div id=root></div>", 200, "partially_verified"),  # JS page without details
        ("<p>Ada Lovelace ABC123XYZ</p>", 404, "self_reported"),
    ],
)
async def test_certificate_levels_from_verification_page(
    client: AsyncClient, catalog: dict[str, Skill], html: str, status: int, level: str
) -> None:
    url = "https://coursera.org/verify/ABC123XYZ"
    wire(FIELDS, {url: page(url, html, status)})
    headers = await signup(client)

    body = await detail(
        client,
        headers,
        (await upload(client, headers, text_pdf(CERT_PDF_BODY), "application/pdf")).json()["id"],
    )

    assert body["verification_level"] == level and body["status"] == "needs_more"


async def test_certificate_for_someone_else_is_rejected(
    client: AsyncClient, catalog: dict[str, Skill]
) -> None:
    wire(
        {**FIELDS, "recipient_name": "John Doe", "verification_url": None, "credential_id": None},
        {},
    )
    headers = await signup(client)

    body = await detail(
        client,
        headers,
        (
            await upload(
                client, headers, text_pdf("<p>Certificate: John Doe</p>"), "application/pdf"
            )
        ).json()["id"],
    )

    assert body["status"] == "rejected" and body["verification_level"] is None
    assert "John Doe" in body["decision"]


async def test_image_certificate_goes_to_vision_and_is_sanitised(
    client: AsyncClient, catalog: dict[str, Skill]
) -> None:
    ai, _, storage = wire({**FIELDS, "verification_url": None}, {})
    headers = await signup(client)

    response = await upload(
        client,
        headers,
        png_bytes((2400, 1600), exif=True),
        "image/jpeg",
        name="cert.jpg",
        skill_ids=[str(catalog["python"].id)],
    )

    body = await detail(client, headers, response.json()["id"])
    assert body["report"]["certificate"]["text_source"] == "vision"
    (image,) = ai.requests[0].images
    assert image.media_type == "image/jpeg" and image.data.startswith(b"\xff\xd8")
    (stored, content_type) = next(iter(storage.files.values()))
    assert content_type == "image/jpeg" and b"SecretCamera" not in stored
    assert body["verification_level"] == "self_reported"  # credential ID but no link


async def test_certificate_upload_validation(
    client: AsyncClient, catalog: dict[str, Skill]
) -> None:
    wire(FIELDS, {})
    headers = await signup(client)

    wrong = await upload(client, headers, b"GIF89a....", "image/gif", name="c.gif")
    big = await upload(client, headers, b"%PDF-" + b"0" * (5 * 1024 * 1024), "application/pdf")
    spoofed = await upload(client, headers, b"%PDF-1.7 x", "image/png", name="c.png")
    json_cert = await client.post(
        "/api/proofs", json={"type": "certificate", "url": "x"}, headers=headers
    )

    assert (wrong.status_code, big.status_code, spoofed.status_code, json_cert.status_code) == (
        415,
        413,
        415,
        422,
    )


# --- live links end to end ----------


async def make_github_proof(db_session: AsyncSession, email: str, status: ProofStatus) -> str:
    user = await db_session.scalar(select(User).where(User.email == email))
    assert user
    proof = Proof(
        user_id=user.id,
        type=ProofType.GITHUB_REPO,
        url="https://github.com/ada/tracker",
        status=status,
        ai_report=ProofReport(repo=repo_facts()),
    )
    db_session.add(proof)
    await db_session.commit()
    return str(proof.id)


async def test_live_link_tied_to_verified_repo(
    client: AsyncClient, db_session: AsyncSession, catalog: dict[str, Skill]
) -> None:
    site = "https://tracker.dev"
    _, fetcher, _ = wire(
        FIELDS,
        {
            site: page(
                site,
                '<title>Habit Tracker</title><a href="https://github.com/ada/tracker">Source</a>',
            )
        },
    )
    headers = await signup(client, "live@example.com")
    repo_id = await make_github_proof(db_session, "live@example.com", ProofStatus.VERIFIED)

    response = await client.post(
        "/api/proofs",
        json={"type": "live_link", "url": "tracker.dev", "linked_proof_id": repo_id},
        headers=headers,
    )

    assert response.status_code == 202, response.text
    body = await detail(client, headers, response.json()["id"])
    assert body["verification_level"] == "verified" and body["status"] == "verified"
    live = body["report"]["live"]
    assert (
        live["title"] == "Habit Tracker" and live["https"] and live["linked_repo"] == "ada/tracker"
    )
    assert body["linked_proof_id"] == repo_id


async def test_live_link_levels_end_to_end(
    client: AsyncClient, db_session: AsyncSession, catalog: dict[str, Skill]
) -> None:
    wire(
        FIELDS,
        {
            "https://solo.dev": page("https://solo.dev", "<title>Solo</title>"),
            "https://down.dev": FetchFailedError("The site didn't respond within 10 seconds."),
            "http://10.0.0.1": BlockedUrlError("That link points to a private address."),
        },
    )
    headers = await signup(client, "live2@example.com")

    async def level(url: str) -> tuple[str, str | None]:
        proof_id = (
            await client.post(
                "/api/proofs", json={"type": "live_link", "url": url}, headers=headers
            )
        ).json()["id"]
        body = await detail(client, headers, proof_id)
        return body["status"], body["verification_level"]

    assert await level("https://solo.dev") == ("needs_more", "self_reported")
    assert await level("https://down.dev") == ("needs_more", None)
    assert await level("http://10.0.0.1") == ("rejected", None)


async def test_live_link_cannot_borrow_someone_elses_repo(
    client: AsyncClient, db_session: AsyncSession, catalog: dict[str, Skill]
) -> None:
    wire(FIELDS, {})
    await signup(client, "owner-live@example.com")
    theirs = await make_github_proof(db_session, "owner-live@example.com", ProofStatus.VERIFIED)
    headers = await signup(client, "thief-live@example.com")

    response = await client.post(
        "/api/proofs",
        json={"type": "live_link", "url": "https://x.dev", "linked_proof_id": theirs},
        headers=headers,
    )
    bad_url = await client.post(
        "/api/proofs", json={"type": "live_link", "url": "not a url"}, headers=headers
    )

    assert response.status_code == 422 and "your own" in response.json()["detail"]
    assert bad_url.status_code == 422
