"""Pick the one thing the user should do next, from data the dashboard already has."""

import uuid
from typing import Protocol

from app.models.enums import PlanStatus, SkillImportance
from app.schemas.dashboard import NextAction, NextActionKind
from app.schemas.roadmap import Roadmap, RoadmapItem
from app.services.proofs.rules import get_rules
from app.services.skill_gap.engine import CREDIT

GOOD_ATS = 80

_IMPORTANCE = {
    SkillImportance.CRITICAL: "critical",
    SkillImportance.IMPORTANT: "important",
    SkillImportance.NICE_TO_HAVE: "nice to have",
}


class ResumeRef(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def title(self) -> str: ...
    @property
    def ats_score(self) -> int | None: ...


def next_action(
    latest: ResumeRef | None, current: ResumeRef | None, roadmap: Roadmap | None
) -> NextAction:
    """latest: most recently edited resume; current: most recent one with a target role."""
    if latest is None:
        return NextAction(
            kind="create_resume",
            title="Create your first resume",
            detail="Everything here builds on it: your skill gap, roadmap and ATS score.",
        )
    if current is None or roadmap is None:
        return NextAction(
            kind="choose_role",
            title=f"Choose a target role for “{latest.title}”",
            detail="Pick the job you're aiming for to see your skill gap and how to close it.",
            resume_id=latest.id,
        )

    role = roadmap.role.name
    items = roadmap.items  # unverified skills, most important first
    if items:
        # The biggest gap is the one worth the most readiness: a missing critical skill beats
        # proving one already listed. Ties keep roadmap order.
        top = max(items, key=gain)
        doing = next((i for i in items if i.plan_status is PlanStatus.IN_PROGRESS), None)
        # Keep momentum, unless a critical gap is being left untouched for something smaller.
        if doing and (
            top.importance is not SkillImportance.CRITICAL
            or doing.importance is SkillImportance.CRITICAL
        ):
            return _skill(
                "continue_skill",
                f"Keep going with {doing.name}",
                "It's in progress on your roadmap. Finish the proof project, then upload proof.",
                current,
                doing,
            )
        if top.gap_status == "missing" and top.plan_status is not PlanStatus.DONE:
            return _skill(
                "close_gap",
                f"{top.name} is your biggest gap. Start here.",
                f"It's {_IMPORTANCE[top.importance]} for {role} and not on your resume yet.",
                current,
                top,
            )
        proof = _proof_phrase(top)
        detail = (
            f"You've finished learning it. Upload {proof} to get it verified."
            if top.gap_status == "missing"
            else f"It's on your resume but not verified yet. Upload {proof}."
        )
        return _skill("prove_skill", f"Prove {top.name} to get it verified", detail, current, top)

    if current.ats_score is None:
        return NextAction(
            kind="run_ats",
            title="Run your first ATS check",
            detail=f"See how applicant tracking systems read “{current.title}”.",
            resume_id=current.id,
        )
    if current.ats_score < GOOD_ATS:
        return NextAction(
            kind="improve_ats",
            title=f"Raise your ATS score from {current.ats_score}",
            detail="Open the ATS check and fix the issues that cost the most points first.",
            resume_id=current.id,
        )
    return NextAction(
        kind="all_set",
        title=f"You're job-ready for {role}",
        detail="Every skill is verified. Tailor your resume to each job you apply for.",
        resume_id=current.id,
    )


def _proof_phrase(item: RoadmapItem) -> str:
    """'a licence or registration or a certificate': the skill's two best proof types."""
    rules = get_rules()
    labels = [rules.types[t].label.lower() for t in item.proof.accepted[:2]]
    phrases = [f"an {label}" if label[0] in "aeiou" else f"a {label}" for label in labels]
    return " or ".join(phrases) or "proof"


def gain(item: RoadmapItem) -> float:
    """Readiness points (weighted) that closing this gap would add."""
    return item.weight * (1 - CREDIT[item.gap_status])


def _skill(
    kind: NextActionKind, title: str, detail: str, resume: ResumeRef, item: RoadmapItem
) -> NextAction:
    return NextAction(
        kind=kind,
        title=title,
        detail=detail,
        resume_id=resume.id,
        skill_id=item.skill_id,
        skill_slug=item.slug,
    )
