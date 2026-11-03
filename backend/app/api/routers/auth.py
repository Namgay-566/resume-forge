import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated

import httpx
from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.ai.rate_limit import auth_rate_limit, refresh_rate_limit
from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.security import new_oauth_state
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services import github_oauth, oidc_oauth
from app.services.account_service import AccountService, ProviderInUseError
from app.services.auth_service import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    IssuedTokens,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "rf_refresh"
# The browser only sends the refresh cookie to auth endpoints, never to the rest of the API.
REFRESH_COOKIE_PATH = "/api/auth"
STATE_COOKIE = "rf_oauth_state"

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _set_refresh_cookie(response: Response, tokens: IssuedTokens) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        expires=tokens.refresh_expires_at,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite=get_settings().cookie_samesite,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite=get_settings().cookie_samesite,
    )


def check_origin(request: Request) -> None:
    """Cookie-authenticated endpoints only accept requests from our own frontend (CSRF).
    Browsers always send Origin on cross-site POSTs; non-browser clients may omit it."""
    origin = request.headers.get("origin")
    if origin is not None and origin not in get_settings().cors_origin_list:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed")


def token_response(response: Response, user: User, tokens: IssuedTokens) -> TokenResponse:
    _set_refresh_cookie(response, tokens)
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@auth_rate_limit
async def register(
    request: Request, body: RegisterRequest, response: Response, session: SessionDep
) -> TokenResponse:
    service = AuthService(session)
    try:
        user = await service.register(email=body.email, password=body.password, name=body.name)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered") from exc
    return token_response(response, user, await service.issue_tokens(user))


@router.post("/login", response_model=TokenResponse)
@auth_rate_limit
async def login(
    request: Request, body: LoginRequest, response: Response, session: SessionDep
) -> TokenResponse:
    service = AuthService(session)
    try:
        user = await service.authenticate(email=body.email, password=body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password") from exc
    return token_response(response, user, await service.issue_tokens(user))


@router.post("/refresh", response_model=TokenResponse)
@refresh_rate_limit
async def refresh(
    request: Request, response: Response, session: SessionDep, refresh_token: RefreshCookie = None
) -> TokenResponse:
    check_origin(request)
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token")
    try:
        user, tokens = await AuthService(session).refresh(refresh_token)
    except InvalidRefreshTokenError as exc:
        # FastAPI discards `response` when raising, so the clearing header goes on the error.
        cleared = Response()
        clear_refresh_cookie(cleared)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired refresh token",
            headers={"set-cookie": cleared.headers["set-cookie"]},
        ) from exc
    return token_response(response, user, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, response: Response, session: SessionDep, refresh_token: RefreshCookie = None
) -> None:
    check_origin(request)
    if refresh_token:
        await AuthService(session).logout(refresh_token)
    clear_refresh_cookie(response)


def _state_cookie_path(provider: str) -> str:
    return f"/api/auth/{provider}"


# A state starting with this connects the provider to the signed-in account (Settings)
# instead of signing in. Only our own cookie decides the mode; the provider echoes state.
LINK_STATE_PREFIX = "link."


def _start_oauth(
    provider: str, authorize: Callable[[str], str], *, link: bool = False
) -> RedirectResponse:
    """Redirect to the provider with a fresh state, kept in a short-lived cookie."""
    state = (LINK_STATE_PREFIX if link else "") + new_oauth_state()
    response = RedirectResponse(authorize(state))
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        path=_state_cookie_path(provider),
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
    )
    return response


def _oauth_failure(provider: str) -> RedirectResponse:
    failure = RedirectResponse(f"{get_settings().frontend_url}/login?error={provider}")
    failure.delete_cookie(STATE_COOKIE, path=_state_cookie_path(provider))
    return failure


def _settings_redirect(provider: str, outcome: str) -> RedirectResponse:
    """Back to Settings after connecting: ?connected=github or ?connect_error=in_use."""
    response = RedirectResponse(f"{get_settings().frontend_url}/settings?{outcome}")
    response.delete_cookie(STATE_COOKIE, path=_state_cookie_path(provider))
    return response


def _state_ok(state: str | None, expected: str | None) -> bool:
    return bool(state and expected and secrets.compare_digest(state, expected))


def _is_link(expected_state: str | None) -> bool:
    return bool(expected_state and expected_state.startswith(LINK_STATE_PREFIX))


async def _signed_in(provider: str, service: AuthService, user: User) -> RedirectResponse:
    # The frontend picks up the session by calling /auth/refresh with this cookie.
    success = RedirectResponse(f"{get_settings().frontend_url}/dashboard")
    success.delete_cookie(STATE_COOKIE, path=_state_cookie_path(provider))
    _set_refresh_cookie(success, await service.issue_tokens(user))
    return success


