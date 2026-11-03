import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.client import AIClient
from app.ai.project_draft import draft_project
from app.models import Proof, Resume, Skill, User, UserSkill
from app.models.enums import ProofStatus, ProofType, VerificationStatus
from app.schemas.proof_report import ProjectDraft
from app.schemas.suggestions import ProofLink, SuggestionsResponse
from app.services.ats.keywords import normalize
from app.services.candidate_context import candidate_context
from app.services.resume_service import ResumeService
from app.services.suggestions.engine import ProofView, SkillView, proof_link, suggest


class ProofNotSuggestableError(Exception):
    pass


class AIBudgetExhaustedError(Exception):
    pass


async def proof_views(session: AsyncSession, user_id: uuid.UUID) -> list[ProofView]:
    proofs = list(
        await session.scalars(
            select(Proof)
            .where(Proof.user_id == user_id)
            .options(selectinload(Proof.skills))
            .order_by(Proof.created_at)
        )
    )
    return [
        ProofView(
            id=p.id,
            type=p.type,
            status=p.status,
            url=p.url,
            report=p.ai_report,
            skill_ids=frozenset(s.id for s in p.skills),
            created_order=i,
        )
        for i, p in enumerate(proofs)
    ]


async def proof_links(session: AsyncSession, user_id: uuid.UUID) -> dict[str, ProofLink]:
    """Every non-rejected proof, keyed by id, for citing on the resume and in exports."""
    return {
        str(view.id): proof_link(view)
        for view in await proof_views(session, user_id)
        if view.status is not ProofStatus.REJECTED
    }


class SuggestionService:
    def __init__(self, session: AsyncSession, ai: AIClient) -> None:
        self.session = session
        self.ai = ai
        self.resumes = ResumeService(session)

    async def suggestions(self, user: User, resume_id: uuid.UUID) -> SuggestionsResponse:
        resume = await self.resumes.get_resume(user, resume_id)
        views = await proof_views(self.session, user.id)
        verified = [
            SkillView(
                id=s.id,
                name=s.name,
                aliases=frozenset({normalize(a) for a in [s.name, *s.aliases]}),
            )
            for s in await self.session.scalars(
                select(Skill)
                .join(UserSkill, UserSkill.skill_id == Skill.id)
                .where(
                    UserSkill.user_id == user.id,
                    UserSkill.verification_status == VerificationStatus.VERIFIED,
                )
                .order_by(Skill.name)
            )
        ]
        return SuggestionsResponse(
            suggestions=suggest(resume.data, views, verified, resume.dismissed_suggestions),
            proof_links={
                str(v.id): proof_link(v) for v in views if v.status is not ProofStatus.REJECTED
            },
        )

    async def dismiss(self, user: User, resume_id: uuid.UUID, suggestion_id: str) -> None:
        resume: Resume = await self.resumes.get_resume(user, resume_id)
        if suggestion_id not in resume.dismissed_suggestions:
            resume.dismissed_suggestions = [*resume.dismissed_suggestions, suggestion_id[:80]]
            await self.session.commit()

    async def project_draft(
        self,
        user: User,
        resume_id: uuid.UUID,
        proof_id: uuid.UUID,
        *,
        regenerate: bool,
        consume_ai_budget: Callable[[], bool],
    ) -> ProjectDraft:
        resume = await self.resumes.get_resume(user, resume_id)
        proof = await self.session.scalar(
            select(Proof).where(Proof.id == proof_id, Proof.user_id == user.id)
        )
        if (
            proof is None
            or proof.type is not ProofType.GITHUB_REPO
            or proof.status is not ProofStatus.VERIFIED
            or not proof.ai_report
            or not proof.ai_report.repo
        ):
            raise ProofNotSuggestableError
        report = proof.ai_report
        if report.resume_draft and not regenerate:
            return report.resume_draft
        if not consume_ai_budget():
            raise AIBudgetExhaustedError
        draft = await draft_project(
            self.ai,
            report=report,
            repo_url=proof.url or report.repo.url,
            context=await candidate_context(self.session, resume),
        )
        proof.ai_report = report.model_copy(update={"resume_draft": draft})  # new object -> saved
        await self.session.commit()
        return draft
