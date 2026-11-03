import json
import uuid
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient, get_ai_client
from app.ai.errors import AIUnavailableError
from app.ai.project_ideas import _clean, strip_urls
from app.ai.types import AIRequest, AIResponse
from app.core.config import get_settings
from app.main import app
from app.models import LearningResource, RoleSkill, Skill, TargetRole, User, UserSkill
from app.models.enums import (
    PlanStatus,
    ResourceType,
    SkillImportance,
    UserSkillSource,
    VerificationStatus,
)
from app.schemas.project_idea import ProjectIdea
from app.schemas.roadmap import Hours, ProofRequirement, RoadmapItem
from app.schemas.skill_gap import RoleSkillGap
from app.services.roadmap.proof_requirements import proof_requirement
from app.services.roadmap.service import learn_hours, totals
from app.tests.fakes import an_industry

IDEA = {
    "title": "Branch-based feature workflow",
    "summary": "Build a feature on a branch and merge it by pull request, see https://example.com/guide.",
    "steps": [
        "Create a repo",
        "Work on feature branches (docs at git-scm.com/docs)",
        "Open pull requests",
    ],
    "reviewer_checks": ["Commits are small and well described", "Merged via pull requests"],
    "est_hours": 6,
    "stretch": "Add a CI check on pull requests",
}


# --- deterministic pieces -------------------------------------------------------------


def test_proof_requirements_are_specific_where_it_matters() -> None:
    git = proof_requirement("git", "tool", "Git")
    cloud = proof_requirement("cloud-deployment", "platform", "Deployment & Cloud")
    # As seeded: technology skills are proven with code.
    other = proof_requirement("react", "framework", "React", ["github_repo", "live_link"])

    assert git.accepted == ["github_repo"] and any("pull requests" in m for m in git.must_include)
    assert "certificate" in cloud.accepted and "live_link" in cloud.accepted
    assert any("React" in m for m in other.must_include)
    assert any("10 meaningful commits" in m for m in other.must_include)


def test_proof_requirements_fit_every_profession() -> None:
    licence = proof_requirement("nursing-license", "license", "Nursing License")
    excel = proof_requirement("spreadsheets", "tool", "Spreadsheets")
    teamwork = proof_requirement("teamwork", "soft_skill", "Teamwork")

    assert licence.accepted[0] == "professional_license"
    assert any("expiry" in m for m in licence.must_include)
    assert excel.accepted == ["work_sample", "certificate"]
    assert any("Spreadsheets" in m for m in excel.must_include)
    assert teamwork.accepted[0] == "referee_confirmation"
    assert not any("GitHub" in m for m in licence.must_include + excel.must_include)


def test_project_ideas_never_contain_urls() -> None:
    cleaned = _clean(ProjectIdea.model_validate(IDEA))

    text = json.dumps(cleaned.model_dump())
    assert "http" not in text and "example.com" not in text and "git-scm.com" not in text
    assert cleaned.steps[1] == "Work on feature branches (docs at)"
    assert strip_urls("Tag a release (guide at docs.github.com/releases)") == (
        "Tag a release (guide at)"
    )  # subdomains go too, not just the last two labels
    # A URL ending a sentence takes the link only, not the full stop.
    assert cleaned.summary.endswith("merge it by pull request, see.")


def gap(status: str) -> RoleSkillGap:
    return RoleSkillGap(
        skill_id=uuid.uuid4(),
        name="Git",
        slug="git",
        category="tool",
        importance=SkillImportance.CRITICAL,
        weight=10,
        status=status,
        evidence=[],  # type: ignore[arg-type]
    )


def resource(hours: str | None) -> LearningResource:
    return LearningResource(
        title="x",
        provider="x",
        url="https://x",
        type=ResourceType.DOCS,
        level="beginner",
        is_free=True,
        est_hours=Decimal(hours) if hours else None,
    )


