import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import writing as ai_writing
from app.ai.client import AIClient
from app.models import Resume, User
from app.repositories.skill_repository import SkillRepository
from app.schemas.ats import Location
from app.schemas.resume_data import ResumeData
from app.schemas.writing import (
    BulletImproveRequest,
    Suggestion,
    TailorResult,
    WritingOption,
    WritingOptions,
)
from app.services.ats.checks import years_of_experience
from app.services.ats.keywords import AliasIndex, contains, normalize, resume_text
from app.services.candidate_context import candidate_context
from app.services.export.document import plain_text
from app.services.resume_service import ResumeService
from app.services.sections.catalog import get_catalog
from app.services.writing.guard import guard_numbers, number_keys, placeholders


def _tidy(text: str) -> str:
    return " ".join(text.split()).rstrip(".").strip()


def indexed_resume_text(data: ResumeData) -> str:
    """Resume text with stable ids on every bullet, so suggestions can point at them."""
    lines = [f"SUMMARY: {data.summary or '(none)'}", "", "EXPERIENCE"]
    for i, e in enumerate(data.experience):
        dates = " - ".join(
            d for d in (e.start_date, "present" if e.is_current else e.end_date) if d
        )
        lines.append(
            f"[experience {i}] {', '.join(p for p in (e.title, e.company) if p)} ({dates})"
        )
        lines += [f"  [experience {i}.{b}] {bullet}" for b, bullet in enumerate(e.bullets)]
        if e.tools_and_skills:
            lines.append(f"  Tools: {', '.join(e.tools_and_skills)}")
    lines += ["", "PROJECTS"]
    for i, p in enumerate(data.projects):
        lines.append(f"[projects {i}] {p.name}: {p.description}")
        lines += [f"  [projects {i}.{b}] {bullet}" for b, bullet in enumerate(p.bullets)]
        if p.tools_and_skills:
            lines.append(f"  Tools: {', '.join(p.tools_and_skills)}")
    lines += ["", f"SKILLS: {', '.join(s.name for s in data.skills) or '(none)'}"]
    if data.education:
        lines += ["", "EDUCATION"] + [
            f"- {', '.join(x for x in (e.degree, e.field_of_study, e.institution) if x)}"
            for e in data.education
        ]
    if data.certifications:
        lines += ["", "CERTIFICATIONS"] + [f"- {c.name}" for c in data.certifications]
    return "\n".join(lines)


