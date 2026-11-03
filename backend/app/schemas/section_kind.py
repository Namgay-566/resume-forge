from enum import StrEnum


class SectionKind(StrEnum):
    """Kinds of resume section. The first seven are core: their content lives in dedicated
    ResumeData fields. The rest keep generic entries inside the section itself. Headings,
    field labels and per-field defaults come from app/services/sections/catalog.json."""

    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    ACHIEVEMENTS = "achievements"
    CLINICAL_EXPERIENCE = "clinical_experience"
    TEACHING_EXPERIENCE = "teaching_experience"
    INTERNSHIPS = "internships"
    VOLUNTEER = "volunteer"
    RESEARCH = "research"
    PUBLICATIONS = "publications"
    CONFERENCES = "conferences"
    PORTFOLIO = "portfolio"
    TRAINING = "training"
    MEMBERSHIPS = "memberships"
    AWARDS = "awards"
    LANGUAGES = "languages"
    EXTRACURRICULARS = "extracurriculars"
    CUSTOM = "custom"

    @property
    def is_core(self) -> bool:
        return self in CORE_SECTION_KINDS


CORE_SECTION_KINDS = frozenset(
    {
        SectionKind.SUMMARY,
        SectionKind.EXPERIENCE,
        SectionKind.EDUCATION,
        SectionKind.SKILLS,
        SectionKind.PROJECTS,
        SectionKind.CERTIFICATIONS,
        SectionKind.ACHIEVEMENTS,
    }
)
