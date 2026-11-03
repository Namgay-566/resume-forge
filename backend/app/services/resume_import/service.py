import asyncio
import uuid
from dataclasses import dataclass
from pathlib import PurePath

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient
from app.ai.resume_parser import parse_resume_text, to_resume_data
from app.core.filenames import safe_filename
from app.models import Resume, Skill, User
from app.models.enums import ResumeTemplate, ResumeType
from app.repositories.resume_repository import ResumeRepository
from app.repositories.skill_repository import SkillRepository
from app.services.resume_import.extract import (
    MAX_UPLOAD_BYTES,
    FileTooLargeError,
    detect_kind,
    extract_text,
)
from app.services.resume_import.matching import skill_terms, term_variants
from app.services.resume_service import with_account_links
from app.services.sections.layout import suggest_layout, with_layout


@dataclass(frozen=True)
class ImportOutcome:
    resume: Resume
    matched_skills: list[str]
    unmatched_skills: list[str]


def import_title(filename: str | None, full_name: str) -> str:
    stem = PurePath(safe_filename(filename, "")).stem.strip()
    return (stem or full_name or "Imported resume")[:200]


class ResumeImportService:
    def __init__(self, session: AsyncSession, ai: AIClient) -> None:
        self.session = session
        self.ai = ai
        self.resumes = ResumeRepository(session)
        self.skills = SkillRepository(session)

    async def import_file(
        self, user: User, *, filename: str | None, content_type: str | None, content: bytes
    ) -> ImportOutcome:
        if len(content) > MAX_UPLOAD_BYTES:
            raise FileTooLargeError("That file is over 5 MB. Upload a smaller PDF or DOCX.")
        kind = detect_kind(content_type, content)
        text = await asyncio.to_thread(extract_text, kind, content)

        parsed = await parse_resume_text(self.ai, text)
        resume_type = ResumeType(parsed.document_type)
        # No target role yet: the default layout for the document type (a CV leads with
        # education). Every section the parser filled in is kept.
        data = with_layout(to_resume_data(parsed), suggest_layout(resume_type, None))
        data = with_account_links(data, user)

        # Match skill names (and their aliases) against the catalog. One alias can belong to
        # several skills on purpose (e.g. "fastapi" is both Backend Framework and Python Web
        # Framework), so an alias maps to every skill that lists it.
        catalog = await self.skills.find_by_aliases(skill_terms(data))
        by_alias: dict[str, list[Skill]] = {}
        for skill in sorted(catalog, key=lambda s: s.name):
            for alias in skill.aliases:
                by_alias.setdefault(alias, []).append(skill)

        def lookup(name: str) -> list[Skill]:
            for term in term_variants(name):
                if skills := by_alias.get(term):
                    # Prefer the skill literally named this, e.g. "Python" over a framework.
                    return sorted(skills, key=lambda s: s.name.lower() != term)
            return []

        unmatched: list[str] = []
        for resume_skill in data.skills:
            if found := lookup(resume_skill.name):
                resume_skill.skill_id = found[0].id
            else:
                unmatched.append(resume_skill.name)
        tools = [t for e in data.experience for t in e.tools_and_skills]
        tools += [t for p in data.projects for t in p.tools_and_skills]
        matched: dict[uuid.UUID, Skill] = {}
        for name in [s.name for s in data.skills] + tools:
            for skill in lookup(name):
                matched.setdefault(skill.id, skill)

        resume = await self.resumes.add(
            Resume(
                user_id=user.id,
                title=import_title(filename, data.personal_info.full_name),
                type=resume_type,
                # The type is read from the document; the rest are the user's defaults.
                template=user.default_template or ResumeTemplate.CLASSIC,
                experience_level=user.default_experience_level,
                data=data,
            )
        )
        await self.skills.add_user_skills_from_resume(user.id, list(matched))
        await self.session.commit()

        stored = await self.resumes.get_for_user(resume.id, user.id)
        assert stored is not None
        return ImportOutcome(
            resume=stored,
            matched_skills=sorted(s.name for s in matched.values()),
            unmatched_skills=unmatched,
        )
