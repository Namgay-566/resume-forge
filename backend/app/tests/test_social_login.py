"""Google and LinkedIn sign-in (OpenID Connect), the same flow as GitHub: state cookie,
code exchange, find-or-link-or-create, refresh cookie. LinkedIn users get their LinkedIn
URL in new resumes' profile links once it's known."""

import json
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient, get_ai_client
from app.api.routers.auth import REFRESH_COOKIE, STATE_COOKIE
from app.core.config import get_settings
from app.main import app
from app.models import User
from app.services import oidc_oauth
from app.services.auth_service import AuthService, OidcProfile
from app.tests.fakes import FakeProvider
from app.tests.sample_cvs import NURSE_CV, NURSE_PARSED


@pytest.fixture(autouse=True)
def configured(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    settings = get_settings()
    for provider in ("google", "linkedin"):
        monkeypatch.setattr(settings, f"{provider}_client_id", f"{provider}-client")
        monkeypatch.setattr(settings, f"{provider}_client_secret", SecretStr(f"{provider}-secret"))
    yield


def fake_provider_api(monkeypatch: pytest.MonkeyPatch, userinfo: dict[str, Any]) -> list[str]:
    """Stand-in for the provider's token and userinfo endpoints."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.copy_with(query=None)}")
        if request.method == "POST":
            form = parse_qs(request.content.decode())
            if form.get("code") != ["good-code"]:
                return httpx.Response(400, json={"error": "invalid_grant"})
            assert form["grant_type"] == ["authorization_code"]
            assert form["client_secret"][0].endswith("-secret")
            return httpx.Response(200, json={"access_token": "at-1", "token_type": "Bearer"})
        assert request.headers["authorization"] == "Bearer at-1"
        return httpx.Response(200, json=userinfo)

    real = httpx.AsyncClient
    monkeypatch.setattr(
        oidc_oauth.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    return calls


async def start(client: AsyncClient, provider: str) -> str:
    response = await client.get(f"/api/auth/{provider}/login")
    assert response.status_code == 307
    return response.headers["location"]


async def finish(client: AsyncClient, provider: str, code: str = "good-code") -> httpx.Response:
    location = await start(client, provider)
    state = parse_qs(urlparse(location).query)["state"][0]
    return await client.get(f"/api/auth/{provider}/callback", params={"code": code, "state": state})


GOOGLE_USER = {
    "sub": "1099",
    "email": "Priya@Example.com",
    "email_verified": True,
    "name": "Priya Shah",
}
LINKEDIN_USER = {
    "sub": "li-abc",
    "email": "priya@example.com",
    "email_verified": True,
    "given_name": "Priya",
    "family_name": "Shah",
}


@pytest.mark.parametrize(
    ("provider", "host", "scope"),
    [
        ("google", "accounts.google.com", "openid email profile"),
        ("linkedin", "www.linkedin.com", "openid profile email"),
    ],
)
async def test_login_redirects_with_state_cookie(
    client: AsyncClient, provider: str, host: str, scope: str
) -> None:
    response = await client.get(f"/api/auth/{provider}/login")

    target = urlparse(response.headers["location"])
    query = parse_qs(target.query)
    assert target.netloc == host
    assert query["client_id"] == [f"{provider}-client"]
    assert query["scope"] == [scope]
    assert query["redirect_uri"] == [f"http://localhost:8000/api/auth/{provider}/callback"]
    cookie = response.headers["set-cookie"]
    assert f"{STATE_COOKIE}={query['state'][0]}" in cookie
    assert f"Path=/api/auth/{provider}" in cookie and "HttpOnly" in cookie


@pytest.mark.parametrize("provider", ["google", "linkedin"])
async def test_unconfigured_provider_says_so(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.setattr(get_settings(), f"{provider}_client_secret", None)

    response = await client.get(f"/api/auth/{provider}/login")

    assert response.headers["location"].endswith(f"/login?error={provider}_not_configured")


async def test_google_sign_in_creates_account_and_session(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fake_provider_api(monkeypatch, GOOGLE_USER)

    response = await finish(client, "google")

    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:5173/dashboard"
    assert REFRESH_COOKIE in response.headers.get("set-cookie", "")
    assert calls == [
        "POST https://oauth2.googleapis.com/token",
        "GET https://openidconnect.googleapis.com/v1/userinfo",
    ]
    user = await db_session.scalar(select(User).where(User.google_id == "1099"))
    assert user is not None
    assert (user.email, user.name) == ("priya@example.com", "Priya Shah")
    assert user.hashed_password is None
    # The session works.
    refreshed = await client.post("/api/auth/refresh")
    assert refreshed.status_code == 200 and refreshed.json()["user"]["name"] == "Priya Shah"


async def test_linkedin_sign_in_links_existing_account_by_verified_email(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    registered = await client.post(
        "/api/auth/register",
        json={"email": "priya@example.com", "password": "password123", "name": "Priya"},
    )
    client.cookies.clear()
    fake_provider_api(monkeypatch, LINKEDIN_USER)

    response = await finish(client, "linkedin")

    assert response.headers["location"].endswith("/dashboard")
    user = await db_session.scalar(select(User).where(User.linkedin_id == "li-abc"))
    assert user is not None and str(user.id) == registered.json()["user"]["id"]
    me = (await client.post("/api/auth/refresh")).json()["user"]
    assert me["linkedin_connected"] is True and me["linkedin_url"] is None


@pytest.mark.parametrize(
    ("code", "state_ok"),
    [("bad-code", True), ("good-code", False)],
)
async def test_failed_or_forged_callbacks_redirect_to_login(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    state_ok: bool,
) -> None:
    fake_provider_api(monkeypatch, GOOGLE_USER)
    location = await start(client, "google")
    state = parse_qs(urlparse(location).query)["state"][0] if state_ok else "forged"

    response = await client.get("/api/auth/google/callback", params={"code": code, "state": state})

    assert response.headers["location"].endswith("/login?error=google")
    assert REFRESH_COOKIE not in response.headers.get("set-cookie", "")
    assert await db_session.scalar(select(User)) is None


async def test_cancelled_linkedin_sign_in_redirects_to_login(client: AsyncClient) -> None:
    await start(client, "linkedin")

    response = await client.get(
        "/api/auth/linkedin/callback", params={"error": "user_cancelled_login", "state": "x"}
    )

    assert response.headers["location"].endswith("/login?error=linkedin")


async def test_unverified_email_never_links_an_account(db_session: AsyncSession) -> None:
    service = AuthService(db_session)
    owner = await service.register(email="priya@example.com", password="password123", name="P")

    user = await service.login_with_oidc(
        OidcProfile(provider="google", subject="g-1", name="Mallory", verified_email=None)
    )

    assert user.id != owner.id
    assert user.email == "google-g-1@users.noreply.invalid"


async def test_same_provider_account_signs_back_in(db_session: AsyncSession) -> None:
    service = AuthService(db_session)
    profile = OidcProfile(
        provider="linkedin", subject="li-1", name="Priya", verified_email="p@example.com"
    )

    first = await service.login_with_oidc(profile)
    again = await service.login_with_oidc(profile)

    assert first.id == again.id


# --- LinkedIn URL in profile links ------------------------------------------------------


async def linkedin_headers(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, **extra: Any
) -> dict[str, str]:
    fake_provider_api(monkeypatch, {**LINKEDIN_USER, **extra})
    await finish(client, "linkedin")
    token = (await client.post("/api/auth/refresh")).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def links(resume: dict[str, Any]) -> list[dict[str, str]]:
    return list(resume["data"]["personal_info"]["profile_links"])


async def test_linkedin_profile_claim_prefills_new_resumes(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await linkedin_headers(
        client, monkeypatch, profile="https://www.linkedin.com/in/priya-shah/"
    )

    resume = (await client.post("/api/resumes", json={"title": "CV"}, headers=headers)).json()

    assert links(resume) == [{"label": "LinkedIn", "url": "linkedin.com/in/priya-shah"}]


async def test_first_linkedin_url_added_is_remembered_for_new_resumes(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await linkedin_headers(client, monkeypatch)  # no profile URL from LinkedIn
    first = (await client.post("/api/resumes", json={"title": "CV"}, headers=headers)).json()
    assert links(first) == []

    data = first["data"]
    data["personal_info"]["profile_links"] = [
        {"label": "LinkedIn", "url": "linkedin.com/in/priya-shah"}
    ]
    saved = await client.patch(f"/api/resumes/{first['id']}", json={"data": data}, headers=headers)
    assert saved.status_code == 200, saved.text
    second = (await client.post("/api/resumes", json={"title": "CV 2"}, headers=headers)).json()

    assert links(second) == [{"label": "LinkedIn", "url": "linkedin.com/in/priya-shah"}]


async def test_other_users_links_are_not_remembered(client: AsyncClient) -> None:
    signup = await client.post(
        "/api/auth/register",
        json={"email": "e@example.com", "password": "password123", "name": "E"},
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    first = (await client.post("/api/resumes", json={"title": "CV"}, headers=headers)).json()
    data = first["data"]
    data["personal_info"]["profile_links"] = [{"label": "LinkedIn", "url": "linkedin.com/in/e"}]
    await client.patch(f"/api/resumes/{first['id']}", json={"data": data}, headers=headers)

    second = (await client.post("/api/resumes", json={"title": "CV 2"}, headers=headers)).json()

    assert links(second) == []


async def test_imported_cv_gets_the_linkedin_link_it_lacks(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.tests.test_import_sections import DOCX, as_docx

    headers = await linkedin_headers(
        client, monkeypatch, profile="https://www.linkedin.com/in/priya-shah"
    )
    parsed = {**NURSE_PARSED, "personal_info": {"full_name": "Priya", "profile_links": []}}
    provider = FakeProvider(json.dumps(parsed))
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)

    response = await client.post(
        "/api/resumes/import",
        files={"file": ("cv.docx", as_docx(NURSE_CV), DOCX)},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert links(response.json()["resume"]) == [
        {"label": "LinkedIn", "url": "linkedin.com/in/priya-shah"}
    ]
