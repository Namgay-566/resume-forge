"""Google and LinkedIn sign-in: OpenID Connect over the authorization code flow, the same
shape as github_oauth.py (authorize URL -> code exchange -> profile)."""

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode

import httpx
from pydantic import SecretStr

from app.core.config import get_settings
from app.services.auth_service import OidcProfile

OidcProviderName = Literal["google", "linkedin"]


class OidcOAuthError(Exception):
    pass


@dataclass(frozen=True)
class OidcProvider:
    name: OidcProviderName
    label: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: str
    # Extra authorize-URL parameters (e.g. Google's account picker).
    extra: tuple[tuple[str, str], ...] = ()


PROVIDERS: dict[OidcProviderName, OidcProvider] = {
    "google": OidcProvider(
        name="google",
        label="Google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scopes="openid email profile",
        extra=(("prompt", "select_account"),),
    ),
    # "Sign In with LinkedIn using OpenID Connect" product on the LinkedIn app.
    "linkedin": OidcProvider(
        name="linkedin",
        label="LinkedIn",
        authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        token_url="https://www.linkedin.com/oauth/v2/accessToken",
        userinfo_url="https://api.linkedin.com/v2/userinfo",
        scopes="openid profile email",
    ),
}


def _credentials(provider: OidcProvider) -> tuple[str, SecretStr, str]:
    settings = get_settings()
    client_id = getattr(settings, f"{provider.name}_client_id")
    secret = getattr(settings, f"{provider.name}_client_secret")
    redirect_uri = getattr(settings, f"{provider.name}_redirect_uri")
    assert client_id and secret is not None
    return client_id, secret, redirect_uri


def is_enabled(provider: OidcProvider) -> bool:
    return bool(getattr(get_settings(), f"{provider.name}_enabled"))


def authorize_url(provider: OidcProvider, state: str) -> str:
    client_id, _, redirect_uri = _credentials(provider)
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": provider.scopes,
        "state": state,
        **dict(provider.extra),
    }
    return f"{provider.authorize_url}?{urlencode(query)}"


def _profile_url(value: object) -> str | None:
    """The standard OIDC `profile` claim (the person's profile page), if it's a web URL.
    LinkedIn's userinfo doesn't include it today, so this is usually None."""
    if isinstance(value, str) and value.startswith("https://"):
        return value[:200]
    return None


async def fetch_profile(provider: OidcProvider, code: str) -> OidcProfile:
    client_id, secret, redirect_uri = _credentials(provider)
    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post(
            provider.token_url,
            headers={"Accept": "application/json"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": secret.get_secret_value(),
                "redirect_uri": redirect_uri,
            },
        )
        access_token = (
            token_response.json().get("access_token") if token_response.status_code == 200 else None
        )
        if not access_token:
            raise OidcOAuthError("code exchange failed")
        info_response = await client.get(
            provider.userinfo_url, headers={"Authorization": f"Bearer {access_token}"}
        )
    if info_response.status_code != 200:
        raise OidcOAuthError(f"could not load the {provider.label} profile")

    info = info_response.json()
    subject = str(info.get("sub") or "")
    if not subject:
        raise OidcOAuthError(f"{provider.label} returned no account id")
    email = info.get("email")
    verified = info.get("email_verified") in (True, "true")
    name = info.get("name") or " ".join(
        p for p in (info.get("given_name"), info.get("family_name")) if p
    )
    return OidcProfile(
        provider=provider.name,
        subject=subject[:255],
        name=(name or None) and str(name)[:200],
        verified_email=str(email) if email and verified else None,
        profile_url=_profile_url(info.get("profile")),
    )
