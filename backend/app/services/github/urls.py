import re
from dataclasses import dataclass
from urllib.parse import urlsplit

# GitHub rules: owners are alphanumeric + single hyphens (max 39); repo names allow . _ -.
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
_REPO = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
# First path segments that are GitHub pages, not user/org names.
_RESERVED = {
    "about",
    "apps",
    "collections",
    "enterprise",
    "explore",
    "features",
    "issues",
    "login",
    "marketplace",
    "new",
    "notifications",
    "orgs",
    "pricing",
    "pulls",
    "search",
    "settings",
    "sponsors",
    "topics",
    "trending",
    "users",
}


class InvalidRepoUrlError(ValueError):
    pass


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.full_name}"


def parse_repo_url(raw: str) -> RepoRef:
    """Accept github.com repo URLs, with or without scheme, .git or paths like /tree/main."""
    text = raw.strip()
    if not text:
        raise InvalidRepoUrlError("Enter a GitHub repository URL.")
    if "://" not in text:
        text = f"https://{text}"
    parts = urlsplit(text)
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or host not in {"github.com", "www.github.com"}:
        raise InvalidRepoUrlError(
            "Use a github.com repository URL, e.g. https://github.com/you/project."
        )
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) < 2:
        raise InvalidRepoUrlError(
            "That's not a repository URL. It should look like github.com/owner/repo."
        )
    owner, name = segments[0], segments[1].removesuffix(".git")
    if (
        owner.lower() in _RESERVED
        or not _OWNER.match(owner)
        or not _REPO.match(name)
        or name in {".", ".."}
    ):
        raise InvalidRepoUrlError("That's not a valid GitHub repository URL.")
    return RepoRef(owner=owner, name=name)
