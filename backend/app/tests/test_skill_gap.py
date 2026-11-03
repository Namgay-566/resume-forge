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
from app.ai.types import AIRequest, AIResponse
from app.core.config import get_settings
from app.main import app
from app.models import LearningResource, RoleSkill, Skill, TargetRole, User, UserSkill
from app.models.enums import (
    ResourceType,
    SkillImportance,
    UserSkillSource,
    VerificationStatus,
)
from app.schemas.resume_data import ResumeData
from app.services.skill_gap.engine import CatalogSkill, UserSkillRecord, classify, readiness
from app.tests.fakes import an_industry


def skill(name: str, *aliases: str) -> CatalogSkill:
    return CatalogSkill.build(uuid.uuid4(), name, aliases)


def resume(**overrides: Any) -> ResumeData:
    return ResumeData.model_validate(overrides)


SQL = skill("SQL", "sql", "postgres", "postgresql")
PYTHON = skill("Python", "python", "python3")
DOCKER = skill("Docker", "docker", "containers")
JAVA = skill("Java", "java")
BACKEND = skill("Backend Framework", "fastapi", "django", "express")
PYWEB = skill("Python Web Framework", "fastapi", "django", "flask")


# --- matching and aliases ----------------------------------------------------------


def test_skills_section_matches_through_aliases_and_versions() -> None:
    data = resume(skills=[{"name": "Postgres"}, {"name": "Python 3.11"}])

    assert classify(SQL, data, None, None).status == "present_unverified"
    assert classify(PYTHON, data, None, None).evidence[0].kind == "skills_section"


def test_tech_lists_count_and_say_where() -> None:
    data = resume(
        experience=[{"company": "Acme", "title": "Dev", "tools_and_skills": ["Docker"]}],
        projects=[{"name": "Tracker", "tools_and_skills": ["Docker"]}],
    )

    evidence = classify(DOCKER, data, None, None).evidence
    assert [e.detail for e in evidence] == ["Tools used at Acme", "Tools used in Tracker"]


def test_skill_named_in_bullet_text_counts() -> None:
    data = resume(
        experience=[
            {
                "company": "Acme",
                "title": "Dev",
                "bullets": ["Wrote reporting queries in PostgreSQL"],
            }
        ]
    )

    result = classify(SQL, data, None, None)
    assert result.status == "present_unverified"
    assert result.evidence[0].kind == "resume_text"


def test_one_alias_can_satisfy_two_skills() -> None:
    data = resume(skills=[{"name": "FastAPI"}])

    assert classify(BACKEND, data, None, None).status == "present_unverified"
    assert classify(PYWEB, data, None, None).status == "present_unverified"


def test_no_substring_false_positives() -> None:
    data = resume(skills=[{"name": "JavaScript"}], summary="JavaScript developer")

    assert classify(JAVA, data, None, None).status == "missing"


# --- status precedence ----------------------------------------------------------------


def test_verified_proof_beats_everything_even_off_resume() -> None:
    record = UserSkillRecord(DOCKER.id, VerificationStatus.VERIFIED)

    result = classify(DOCKER, resume(), record, "inferred text")

    assert result.status == "present_verified"
    assert result.evidence[0].kind == "verified_proof"


def test_pending_proof_is_unverified_with_a_note() -> None:
    record = UserSkillRecord(DOCKER.id, VerificationStatus.PENDING)

    result = classify(DOCKER, resume(), record, None)

    assert result.status == "present_unverified"
    assert result.evidence[-1].detail == "Proof is being reviewed"


def test_rejected_proof_does_not_count() -> None:
    record = UserSkillRecord(DOCKER.id, VerificationStatus.REJECTED)

    assert classify(DOCKER, resume(), record, None).status == "missing"


def test_ai_inference_only_when_nothing_explicit() -> None:
    data = resume(skills=[{"name": "Docker"}])

    assert classify(DOCKER, data, None, "Built images").status == "present_unverified"
    inferred = classify(SQL, data, None, "Designed the reporting schema")
    assert inferred.status == "inferred"
    assert inferred.evidence[0].detail == "Designed the reporting schema"


# --- readiness scoring ----------------------------------------------------------------


def test_readiness_is_weighted_by_importance() -> None:
    # critical(10) verified, important(5) missing, nice(2) unverified -> (10 + 0 + 1.5) / 17
    assert readiness([(10, "present_verified"), (5, "missing"), (2, "present_unverified")]) == 68


