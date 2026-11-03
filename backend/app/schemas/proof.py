import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ProofStatus, ProofType
from app.schemas.proof_report import ProofReport, VerificationLevel
from app.schemas.referee import RefereeRequestInfo
from app.services.proofs.rules import skill_proof_types


class ProofCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Link proofs. Files (certificates, licences, work samples, letters) go to /upload.
    type: ProofType = ProofType.GITHUB_REPO
    # A URL, or for publications a DOI ("10.1234/abcd").
    url: Annotated[str, Field(min_length=1, max_length=2048)]
    # Required (1-5) for repos, portfolios and publications; optional for live links.
    skill_ids: Annotated[list[uuid.UUID], Field(max_length=5)] = []
    # Live links only: one of your GitHub repo proofs for the same project.
    linked_proof_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_allowed_link_types(self) -> "ProofCreate":
        allowed_links = {
            ProofType.GITHUB_REPO,
            ProofType.LIVE_LINK,
            ProofType.PORTFOLIO_LINK,
            ProofType.PUBLICATION,
            ProofType.CERTIFICATE,
            ProofType.PROFESSIONAL_LICENSE,
        }
        if self.type not in allowed_links:
            raise ValueError(f"Proof type {self.type} must be uploaded as a file.")
        return self


class SkillRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class ProofRead(BaseModel):
    id: uuid.UUID
    type: ProofType
    url: str | None
    status: ProofStatus
    score: int | None
    skills: list[SkillRef]
    # Verified / partially verified / self-reported (None while running or if rejected).
    verification_level: VerificationLevel | None
    # How, in words for the badge: "Verified by referee", "Verified via GitHub",
    # "Self-reported". None while running or if rejected.
    verification_method: str | None = None
    decision: str
    linked_proof_id: uuid.UUID | None
    # Uploads: the original file name (download via GET /api/proofs/{id}/file).
    file_name: str | None
    # While running: the step the analysis is on (e.g. "reviewing"); null otherwise.
    progress: str | None = None
    created_at: datetime


class ProofDetail(ProofRead):
    report: ProofReport | None
    # Referee confirmations: who was asked and the request's state (never their answers).
    referee: RefereeRequestInfo | None = None


class SkillCatalogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    category: str
    # Proof types that suit the skill, best first.
    proof_types: list[ProofType] = []

    @model_validator(mode="after")
    def fill_proof_types(self) -> "SkillCatalogItem":
        self.proof_types = skill_proof_types(
            self.slug, self.category, [t.value for t in self.proof_types]
        )
        return self