"""Who the AI is helping: target role, field, career stage and what results mean in that
field. Every writing and review prompt renders it through prompts/_candidate.j2, so the
advice fits a nurse, a teacher or a salesperson as well as a developer."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateContext:
    target_role: str | None = None
    industry: str | None = None  # "Healthcare"
    # ExperienceLevel value: student, entry, mid, senior, career_changer.
    experience_level: str | None = None
    # "patient outcomes, patient safety, ..." from the industry's data.
    impact_language: str | None = None
    # Spelling value: en_us or en_gb. None: follow the spelling the resume already uses.
    spelling: str | None = None

    @property
    def fresher(self) -> bool:
        return self.experience_level in ("student", "entry")

    @property
    def career_changer(self) -> bool:
        return self.experience_level == "career_changer"


NO_CONTEXT = CandidateContext()