def test_missing_a_critical_skill_costs_more_than_a_nice_to_have() -> None:
    missing_critical = readiness([(10, "missing"), (2, "present_verified")])
    missing_nice = readiness([(10, "present_verified"), (2, "missing")])

    assert missing_critical < 20 < 80 < missing_nice


def test_readiness_credit_per_status() -> None:
    assert readiness([(4, "present_verified")]) == 100
    assert readiness([(4, "present_unverified")]) == 75
    assert readiness([(4, "inferred")]) == 40
    assert readiness([(4, "missing")]) == 0
    assert readiness([]) == 0


# --- endpoint ----------------------------------------------------------------------------


class InferenceProvider:
    name, model = "fake", "fake-1"

    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        if isinstance(self.answer, Exception):
            raise self.answer
        return AIResponse(text=json.dumps(self.answer), model=self.model)


def use(answer: Any) -> InferenceProvider:
    provider = InferenceProvider(answer)
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)
    return provider


INFERRED = {
    "skills": [
        {"skill": "REST APIs", "evidence": "Built REST endpoints for the billing service"},
        {"skill": "Testing", "evidence": "wrote many unit tests for everything"},  # not in resume
        {
            "skill": "Kubernetes",
            "evidence": "Built REST endpoints for the billing service",
        },  # not a candidate
    ]
}

RESUME = {
    "personal_info": {"full_name": "Ada"},
    "experience": [
        {
            "company": "Acme",
            "title": "Engineer",
            "bullets": [
                "Built REST endpoints for the billing service",
                "Shipped features in FastAPI",
            ],
            "tools_and_skills": ["Python"],
        }
    ],
    "skills": [{"name": "Git"}],
}


@pytest.fixture
async def role(db_session: AsyncSession) -> TargetRole:
    skills = {
        "git": Skill(name="Git", slug="git", category="tool", aliases=["git", "github"]),
        "python": Skill(name="Python", slug="python", category="lang", aliases=["python"]),
        "rest": Skill(name="REST APIs", slug="rest-apis", category="concept", aliases=["rest api"]),
        "docker": Skill(name="Docker", slug="docker", category="tool", aliases=["docker"]),
        "testing": Skill(name="Testing", slug="testing", category="practice", aliases=["pytest"]),
        "sql": Skill(name="SQL", slug="sql", category="db", aliases=["sql", "postgres"]),
    }
    role = TargetRole(
        name="Backend Developer",
        slug="backend",
        description="",
        seniority="junior",
        industry=an_industry(),
    )
    db_session.add_all([*skills.values(), role])
    await db_session.flush()
    spec = [
        ("git", SkillImportance.CRITICAL, 10),
        ("python", SkillImportance.CRITICAL, 10),
        ("sql", SkillImportance.CRITICAL, 9),
        ("rest", SkillImportance.CRITICAL, 9),
        ("docker", SkillImportance.IMPORTANT, 6),
        ("testing", SkillImportance.NICE_TO_HAVE, 3),
    ]
    db_session.add_all(
        [
            RoleSkill(role_id=role.id, skill_id=skills[k].id, importance=i, weight=w)
            for k, i, w in spec
        ]
    )
    db_session.add(
        LearningResource(
            skill_id=skills["sql"].id,
            title="SQLBolt",
            provider="SQLBolt",
            url="https://sqlbolt.com/",
            type=ResourceType.TUTORIAL,
            level="beginner",
            is_free=True,
            est_hours=Decimal("4"),
        )
    )
    await db_session.commit()
    return role


async def setup(
    client: AsyncClient, role: TargetRole | None, email: str = "gap@example.com"
) -> tuple[dict[str, str], str]:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123", "name": "Ada"}
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    body: dict[str, Any] = {"title": "Main", "data": RESUME}
    if role:
        body["target_role_id"] = str(role.id)
    created = await client.post("/api/resumes", json=body, headers=headers)
    return headers, created.json()["id"]


