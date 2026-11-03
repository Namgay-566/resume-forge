import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient, get_ai_client
from app.ai.errors import AIUnavailableError
from app.ai.types import AIRequest, AIResponse
from app.ai.writing import BulletOptions, SummaryOptions, TailorPlan
from app.main import app
from app.models import Skill
from app.models.enums import ResumeType
from app.schemas.resume_data import ResumeData
from app.services.ats.checks import run_checks
from app.services.writing.guard import guard_numbers, number_keys, placeholders

RESUME = {
    "personal_info": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
    "summary": "Backend developer.",
    "experience": [
        {
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2021-01",
            "end_date": "2024-01",
            "bullets": [
                "Worked on the billing API for 2,000 merchants",
                "Wrote Postgres queries for reports",
                "Set up Docker for local development",
            ],
            "tools_and_skills": ["Python", "FastAPI", "Docker"],
        }
    ],
    "projects": [{"name": "Tracker", "bullets": ["Built a habit tracker in React"]}],
    "skills": [{"name": "Python"}, {"name": "Git"}, {"name": "React"}],
}


class RoutingProvider:
    """Mocked provider answering by response model."""

    name, model = "fake", "fake-1"

    def __init__(self, answers: dict[type, Any]) -> None:
        self.answers = answers
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        answer = self.answers[request.response_model]
        if isinstance(answer, Exception):
            raise answer
        return AIResponse(text=json.dumps(answer), model=self.model)


def use(answers: dict[type, Any]) -> RoutingProvider:
    provider = RoutingProvider(answers)
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)
    return provider


async def setup(
    client: AsyncClient, email: str = "writer@example.com"
) -> tuple[dict[str, str], str]:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123", "name": "Ada"}
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    resume = await client.post(
        "/api/resumes", json={"title": "Main", "data": RESUME}, headers=headers
    )
    return headers, resume.json()["id"]


# --- number guard ----------


def test_guard_keeps_user_numbers_and_replaces_invented_ones() -> None:
    allowed = number_keys("Worked on the billing API for 2,000 merchants")

    result = guard_numbers(
        "Rebuilt the billing API for 2000 merchants, cutting failures by 35% and saving $1.2M",
        allowed,
    )

    assert result.text == (
        "Rebuilt the billing API for 2000 merchants, cutting failures by [X%] and saving [$X]"
    )
    assert result.replaced == ["35%", "$1.2M"]
    assert result.placeholders == ["[X%]", "[$X]"]


@pytest.mark.parametrize(
    "tech", ["Moved assets to S3 and EC2", "Kept p95 low", "Used OAuth2 and ES6"]
)
def test_guard_ignores_digits_inside_tech_names(tech: str) -> None:
    assert guard_numbers(tech, set()).text == tech


def test_guard_handles_multipliers_and_plain_counts() -> None:
    result = guard_numbers("Grew signups 3x across 12 markets", set())

    assert result.text == "Grew signups [X]x across [X] markets"


def test_placeholders_detected() -> None:
    assert placeholders("Cut costs by [X%] for [X users]") == ["[X%]", "[X users]"]


def test_ats_flags_unfilled_placeholders() -> None:
    raw = json.loads(json.dumps(RESUME))
    raw["experience"][0]["bullets"][1] = "Cut report time by [X%] with indexed Postgres queries"

    checks = {c.id: c for c in run_checks(ResumeData.model_validate(raw), ResumeType.RESUME)}

    assert checks["placeholders"].status == "fail"
    assert checks["placeholders"].location.item_index == 0  # type: ignore[union-attr]
    assert "placeholders" not in {
        c.id for c in run_checks(ResumeData.model_validate(RESUME), ResumeType.RESUME)
    }


# --- improve bullet ----------


