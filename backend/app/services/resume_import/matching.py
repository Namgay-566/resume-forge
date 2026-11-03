import re

from app.schemas.resume_data import ResumeData

_TRAILING_VERSION = re.compile(r"\s*v?\d+(\.\d+)*\+?$")  # "Python 3.11" -> "python"
_SPACES = re.compile(r"\s+")


def normalize_term(value: str) -> str:
    term = _SPACES.sub(" ", value.strip().lower()).strip(" .,;:")
    return term


_BRACKETED = re.compile(r"\s*\(([^()]{1,40})\)\s*")  # "Qualified Teacher Status (QTS)"


def term_variants(value: str) -> list[str]:
    """The term, without a trailing version, and split around a bracketed abbreviation:
    "Qualified Teacher Status (QTS)" -> itself, "qualified teacher status", "qts"."""
    term = normalize_term(value)
    without_version = _TRAILING_VERSION.sub("", term).strip()
    variants = [term, without_version]
    for match in _BRACKETED.finditer(term):
        variants += [_BRACKETED.sub(" ", term).strip(), match.group(1).strip()]
    return list(dict.fromkeys(t for t in variants if t))


def skill_terms(data: ResumeData) -> list[str]:
    """Every skill-like name on the resume: Skills, each entry's tools, and certifications."""
    names = [s.name for s in data.skills]
    names += [t for e in data.experience for t in e.tools_and_skills]
    names += [t for p in data.projects for t in p.tools_and_skills]
    names += [c.name for c in data.certifications]  # licences and qualifications
    return list(dict.fromkeys(v for name in names for v in term_variants(name)))
