import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ats import JdKeywords, RecruiterReview, extract_jd_keywords, review_resume
from app.ai.client import AIClient
from app.ai.errors import AIError, AIUnavailableError
from app.models import ATSAnalysis, Resume, Skill, User
from app.models.enums import SkillImportance
from app.repositories.ats_repository import AtsAnalysisRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.target_role_repository import TargetRoleRepository
from app.schemas.ats import AIReview, AtsReport, KeywordHit, KeywordReport, SectionFeedback
from app.services.ats.checks import run_checks
from app.services.ats.keywords import AliasIndex, catalog_keywords, match_keywords, resume_text
from app.services.ats.scoring import build_fixes, score
from app.services.candidate_context import candidate_context
from app.services.export.document import plain_text
from app.services.resume_service import ResumeService
from app.services.sections.service import SectionService
from app.models.enums import PageSize, ResumeTemplate  

logger = logging.getLogger(__name__)

AIStatusValue = Literal["ok", "unavailable", "failed", "skipped", "rate_limited"]

ROLE_WEIGHTS: dict[SkillImportance, tuple[float, Literal["required", "preferred"]]] = {
    SkillImportance.CRITICAL: (3.0, "required"),
    SkillImportance.IMPORTANT: (2.0, "required"),
    SkillImportance.NICE_TO_HAVE: (1.0, "preferred"),
}
JD_WEIGHTS = {"required": 2.0, "preferred": 1.0}


class AtsService:
    def __init__(self, session: AsyncSession, ai: AIClient) -> None:
        self.session = session
        self.ai = ai
        self.resumes = ResumeService(session)
        self.skills = SkillRepository(session)
        self.roles = TargetRoleRepository(session)
        self.analyses = AtsAnalysisRepository(session)

    async def latest(
        self, user: User, resume_id: uuid.UUID
    ) -> tuple[ATSAnalysis | None, ATSAnalysis | None]:
        """(latest, the one before it) for before/after comparisons."""
        resume = await self.resumes.get_resume(user, resume_id)  # ownership check
        two = await self.analyses.latest_two(resume.id)
        return (two[0] if two else None, two[1] if len(two) > 1 else None)

    async def analyze(
        self,
        user: User,
        resume_id: uuid.UUID,
        job_description: str | None,
        *,
        review: bool = True,
        consume_ai_budget: Callable[[], bool] = lambda: True,
    ) -> tuple[ATSAnalysis, ATSAnalysis | None]:
        """Returns (new analysis, the previous one)."""
        resume = await self.resumes.get_resume(user, resume_id)
        previous = await self.analyses.latest_for_resume(resume.id)
        jd = (job_description or "").strip() or None
        data, resume_type = resume.data, resume.type

        # 1. Deterministic checks (no AI).
        role_sections = await SectionService(self.session).role_sections(resume.target_role_id)
        
        # NEW: Pass template and page size so the length check renders an actual PDF
        page_size = user.page_size or PageSize.A4
        checks = run_checks(
            data, 
            resume_type, 
            resume.experience_level, 
            role_sections,
            template=resume.template,
            page_size=page_size
        )

        # 2. AI, only where needed: an unchanged JD reuses the last analysis's keyword list,
        # and review=False skips the recruiter review (so a re-check costs nothing).
        catalog = await self.skills.list_all()
        reused = (
            previous.report.keywords.matched + previous.report.keywords.missing
            if previous
            and jd
            and previous.job_description == jd
            and previous.report.keywords.source == "job_description"
            else None
        )
        needs_ai = review or bool(jd and reused is None)
        ai_allowed = needs_ai and consume_ai_budget()
        context = await candidate_context(self.session, resume)
        needs_jd = bool(jd and reused is None and ai_allowed)
        jd_task = extract_jd_keywords(self.ai, jd, context) if jd and needs_jd else None
        review_task = (
            review_resume(
                self.ai,
                resume_text=plain_text(data, resume_type),
                job_description=jd,
                context=context,
            )
            if review and ai_allowed
            else None
        )
        tasks = [t for t in (jd_task, review_task) if t is not None]
        results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []
        jd_result = results[0] if jd_task else None
        review_result = results[-1] if review_task else None
        for result in results:  # only AI failures are tolerated; real bugs still raise
            if isinstance(result, BaseException) and not isinstance(result, AIError):
                raise result

        # 3. Keywords: JD (AI, or catalog scan fallback) or the target role's skills.
        keywords = await self._keywords(resume, jd, jd_result, catalog, reused)

        # 4. AI review.
        ai_status: AIStatusValue
        if review_task is not None and review_result is not None:
            ai_review, ai_status = self._review(review_result)
        else:
            ai_review, ai_status = None, ("skipped" if not review else "rate_limited")

        # 5. Score, fixes, save.
        total, categories, scored_checks = score(checks, keywords)
        report = AtsReport(
            score=total,
            categories=categories,
            checks=scored_checks,
            keywords=keywords,
            ai_review=ai_review,
            ai_status=ai_status,
            fixes=build_fixes(scored_checks, keywords, ai_review),
        )
        analysis = await self.analyses.add(
            ATSAnalysis(resume_id=resume.id, job_description=jd, score=total, report=report)
        )
        resume.ats_score = total
        await self.session.commit()
        await self.session.refresh(analysis, attribute_names=["created_at"])
        return analysis, previous

    async def _keywords(
        self,
        resume: Resume,
        jd: str | None,
        jd_result: JdKeywords | BaseException | None,
        catalog: list[Skill],
        reused: list[KeywordHit] | None = None,
    ) -> KeywordReport:
        index = AliasIndex.from_skills(catalog)
        text = resume_text(resume.data)
        if jd:
            if reused is not None:  # same JD as last time: re-match the same keywords
                wanted = [h.model_copy(update={"matched_as": None}) for h in reused]
                extraction = "ai"
            elif isinstance(jd_result, JdKeywords):
                wanted = [
                    KeywordHit(
                        keyword=k.keyword, importance=k.importance, weight=JD_WEIGHTS[k.importance]
                    )
                    for k in jd_result.keywords
                ]
                extraction: Literal["ai", "catalog"] = "ai"
            else:
                logger.warning(
                    "ATS: JD keyword extraction failed, using catalog scan: %s", jd_result
                )
                wanted = [
                    h.model_copy(update={"weight": JD_WEIGHTS["required"]})
                    for h in catalog_keywords(jd, catalog)
                ]
                extraction = "catalog"
            matched, missing = match_keywords(wanted, text, index)
            return KeywordReport(
                source="job_description", extraction=extraction, matched=matched, missing=missing
            )

        role_id = resume.target_role_id
        if role_id is None:
            return KeywordReport(source=None)
        wanted = []
        for rs in await self.roles.role_skills(role_id):
            weight, importance = ROLE_WEIGHTS[rs.importance]
            wanted.append(KeywordHit(keyword=rs.skill.name, importance=importance, weight=weight))
        matched, missing = match_keywords(wanted, text, index)
        return KeywordReport(
            source="target_role", extraction="target_role", matched=matched, missing=missing
        )

    def _review(
        self, result: RecruiterReview | BaseException
    ) -> tuple[AIReview | None, AIStatusValue]:
        if isinstance(result, RecruiterReview):
            return (
                AIReview(
                    overall=result.overall,
                    sections=[SectionFeedback(**s.model_dump()) for s in result.sections],
                ),
                "ok",
            )
        logger.warning("ATS: AI review skipped: %s", result)
        return None, "unavailable" if isinstance(result, AIUnavailableError) else "failed"