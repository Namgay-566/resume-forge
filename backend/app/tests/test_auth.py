from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.auth import REFRESH_COOKIE
from app.models import RefreshToken, User
from app.services.auth_service import AuthService, GitHubProfile

NEW_USER = {"email": "Ada@Example.com", "password": "correct horse battery", "name": "Ada"}


async def register(client: AsyncClient, **overrides: str) -> dict[str, object]:
    response = await client.post("/api/auth/register", json={**NEW_USER, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def auth_header(token: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- register ---------------------------------------------------------------


async def test_register_returns_token_user_and_refresh_cookie(client: AsyncClient) -> None:
    response = await client.post("/api/auth/register", json=NEW_USER)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "ada@example.com"
    assert "hashed_password" not in body["user"]

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{REFRESH_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "Path=/api/auth" in cookie


async def test_register_hashes_password(client: AsyncClient, db_session: AsyncSession) -> None:
    await register(client)

    user = await db_session.scalar(select(User))
    assert user is not None
    assert user.hashed_password is not None
    assert user.hashed_password.startswith("$argon2")
    assert NEW_USER["password"] not in user.hashed_password


async def test_register_rejects_duplicate_email_case_insensitively(client: AsyncClient) -> None:
    await register(client)

    response = await client.post(
        "/api/auth/register", json={**NEW_USER, "email": "ADA@example.com"}
    )

    assert response.status_code == 409


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post("/api/auth/register", json={**NEW_USER, "password": "short"})

    assert response.status_code == 422


async def test_register_rejects_invalid_email(client: AsyncClient) -> None:
    response = await client.post("/api/auth/register", json={**NEW_USER, "email": "not-an-email"})

    assert response.status_code == 422


# --- login ------------------------------------------------------------------


async def test_login_with_correct_password(client: AsyncClient) -> None:
    await register(client)

    response = await client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": NEW_USER["password"]}
    )

    assert response.status_code == 200
    assert response.json()["user"]["name"] == "Ada"
    assert REFRESH_COOKIE in response.cookies


async def test_login_wrong_password_and_unknown_email_look_identical(client: AsyncClient) -> None:
    await register(client)

    wrong_password = await client.post(
        "/api/auth/login", json={"email": NEW_USER["email"], "password": "wrong password"}
    )
    unknown_email = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "wrong password"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


async def test_github_only_user_cannot_password_login(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await AuthService(db_session).login_with_github(
        GitHubProfile(id=1, login="octocat", name=None, verified_email="octo@example.com")
    )

    response = await client.post(
        "/api/auth/login", json={"email": "octo@example.com", "password": "anything at all"}
    )

    assert response.status_code == 401


# --- me ---------------------------------------------------------------------


async def test_me_returns_current_user(client: AsyncClient) -> None:
    token = (await register(client))["access_token"]

    response = await client.get("/api/me", headers=auth_header(token))

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


async def test_me_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get("/api/me", headers=auth_header("not.a.jwt"))

    assert response.status_code == 401


async def test_me_rejects_expired_token(client: AsyncClient, monkeypatch: object) -> None:
    import jwt

    from app.core.config import get_settings

    settings = get_settings()
    user_id = (await register(client))["user"]["id"]  # type: ignore[index]
    past = datetime.now(UTC) - timedelta(hours=1)
    expired = jwt.encode(
        {"sub": user_id, "type": "access", "iat": past, "exp": past + timedelta(minutes=1)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get("/api/me", headers=auth_header(expired))

    assert response.status_code == 401


# --- refresh / logout -------------------------------------------------------


async def test_refresh_rotates_the_cookie(client: AsyncClient) -> None:
    await register(client)
    first_cookie = client.cookies[REFRESH_COOKIE]

    response = await client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert client.cookies[REFRESH_COOKIE] != first_cookie
    me = await client.get("/api/me", headers=auth_header(response.json()["access_token"]))
    assert me.status_code == 200


async def test_refresh_without_cookie_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/auth/refresh")

    assert response.status_code == 401


async def test_reused_old_refresh_token_revokes_all_sessions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(client)
    stolen = client.cookies[REFRESH_COOKIE]
    await client.post("/api/auth/refresh")
    # Push the rotation outside the grace window, as if the thief replays it later.
    await db_session.execute(
        update(RefreshToken)
        .where(RefreshToken.revoked_at.is_not(None))
        .values(revoked_at=datetime.now(UTC) - timedelta(minutes=5))
    )
    await db_session.commit()
    current = client.cookies[REFRESH_COOKIE]

    client.cookies.set(REFRESH_COOKIE, stolen, path="/api/auth")
    replay = await client.post("/api/auth/refresh")
    client.cookies.set(REFRESH_COOKIE, current, path="/api/auth")
    legit = await client.post("/api/auth/refresh")

    assert replay.status_code == 401
    assert legit.status_code == 401


async def test_concurrent_refresh_with_same_cookie_is_allowed(client: AsyncClient) -> None:
    """Two tabs refreshing at once send the same cookie; neither should be logged out."""
    await register(client)
    shared = client.cookies[REFRESH_COOKIE]

    first = await client.post("/api/auth/refresh")
    client.cookies.set(REFRESH_COOKIE, shared, path="/api/auth")
    second = await client.post("/api/auth/refresh")

    assert first.status_code == second.status_code == 200


async def test_logout_invalidates_refresh_token(client: AsyncClient) -> None:
    await register(client)
    token = client.cookies[REFRESH_COOKIE]

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    client.cookies.set(REFRESH_COOKIE, token, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401


# --- GitHub account linking -------------------------------------------------


async def test_github_login_links_existing_account_by_verified_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id = (await register(client))["user"]["id"]  # type: ignore[index]

    user = await AuthService(db_session).login_with_github(
        GitHubProfile(id=42, login="ada-gh", name="Ada L", verified_email="ada@example.com")
    )

    assert str(user.id) == user_id
    assert user.github_username == "ada-gh"


async def test_github_login_updates_renamed_username(db_session: AsyncSession) -> None:
    service = AuthService(db_session)
    first = await service.login_with_github(
        GitHubProfile(id=7, login="old-name", name=None, verified_email=None)
    )

    again = await service.login_with_github(
        GitHubProfile(id=7, login="new-name", name=None, verified_email=None)
    )

    assert again.id == first.id
    assert again.github_username == "new-name"
    assert again.email == "7+old-name@users.noreply.github.com"
