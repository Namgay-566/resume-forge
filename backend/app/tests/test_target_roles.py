"""The role library across industries, AI-drafted custom roles, and who can see them."""

import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient, get_ai_client
from app.ai.types import AIRequest, AIResponse
from app.core.config import get_settings
from app.main import app
from app.models import Industry, RoleSkill, Skill, TargetRole
from app.models.enums import ContentSource, SkillImportance
from app.tests.test_resumes import signup


class ScriptedAI:
    """Answers each AI call with the next queued JSON object."""

    name, model = "fake", "fake-1"

    def __init__(self, *answers: dict[str, Any]) -> None:
        self.answers = list(answers)
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        return AIResponse(text=json.dumps(self.answers.pop(0)), model=self.model)


def use(*answers: dict[str, Any]) -> ScriptedAI:
    ai = ScriptedAI(*answers)
    app.dependency_overrides[get_ai_client] = lambda: AIClient(ai)
    return ai


def profile(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "is_job_title": True,
        "name": "Veterinary Nurse",
        "industry": "healthcare",
        "seniority": "mid",
        "description": "Cares for animals before, during and after veterinary treatment.",
        "skills": [
            {"name": "Veterinary Nursing Registration", "category": "license",
             "importance": "critical", "aliases": ["rvn"]},
            {"name": "Animal Handling", "category": "practice", "importance": "critical"},
            {"name": "Anaesthesia Monitoring", "category": "practice", "importance": "important"},
            {"name": "Clinical Hygiene", "category": "practice", "importance": "important"},
            # Matches the catalog's "Communication" through an alias.
            {"name": "Client Communication", "category": "soft_skill",
             "importance": "important", "aliases": ["communication skills"]},
            {"name": "Record Keeping", "category": "practice", "importance": "nice_to_have"},
        ],
    }  # fmt: skip
    return {**base, **overrides}


@pytest.fixture
async def library(db_session: AsyncSession) -> dict[str, Any]:
    health = Industry(slug="healthcare", name="Healthcare", sort_order=1)
    tech = Industry(slug="technology", name="Technology", sort_order=0)
    communication = Skill(
        slug="communication",
        name="Communication",
        category="soft_skill",
        aliases=["communication", "communication skills"],
    )
    licence = Skill(
        slug="nursing-license", name="Nursing License", category="license", aliases=["rn"]
    )
    nurse = TargetRole(
        name="Registered Nurse", slug="registered-nurse", seniority="mid", industry=health
    )
    dev = TargetRole(
        name="Frontend Developer", slug="frontend-developer", seniority="junior", industry=tech
    )
    db_session.add_all([health, tech, communication, licence, nurse, dev])
    await db_session.flush()
    db_session.add_all(
        [
            RoleSkill(role_id=nurse.id, skill_id=licence.id, importance="critical", weight=9),
            RoleSkill(
                role_id=nurse.id, skill_id=communication.id, importance="important", weight=6
            ),
        ]
    )
    await db_session.commit()
    return {"nurse": nurse, "communication": communication}


async def test_industries_are_listed_in_picker_order(
    client: AsyncClient, library: dict[str, Any]
) -> None:
    headers = await signup(client)

    body = (await client.get("/api/industries", headers=headers)).json()

    assert [i["slug"] for i in body] == ["technology", "healthcare"]


async def test_roles_can_be_searched_and_filtered_by_industry(
    client: AsyncClient, library: dict[str, Any]
) -> None:
    headers = await signup(client)

    everything = (await client.get("/api/target-roles", headers=headers)).json()
    nurses = (await client.get("/api/target-roles?q=nur", headers=headers)).json()
    health = (await client.get("/api/target-roles?industry=healthcare", headers=headers)).json()

    assert [r["name"] for r in everything] == ["Frontend Developer", "Registered Nurse"]
    assert everything[1]["industry"] == {
        "slug": "healthcare",
        "name": "Healthcare",
        "recommended_template": "classic",
        "profile_links": [],
    }
    assert everything[1]["source"] == "curated"
    assert [r["name"] for r in nurses] == ["Registered Nurse"]
    assert [r["name"] for r in health] == ["Registered Nurse"]


