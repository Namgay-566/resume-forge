"""Normalised keyword matching between a keyword list and the resume text, using the skills
catalog's aliases so "PostgreSQL" in a job description is satisfied by "Postgres" on a resume."""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.models import Skill
from app.schemas.ats import KeywordHit
from app.schemas.resume_data import ResumeData
from app.services.resume_import.matching import term_variants

_NOT_WORDISH = re.compile(r"[^a-z0-9+#./ ]+")
_SPACES = re.compile(r"\s+")
_WORD_CHARS = "a-z0-9+#"


def normalize(text: str) -> str:
    lowered = _NOT_WORDISH.sub(" ", text.lower().replace("–", " ").replace("/", " / "))
    return _SPACES.sub(" ", lowered).strip()


def contains(haystack: str, phrase: str) -> bool:
    """Whole-word/phrase match that keeps C++, C#, node.js and ci/cd intact."""
    if not phrase:
        return False
    pattern = rf"(?<![{_WORD_CHARS}]){re.escape(phrase)}(?![{_WORD_CHARS}])"
    return re.search(pattern, haystack) is not None


def resume_text(data: ResumeData) -> str:
    p = data.personal_info
    parts: list[str] = [p.headline, data.summary]
    for e in data.experience:
        parts += [e.title, e.company, *e.bullets, *e.tools_and_skills]
    for ed in data.education:
        parts += [ed.degree, ed.field_of_study or "", ed.institution, *ed.bullets]
    for pr in data.projects:
        parts += [pr.name, pr.description, *pr.bullets, *pr.tools_and_skills]
    parts += [s.name for s in data.skills]
    parts += [c.name for c in data.certifications]
    parts += data.achievements
    parts += data.extra_text_parts()  # clinical experience, publications, languages...
    return normalize(" \n ".join(part for part in parts if part))


@dataclass(frozen=True)
class AliasIndex:
    """alias -> every alias of every skill that lists it."""

    groups: dict[str, frozenset[str]]

    @classmethod
    def from_skills(cls, skills: Iterable[Skill]) -> "AliasIndex":
        groups: dict[str, set[str]] = {}
        for skill in skills:
            aliases = {normalize(a) for a in skill.aliases} | {normalize(skill.name)}
            for alias in aliases:
                groups.setdefault(alias, set()).update(aliases)
        return cls({k: frozenset(v) for k, v in groups.items()})

    def variants(self, keyword: str) -> list[str]:
        base = [normalize(v) for v in term_variants(keyword)]
        extra = sorted({a for v in base for a in self.groups.get(v, ())} - set(base))
        return list(dict.fromkeys(base + extra))


def match_keywords(
    keywords: list[KeywordHit], text: str, index: AliasIndex
) -> tuple[list[KeywordHit], list[KeywordHit]]:
    matched: list[KeywordHit] = []
    missing: list[KeywordHit] = []
    seen: set[str] = set()
    for hit in keywords:
        key = normalize(hit.keyword)
        if not key or key in seen:
            continue
        seen.add(key)
        found = next((v for v in index.variants(hit.keyword) if contains(text, v)), None)
        if found:
            as_alias = None if found == key else found
            matched.append(hit.model_copy(update={"matched_as": as_alias}))
        else:
            missing.append(hit)
    return matched, missing


def catalog_keywords(job_description: str, skills: Iterable[Skill]) -> list[KeywordHit]:
    """Fallback JD keyword extraction without AI: catalog skills mentioned in the JD."""
    text = normalize(job_description)
    hits = []
    for skill in sorted(skills, key=lambda s: s.name):
        aliases = {normalize(a) for a in skill.aliases} | {normalize(skill.name)}
        if any(contains(text, alias) for alias in aliases):
            hits.append(KeywordHit(keyword=skill.name))
    return hits