async def _linked(
    provider: str,
    session: SessionDep,
    refresh_token: str | None,
    link: Callable[[AccountService, User], Awaitable[User]],
) -> RedirectResponse:
    """Attach the provider account to whoever the refresh cookie belongs to."""
    user = await AuthService(session).user_for_refresh_token(refresh_token or "")
    if user is None:
        return _settings_redirect(provider, f"connect_error={provider}_session")
    try:
        await link(AccountService(session), user)
    except ProviderInUseError:
        return _settings_redirect(provider, "connect_error=in_use")
    return _settings_redirect(provider, f"connected={provider}")


StateCookie = Annotated[str | None, Cookie(alias=STATE_COOKIE)]
LinkQuery = Annotated[bool, Query(description="Connect to the signed-in account (Settings)")]


@router.get("/github/login", include_in_schema=True)
async def github_login(link: LinkQuery = False) -> RedirectResponse:
    settings = get_settings()
    if not settings.github_enabled:
        page = "settings?connect_error=" if link else "login?error="
        return RedirectResponse(f"{settings.frontend_url}/{page}github_not_configured")
    return _start_oauth("github", github_oauth.authorize_url, link=link)


@router.get("/github/callback")
async def github_callback(
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    expected_state: StateCookie = None,
    refresh_token: RefreshCookie = None,
) -> RedirectResponse:
    link = _is_link(expected_state)
    if not get_settings().github_enabled or not code or not _state_ok(state, expected_state):
        return (
            _settings_redirect("github", "connect_error=github")
            if link
            else _oauth_failure("github")
        )
    try:
        profile = await github_oauth.fetch_profile(code)
    except github_oauth.GitHubOAuthError:
        return (
            _settings_redirect("github", "connect_error=github")
            if link
            else _oauth_failure("github")
        )
    if link:
        return await _linked(
            "github",
            session,
            refresh_token,
            lambda account, user: account.link_github(user, profile),
        )
    service = AuthService(session)
    return await _signed_in("github", service, await service.login_with_github(profile))


async def _oidc_login(name: oidc_oauth.OidcProviderName, link: bool) -> RedirectResponse:
    provider = oidc_oauth.PROVIDERS[name]
    if not oidc_oauth.is_enabled(provider):
        page = "settings?connect_error=" if link else "login?error="
        return RedirectResponse(f"{get_settings().frontend_url}/{page}{name}_not_configured")
    return _start_oauth(name, lambda state: oidc_oauth.authorize_url(provider, state), link=link)


async def _oidc_callback(
    name: oidc_oauth.OidcProviderName,
    session: SessionDep,
    code: str | None,
    state: str | None,
    expected_state: str | None,
    refresh_token: str | None,
) -> RedirectResponse:
    provider = oidc_oauth.PROVIDERS[name]
    link = _is_link(expected_state)

    def failure() -> RedirectResponse:
        return _settings_redirect(name, f"connect_error={name}") if link else _oauth_failure(name)

    if not oidc_oauth.is_enabled(provider) or not code or not _state_ok(state, expected_state):
        return failure()
    try:
        profile = await oidc_oauth.fetch_profile(provider, code)
    except (oidc_oauth.OidcOAuthError, httpx.HTTPError, ValueError):
        return failure()
    if link:
        return await _linked(
            name, session, refresh_token, lambda account, user: account.link_oidc(user, profile)
        )
    service = AuthService(session)
    return await _signed_in(name, service, await service.login_with_oidc(profile))


@router.get("/google/login")
async def google_login(link: LinkQuery = False) -> RedirectResponse:
    return await _oidc_login("google", link)


@router.get("/google/callback")
async def google_callback(
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    expected_state: StateCookie = None,
    refresh_token: RefreshCookie = None,
) -> RedirectResponse:
    return await _oidc_callback("google", session, code, state, expected_state, refresh_token)


@router.get("/linkedin/login")
async def linkedin_login(link: LinkQuery = False) -> RedirectResponse:
    return await _oidc_login("linkedin", link)


@router.get("/linkedin/callback")
async def linkedin_callback(
    session: SessionDep,
    code: str | None = None,
    state: str | None = None,
    expected_state: StateCookie = None,
    refresh_token: RefreshCookie = None,
) -> RedirectResponse:
    # A cancelled sign-in comes back with ?error=... and no code: a failure redirect.
    return await _oidc_callback("linkedin", session, code, state, expected_state, refresh_token)