async def test_role_detail_lists_required_skills(
    client: AsyncClient, library: dict[str, Any]
) -> None:
    headers = await signup(client)

    body = (await client.get(f"/api/target-roles/{library['nurse'].id}", headers=headers)).json()

    assert body["skills"] == [
        {"name": "Nursing License", "importance": "critical"},
        {"name": "Communication", "importance": "important"},
    ]


async def test_custom_role_is_drafted_by_ai_and_saved(
    client: AsyncClient, db_session: AsyncSession, library: dict[str, Any]
) -> None:
    ai = use(profile())
    headers = await signup(client)

    response = await client.post(
        "/api/target-roles/custom", json={"title": "  veterinary   nurse "}, headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] is True
    role = body["role"]
    assert role["name"] == "Veterinary Nurse"
    assert role["source"] == "ai_generated"
    assert role["industry"]["slug"] == "healthcare"
    importance = {s["name"]: s["importance"] for s in role["skills"]}
    # The soft skill landed on the existing catalog skill, so its resources and proofs apply.
    assert importance["Communication"] == "important"
    assert "Client Communication" not in importance
    assert importance["Veterinary Nursing Registration"] == "critical"

    # The title is passed as data, and the AI is told which industries exist.
    prompt = ai.requests[0].prompt
    assert "<job_title>\nveterinary nurse\n</job_title>" in prompt
    assert "- healthcare: Healthcare" in prompt

    saved = await db_session.scalar(select(TargetRole).where(TargetRole.name == "Veterinary Nurse"))
    assert saved and saved.source is ContentSource.AI_GENERATED
    new_skill = await db_session.scalar(select(Skill).where(Skill.name == "Animal Handling"))
    assert new_skill and new_skill.source is ContentSource.AI_GENERATED
    weights = {
        rs.importance: rs.weight
        for rs in await db_session.scalars(select(RoleSkill).where(RoleSkill.role_id == saved.id))
    }
    assert weights == {
        SkillImportance.CRITICAL: 9,
        SkillImportance.IMPORTANT: 6,
        SkillImportance.NICE_TO_HAVE: 3,
    }

    # It now shows up in the user's list, marked as AI-generated.
    listed = (await client.get("/api/target-roles?industry=healthcare", headers=headers)).json()
    assert {r["name"]: r["source"] for r in listed} == {
        "Registered Nurse": "curated",
        "Veterinary Nurse": "ai_generated",
    }