def test_learn_hours() -> None:
    assert learn_hours(gap("missing"), [resource("4"), resource("12")]) == 4.0  # starter resource
    assert learn_hours(gap("inferred"), []) == 6.0  # default without resources
    assert learn_hours(gap("missing"), [resource("300")]) == 30.0  # huge courses capped
    assert learn_hours(gap("present_unverified"), [resource("4")]) == 0.0  # just prove it


def test_totals_exclude_done_items_from_remaining() -> None:
    def item(total: float, status: PlanStatus) -> RoadmapItem:
        g = gap("missing")
        return RoadmapItem(
            skill_id=g.skill_id,
            name=g.name,
            slug=g.slug,
            category=g.category,
            importance=g.importance,
            weight=g.weight,
            gap_status="missing",
            plan_status=status,
            resources=[],
            search_phrase="",
            proof=ProofRequirement(accepted=["github_repo"], must_include=[]),
            project=None,
            hours=Hours(learn=0, project=total, total=total),
        )

    result = totals(
        [
            item(10, PlanStatus.DONE),
            item(6, PlanStatus.IN_PROGRESS),
            item(4, PlanStatus.NOT_STARTED),
        ]
    )

    assert (result.items, result.done, result.in_progress) == (3, 1, 1)
    assert (result.hours_total, result.hours_remaining) == (20, 10)


# --- endpoints ---------------------------------------------------------------------------


class ProjectProvider:
    name, model = "fake", "fake-1"

    def __init__(self, answer: Any = IDEA) -> None:
        self.answer = answer
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        if isinstance(self.answer, Exception):
            raise self.answer
        return AIResponse(text=json.dumps(self.answer), model=self.model)


def use(answer: Any = IDEA) -> ProjectProvider:
    provider = ProjectProvider(answer)
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)
    return provider


@pytest.fixture
async def role(db_session: AsyncSession) -> dict[str, Any]:
    skills = {
        "git": Skill(name="Git", slug="git", category="tool", aliases=["git"]),
        "python": Skill(name="Python", slug="python", category="language", aliases=["python"]),
        "docker": Skill(name="Docker", slug="docker", category="tool", aliases=["docker"]),
        "sql": Skill(name="SQL", slug="sql", category="database", aliases=["sql"]),
        "ci": Skill(name="CI/CD", slug="ci-cd", category="practice", aliases=["ci/cd"]),
    }
    role = TargetRole(
        name="Backend Developer",
        slug="backend",
        description="",
        seniority="junior",
        industry=an_industry(),
    )
    other = TargetRole(
        name="Data Analyst",
        slug="analyst",
        description="",
        seniority="junior",
        industry=an_industry(),
    )
    db_session.add_all([*skills.values(), role, other])
    await db_session.flush()
    spec = [
        ("git", SkillImportance.CRITICAL, 10),
        ("python", SkillImportance.CRITICAL, 10),
        ("sql", SkillImportance.CRITICAL, 9),
        ("docker", SkillImportance.IMPORTANT, 6),
        ("ci", SkillImportance.NICE_TO_HAVE, 3),
    ]
    db_session.add_all(
        [
            RoleSkill(role_id=role.id, skill_id=skills[k].id, importance=i, weight=w)
            for k, i, w in spec
        ]
    )
    db_session.add(
        RoleSkill(
            role_id=other.id,
            skill_id=skills["sql"].id,
            importance=SkillImportance.CRITICAL,
            weight=10,
        )
    )
    db_session.add_all(
        [
            LearningResource(
                skill_id=skills["git"].id,
                title="Paid advanced",
                provider="P",
                url="https://paid.example",
                type=ResourceType.COURSE,
                level="advanced",
                is_free=False,
                est_hours=Decimal("2"),
            ),
            LearningResource(
                skill_id=skills["git"].id,
                title="Free intermediate",
                provider="P",
                url="https://intermediate.example",
                type=ResourceType.DOCS,
                level="intermediate",
                is_free=True,
                est_hours=Decimal("1"),
            ),
            LearningResource(
                skill_id=skills["git"].id,
                title="Free beginner",
                provider="P",
                url="https://beginner.example",
                type=ResourceType.TUTORIAL,
                level="beginner",
                is_free=True,
                est_hours=Decimal("4"),
            ),
        ]
    )
    await db_session.commit()
    return {"role": role, "other": other, **skills}


