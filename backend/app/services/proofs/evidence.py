"""Decisions for non-code proof: licences, portfolios, work samples, publications and
letters. Pure functions (no DB, network or AI).

The one rule everywhere: a level is only as high as what we could check ourselves.
- Verified: an independent source confirms it (the licensing body's public register shows
  the licence, the DOI registry lists the user as an author).
- Partially verified: something real checked out, but not everything (the register page
  loads but doesn't show the number; a portfolio page shows the user's name).
- Self-reported: we couldn't check it (a work sample, a reference letter), however good it is.
"""

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import unquote, urlsplit

from app.schemas.proof_report import (
    LetterInfo,
    LicenseInfo,
    NameMatch,
    PortfolioInfo,
    PublicationInfo,
    SkillVerdict,
    VerificationLevel,
    WorkSampleInfo,
)
from app.services.proofs.certificates import match_name

EXPIRY_WARNING_DAYS = 90


@dataclass(frozen=True)
class Outcome:
    # None: the proof can't count (rejected, or e.g. an expired licence).
    level: VerificationLevel | None
    reason: str
    rejected: bool = False


# --- dates ------------------------------------------------------------------------------

_DATE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?$")


def parse_date(value: str | None, *, end_of_month: bool = False) -> date | None:
    """'2027-03-31' or '2027-03' (a month-only expiry runs to the month's end)."""
    match = _DATE.match((value or "").strip())
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if match.group(3):
        try:
            return date(year, month, int(match.group(3)))
        except ValueError:
            return None
    if not end_of_month:
        return date(year, month, 1)
    next_month = date(year + month // 12, month % 12 + 1, 1)
    return date.fromordinal(next_month.toordinal() - 1)


def check_expiry(info: LicenseInfo, today: date) -> None:
    expiry = parse_date(info.expiry_date, end_of_month=True)
    if info.expiry_date and expiry is None:
        info.expiry_detail = f"The expiry date ({info.expiry_date}) couldn't be read."
        return
    if expiry is None:
        info.expiry_detail = "No expiry date is shown. Some licences don't expire; check yours."
        return
    days = (expiry - today).days
    info.expired = days < 0
    info.expires_soon = 0 <= days <= EXPIRY_WARNING_DAYS
    if info.expired:
        info.expiry_detail = f"Expired on {expiry.isoformat()}."
    elif info.expires_soon:
        info.expiry_detail = f"Expires on {expiry.isoformat()}, in {days} days. Renew it soon."
    else:
        info.expiry_detail = f"Valid until {expiry.isoformat()}."


# --- licences -----------------------------------------------------------------------------


def decide_license(info: LicenseInfo) -> Outcome:
    if not info.is_license:
        return Outcome(
            None,
            "This doesn't look like a licence or registration. Upload course certificates "
            "as certificates.",
            rejected=True,
        )
    name = info.name_match
    if name and name.status == "mismatch":
        return Outcome(None, name.detail + " Upload a licence issued to you.", rejected=True)
    if info.expired:
        return Outcome(
            None, f"This licence has expired ({info.expiry_detail}) Upload your current licence."
        )
    body = info.issuing_body or "the issuing body"
    check = info.register_check
    if check and check.reachable and check.on_trusted_domain:
        if check.details_on_page and name and name.status == "match":
            return Outcome("verified", f"Confirmed on {body}'s public register.")
        why = (
            "the page doesn't show your licence number or name (registers often need a search)"
            if not check.details_on_page
            else "the name on the licence is only a partial match for yours"
        )
        return Outcome("partially_verified", f"The register link works, but {why}.")
    if check and check.reachable:
        return Outcome(
            "self_reported",
            f"The register link isn't on {body}'s website or a government domain, so it can't "
            "confirm the licence.",
        )
    if check:
        return Outcome("self_reported", f"The register link couldn't be checked: {check.detail}")
    number = f" (number {info.license_number})" if info.license_number else ""
    return Outcome(
        "self_reported",
        f"Recorded as self-reported. Employers can check your licence{number} on {body}'s "
        "public register. Add a link to your register entry to have it verified.",
    )


# --- portfolios ---------------------------------------------------------------------------

PLATFORMS = {
    "behance.net": "Behance",
    "dribbble.com": "Dribbble",
    "medium.com": "Medium",
    "substack.com": "Substack",
    "artstation.com": "ArtStation",
    "vimeo.com": "Vimeo",
    "youtube.com": "YouTube",
    "flickr.com": "Flickr",
    "issuu.com": "Issuu",
    "wordpress.com": "WordPress",
    "wixsite.com": "Wix",
    "squarespace.com": "Squarespace",
    "notion.site": "Notion",
    "canva.site": "Canva",
    "carrd.co": "Carrd",
    "muckrack.com": "Muck Rack",
    "contently.com": "Contently",
    "clippings.me": "Clippings.me",
}


def portfolio_platform(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    for domain, name in PLATFORMS.items():
        if host == domain or host.endswith(f".{domain}"):
            return name
    return None


def _demonstrated(skills: list[SkillVerdict]) -> list[str]:
    return [s.name for s in skills if s.verdict == "demonstrated"]


def decide_portfolio(
    info: PortfolioInfo, skills: list[SkillVerdict], reviewed: bool, injected: bool
) -> Outcome:
    """Never 'verified': a public page can't prove who made the work."""
    if not info.reachable:
        return Outcome(None, "The page couldn't be reached. Check it's public, then re-run.")
    if injected:
        return Outcome(
            "self_reported",
            "The page contains text aimed at the AI reviewer, so its review can't be trusted. "
            "Remove it and re-run the analysis.",
        )
    shown = _demonstrated(skills)
    if not reviewed:
        return Outcome(
            "self_reported", "The page is live, but the review couldn't run. Re-run it later."
        )
    if info.name_on_page and shown:
        return Outcome(
            "partially_verified",
            f"The page is live, shows your name and demonstrates {', '.join(shown)}. It can't be "
            "fully verified: a public page can't prove who made the work.",
        )
    if not info.name_on_page:
        return Outcome(
            "self_reported",
            "The page is live, but your name isn't on it, so the work can't be tied to you. "
            "Add your name to the page.",
        )
    return Outcome(
        "self_reported",
        "The page is live and shows your name, but the reviewer didn't find clear evidence "
        "of the skills you picked.",
    )


# --- work samples ---------------------------------------------------------------------------


def decide_work_sample(info: WorkSampleInfo, skills: list[SkillVerdict]) -> Outcome:
    """Always self-reported when accepted: nobody can confirm who produced an uploaded file."""
    if not info.is_work_sample:
        return Outcome(
            None, "This doesn't look like a piece of work. Upload the work itself.", rejected=True
        )
    shown = _demonstrated(skills)
    what = info.kind or "work sample"
    if shown:
        return Outcome(
            "self_reported",
            f"Reviewed as {what}: it demonstrates {', '.join(shown)}. It counts as "
            "self-reported because we can't confirm you produced it.",
        )
    return Outcome(
        "self_reported",
        f"Reviewed as {what}, but it doesn't clearly show the skills you picked. It counts as "
        "self-reported either way.",
    )


# --- publications -----------------------------------------------------------------------------

_DOI = re.compile(r"(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)


def parse_doi(raw: str) -> str | None:
    """'10.1234/abc', 'doi:10.1234/abc' or 'https://doi.org/10.1234/abc' -> '10.1234/abc'."""
    text = unquote(raw.strip())
    match = _DOI.search(text)
    return match.group(1).rstrip(".,;)").lower() if match else None


def best_author_match(authors: list[str], account_name: str) -> tuple[NameMatch, str | None]:
    """The strongest match between the account name and any listed author."""
    if not authors:
        return NameMatch(status="missing", detail="No authors are listed."), None
    rank = {"match": 0, "partial": 1, "mismatch": 2, "missing": 3}
    scored = sorted(
        ((match_name(author, account_name), author) for author in authors),
        key=lambda pair: rank[pair[0].status],
    )
    best, author = scored[0]
    if best.status == "match":
        return NameMatch(status="match", detail=f"You're listed as an author ({author})."), author
    if best.status == "partial":
        return (
            NameMatch(status="partial", detail=f"“{author}” is similar to your name."),
            author,
        )
    listed = ", ".join(authors[:6]) + ("…" if len(authors) > 6 else "")
    detail = f"Your name isn't among the authors: {listed}."
    return NameMatch(status="mismatch", detail=detail), None


def decide_publication(info: PublicationInfo, skills: list[SkillVerdict]) -> Outcome:
    match = info.author_match
    if info.doi and not info.registered and info.source is None:
        return Outcome(
            None, f"The DOI {info.doi} couldn't be found in the DOI registry. Check it's correct."
        )
    if match is None or match.status == "missing":
        return Outcome(
            None, "No author list could be found, so authorship can't be checked. Try the DOI."
        )
    if match.status == "mismatch":
        return Outcome(None, match.detail, rejected=True)
    shown = _demonstrated(skills)
    tail = f" It demonstrates {', '.join(shown)}." if shown else ""
    if info.source == "crossref" and match.status == "match":
        return Outcome("verified", f"The DOI registry lists you as an author.{tail}")
    if info.source == "crossref":
        return Outcome(
            "partially_verified",
            f"The DOI is registered, but the author name is only a partial match.{tail}",
        )
    return Outcome(
        "partially_verified",
        "The page lists you as an author, but without a DOI we can't confirm the publisher. "
        f"Add the DOI to have it verified.{tail}",
    )


# --- letters ------------------------------------------------------------------------------


def decide_letter(info: LetterInfo) -> Outcome:
    """Always self-reported when accepted: we can't contact the writer."""
    if not info.is_letter:
        return Outcome(
            None,
            "This doesn't look like a reference or experience letter.",
            rejected=True,
        )
    name = info.name_match
    if name and name.status == "mismatch":
        return Outcome(None, name.detail + " Upload a letter about you.", rejected=True)
    writer = ", ".join(x for x in (info.writer_name, info.writer_title, info.organization) if x)
    by = f" from {writer}" if writer else ""
    contact = (
        " It includes the writer's contact details, so an employer can follow it up."
        if info.has_contact_details
        else " Ask the writer to add contact details so employers can follow it up."
    )
    mentioned = [s.name for s in info.skills_mentioned]
    about = f" It mentions {', '.join(mentioned)}." if mentioned else ""
    return Outcome(
        "self_reported",
        f"A letter{by}. Letters can't be independently verified, so it counts as "
        f"self-reported.{about}{contact}",
    )
