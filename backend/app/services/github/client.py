"""Thin async client for the GitHub REST API calls the proof analyzer needs."""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.core.config import get_settings

API = "https://api.github.com"
API_VERSION = "2022-11-28"
_LAST_PAGE = re.compile(r'[?&]page=(\d+)>;\s*rel="last"')


class GitHubError(Exception):
    """Base for GitHub failures. `str(exc)` is safe to show to the user."""


class RepoNotFoundError(GitHubError):
    pass


class GitHubRateLimitedError(GitHubError):
    pass


class GitHubUnavailableError(GitHubError):
    pass


@dataclass(frozen=True)
class TreeEntry:
    path: str
    size: int


class GitHubAPI(Protocol):
    """What the analyzer uses. Implemented by GitHubClient; tests provide a fake."""

    async def repo(self, owner: str, name: str) -> dict[str, Any]: ...
    async def languages(self, owner: str, name: str) -> dict[str, int]: ...
    async def readme(self, owner: str, name: str) -> str | None: ...
    async def tree(self, owner: str, name: str, ref: str) -> tuple[list[TreeEntry], bool]: ...
    async def commit_count(self, owner: str, name: str) -> int: ...
    async def recent_commits(
        self, owner: str, name: str, limit: int = 100
    ) -> list[dict[str, Any]]: ...
    async def contributors(self, owner: str, name: str) -> list[dict[str, Any]]: ...
    async def file(self, owner: str, name: str, path: str, ref: str) -> str | None: ...
    async def ahead_of_parent(
        self, owner: str, name: str, branch: str, parent_owner: str, parent_branch: str
    ) -> int | None: ...


class GitHubClient:
    def __init__(self, token: str | None, timeout: float = 20) -> None:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.AsyncClient(base_url=API, headers=headers, timeout=timeout)

    async def _get(self, path: str, *, raw: bool = False, **params: Any) -> httpx.Response:
        headers = {"Accept": "application/vnd.github.raw+json"} if raw else None
        try:
            response = await self._http.get(path, params=params or None, headers=headers)
        except httpx.HTTPError as exc:
            raise GitHubUnavailableError(
                "Couldn't reach GitHub. Try again in a few minutes."
            ) from exc
        if response.status_code in (403, 429) and (
            response.headers.get("x-ratelimit-remaining") == "0" or response.status_code == 429
        ):
            raise GitHubRateLimitedError("GitHub's rate limit was reached. Try again in an hour.")
        if response.status_code >= 500:
            raise GitHubUnavailableError("GitHub is having problems. Try again in a few minutes.")
        return response

    async def repo(self, owner: str, name: str) -> dict[str, Any]:
        response = await self._get(f"/repos/{owner}/{name}")
        if response.status_code == 404:
            raise RepoNotFoundError(
                "Repository not found. Check the URL and make sure the repo is public."
            )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def languages(self, owner: str, name: str) -> dict[str, int]:
        response = await self._get(f"/repos/{owner}/{name}/languages")
        return response.json() if response.status_code == 200 else {}

    async def readme(self, owner: str, name: str) -> str | None:
        response = await self._get(f"/repos/{owner}/{name}/readme", raw=True)
        return response.text if response.status_code == 200 else None

    async def tree(self, owner: str, name: str, ref: str) -> tuple[list[TreeEntry], bool]:
        response = await self._get(f"/repos/{owner}/{name}/git/trees/{ref}", recursive="1")
        if response.status_code != 200:
            return [], False
        body = response.json()
        entries = [
            TreeEntry(path=item["path"], size=int(item.get("size") or 0))
            for item in body.get("tree", [])
            if item.get("type") == "blob"
        ]
        return entries, bool(body.get("truncated"))

    async def commit_count(self, owner: str, name: str) -> int:
        """Total commits on the default branch, from the last-page number with 1 per page."""
        response = await self._get(f"/repos/{owner}/{name}/commits", per_page="1")
        if response.status_code == 409:  # empty repository
            return 0
        if response.status_code != 200:
            return 0
        match = _LAST_PAGE.search(response.headers.get("link", ""))
        return int(match.group(1)) if match else len(response.json())

    async def recent_commits(self, owner: str, name: str, limit: int = 100) -> list[dict[str, Any]]:
        response = await self._get(f"/repos/{owner}/{name}/commits", per_page=str(min(limit, 100)))
        return response.json() if response.status_code == 200 else []

    async def contributors(self, owner: str, name: str) -> list[dict[str, Any]]:
        response = await self._get(f"/repos/{owner}/{name}/contributors", per_page="100")
        return response.json() if response.status_code == 200 else []

    async def file(self, owner: str, name: str, path: str, ref: str) -> str | None:
        response = await self._get(f"/repos/{owner}/{name}/contents/{path}", raw=True, ref=ref)
        return response.text if response.status_code == 200 else None

    async def ahead_of_parent(
        self, owner: str, name: str, branch: str, parent_owner: str, parent_branch: str
    ) -> int | None:
        """How many commits the fork has that its parent doesn't (None if unknown)."""
        basehead = f"{parent_owner}:{parent_branch}...{owner}:{branch}"
        response = await self._get(f"/repos/{owner}/{name}/compare/{basehead}")
        if response.status_code != 200:
            return None
        return int(response.json().get("ahead_by", 0))


@lru_cache
def _default_client() -> GitHubClient:
    token = get_settings().github_api_token
    return GitHubClient(token.get_secret_value() if token else None)


def get_github_client() -> GitHubAPI:
    """FastAPI dependency; tests override it with a fake."""
    return _default_client()
