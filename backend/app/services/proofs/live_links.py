"""Live project links: is the site up, what is it, and is it tied to verified code?"""

from dataclasses import dataclass
from urllib.parse import urlsplit

from app.schemas.proof_report import LiveLinkInfo, RepoFacts, VerificationLevel
from app.services.web.fetch import PageMeta


@dataclass(frozen=True)
class LiveOutcome:
    level: VerificationLevel | None  # None = not reachable
    reason: str


def _host(url: str | None) -> str:
    return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")


def find_connection(site_url: str, page: PageMeta, repo: RepoFacts | None) -> str | None:
    """Evidence that the site and the linked repository belong together."""
    if repo is None:
        return None
    if repo.homepage and _host(repo.homepage) and _host(repo.homepage) == _host(site_url):
        return f"{repo.full_name} lists this site as its website on GitHub."
    repo_path = f"github.com/{repo.full_name}".lower()
    if any(repo_path in link.lower() for link in page.links):
        return f"The site links to {repo.full_name}."
    return None


def decide_live(info: LiveLinkInfo) -> LiveOutcome:
    if not info.reachable:
        return LiveOutcome(
            None, "The site couldn't be reached. Check the link works in a private browser window."
        )
    if not info.linked_repo:
        return LiveOutcome(
            "self_reported",
            "The site is live. Link it to a GitHub proof so we can connect it to code you wrote.",
        )
    if info.linked_repo_verified and info.connection:
        return LiveOutcome("verified", f"Live, and tied to your verified repo: {info.connection}")
    if info.linked_repo_verified:
        return LiveOutcome(
            "partially_verified",
            f"Live, and {info.linked_repo} is verified, but nothing ties the two together. Add the "
            "site as the repo's website on GitHub, or link to the repo from the site.",
        )
    if info.connection:
        return LiveOutcome(
            "partially_verified",
            f"Live and connected to {info.linked_repo}, but that repo isn't verified yet.",
        )
    return LiveOutcome(
        "self_reported",
        f"The site is live, but it isn't tied to {info.linked_repo} and that repo isn't verified.",
    )
