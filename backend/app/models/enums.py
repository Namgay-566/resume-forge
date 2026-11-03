from enum import StrEnum


class ResumeType(StrEnum):
    RESUME = "resume"
    CV = "cv"


class ResumeTemplate(StrEnum):
    """All templates are single-column and ATS-safe; they differ only in typography/spacing."""

    CLASSIC = "classic"
    MODERN_MINIMAL = "modern_minimal"
    COMPACT = "compact"
    # Serif, understated: finance, law, government.
    CONSERVATIVE = "conservative"
    # Clean sans-serif with a quiet accent colour: business, marketing, sales.
    PROFESSIONAL = "professional"
    # Long-format academic CV: roomy serif for publications, teaching and grants.
    ACADEMIC = "academic"


class ContentSource(StrEnum):
    """Where a role or skill came from. AI-generated ones are kept for human review."""

    CURATED = "curated"
    AI_GENERATED = "ai_generated"


class ExperienceLevel(StrEnum):
    """Where the candidate is in their career. Shapes scoring and advice."""

    STUDENT = "student"  # student or fresher, little or no work experience
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    CAREER_CHANGER = "career_changer"


class SkillImportance(StrEnum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    NICE_TO_HAVE = "nice_to_have"

    @property
    def default_weight(self) -> int:
        """Weight (1-10) in the readiness score when a role doesn't set one explicitly."""
        return {"critical": 9, "important": 6, "nice_to_have": 3}[self.value]


class UserSkillSource(StrEnum):
    RESUME = "resume"
    VERIFIED_PROOF = "verified_proof"
    SELF_DECLARED = "self_declared"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ResourceType(StrEnum):
    COURSE = "course"
    DOCS = "docs"
    TUTORIAL = "tutorial"
    VIDEO = "video"


class ProofType(StrEnum):
    GITHUB_REPO = "github_repo"
    LIVE_LINK = "live_link"
    CERTIFICATE = "certificate"
    PROFESSIONAL_LICENSE = "professional_license"
    PORTFOLIO_LINK = "portfolio_link"
    WORK_SAMPLE = "work_sample"
    PUBLICATION = "publication"
    REFERENCE_LETTER = "reference_letter"
    EXPERIENCE_LETTER = "experience_letter"
    # A named referee confirms the role, dates and skills through a one-time link.
    REFEREE_CONFIRMATION = "referee_confirmation"

    @property
    def is_upload(self) -> bool:
        """Proofs submitted as a file rather than a link."""
        return self in UPLOAD_PROOF_TYPES

    @property
    def is_letter(self) -> bool:
        return self in (ProofType.REFERENCE_LETTER, ProofType.EXPERIENCE_LETTER)


UPLOAD_PROOF_TYPES = frozenset(
    {
        ProofType.CERTIFICATE,
        ProofType.PROFESSIONAL_LICENSE,
        ProofType.WORK_SAMPLE,
        ProofType.REFERENCE_LETTER,
        ProofType.EXPERIENCE_LETTER,
    }
)


class ProofStatus(StrEnum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    VERIFIED = "verified"
    REJECTED = "rejected"
    NEEDS_MORE = "needs_more"
    # Waiting on someone else (a referee's answer).
    AWAITING_RESPONSE = "awaiting_response"


class PlanStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class PageSize(StrEnum):
    """Paper size for exports. A4 in most of the world; US Letter in the US and Canada."""

    A4 = "a4"
    LETTER = "letter"


class Spelling(StrEnum):
    """Which English spelling AI writing uses (organise/organize, colour/color)."""

    US = "en_us"
    UK = "en_gb"