async def setup(
    client: AsyncClient, role: TargetRole, email: str = "road@example.com"
) -> tuple[dict[str, str], str]:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123", "name": "Ada"}
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    data = {"skills": [{"name": "Python"}, {"name": "SQL"}]}
    created = await client.post(
        "/api/resumes",
        json={"title": "Main", "target_role_id": str(role.id), "data": data},
        headers=headers,
    )
    return headers, created.json()["id"]


async def test_roadmap_orders_gaps_and_ranks_resources(
    client: AsyncClient, db_session: AsyncSession, role: dict[str, Any]
) -> None:
    use()
    headers, resume_id = await setup(client, role["role"])
    user = await db_session.scalar(select(User).where(User.email == "road@example.com"))
    assert user
    db_session.add(
        UserSkill(
            user_id=user.id,
            skill_id=role["sql"].id,
            source=UserSkillSource.VERIFIED_PROOF,
            verification_status=VerificationStatus.VERIFIED,
        )
    )
    await db_session.commit()

    body = (await client.get(f"/api/resumes/{resume_id}/roadmap", headers=headers)).json()

    names = [i["name"] for i in body["items"]]
    assert names == ["Git", "Python", "Docker", "CI/CD"]  # verified SQL left out; by importance
    git = body["items"][0]
    assert [r["title"] for r in git["resources"]] == [
        "Free beginner",
        "Free intermediate",
        "Paid advanced",
    ]
    assert git["proof"]["accepted"] == ["github_repo"]
    assert git["plan_status"] == "not_started" and git["project"] is None
    assert git["hours"] == {
        "learn": 4.0,
        "project": 8.0,
        "total": 12.0,
    }  # starter resource + default
    python = body["items"][1]
    assert python["gap_status"] == "present_unverified"
    assert python["hours"]["learn"] == 0.0  # already on the resume: only needs proof
    assert (
        body["totals"]["items"] == 4
        and body["totals"]["hours_remaining"] == body["totals"]["hours_total"]
    )


async def test_status_updates_persist_and_update_totals(
    client: AsyncClient, role: dict[str, Any]
) -> None:
    use()
    headers, resume_id = await setup(client, role["role"])
    git_id = str(role["git"].id)

    started = await client.put(
        f"/api/roadmap/{git_id}", json={"status": "in_progress"}, headers=headers
    )
    assert started.status_code == 200 and started.json()["status"] == "in_progress"
    await client.put(f"/api/roadmap/{role['docker'].id}", json={"status": "done"}, headers=headers)

    body = (await client.get(f"/api/resumes/{resume_id}/roadmap", headers=headers)).json()
    statuses = {i["name"]: i["plan_status"] for i in body["items"]}
    assert statuses["Git"] == "in_progress" and statuses["Docker"] == "done"
    docker_hours = next(i["hours"]["total"] for i in body["items"] if i["name"] == "Docker")
    assert body["totals"]["done"] == 1 and body["totals"]["in_progress"] == 1
    assert body["totals"]["hours_remaining"] == round(
        body["totals"]["hours_total"] - docker_hours, 1
    )

    bad = await client.put(f"/api/roadmap/{uuid.uuid4()}", json={"status": "done"}, headers=headers)
    invalid = await client.put(
        f"/api/roadmap/{git_id}", json={"status": "finished"}, headers=headers
    )
    assert (bad.status_code, invalid.status_code) == (404, 422)