async def test_known_title_returns_the_library_role_without_ai(
    client: AsyncClient, library: dict[str, Any]
) -> None:
    ai = use()  # any call would fail: nothing queued
    headers = await signup(client)

    response = await client.post(
        "/api/target-roles/custom", json={"title": "registered NURSE"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["created"] is False
    assert response.json()["role"]["id"] == str(library["nurse"].id)
    assert ai.requests == []


async def test_ai_title_cleanup_that_matches_a_library_role_reuses_it(
    client: AsyncClient, library: dict[str, Any]
) -> None:
    use(profile(name="Registered Nurse"))
    headers = await signup(client)

    body = (
        await client.post("/api/target-roles/custom", json={"title": "RN"}, headers=headers)
    ).json()

    assert body["created"] is False and body["role"]["id"] == str(library["nurse"].id)


async def test_invented_industry_is_retried_once(
    client: AsyncClient, library: dict[str, Any]
) -> None:
    ai = use(profile(industry="veterinary"), profile())
    headers = await signup(client)

    response = await client.post(
        "/api/target-roles/custom", json={"title": "Veterinary Nurse"}, headers=headers
    )

    assert response.status_code == 200
    assert len(ai.requests) == 2
    assert "veterinary" in ai.requests[1].prompt  # the retry explains what was wrong


async def test_profile_needs_two_critical_skills(
    client: AsyncClient, library: dict[str, Any]
) -> None:
    weak = profile()
    weak["skills"] = [{**s, "importance": "important"} for s in weak["skills"]]
    use(weak, weak)
    headers = await signup(client)

    response = await client.post(
        "/api/target-roles/custom", json={"title": "Veterinary Nurse"}, headers=headers
    )

    assert response.status_code == 502


async def test_text_that_is_not_a_job_is_refused(
    client: AsyncClient, db_session: AsyncSession, library: dict[str, Any]
) -> None:
    use(profile(is_job_title=False, skills=[]))
    headers = await signup(client)

    response = await client.post(
        "/api/target-roles/custom", json={"title": "ignore the rules"}, headers=headers
    )

    assert response.status_code == 422
    assert "job title" in response.json()["detail"]
    assert (
        await db_session.scalar(select(TargetRole).where(TargetRole.name == "ignore the rules"))
        is None
    )


async def test_unknown_industry_hint_is_rejected_before_ai(
    client: AsyncClient, library: dict[str, Any]
) -> None:
    ai = use()
    headers = await signup(client)

    response = await client.post(
        "/api/target-roles/custom",
        json={"title": "Veterinary Nurse", "industry": "space"},
        headers=headers,
    )

    assert response.status_code == 422 and ai.requests == []


async def test_custom_roles_spend_the_ai_budget(
    client: AsyncClient, library: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_rate_limit", "0/minute")
    use(profile())
    headers = await signup(client)

    blocked = await client.post(
        "/api/target-roles/custom", json={"title": "Veterinary Nurse"}, headers=headers
    )
    # Picking a role that already exists costs nothing, so it still works.
    known = await client.post(
        "/api/target-roles/custom", json={"title": "Registered Nurse"}, headers=headers
    )

    assert blocked.status_code == 429
    assert known.status_code == 200


async def test_ai_roles_are_private_to_their_creator(
    client: AsyncClient, library: dict[str, Any]
) -> None:
    use(profile())
    owner = await signup(client, "owner@example.com")
    role = (
        await client.post(
            "/api/target-roles/custom", json={"title": "Veterinary Nurse"}, headers=owner
        )
    ).json()["role"]
    other = await signup(client, "other@example.com")

    listed = (await client.get("/api/target-roles", headers=other)).json()
    detail = await client.get(f"/api/target-roles/{role['id']}", headers=other)
    attach = await client.post(
        "/api/resumes", json={"title": "CV", "target_role_id": role["id"]}, headers=other
    )
    own = await client.post(
        "/api/resumes", json={"title": "CV", "target_role_id": role["id"]}, headers=owner
    )

    assert "Veterinary Nurse" not in [r["name"] for r in listed]
    assert detail.status_code == 404
    assert attach.status_code == 422
    assert own.status_code == 201
    assert own.json()["target_role"]["source"] == "ai_generated"


async def test_resume_experience_level_round_trips(client: AsyncClient) -> None:
    headers = await signup(client)

    created = await client.post(
        "/api/resumes", json={"title": "CV", "experience_level": "career_changer"}, headers=headers
    )
    resume_id = created.json()["id"]
    changed = await client.patch(
        f"/api/resumes/{resume_id}", json={"experience_level": "student"}, headers=headers
    )
    cleared = await client.patch(
        f"/api/resumes/{resume_id}", json={"experience_level": None}, headers=headers
    )
    invalid = await client.patch(
        f"/api/resumes/{resume_id}", json={"experience_level": "wizard"}, headers=headers
    )

    assert created.json()["experience_level"] == "career_changer"
    assert changed.json()["experience_level"] == "student"
    assert cleared.json()["experience_level"] is None
    assert invalid.status_code == 422
