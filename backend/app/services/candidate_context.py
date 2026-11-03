"""Build the AI's CandidateContext from a resume: its target role, that role's field and
the field's impact language, the resume's career stage, and the owner's spelling choice."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context import CandidateContext
from app.models import Resume, User
from app.repositories.target_role_repository import TargetRoleRepository


async def candidate_context(session: AsyncSession, resume: Resume) -> CandidateContext:
    level = resume.experience_level.value if resume.experience_level else None
    owner = await session.get(User, resume.user_id)  # already loaded: the signed-in user
    spelling = owner.spelling.value if owner and owner.spelling else None
    if resume.target_role_id is None:
        return CandidateContext(experience_level=level, spelling=spelling)
    role = await TargetRoleRepository(session).get_with_industry(resume.target_role_id)
    if role is None:
        return CandidateContext(experience_level=level, spelling=spelling)
    return CandidateContext(
        target_role=role.name,
        industry=role.industry.name,
        experience_level=level,
        impact_language=role.industry.impact_language or None,
        spelling=spelling,
    )