async def test_improve_bullet_returns_guarded_options(client: AsyncClient) -> None:
    provider = use(
        {
            BulletOptions: {
                "options": [
                    {
                        "text": "Rebuilt the billing API in FastAPI for 2,000 merchants, "
                        "cutting errors by 40%.",
                        "rationale": "Adds a result",
                    },
                    {
                        "text": "Led the billing API rewrite for 2,000 merchants, "
                        "reducing payout time by [X hours]",
                        "rationale": "Leads with ownership",
                    },
                    {
                        "text": "Worked on the billing API for 2,000 merchants",
                        "rationale": "same as before",
                    },
                ]
            }
        }
    )
    headers, resume_id = await setup(client)

    response = await client.post(
        f"/api/resumes/{resume_id}/ai/improve-bullet",
        json={
            "text": "Worked on the billing API for 2,000 merchants",
            "section": "experience",
            "position": "Engineer at Acme",
            "tools_and_skills": ["Python", "FastAPI"],
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    options = response.json()["options"]
    assert len(options) == 2  # the unchanged copy of the original is dropped
    first, second = options
    assert first["text"] == (
        "Rebuilt the billing API in FastAPI for 2,000 merchants, cutting errors by [X%]"
    )
    assert first["replaced_numbers"] == ["40%"]
    assert first["placeholders"] == ["[X%]"]
    assert second["placeholders"] == ["[X hours]"] and second["replaced_numbers"] == []
    prompt = provider.requests[0].prompt
    assert "Engineer at Acme" in prompt and "FastAPI" in prompt


@pytest.mark.parametrize(
    ("section", "title", "heading", "guidance"),
    [
        ("volunteer", None, "Section: Volunteer Work", "people or cause served"),
        ("clinical_experience", None, "Section: Clinical Experience", "patient care delivered"),
        ("teaching_experience", None, "Section: Teaching Experience", "pupils' progress"),
        ("research", "Doctoral Research", "Section: Doctoral Research", "methods and tools"),
        ("education", None, "Section: Education", "dissertation"),
        ("achievements", None, "Section: Achievements", "why it mattered"),
        ("custom", "Fieldwork", "Section: Fieldwork", "Match the section's heading"),
    ],
)
async def test_improve_bullet_works_in_every_section_with_bullets(
    client: AsyncClient, section: str, title: str | None, heading: str, guidance: str
) -> None:
    provider = use(
        {
            BulletOptions: {
                "options": [
                    {"text": "Led a weekly food bank rota for 20 volunteers", "rationale": "x"}
                ]
            }
        }
    )  # noqa: E501
    headers, resume_id = await setup(client)

    response = await client.post(
        f"/api/resumes/{resume_id}/ai/improve-bullet",
        json={
            "text": "Helped at the food bank with 20 volunteers",
            "section": section,
            "section_title": title,
            "position": "Volunteer at City Food Bank",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["options"][0]["text"].startswith("Led a weekly food bank rota")
    prompt = provider.requests[0].prompt
    assert heading in prompt and guidance in prompt
    assert "Volunteer at City Food Bank" in prompt
    assert "any resume section" in (provider.requests[0].system or "")


@pytest.mark.parametrize("section", ["skills", "summary", "languages", "made_up"])
async def test_improve_bullet_refuses_sections_without_bullets(
    client: AsyncClient, section: str
) -> None:
    use({})
    headers, resume_id = await setup(client)

    response = await client.post(
        f"/api/resumes/{resume_id}/ai/improve-bullet",
        json={"text": "Fluent Spanish", "section": section},
        headers=headers,
    )

    assert response.status_code == 422


# --- summary ----------


async def test_summary_allows_years_but_not_invented_metrics(client: AsyncClient) -> None:
    provider = use(
        {
            SummaryOptions: {
                "options": [
                    "Backend developer with 3 years of Python and FastAPI, "
                    "serving 2,000 merchants.",
                    "Engineer who improved uptime to 99.9% across 5 services.",
                ]
            }
        }
    )
    headers, resume_id = await setup(client)

    response = await client.post(f"/api/resumes/{resume_id}/ai/summary", headers=headers)

    first, second = response.json()["options"]
    assert "3 years" in first["text"] and first["replaced_numbers"] == []
    assert second["text"] == "Engineer who improved uptime to [X%] across [X] services."
    assert (
        "Years of professional experience (calculated from the resume): 3"
        in provider.requests[0].prompt
    )


# --- tailor ----------


@pytest.fixture
async def catalog(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Skill(name="SQL", slug="sql", category="db", aliases=["sql", "postgres", "postgresql"]),
            Skill(name="Docker", slug="docker", category="tool", aliases=["docker"]),
            Skill(name="Kubernetes", slug="k8s", category="tool", aliases=["kubernetes", "k8s"]),
            Skill(name="Git", slug="git", category="tool", aliases=["git", "github"]),
        ]
    )
    await db_session.commit()


PLAN = {
    "bullet_rewrites": [
        {
            "section": "experience",
            "item_index": 0,
            "bullet_index": 1,
            "text": "Wrote PostgreSQL reporting queries that cut report time by 50%",
            "reason": "The job emphasises PostgreSQL.",
        },
        {"section": "experience", "item_index": 3, "bullet_index": 0, "text": "x", "reason": "bad"},
        {
            "section": "projects",
            "item_index": 0,
            "bullet_index": 0,
            "text": "Built a habit tracker in React",
            "reason": "unchanged",
        },
    ],
    "highlights": [
        {
            "section": "experience",
            "item_index": 0,
            "bullet_index": 2,
            "reason": "Docker is required.",
        },
        {"section": "experience", "item_index": 0, "bullet_index": 0, "reason": "already first"},
    ],
    "featured_skills": ["React", "Python", "Rust"],
    "featured_skills_reason": "Frontend first for this role.",
    "skills_to_add": [
        {"name": "PostgreSQL", "reason": "Required; you wrote Postgres queries."},
        {"name": "Docker", "reason": "Required; you set up Docker."},
        {"name": "Kubernetes", "reason": "Required."},
        {"name": "GitHub", "reason": "Listed."},
    ],
    "gaps": ["AWS certification"],
    "summary": "Backend developer focused on PostgreSQL-backed APIs for 2,000 merchants.",
    "summary_reason": "Mirror the job title.",
}


async def test_tailor_returns_validated_suggestions_and_changes_nothing(
    client: AsyncClient, catalog: None
) -> None:
    provider = use({TailorPlan: PLAN})
    headers, resume_id = await setup(client)
    before = (await client.get(f"/api/resumes/{resume_id}", headers=headers)).json()

    response = await client.post(
        f"/api/resumes/{resume_id}/ai/tailor",
        json={"job_description": "Backend role: PostgreSQL, Docker, Kubernetes required."},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for s in body["suggestions"]:
        by_kind.setdefault(s["kind"], []).append(s)

    (rewrite,) = by_kind["rewrite_bullet"]  # out-of-range and no-op rewrites dropped
    assert rewrite["before"] == "Wrote Postgres queries for reports"
    assert rewrite["after"] == "Wrote PostgreSQL reporting queries that cut report time by [X%]"
    assert rewrite["placeholders"] == ["[X%]"]

    (move,) = by_kind["move_bullet_up"]  # bullet 0 is already first, so only one
    assert move["after_items"][0] == "Set up Docker for local development"
    assert sorted(move["after_items"]) == sorted(move["before_items"])

    (skills,) = by_kind["feature_skills"]
    assert skills["after_items"] == ["React", "Python", "Git"]  # unknown "Rust" ignored

    added = [s["after"] for s in by_kind["add_skill"]]
    assert added == ["PostgreSQL", "Docker"]  # evidence on the resume; GitHub already = Git
    assert "Kubernetes" in body["gaps"] and "AWS certification" in body["gaps"]

    (summary,) = by_kind["rewrite_summary"]
    assert summary["before"] == "Backend developer."
    assert "2,000 merchants" in summary["after"]

    assert "[experience 0.1] Wrote Postgres queries for reports" in provider.requests[0].prompt
    after = (await client.get(f"/api/resumes/{resume_id}", headers=headers)).json()
    assert after["data"] == before["data"]  # never auto-applied


# --- errors ----------


async def test_writing_help_reports_ai_outage(client: AsyncClient) -> None:
    use({SummaryOptions: AIUnavailableError("no key")})
    headers, resume_id = await setup(client)

    response = await client.post(f"/api/resumes/{resume_id}/ai/summary", headers=headers)

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


async def test_writing_help_is_owner_only(client: AsyncClient) -> None:
    use({SummaryOptions: {"options": ["x"]}})
    _, resume_id = await setup(client, "owner-w@example.com")
    intruder, _ = await setup(client, "intruder-w@example.com")

    response = await client.post(f"/api/resumes/{resume_id}/ai/summary", headers=intruder)

    assert response.status_code == 404
