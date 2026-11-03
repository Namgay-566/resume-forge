import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProofType, SkillImportance, VerificationStatus
from app.schemas.target_role import TargetRoleSummary

SkillStatus = Literal["present_verified", "present_unverified", "inferred", "missing"]
EvidenceKind = Literal[
    "verified_proof",  # user_skills verified by an accepted proof
    "profile",  # user_skills without verification (self-declared, from an import, proof pending)
    "skills_section",
    "certification",  # listed in Licenses & Certifications (a licence, a qualification)
    "tools",  # a job's or project's tools and skills list
    "resume_text",  # named in a bullet, summary or project description
    "ai_inferred",
]


class Evidence(BaseModel):
    kind: EvidenceKind
    detail: str  # human-readable, e.g. "Tools used at Acme" or the quoted bullet


class SkillGroupRef(BaseModel):
    """The field's own category for a skill ("Clinical skills", "Credentials"...)."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    sort_order: int


OTHER_GROUP = SkillGroupRef(slug="other", name="Other skills", sort_order=999)


class RoleSkillGap(BaseModel):
    skill_id: uuid.UUID
    name: str
    slug: str
    category: str
    importance: SkillImportance
    weight: int
    status: SkillStatus
    evidence: list[Evidence]
    # From user_skills, when the user has a row for this skill (e.g. "pending" proof review).
    verification_status: VerificationStatus | None = None
    # How it was verified, for the badge ("Verified by referee", "Verified via GitHub"...).
    verified_by: str | None = None
    # Kinds of proof that suit this skill, best first (a licence for a nursing licence, a
    # work sample or certificate for Excel, a repo for React).
    proof_types: list[ProofType] = []
    # How the Skill Gap page groups it.
    group: SkillGroupRef = OTHER_GROUP


class StatusCounts(BaseModel):
    present_verified: int = 0
    present_unverified: int = 0
    inferred: int = 0
    missing: int = 0


class SkillGapReport(BaseModel):
    resume_id: uuid.UUID
    role: TargetRoleSummary
    readiness: int  # 0-100, weighted by each role skill's weight
    skills: list[RoleSkillGap]  # ordered: importance, then weight, then name
    counts: StatusCounts
    missing_critical: list[str]
    # AI inference outcome. skipped: nothing left to infer; cached: reused an earlier result.
    ai_status: Literal["ok", "cached", "skipped", "rate_limited", "unavailable", "failed"]
