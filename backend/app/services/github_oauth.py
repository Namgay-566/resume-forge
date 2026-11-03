"""Minimal GitHub OAuth client (authorization code flow)."""

from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.services.auth_service import GitHubProfile

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
API_URL = "https://api.github.com"
SCOPES = "read:user user:email"


class GitHubOAuthError(Exception):
    pass


def authorize_url(state: str) -> str:
    settings = get_settings()
    query = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": SCOPES,
        "state": state,
        "allow_signup": "true",
    }
    return f"{AUTHORIZE_URL}?{urlencode(query)}"


async def fetch_profile(code: str) -> GitHubProfile:
    settings = get_settings()
    assert settings.github_client_secret is not None
    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.post(
            TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret.get_secret_value(),
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
        )
        access_token = token_response.json().get("access_token")
        if token_response.status_code != 200 or not access_token:
            raise GitHubOAuthError("code exchange failed")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }
        user_response = await client.get(f"{API_URL}/user", headers=headers)
        emails_response = await client.get(f"{API_URL}/user/emails", headers=headers)
        if user_response.status_code != 200:
            raise GitHubOAuthError("could not load GitHub profile")

    user = user_response.json()
    emails = emails_response.json() if emails_response.status_code == 200 else []
    verified_email = next(
        (e["email"] for e in emails if e.get("primary") and e.get("verified")), None
    )
    return GitHubProfile(
        id=int(user["id"]),
        login=user["login"],
        name=user.get("name"),
        verified_email=verified_email,
    )
