import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Resume, User
from app.models.enums import ResumeTemplate
from app.repositories.resume_repository import ResumeRepository
from app.repositories.target_role_repository import TargetRoleRepository
from app.schemas.resume import ResumeCreate, ResumeUpdate
from app.schemas.resume_data import MAX_PROFILE_LINKS, PersonalInfo, ProfileLink, ResumeData
from app.services.sections.layout import with_layout
from app.services.sections.service import SectionService

MAX_TITLE_LENGTH = 200


class ResumeNotFoundError(Exception):
    pass


class TargetRoleNotFoundError(Exception):
    pass


def copy_title(title: str) -> str:
    suffix = " (copy)"
    return title[: MAX_TITLE_LENGTH - len(suffix)] + suffix


def account_profile_links(user: User) -> list[ProfileLink]:
    """Links known from the account: the LinkedIn profile of a LinkedIn user, once known
    (shared at sign-in, or taken from the first resume they added it to)."""
    if not user.linkedin_url:
        return []
    url = re.sub(r"^(?:https?://)?(?:www\.)?", "", user.linkedin_url.strip(), flags=re.I)
    return [ProfileLink(label="LinkedIn", url=url.rstrip("/"))]


def with_account_links(data: ResumeData, user: User) -> ResumeData:
    """`data` plus account links it doesn't have yet (an imported CV without LinkedIn, say)."""
    have = {link.label.strip().lower() for link in data.personal_info.profile_links}
    extra = [link for link in account_profile_links(user) if link.label.lower() not in have]
    if not extra:
        return data
    links = [*data.personal_info.profile_links, *extra][:MAX_PROFILE_LINKS]
    personal = data.personal_info.model_copy(update={"profile_links": links})
    return data.model_copy(update={"personal_info": personal})


def remember_linkedin_url(user: User, data: ResumeData) -> None:
    """LinkedIn sign-in doesn't share the profile URL, so the first one a LinkedIn user
    puts on a resume is kept for their next resumes."""
    if not user.linkedin_connected or user.linkedin_url:
        return
    for link in data.personal_info.profile_links:
        url = link.url.strip()
        if link.label.strip().lower() == "linkedin" and "linkedin.com/" in url.lower():
            user.linkedin_url = url[:200]
            return


class ResumeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.resumes = ResumeRepository(session)
        self.roles = TargetRoleRepository(session)

    async def list_resumes(self, user: User) -> list[Resume]:
        return await self.resumes.list_for_user(user.id)

    async def get_resume(self, user: User, resume_id: uuid.UUID) -> Resume:
        resume = await self.resumes.get_for_user(resume_id, user.id)
        if resume is None:
            raise ResumeNotFoundError
        return resume

    async def create_resume(self, user: User, body: ResumeCreate) -> Resume:
        await self._check_role(user, body.target_role_id)
        # Anything the request leaves out comes from the user's defaults (Settings).
        given = body.model_fields_set
        resume_type = body.type if "type" in given else user.default_resume_type
        level = (
            body.experience_level if "experience_level" in given else user.default_experience_level
        )
        template = body.template or user.default_template
        data = body.data
        if data is None:
            # A new resume starts with the sections suggested for its role and career stage.
            layout, _ = await SectionService(self.session).suggest(
                user,
                role_id=body.target_role_id,
                level=level,
                resume_type=resume_type,
            )
            data = with_layout(
                ResumeData(
                    personal_info=PersonalInfo(
                        full_name=user.name,
                        email=_valid_email(user.email),
                        profile_links=account_profile_links(user),
                    )
                ),
                layout,
            )
        resume = await self.resumes.add(
            Resume(
                user_id=user.id,
                title=body.title,
                type=resume_type,
                template=template or await self._recommended_template(body.target_role_id),
                target_role_id=body.target_role_id,
                experience_level=level,
                data=data,
            )
        )
        await self.session.commit()
        return await self.get_resume(user, resume.id)

    async def update_resume(self, user: User, resume_id: uuid.UUID, body: ResumeUpdate) -> Resume:
        resume = await self.get_resume(user, resume_id)
        changes = body.model_dump(exclude_unset=True)
        if "target_role_id" in changes:
            await self._check_role(user, changes["target_role_id"])
        if "data" in changes:
            # Keep the validated model, not model_dump()'s plain dict.
            changes["data"] = body.data
            if body.data is not None:
                remember_linkedin_url(user, body.data)

        for field, value in changes.items():
            setattr(resume, field, value)
        await self.session.commit()
        return await self.get_resume(user, resume_id)

    async def duplicate_resume(self, user: User, resume_id: uuid.UUID) -> Resume:
        source = await self.get_resume(user, resume_id)
        copy = await self.resumes.add(
            Resume(
                user_id=user.id,
                title=copy_title(source.title),
                type=source.type,
                template=source.template,
                target_role_id=source.target_role_id,
                experience_level=source.experience_level,
                data=source.data.model_copy(deep=True),
            )
        )
        await self.session.commit()
        return await self.get_resume(user, copy.id)

    async def delete_resume(self, user: User, resume_id: uuid.UUID) -> None:
        resume = await self.get_resume(user, resume_id)
        await self.resumes.delete(resume)
        await self.session.commit()

    async def _recommended_template(self, role_id: uuid.UUID | None) -> ResumeTemplate:
        """The template suited to the role's field (conservative for law, academic for
        research...); Classic without a role."""
        role = await self.roles.get_with_industry(role_id) if role_id else None
        value = role.industry.recommended_template if role else None
        return (
            ResumeTemplate(value)
            if value in ResumeTemplate._value2member_map_
            else (ResumeTemplate.CLASSIC)
        )

    async def _check_role(self, user: User, role_id: uuid.UUID | None) -> None:
        # Another user's AI-generated role is as good as missing.
        if role_id is not None and not await self.roles.is_visible(role_id, user.id):
            raise TargetRoleNotFoundError


def _valid_email(email: str) -> str | None:
    # GitHub no-reply addresses are valid emails but useless on a resume.
    return None if email.endswith("@users.noreply.github.com") else email