async def test_skill_gap_report(
    client: AsyncClient, db_session: AsyncSession, role: TargetRole
) -> None:
    provider = use(INFERRED)
    headers, resume_id = await setup(client, role)
    user = await db_session.scalar(select(User).where(User.email == "gap@example.com"))
    docker = await db_session.scalar(select(Skill).where(Skill.slug == "docker"))
    assert user and docker
    db_session.add(
        UserSkill(
            user_id=user.id,
            skill_id=docker.id,
            source=UserSkillSource.VERIFIED_PROOF,
            verification_status=VerificationStatus.VERIFIED,
        )
    )
    await db_session.commit()

    response = await client.get(f"/api/resumes/{resume_id}/skill-gap", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    status = {s["name"]: s["status"] for s in body["skills"]}
    assert status == {
        "Git": "present_unverified",  # skills section
        "Python": "present_unverified",  # tech list
        "REST APIs": "inferred",  # AI, with a real quote from the resume
        "SQL": "missing",
        "Docker": "present_verified",  # verified proof, even though not on the resume
        "Testing": "missing",  # AI claim had fabricated evidence -> dropped
    }
    assert [s["name"] for s in body["skills"]][:4] == ["Git", "Python", "REST APIs", "SQL"]
    assert body["missing_critical"] == ["SQL"]
    assert body["counts"] == {
        "present_verified": 1,
        "present_unverified": 2,
        "inferred": 1,
        "missing": 2,
    }
    # (10*.75 + 10*.75 + 9*.4 + 9*0 + 6*1 + 3*0) / 47
    assert body["readiness"] == round(100 * 24.6 / 47)
    assert body["ai_status"] == "ok"
    rest = next(s for s in body["skills"] if s["name"] == "REST APIs")
    assert rest["evidence"][0]["detail"] == "Built REST endpoints for the billing service"
    # Only skills that were still missing were offered to the AI.
    prompt = provider.requests[0].prompt
    assert "- SQL" in prompt and "- REST APIs" in prompt and "- Git" not in prompt


async def test_inference_is_cached_until_the_text_changes(
    client: AsyncClient, role: TargetRole
) -> None:
    provider = use(INFERRED)
    headers, resume_id = await setup(client, role)
    url = f"/api/resumes/{resume_id}/skill-gap"

    first = (await client.get(url, headers=headers)).json()
    second = (await client.get(url, headers=headers)).json()
    assert (first["ai_status"], second["ai_status"]) == ("ok", "cached")
    assert len(provider.requests) == 1
    assert second["skills"] == first["skills"]

    data = json.loads(json.dumps(RESUME))
    data["experience"][0]["bullets"].append("Mentored two interns")
    await client.patch(f"/api/resumes/{resume_id}", json={"data": data}, headers=headers)
    third = (await client.get(url, headers=headers)).json()
    assert third["ai_status"] == "ok" and len(provider.requests) == 2


async def test_exhausted_ai_budget_still_returns_the_report(
    client: AsyncClient, role: TargetRole, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_rate_limit", "1/minute")
    provider = use(INFERRED)
    headers, resume_id = await setup(client, role)
    url = f"/api/resumes/{resume_id}/skill-gap"

    assert (await client.get(url, headers=headers)).json()["ai_status"] == "ok"
    from app.services.skill_gap.service import inference_cache

    inference_cache.clear()
    response = await client.get(url, headers=headers)

    assert response.status_code == 200
    assert response.json()["ai_status"] == "rate_limited"
    assert len(provider.requests) == 1
    rest = next(s for s in response.json()["skills"] if s["name"] == "REST APIs")
    assert rest["status"] == "missing"  # no inference without AI


async def test_ai_outage_gives_deterministic_report(client: AsyncClient, role: TargetRole) -> None:
    use(AIUnavailableError("no key"))
    headers, resume_id = await setup(client, role)

    body = (await client.get(f"/api/resumes/{resume_id}/skill-gap", headers=headers)).json()

    assert body["ai_status"] == "unavailable"
    assert {s["name"]: s["status"] for s in body["skills"]}["Python"] == "present_unverified"


async def test_requires_target_role_and_ownership(client: AsyncClient, role: TargetRole) -> None:
    use(INFERRED)
    headers, no_role_id = await setup(client, None, "norole@example.com")
    _, resume_id = await setup(client, role, "owner-gap@example.com")

    no_role = await client.get(f"/api/resumes/{no_role_id}/skill-gap", headers=headers)
    intruder = await client.get(f"/api/resumes/{resume_id}/skill-gap", headers=headers)

    assert no_role.status_code == 409 and "target role" in no_role.json()["detail"]
    assert intruder.status_code == 404


async def test_learning_resources_are_curated(
    client: AsyncClient, db_session: AsyncSession, role: TargetRole
) -> None:
    headers, _ = await setup(client, role)
    sql = await db_session.scalar(select(Skill).where(Skill.slug == "sql"))
    assert sql

    body = (await client.get(f"/api/skills/{sql.id}/learning-resources", headers=headers)).json()

    assert body["skill_name"] == "SQL"
    assert [r["url"] for r in body["resources"]] == ["https://sqlbolt.com/"]