class WritingService:
    def __init__(self, session: AsyncSession, ai: AIClient) -> None:
        self.session = session
        self.ai = ai
        self.resumes = ResumeService(session)
        self.skills = SkillRepository(session)

    async def _resume(self, user: User, resume_id: uuid.UUID) -> Resume:
        return await self.resumes.get_resume(user, resume_id)  # raises if not the owner's

    # --- bullets ----------------------------------------------------------------------

    async def improve_bullet(
        self, user: User, resume_id: uuid.UUID, body: BulletImproveRequest
    ) -> WritingOptions:
        resume = await self._resume(user, resume_id)
        spec = get_catalog().spec(body.section)
        result = await ai_writing.improve_bullet(
            self.ai,
            bullet=body.text,
            position=body.position,
            tools=body.tools_and_skills,
            section=ai_writing.BulletSection(
                heading=body.section_title or spec.heading,
                guidance=spec.bullet_guidance or "",
            ),
            context=await candidate_context(self.session, resume),
        )
        allowed = number_keys(body.text, body.position, *body.tools_and_skills)
        options: list[WritingOption] = []
        seen = {_tidy(body.text).lower()}
        for option in result.options:
            guarded = guard_numbers(_tidy(option.text), allowed)
            if not guarded.text or guarded.text.lower() in seen:
                continue
            seen.add(guarded.text.lower())
            options.append(
                WritingOption(
                    text=guarded.text[:500],
                    rationale=option.rationale,
                    placeholders=guarded.placeholders,
                    replaced_numbers=guarded.replaced,
                )
            )
        return WritingOptions(options=options)

    # --- summary ------------------------------------------------------------------------

    async def generate_summary(self, user: User, resume_id: uuid.UUID) -> WritingOptions:
        resume = await self._resume(user, resume_id)
        text = plain_text(resume.data, resume.type)
        years = years_of_experience(resume.data)
        whole_years = math.floor(years) if years >= 1 else None
        result = await ai_writing.generate_summary(
            self.ai,
            resume_text=text,
            years=whole_years,
            context=await candidate_context(self.session, resume),
        )
        allowed = number_keys(text) | ({str(whole_years)} if whole_years else set())
        options = []
        for summary in result.options:
            guarded = guard_numbers(" ".join(summary.split()), allowed)
            options.append(
                WritingOption(
                    text=guarded.text[:2000],
                    placeholders=guarded.placeholders,
                    replaced_numbers=guarded.replaced,
                )
            )
        return WritingOptions(options=options)

    # --- tailoring ----------------------------------------------------------------------------

    async def tailor(self, user: User, resume_id: uuid.UUID, job_description: str) -> TailorResult:
        resume = await self._resume(user, resume_id)
        data = resume.data
        plan = await ai_writing.tailor(
            self.ai,
            resume_text=indexed_resume_text(data),
            job_description=job_description,
            context=await candidate_context(self.session, resume),
        )

        def bullets_of(section: str, item: int) -> list[str] | None:
            entries = data.experience if section == "experience" else data.projects
            return entries[item].bullets if 0 <= item < len(entries) else None

        suggestions: list[Suggestion] = []
        gaps = list(dict.fromkeys(g.strip() for g in plan.gaps if g.strip()))

        def add(kind: str, location: Location, reason: str, **fields: object) -> None:
            after = fields.get("after")
            suggestions.append(
                Suggestion(
                    id=f"{kind}-{len(suggestions) + 1}",
                    kind=kind,  # type: ignore[arg-type]
                    location=location,
                    reason=reason.strip(),
                    placeholders=placeholders(after) if isinstance(after, str) else [],
                    **fields,  # type: ignore[arg-type]
                )
            )

        rewritten: set[tuple[str, int, int]] = set()
        for r in plan.bullet_rewrites:
            bullets = bullets_of(r.section, r.item_index)
            key = (r.section, r.item_index, r.bullet_index)
            if bullets is None or not 0 <= r.bullet_index < len(bullets) or key in rewritten:
                continue
            before = bullets[r.bullet_index]
            after = guard_numbers(_tidy(r.text), number_keys(before)).text[:500]
            if not after or _tidy(before).lower() == after.lower():
                continue
            rewritten.add(key)
            add(
                "rewrite_bullet",
                Location(section=r.section, item_index=r.item_index),
                r.reason,
                before=before,
                after=after,
            )

        for h in plan.highlights:
            bullets = bullets_of(h.section, h.item_index)
            if bullets is None or not 0 < h.bullet_index < len(bullets):  # 0 is already first
                continue
            reordered = [bullets[h.bullet_index]] + [
                b for i, b in enumerate(bullets) if i != h.bullet_index
            ]
            add(
                "move_bullet_up",
                Location(section=h.section, item_index=h.item_index),
                h.reason,
                before_items=list(bullets),
                after_items=reordered,
            )

        current = [s.name for s in data.skills]
        lower = {name.lower(): name for name in current}
        featured = list(
            dict.fromkeys(lower[n.lower()] for n in plan.featured_skills if n.lower() in lower)
        )
        reordered_skills = featured + [n for n in current if n not in featured]
        if featured and reordered_skills != current:
            add(
                "feature_skills",
                Location(section="skills"),
                plan.featured_skills_reason or "Put the skills this job asks for first.",
                before_items=current,
                after_items=reordered_skills,
            )

        catalog = AliasIndex.from_skills(await self.skills.list_all())
        text = resume_text(data)
        have = {v for name in current for v in catalog.variants(name)}
        for skill in plan.skills_to_add:
            name = skill.name.strip()
            variants = catalog.variants(name)
            if not name or any(v in have for v in variants):
                continue  # already listed (possibly under an alias)
            if any(contains(text, v) for v in variants):  # evidence on the resume
                have.update(variants)
                add("add_skill", Location(section="skills"), skill.reason, after=name[:200])
            elif name not in gaps:
                gaps.append(name)  # no evidence: never suggest claiming it

        if plan.summary and normalize(plan.summary) != normalize(data.summary):
            allowed = number_keys(plain_text(data, resume.type))
            after = guard_numbers(" ".join(plan.summary.split()), allowed).text[:2000]
            add(
                "rewrite_summary",
                Location(section="summary"),
                plan.summary_reason or "Aim the summary at this job.",
                before=data.summary,
                after=after,
            )

        return TailorResult(suggestions=suggestions, gaps=gaps[:15])
