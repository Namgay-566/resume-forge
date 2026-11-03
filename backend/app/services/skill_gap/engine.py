"""Skill gap logic. Pure functions: resume data + role skills + the user's skill records in,
statuses and a readiness score out. No database, no AI (inferences are passed in)."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.models.enums import SkillImportance, VerificationStatus
from app.schemas.resume_data import ResumeData
from app.schemas.skill_gap import Evidence, SkillStatus
from app.services.ats.keywords import contains, normalize
from app.services.resume_import.matching import term_variants

# Share of a skill's weight earned in each status.
CREDIT: dict[SkillStatus, float] = {
    "present_verified": 1.0,
    "present_unverified": 0.75,
    "inferred": 0.4,
    "missing": 0.0,
}
IMPORTANCE_ORDER = {
    SkillImportance.CRITICAL: 0,
    SkillImportance.IMPORTANT: 1,
    SkillImportance.NICE_TO_HAVE: 2,
}


@dataclass(frozen=True)
class CatalogSkill:
    id: object
    name: str
    aliases: frozenset[str]  # normalised, includes the name

    @classmethod
    def build(cls, id: object, name: str, aliases: Iterable[str]) -> "CatalogSkill":
        return cls(id, name, frozenset(normalize(a) for a in [name, *aliases] if a.strip()))

    def matches_term(self, term: str) -> bool:
        return normalize(term) in self.aliases

    def mentioned_in(self, text: str) -> bool:
        return any(contains(text, alias) for alias in self.aliases)


@dataclass(frozen=True)
class UserSkillRecord:
    skill_id: object
    verification_status: VerificationStatus


@dataclass
class SkillResult:
    status: SkillStatus
    evidence: list[Evidence] = field(default_factory=list)
    verification_status: VerificationStatus | None = None


def _named(terms: Iterable[str], skill: CatalogSkill) -> bool:
    return any(skill.matches_term(v) for term in terms for v in term_variants(term))


def resume_evidence(data: ResumeData, skill: CatalogSkill) -> list[Evidence]:
    """Where the resume itself shows this skill, strongest first."""
    found: list[Evidence] = []
    if _named((s.name for s in data.skills), skill):
        found.append(Evidence(kind="skills_section", detail="Listed in your Skills section"))
    for c in data.certifications:
        # "NMC Registration", "ACCA", "BLS": licences and qualifications are skills too.
        if _named([c.name], skill) or (c.issuer and _named([f"{c.issuer} {c.name}"], skill)):
            detail = f"Listed in Licenses & Certifications: {c.name}"
            found.append(Evidence(kind="certification", detail=detail))
            break
    for e in data.experience:
        if _named(e.tools_and_skills, skill):
            found.append(
                Evidence(kind="tools", detail=f"Tools used at {e.company or e.title or 'a job'}")
            )
    for p in data.projects:
        if _named(p.tools_and_skills, skill):
            found.append(Evidence(kind="tools", detail=f"Tools used in {p.name or 'a project'}"))
    if not found:
        texts = [data.summary]
        texts += [b for e in data.experience for b in e.bullets]
        texts += [p.description for p in data.projects] + [
            b for p in data.projects for b in p.bullets
        ]
        texts += [part for s in data.extra_sections() for e in s.entries for part in e.text_parts()]
        for text in texts:
            if text and skill.mentioned_in(normalize(text)):
                found.append(Evidence(kind="resume_text", detail=text))
                break
    return found


def classify(
    skill: CatalogSkill,
    data: ResumeData,
    user_skill: UserSkillRecord | None,
    inferred_evidence: str | None,
) -> SkillResult:
    """Status precedence: verified proof > on resume or profile > AI inferred > missing."""
    status_from_profile = user_skill.verification_status if user_skill else None
    evidence = resume_evidence(data, skill)

    if status_from_profile is VerificationStatus.VERIFIED:
        return SkillResult(
            "present_verified",
            [Evidence(kind="verified_proof", detail="Verified with proof"), *evidence],
            status_from_profile,
        )
    if user_skill and status_from_profile is not VerificationStatus.REJECTED:
        label = (
            "Proof is being reviewed"
            if status_from_profile is VerificationStatus.PENDING
            else ("In your skills profile")
        )
        evidence = [*evidence, Evidence(kind="profile", detail=label)]
    if evidence:
        return SkillResult("present_unverified", evidence, status_from_profile)
    if inferred_evidence:
        return SkillResult(
            "inferred",
            [Evidence(kind="ai_inferred", detail=inferred_evidence)],
            status_from_profile,
        )
    return SkillResult("missing", [], status_from_profile)


def readiness(results: Iterable[tuple[int, SkillStatus]]) -> int:
    """Weighted share of the role's skills you have: sum(weight x credit) / sum(weight)."""
    pairs = list(results)
    total = sum(weight for weight, _ in pairs)
    if total == 0:
        return 0
    return round(100 * sum(weight * CREDIT[status] for weight, status in pairs) / total)