async def test_project_idea_is_generated_once_and_reused(
    client: AsyncClient, role: dict[str, Any]
) -> None:
    provider = use()
    headers, resume_id = await setup(client, role["role"])
    url = f"/api/resumes/{resume_id}/roadmap/{role['git'].id}/project"

    first = await client.post(url, headers=headers)
    second = await client.post(url, headers=headers)

    assert first.status_code == 200, first.text
    idea = first.json()
    assert idea["tailored_for"] == "Backend Developer"
    assert "http" not in json.dumps(idea) and "example.com" not in json.dumps(idea)
    assert second.json() == idea and len(provider.requests) == 1  # cached in the plan item
    prompt = provider.requests[0].prompt
    assert "Skill to prove: Git" in prompt and "Target role: Backend Developer" in prompt
    assert "new to this skill" in prompt  # Git is missing, so it's also a learning project

    regenerated = await client.post(f"{url}?regenerate=true", headers=headers)
    assert regenerated.status_code == 200 and len(provider.requests) == 2

    roadmap = (await client.get(f"/api/resumes/{resume_id}/roadmap", headers=headers)).json()
    git = roadmap["items"][0]
    assert git["project"]["title"] == IDEA["title"]
    assert git["hours"]["project"] == 6.0  # now uses the project's own estimate


async def test_project_idea_for_skill_already_listed(
    client: AsyncClient, role: dict[str, Any]
) -> None:
    provider = use()
    headers, resume_id = await setup(client, role["role"])

    await client.post(
        f"/api/resumes/{resume_id}/roadmap/{role['python'].id}/project", headers=headers
    )

    assert "already lists this skill" in provider.requests[0].prompt


async def test_project_idea_errors(
    client: AsyncClient, role: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    use(AIUnavailableError("no key"))
    headers, resume_id = await setup(client, role["role"])
    base = f"/api/resumes/{resume_id}/roadmap"

    outage = await client.post(f"{base}/{role['git'].id}/project", headers=headers)
    not_in_role = await client.post(f"{base}/{uuid.uuid4()}/project", headers=headers)
    monkeypatch.setattr(get_settings(), "ai_rate_limit", "1/minute")
    use()
    await client.post(f"{base}/{role['docker'].id}/project", headers=headers)
    limited = await client.post(f"{base}/{role['ci'].id}/project", headers=headers)

    assert outage.status_code == 503
    assert not_in_role.status_code == 404
    assert limited.status_code == 429


async def test_dashboard_summarises_without_calling_ai(
    client: AsyncClient, role: dict[str, Any]
) -> None:
    provider = use()
    headers, resume_id = await setup(client, role["role"])
    await client.put(
        f"/api/roadmap/{role['docker'].id}", json={"status": "in_progress"}, headers=headers
    )
    await client.put(f"/api/roadmap/{role['git'].id}", json={"status": "done"}, headers=headers)

    body = (await client.get("/api/dashboard", headers=headers)).json()

    assert body["resume_id"] == resume_id and body["role"]["name"] == "Backend Developer"
    assert isinstance(body["readiness"], int)
    assert body["totals"]["done"] == 1 and body["totals"]["in_progress"] == 1
    assert body["next_up"]["name"] == "Docker"  # in-progress items come first
    assert provider.requests == []


async def test_dashboard_for_new_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "password123", "name": "N"},
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    body = (await client.get("/api/dashboard", headers=headers)).json()

    assert body["resume_count"] == 0 and body["totals"] is None and body["next_up"] is None


async def test_roadmap_is_owner_only(client: AsyncClient, role: dict[str, Any]) -> None:
    use()
    _, resume_id = await setup(client, role["role"], "owner-road@example.com")
    intruder, _ = await setup(client, role["role"], "intruder-road@example.com")

    assert (
        await client.get(f"/api/resumes/{resume_id}/roadmap", headers=intruder)
    ).status_code == 404
    project = await client.post(
        f"/api/resumes/{resume_id}/roadmap/{role['git'].id}/project", headers=intruder
    )
    assert project.status_code == 404
