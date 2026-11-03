import hashlib
import json
import logging
import uuid
from collections import OrderedDict
from collections.abc import Callable
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient
from app.ai.context import NO_CONTEXT, CandidateContext
from app.ai.errors import AIError, AIUnavailableError
from app.ai.skill_inference import infer_skills
from app.models import ReadinessSnapshot, User
from app.models.enums import SkillImportance
from app.repositories.proof_repository import ProofRepository
from app.repositories.score_history_repository import ScoreHistoryRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.target_role_repository import TargetRoleRepository
from app.schemas.resume_data import ResumeData
from app.schemas.skill_gap import (
    OTHER_GROUP,
    RoleSkillGap,
    SkillGapReport,
    SkillGroupRef,
    StatusCounts,
)
from app.schemas.target_role import TargetRoleSummary
from app.services.ats.keywords import normalize
from app.services.candidate_context import candidate_context
from app.services.proofs.methods import method_label, verified_skill_ids
from app.services.proofs.rules import skill_proof_types
from app.services.resume_service import ResumeService
from app.services.skill_gap.engine import (
    IMPORTANCE_ORDER,
    CatalogSkill,
    UserSkillRecord,
    classify,
    readiness,
)

logger = logging.getLogger(__name__)

AIStatus = Literal["ok", "cached", "skipped", "rate_limited", "unavailable", "failed"]


class NoTargetRoleError(Exception):
    pass


def inference_text(data: ResumeData) -> str:
    """The prose the AI infers from: summary, bullets and project descriptions."""
    parts = [data.summary]
    for e in data.experience:
        parts += [f"{e.title} at {e.company}".strip(), *e.bullets]
    for p in data.projects:
        parts += [p.name, p.description, *p.bullets]
    for section in data.extra_sections():
        for e in section.entries:
            heading = ", ".join(x for x in (e.title, e.organization) if x)
            parts += [heading, e.description, *e.bullets]
    return "\n".join(part for part in parts if part and part.strip())


class InferenceCache:
    """Small in-process LRU so re-opening the page doesn't re-run the AI on unchanged text."""

    def __init__(self, size: int = 512) -> None:
        self._items: OrderedDict[str, dict[str, str]] = OrderedDict()
        self._size = size

    def get(self, key: str) -> dict[str, str] | None:
        if key in self._items:
            self._items.move_to_end(key)
            return self._items[key]
        return None

    def put(self, key: str, value: dict[str, str]) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        while len(self._items) > self._size:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()


inference_cache = InferenceCache()


