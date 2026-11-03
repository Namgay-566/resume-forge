"""The demo job seekers (nurse, teacher, accountant, marketer, fresh graduate, career
changer) run through the skill gap report and ATS scoring on the real seed catalog, so the
whole pipeline is exercised for fields other than technology."""

import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient, get_ai_client
from app.ai.types import AIRequest, AIResponse
from app.db.demo import seed_demo_user
from app.db.demo_data import DEMO_USERS, DemoUser
from app.db.seed import apply_seed, load_seed_data
from app.main import app

PASSWORD = "demo-password-123"


class QuietAI:
    """Skill inference finds nothing extra; nothing else should call the AI here."""

    name, model = "fake", "fake-1"

    async def generate(self, request: AIRequest) -> AIResponse:
        assert request.response_model.__name__ == "InferredSkills", request.response_model
        return AIResponse(text=json.dumps({"skills": []}), model="f")


@pytest.fixture
async def catalog(db_session: AsyncSession) -> None:
    await apply_seed(db_session, load_seed_data())
    await db_session.commit()


async def run_demo(client: AsyncClient, db_session: AsyncSession, demo: DemoUser) -> dict[str, Any]:
    app.dependency_overrides[get_ai_client] = lambda: AIClient(QuietAI())
    resume = await seed_demo_user(db_session, demo, PASSWORD)
    login = await client.post("/api/auth/login", json={"email": demo.email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    gap = await client.get(f"/api/resumes/{resume.id}/skill-gap", headers=headers)
    ats = await client.post(
        f"/api/resumes/{resume.id}/ats-analyses", json={"review": False}, headers=headers
    )
    stored = (await client.get(f"/api/resumes/{resume.id}", headers=headers)).json()
    assert gap.status_code == 200, gap.text
    assert ats.status_code == 201 or ats.status_code == 200, ats.text
    report = ats.json()["report"]
    return {
        "gap": gap.json(),
        "ats": report,
        "checks": {c["id"]: c for c in report["checks"]},
        "skills": {s["slug"]: s for s in gap.json()["skills"]},
        "resume": stored,
    }


# Per demo user: the recommended template, skills the resume shows (status not "missing"),
# and ATS section checks that must pass for their field and career stage.
EXPECT: dict[str, dict[str, Any]] = {
    "nurse": {
        "template": "classic",
        "present": [
            "nursing-license",
            "basic-life-support",
            "patient-assessment",
            "infection-control",
        ],
        "passing": ["section_certifications", "section_experience", "section_education"],
    },
    "teacher": {
        "template": "classic",
        "present": [
            "teaching-certification",
            "lesson-planning",
            "classroom-management",
            "safeguarding",
        ],
        "passing": ["section_certifications", "section_experience"],
    },
    "accountant": {
        "template": "conservative",
        "present": ["cpa-ca-acca", "bookkeeping", "financial-reporting", "spreadsheets"],
        "passing": ["section_certifications", "section_experience"],
    },
    "marketer": {
        "template": "professional",
        "present": ["seo", "email-marketing", "marketing-analytics", "digital-marketing"],
        "passing": ["section_experience", "section_skills"],
    },
    # A student with an internship and projects but no jobs still has "experience".
    "fresher": {
        "template": "professional",
        "present": ["social-media-marketing", "content-writing"],
        "passing": ["section_experience", "section_education"],
    },
    # Ten years in retail count as experience for a project manager.
    "career_changer": {
        "template": "professional",
        "present": ["project-management", "budgeting", "leadership"],
        "passing": ["section_experience", "section_skills"],
    },
}


@pytest.mark.parametrize("demo", DEMO_USERS, ids=[d.key for d in DEMO_USERS])
async def test_demo_user_skill_gap_and_ats(
    client: AsyncClient, db_session: AsyncSession, catalog: None, demo: DemoUser
) -> None:
    result = await run_demo(client, db_session, demo)
    expect = EXPECT[demo.key]

    gap, ats = result["gap"], result["ats"]
    assert gap["role"]["slug"] == demo.role_slug
    assert 0 < gap["readiness"] <= 100
    assert result["resume"]["template"] == expect["template"]
    assert result["resume"]["experience_level"] == demo.level.value
    for slug in expect["present"]:
        assert result["skills"][slug]["status"] != "missing", (
            demo.key,
            slug,
            result["skills"][slug],
        )
    for check in expect["passing"]:
        assert result["checks"][check]["status"] == "pass", (demo.key, result["checks"][check])
    # Keywords are the role's own skills, so the score reflects the field, not tech terms.
    assert ats["keywords"]["source"] == "target_role"
    assert ats["score"] >= 50, (
        demo.key,
        ats["score"],
        [c for c in ats["checks"] if c["status"] != "pass"],
    )


async def test_every_demo_user_gets_a_skill_proof_suggestion(
    client: AsyncClient, db_session: AsyncSession, catalog: None
) -> None:
    for demo in DEMO_USERS:
        skills = (await run_demo(client, db_session, demo))["gap"]["skills"]
        assert all(s["proof_types"] for s in skills), demo.key


async def test_demo_nurse_licence_is_found_in_certifications(
    client: AsyncClient, db_session: AsyncSession, catalog: None
) -> None:
    nurse = next(d for d in DEMO_USERS if d.key == "nurse")

    licence = (await run_demo(client, db_session, nurse))["skills"]["nursing-license"]

    assert licence["evidence"][0] == {
        "kind": "certification",
        "detail": "Listed in Licenses & Certifications: NMC Registration",
    }
