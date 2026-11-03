"""Proof analysis report (stored in proofs.ai_report). Free of model imports on purpose:
the Proof model stores it via PydanticJSONB."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["pass", "warn", "fail"]
Verdict = Literal["demonstrated", "partially", "not_demonstrated"]


class Contributor(BaseModel):
    login: str
    commits: int


class RepoFacts(BaseModel):
    full_name: str
    url: str
    description: str | None
    default_branch: str
    fork: bool
    parent: str | None = None
    ahead_of_parent: int | None = None  # commits the fork has that its parent doesn't
    stars: int
    homepage: str | None = None  # the repo's website setting on GitHub
    created_at: datetime | None
    pushed_at: datetime | None
    languages: dict[str, float]  # language -> share of code (0-100)
    commit_count: int
    commit_days: int  # distinct days with commits (among the latest 100)
    contributors: list[Contributor]
    file_count: int
    tree_truncated: bool
    has_readme: bool
    readme_excerpt: str | None = None  # kept for drafting a resume entry later
    readme_chars: int = 0
    has_tests: bool
    has_ci: bool
    has_docker: bool
    key_files: list[str]  # config files the review looked at
    sampled_files: list[str]  # source files the review looked at


class Ownership(BaseModel):
    status: Literal["confirmed", "failed", "unknown"]
    detail: str
    user_commits: int | None = None
    share: float | None = None  # user's share of all commits, 0-1


class ProofCheck(BaseModel):
    id: str
    status: CheckStatus
    title: str
    detail: str
    # Gate checks must pass for the skill to be verified; others are informational.
    gate: bool = True


class SkillVerdict(BaseModel):
    skill_id: uuid.UUID
    name: str
    verdict: Verdict
    evidence: list[str]


VerificationLevel = Literal["verified", "partially_verified", "self_reported"]


class NameMatch(BaseModel):
    status: Literal["match", "partial", "mismatch", "missing"]
    detail: str


class UrlCheck(BaseModel):
    url: str
    final_url: str | None = None
    status_code: int | None = None
    reachable: bool = False
    on_trusted_domain: bool = False  # issuer's own site or a known credential platform
    details_on_page: bool = False  # recipient name or credential ID visible on the page
    detail: str = ""


class CertificateInfo(BaseModel):
    filename: str
    content_type: str
    text_source: Literal["pdf_text", "vision"] | None = None
    is_certificate: bool = True
    issuer: str | None = None
    recipient_name: str | None = None
    course_name: str | None = None
    issue_date: str | None = None
    credential_id: str | None = None
    verification_url: str | None = None
    name_match: NameMatch | None = None
    url_check: UrlCheck | None = None
    mapped_skills: list[str] = []


class LiveLinkInfo(BaseModel):
    url: str
    final_url: str | None = None
    status_code: int | None = None
    reachable: bool = False
    https: bool = False
    response_ms: int | None = None
    title: str = ""
    description: str = ""
    site_name: str = ""
    linked_repo: str | None = None  # full_name of the linked GitHub proof
    linked_repo_verified: bool = False
    connection: str | None = None  # how the site is tied to the repo, if we found it


class UploadInfo(BaseModel):
    """The uploaded file behind a proof (any upload type)."""

    filename: str
    content_type: str
    text_source: Literal["pdf_text", "docx_text", "vision"] | None = None


class LicenseInfo(BaseModel):
    is_license: bool = True
    license_type: str | None = None  # e.g. "Registered Nurse", "Journeyman Electrician"
    holder_name: str | None = None
    license_number: str | None = None
    issuing_body: str | None = None
    jurisdiction: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    # A link to the holder's entry on the public register: given by the user, or printed.
    register_url: str | None = None
    register_source: Literal["user", "document"] | None = None
    name_match: NameMatch | None = None
    register_check: UrlCheck | None = None
    expired: bool = False
    expires_soon: bool = False  # within 90 days
    expiry_detail: str = ""
    mapped_skills: list[str] = []


class PortfolioInfo(BaseModel):
    url: str
    final_url: str | None = None
    status_code: int | None = None
    reachable: bool = False
    https: bool = False
    title: str = ""
    description: str = ""
    site_name: str = ""
    platform: str | None = None  # "Behance", "Dribbble", "Medium"... when recognised
    name_on_page: bool = False
    text_chars: int = 0  # how much readable text the page had for the review


class WorkSampleInfo(BaseModel):
    is_work_sample: bool = True
    kind: str | None = None  # what the reviewer took it to be, e.g. "a lesson plan"
    text_chars: int = 0


class PublicationInfo(BaseModel):
    input: str
    doi: str | None = None
    url: str | None = None
    # "crossref": the DOI's registered metadata; "page": metadata read from the web page.
    source: Literal["crossref", "page"] | None = None
    registered: bool = False  # the DOI exists in the registry
    title: str | None = None
    venue: str | None = None
    published: str | None = None
    authors: list[str] = []
    author_match: NameMatch | None = None
    matched_author: str | None = None


class MentionedSkill(BaseModel):
    name: str
    quote: str  # the words in the letter that mention it


class LetterInfo(BaseModel):
    is_letter: bool = True
    letter_kind: Literal["reference", "experience", "recommendation", "other"] | None = None
    writer_name: str | None = None
    writer_title: str | None = None
    organization: str | None = None
    date: str | None = None
    subject_name: str | None = None
    relationship: str | None = None  # how the writer knows the candidate
    has_contact_details: bool = False
    name_match: NameMatch | None = None
    skills_mentioned: list[MentionedSkill] = []


class ProjectDraft(BaseModel):
    """AI-drafted resume project entry for a verified repo (user edits before accepting)."""

    name: str
    description: str
    bullets: list[str]
    tools_and_skills: list[str]
    link: str


class ProofReport(BaseModel):
    repo: RepoFacts | None = None
    ownership: Ownership | None = None
    checks: list[ProofCheck] = []
    skills: list[SkillVerdict] = []
    summary: str = ""
    strengths: list[str] = []
    code_quality: list[str] = []
    red_flags: list[str] = []
    suggestions: list[str] = []
    ai_score: int | None = None
    ai_status: Literal["ok", "unavailable", "failed", "skipped"] = "skipped"
    certificate: CertificateInfo | None = None
    resume_draft: ProjectDraft | None = None
    live: LiveLinkInfo | None = None
    upload: UploadInfo | None = None
    license: LicenseInfo | None = None
    portfolio: PortfolioInfo | None = None
    work_sample: WorkSampleInfo | None = None
    publication: PublicationInfo | None = None
    letter: LetterInfo | None = None
    # Referee confirmations: whether the referee wrote from a work or a personal address.
    referee_domain_kind: Literal["company", "free"] | None = None
    # Who the AI reviewed as, e.g. "a senior nurse and clinical educator".
    reviewer: str | None = None
    # One honest scale for every proof type (None while running, when rejected, or when the
    # proof can't count at all, e.g. an expired licence).
    verification_level: VerificationLevel | None = None
    # Plain-language reason for the final status.
    decision: str = ""
    error: str | None = None
    analyzed_at: datetime | None = None
