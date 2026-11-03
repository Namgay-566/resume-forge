"""Home screen: resume cards with score history, and the rule-based next best action."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReadinessSnapshot, User, UserSkill
from app.models.enums import PlanStatus, SkillImportance, UserSkillSource, VerificationStatus
from app.schemas.roadmap import Hours, ProofRequirement, Roadmap, RoadmapItem, RoadmapTotals
from app.schemas.target_role import TargetRoleSummary
from app.services.dashboard.next_action import next_action
from app.tests.test_roadmap import role, setup, use  # noqa: F401  (fixture)

# --- next best action (pure) ----------------------------------------------------------


class Ref:
    def __init__(self, title: str = "Main", ats_score: int | None = None) -> None:
        self.id, self.title, self.ats_score = uuid.uuid4(), title, ats_score


def item(
    name: str,
    importance: SkillImportance = SkillImportance.CRITICAL,
    gap: str = "missing",
    plan: PlanStatus = PlanStatus.NOT_STARTED,
) -> RoadmapItem:
    return RoadmapItem(
        skill_id=uuid.uuid4(),
        name=name,
        slug=name.lower(),
        category="tool",
        importance=importance,
        weight=10,
        gap_status=gap,  # type: ignore[arg-type]
        plan_status=plan,
        resources=[],
        search_phrase="",
        proof=ProofRequirement(accepted=["github_repo"], must_include=[]),
        project=None,
        hours=Hours(learn=1, project=1, total=2),
    )


def roadmap(*items: RoadmapItem) -> Roadmap:
    return Roadmap(
        resume_id=uuid.uuid4(),
        role=TargetRoleSummary(id=uuid.uuid4(), name="Full Stack Developer", slug="fs"),
        readiness=40,
        items=list(items),
        totals=RoadmapTotals(items=0, done=0, in_progress=0, hours_total=0, hours_remaining=0),
    )


def test_next_action_setup_steps() -> None:
    assert next_action(None, None, None).kind == "create_resume"
    latest = Ref("Draft")
    action = next_action(latest, None, None)
    assert action.kind == "choose_role" and "Draft" in action.title
    assert action.resume_id == latest.id


def test_biggest_gap_comes_first() -> None:
    resume = Ref()
    git = item("Git")

    action = next_action(resume, resume, roadmap(git, item("Docker", SkillImportance.IMPORTANT)))

    assert action.kind == "close_gap"
    assert action.title == "Git is your biggest gap. Start here."
    assert action.detail == "It's critical for Full Stack Developer and not on your resume yet."
    assert (action.skill_id, action.skill_slug, action.resume_id) == (
        git.skill_id,
        "git",
        resume.id,
    )


def test_biggest_gap_is_the_one_worth_most_readiness() -> None:
    resume = Ref()
    listed = item("JavaScript", gap="present_unverified")  # first in roadmap order
    missing = item("HTML/CSS")

    action = next_action(resume, resume, roadmap(listed, missing))

    assert action.title == "HTML/CSS is your biggest gap. Start here."


def test_momentum_unless_a_critical_gap_is_ignored() -> None:
    resume = Ref()
    docker = item("Docker", SkillImportance.IMPORTANT, plan=PlanStatus.IN_PROGRESS)
    sql = item("SQL", SkillImportance.IMPORTANT)
    # Top gap isn't critical: keep going with what's in progress.
    assert next_action(resume, resume, roadmap(sql, docker)).title == "Keep going with Docker"
    # A critical gap beats a smaller skill in progress...
    assert next_action(resume, resume, roadmap(item("Git"), docker)).kind == "close_gap"
    # ...but not a critical one in progress.
    python = item("Python", plan=PlanStatus.IN_PROGRESS)
    assert next_action(resume, resume, roadmap(item("Git"), python)).title == (
        "Keep going with Python"
    )


def test_prove_what_is_listed_or_learned() -> None:
    resume = Ref()
    listed = next_action(resume, resume, roadmap(item("Git", gap="present_unverified")))
    learned = next_action(resume, resume, roadmap(item("Git", plan=PlanStatus.DONE)))

    assert listed.kind == learned.kind == "prove_skill"
    assert listed.title == "Prove Git to get it verified"
    assert "on your resume" in listed.detail and "finished learning" in learned.detail


def test_ats_once_every_skill_is_verified() -> None:
    fresh = Ref()
    assert next_action(fresh, fresh, roadmap()).kind == "run_ats"
    low = Ref(ats_score=62)
    assert next_action(low, low, roadmap()).title == "Raise your ATS score from 62"
    done = next_action(Ref(ats_score=91), Ref(ats_score=91), roadmap())
    assert done.kind == "all_set" and "Full Stack Developer" in done.title


# --- API ------------------------------------------------------------------------------


async def test_dashboard_cards_history_and_next_action(
    client: AsyncClient,
    db_session: AsyncSession,
    role: dict[str, Any],  # noqa: F811  (imported fixture)
) -> None:
    provider = use()
    headers, resume_id = await setup(client, role["role"], "dash@example.com")
    other = await client.post(
        "/api/resumes", json={"title": "Draft"}, headers=headers
    )  # newest, no target role

    body = (await client.get("/api/dashboard", headers=headers)).json()

    assert body["next_action"]["kind"] == "close_gap"
    assert body["next_action"]["title"] == "Git is your biggest gap. Start here."
    assert body["next_action"]["resume_id"] == resume_id
    draft, main = body["resumes"]  # most recently edited first
    assert draft["id"] == other.json()["id"] and draft["readiness"] is None
    assert draft["readiness_history"] == [] and draft["target_role"] is None
    assert main["target_role"]["name"] == "Backend Developer"
    assert [p["score"] for p in main["readiness_history"]] == [main["readiness"]]
    assert body["resume_id"] == resume_id and body["totals"]["items"] > 0

    # Unchanged readiness adds no point; a newly verified skill does.
    await client.get("/api/dashboard", headers=headers)
    user = await db_session.scalar(select(User).where(User.email == "dash@example.com"))
    assert user
    db_session.add(
        UserSkill(
            user_id=user.id,
            skill_id=role["git"].id,
            source=UserSkillSource.VERIFIED_PROOF,
            verification_status=VerificationStatus.VERIFIED,
        )
    )
    await db_session.flush()
    for _ in range(2):
        await client.post(
            f"/api/resumes/{resume_id}/ats-analyses", json={"review": False}, headers=headers
        )

    body = (await client.get("/api/dashboard", headers=headers)).json()

    main = body["resumes"][0]  # ATS checks touched it, so it's the most recent now
    before, after = (p["score"] for p in main["readiness_history"])
    assert after > before and after == main["readiness"]
    assert len(main["ats_history"]) == 2 and main["ats_history"][-1]["score"] == main["ats_score"]
    assert main["ats_history"][0]["at"] <= main["ats_history"][1]["at"]
    assert body["next_action"]["skill_slug"] != "git"
    assert provider.requests == []  # the dashboard never calls the AI


async def test_readiness_history_is_per_target_role(
    client: AsyncClient,
    db_session: AsyncSession,
    role: dict[str, Any],  # noqa: F811  (imported fixture)
) -> None:
    use()
    headers, resume_id = await setup(client, role["role"], "dash-role@example.com")
    await client.get("/api/dashboard", headers=headers)

    await client.patch(
        f"/api/resumes/{resume_id}", json={"target_role_id": str(role["other"].id)}, headers=headers
    )
    body = (await client.get("/api/dashboard", headers=headers)).json()

    card = body["resumes"][0]
    assert card["target_role"]["name"] == "Data Analyst"
    assert [p["score"] for p in card["readiness_history"]] == [card["readiness"]]
    stored = await db_session.scalar(
        select(func.count())
        .select_from(ReadinessSnapshot)
        .where(ReadinessSnapshot.resume_id == uuid.UUID(resume_id))
    )
    assert stored == 2  # the old role's history is kept, just not mixed in


async def test_dashboard_for_new_user_suggests_a_resume(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "dash-new@example.com", "password": "password123", "name": "N"},
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    body = (await client.get("/api/dashboard", headers=headers)).json()

    assert body["resumes"] == [] and body["next_action"]["kind"] == "create_resume"