def cache_key(text: str, candidates: list[str]) -> str:
    raw = json.dumps({"t": text, "c": sorted(candidates)}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


async def verification_methods(session: AsyncSession, user_id: uuid.UUID) -> dict[uuid.UUID, str]:
    """Skill id -> how its newest verified proof verified it ("Verified by referee")."""
    proofs = await ProofRepository(session).verified_for_user(user_id)
    found: dict[uuid.UUID, str] = {}
    for proof in proofs:
        report = proof.ai_report
        label = method_label(proof.type, report.verification_level if report else None, report)
        if label:
            for skill_id in verified_skill_ids({s.id for s in proof.skills}, report):
                found[skill_id] = label  # newest wins
    return found


class SkillGapService:
    def __init__(self, session: AsyncSession, ai: AIClient) -> None:
        self.ai = ai
        self.session = session
        self.resumes = ResumeService(session)
        self.history = ScoreHistoryRepository(session)
        # One user per service instance: the dashboard reports on several resumes at once.
        self._mine: dict[uuid.UUID, UserSkillRecord] | None = None
        self.roles = TargetRoleRepository(session)
        self.skills = SkillRepository(session)

    async def report(
        self,
        user: User,
        resume_id: uuid.UUID,
        *,
        consume_ai_budget: Callable[[], bool],
        allow_ai: bool = True,
    ) -> SkillGapReport:
        """allow_ai=False uses cached inferences only and never calls the AI (e.g. dashboard)."""
        resume = await self.resumes.get_resume(user, resume_id)
        if resume.target_role is None:
            raise NoTargetRoleError
        data = resume.data
        role_skills = await self.roles.role_skills(resume.target_role.id)
        mine = await self._user_skills(user)
        catalog = {
            rs.skill_id: CatalogSkill.build(rs.skill_id, rs.skill.name, rs.skill.aliases)
            for rs in role_skills
        }

        # Deterministic pass first; only skills still missing are worth asking the AI about.
        first = {sid: classify(skill, data, mine.get(sid), None) for sid, skill in catalog.items()}
        candidates = [catalog[sid].name for sid, r in first.items() if r.status == "missing"]
        context = await candidate_context(self.session, resume)
        inferred, ai_status = await self._infer(
            data, candidates, consume_ai_budget, allow_ai, context
        )

        methods = await verification_methods(self.session, user.id)
        items: list[RoleSkillGap] = []
        for rs in role_skills:
            skill = catalog[rs.skill_id]
            result = classify(skill, data, mine.get(rs.skill_id), inferred.get(skill.name))
            items.append(
                RoleSkillGap(
                    skill_id=rs.skill_id,
                    name=rs.skill.name,
                    slug=rs.skill.slug,
                    category=rs.skill.category,
                    importance=rs.importance,
                    weight=rs.weight,
                    status=result.status,
                    evidence=result.evidence,
                    verification_status=result.verification_status,
                    verified_by=methods.get(rs.skill_id)
                    if result.status == "present_verified"
                    else None,
                    proof_types=skill_proof_types(
                        rs.skill.slug, rs.skill.category, rs.skill.proof_types
                    ),
                    group=SkillGroupRef.model_validate(rs.skill.group)
                    if rs.skill.group
                    else OTHER_GROUP,
                )
            )
        items.sort(key=lambda i: (IMPORTANCE_ORDER[i.importance], -i.weight, i.name))

        counts = StatusCounts()
        for item in items:
            setattr(counts, item.status, getattr(counts, item.status) + 1)
        score = readiness((i.weight, i.status) for i in items)
        await self._record(resume.id, resume.target_role.id, score)
        return SkillGapReport(
            resume_id=resume.id,
            role=TargetRoleSummary.model_validate(resume.target_role),
            readiness=score,
            skills=items,
            counts=counts,
            missing_critical=[
                i.name
                for i in items
                if i.status == "missing" and i.importance is SkillImportance.CRITICAL
            ],
            ai_status=ai_status,
        )

    async def _user_skills(self, user: User) -> dict[uuid.UUID, UserSkillRecord]:
        if self._mine is None:
            self._mine = {
                us.skill_id: UserSkillRecord(us.skill_id, us.verification_status)
                for us in await self.skills.user_skills(user.id)
            }
        return self._mine

    async def _record(self, resume_id: uuid.UUID, role_id: uuid.UUID, score: int) -> None:
        """Add a history point when readiness (or the role it's measured against) changed."""
        last = await self.history.latest_readiness(resume_id)
        if last is not None and last.score == score and last.target_role_id == role_id:
            return
        await self.history.add_readiness(
            ReadinessSnapshot(resume_id=resume_id, target_role_id=role_id, score=score)
        )
        await self.session.commit()

    async def _infer(
        self,
        data: ResumeData,
        candidates: list[str],
        consume_ai_budget: Callable[[], bool],
        allow_ai: bool = True,
        context: CandidateContext = NO_CONTEXT,
    ) -> tuple[dict[str, str], AIStatus]:
        """skill name -> evidence quote, validated against the resume text."""
        text = inference_text(data)
        if not candidates or not text.strip():
            return {}, "skipped"
        key = cache_key(text, candidates)
        if (cached := inference_cache.get(key)) is not None:
            return cached, "cached"
        if not allow_ai:
            return {}, "skipped"
        if not consume_ai_budget():
            return {}, "rate_limited"
        try:
            result = await infer_skills(
                self.ai, resume_text=text, candidates=candidates, context=context
            )
        except AIUnavailableError as exc:
            logger.warning("Skill gap: AI unavailable: %s", exc)
            return {}, "unavailable"
        except AIError as exc:
            logger.warning("Skill gap: inference failed: %s", exc)
            return {}, "failed"

        allowed = {normalize(c): c for c in candidates}
        haystack = normalize(text)
        inferred: dict[str, str] = {}
        for item in result.skills:
            name = allowed.get(normalize(item.skill))
            quote = " ".join(item.evidence.split())
            # Keep only candidates, with evidence that really is in the resume.
            if name and quote and normalize(quote) in haystack and name not in inferred:
                inferred[name] = quote
        inference_cache.put(key, inferred)
        return inferred, "ok"
