import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProofType
from app.schemas.proof_report import ProjectDraft, VerificationLevel
from app.schemas.resume_data import CertificationItem, ProjectItem, SectionItem
from app.schemas.section_kind import SectionKind


class ProofLink(BaseModel):
    """How a proof is cited on the resume: a plain-text URL (ATS-safe) and whether it's verified."""

    proof_id: uuid.UUID
    type: ProofType
    url: str | None  # full URL for the link target
    display_url: str | None  # without scheme/www, as printed on the resume
    verified: bool
    level: VerificationLevel | None
    # How it was verified, e.g. "Verified by referee" (see services/proofs/methods.py).
    method: str | None = None


class BulletTarget(BaseModel):
    """The entry an add_bullet suggestion goes into: a job in Experience, or an entry in a
    section that counts as experience (Clinical or Teaching Experience...)."""

    section_id: str  # "experience" or the section's id
    item_index: int
    # The entry's title when suggested, so the editor can tell if it moved or changed.
    item_title: str
    label: str  # e.g. "Staff Nurse at St Mary's Hospital"


class ResumeSuggestion(BaseModel):
    # Stable: "skill:<skill id>", "project:<proof id>", "cert:<proof id>",
    # "entry:<proof id>", "bullet:<proof id>".
    id: str
    kind: Literal[
        "add_skill",
        "link_skill_proof",
        "add_project",
        "add_certification",
        "add_section_entry",
        "add_bullet",
    ]
    title: str
    detail: str
    proof_id: uuid.UUID
    skill_id: uuid.UUID | None = None
    skill_name: str | None = None
    # link_skill_proof: which Skills entry matched (and its text, to detect edits since).
    skill_index: int | None = None
    resume_skill_name: str | None = None
    # add_project: a repo to draft from with AI, or a ready entry (from a work sample).
    repo_url: str | None = None
    project: ProjectItem | None = None
    certification: CertificationItem | None = None  # add_certification, prefilled
    # add_section_entry: a prefilled entry (link as plain text) for this section.
    section_kind: SectionKind | None = None
    section_heading: str | None = None
    entry: SectionItem | None = None
    # add_bullet: a bullet for an existing entry.
    bullet: str | None = None
    target: BulletTarget | None = None
    level: VerificationLevel | None = None


class SuggestionsResponse(BaseModel):
    suggestions: list[ResumeSuggestion]
    proof_links: dict[str, ProofLink]


class ProjectDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proof_id: uuid.UUID
    regenerate: bool = False


DraftResponse = ProjectDraft
