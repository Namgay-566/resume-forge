"""How much an email address says about where someone works.

- company: an organisation's own domain (stmarys.nhs.uk, acme.com). Strongest.
- free: a personal mailbox anyone can open (gmail.com, yahoo.com). Lower trust: it can't
  tie the person to an organisation.
- disposable: throwaway inboxes. Refused.
The lists are data (email_domains.json); subdomains count (mail.yahoo.co.uk -> yahoo.co.uk).
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import EmailStr, TypeAdapter, ValidationError

DomainKind = Literal["company", "free", "disposable"]
_email = TypeAdapter(EmailStr)
_WORD = re.compile(r"[a-z0-9]+")
# Words that say nothing about which organisation it is.
_GENERIC = frozenset(
    "the and of ltd limited llc inc plc co company group corp corporation services service "
    "trust nhs uk com org net gov edu ac mail email school hospital university college".split()
)


class InvalidEmailError(ValueError):
    pass


@cache
def _lists() -> dict[str, frozenset[str]]:
    data = json.loads(Path(__file__).with_name("email_domains.json").read_text(encoding="utf-8"))
    return {kind: frozenset(d.lower() for d in domains) for kind, domains in data.items()}


def normalize_email(raw: str) -> str:
    try:
        email = str(_email.validate_python(raw.strip()))
    except ValidationError as exc:
        raise InvalidEmailError("Enter a valid email address.") from exc
    local, _, domain = email.rpartition("@")
    return f"{local}@{domain.lower()}"


def email_domain(email: str) -> str:
    return email.rpartition("@")[2].lower()


def classify(email: str) -> DomainKind:
    domain = email_domain(email)
    lists = _lists()
    parts = domain.split(".")
    candidates = {".".join(parts[i:]) for i in range(len(parts) - 1)}
    if candidates & lists["disposable"]:
        return "disposable"
    if candidates & lists["free"]:
        return "free"
    return "company"


def domain_matches_organization(email: str, organization: str) -> bool:
    """Whether the domain plausibly belongs to the organisation: a distinctive word of the
    name appears in the domain ("St Mary's Hospital" and stmarys.nhs.uk, "Acme Foods" and
    acmefoods.com). A hint shown to people, never a pass/fail check."""
    domain = email_domain(email).replace("-", "")
    words = [w for w in _WORD.findall(organization.lower().replace("'", "")) if w not in _GENERIC]
    joined = "".join(words)
    if joined and joined in domain:
        return True
    return any(len(w) >= 4 and w in domain for w in words)
