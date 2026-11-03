"""AI prompts and learning help adapt to every field, not just technology."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient, get_ai_client
from app.ai.context import CandidateContext
from app.ai.prompts import PROMPTS_DIR, available_prompts, render_prompt
from app.ai.types import AIRequest, AIResponse
from app.ai.writing import BulletSection
from app.db.seed import SEED_DIR, load_seed_data
from app.main import app
from app.models import Industry, RoleSkill, Skill, TargetRole
from app.models.enums import SkillImportance
from app.services.learning import search_phrase
from app.tests.test_resumes import signup

NURSE = CandidateContext(
    target_role="Registered Nurse",
    industry="Healthcare",
    experience_level="mid",
    impact_language="patient outcomes, patient safety",
)

# --- prompts ------------------------------------------------------------------------------

# Only the GitHub repository reviewers may talk about code and developers.
REPO_PROMPTS = {
    "proof_review_system",
    "proof_review_user",
    "project_draft_system",
    "project_draft_user",
}


@pytest.mark.parametrize("name", sorted(set(available_prompts()) - REPO_PROMPTS))
def test_prompts_have_no_tech_defaults(name: str) -> None:
    text = (PROMPTS_DIR / f"{name}.j2").read_text().lower()

    for phrase in ("software and data", "senior developer", "technical recruiter", "github repo"):
        assert phrase not in text, f"{name}: {phrase!r}"


def test_candidate_context_renders_field_and_stage() -> None:
    prompt = render_prompt(
        "bullet_improve_user",
        bullet="Cared for patients",
        position="Staff Nurse",
        tools=[],
        section=BulletSection("Clinical Experience", "Show patient care delivered."),
        ctx=NURSE,
    )

    assert "Section: Clinical Experience" in prompt
    assert "A strong bullet in this section: Show patient care delivered." in prompt
    assert "Target role: Registered Nurse" in prompt
    assert "Field: Healthcare" in prompt
    assert "Career stage: mid-level" in prompt
    assert "Results that matter in this field: patient outcomes, patient safety" in prompt
    assert "Fresher mode" not in prompt and "Career changer mode" not in prompt


@pytest.mark.parametrize(
    ("level", "mode"),
    [
        ("student", "Fresher mode"),
        ("entry", "Fresher mode"),
        ("career_changer", "Career changer mode"),
    ],
)
def test_fresher_and_career_changer_modes(level: str, mode: str) -> None:
    ctx = CandidateContext(
        target_role="Teaching Assistant", industry="Education", experience_level=level
    )

    prompt = render_prompt("summary_user", resume_text="x", years=None, ctx=ctx)

    assert mode in prompt
    if mode == "Career changer mode":
        assert "moving into Education" in prompt and "transferable skills" in prompt
    else:
        assert "internships" in prompt and "education" in prompt


def test_prompts_work_without_context() -> None:
    prompt = render_prompt("tailor_user", resume_text="x", job_description="y")

    assert "Target role" not in prompt and "Resume:" in prompt


def test_system_prompts_carry_the_field_rules() -> None:
    for name in (
        "ats_review_system",
        "bullet_improve_system",
        "summary_system",
        "tailor_system",
        "project_idea_system",
    ):
        assert "Never assume the candidate works in technology" in render_prompt(name), name


def test_bullet_improver_knows_each_fields_results() -> None:
    system = render_prompt("bullet_improve_system")

    for words in ("patient outcomes", "revenue", "student progress", "[X patients]", "[X leads]"):
        assert words in system


# --- end to end: context comes from the resume's role and industry ------------------------


class Recorder:
    name, model = "fake", "fake-1"

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        return AIResponse(text=json.dumps(self.answers[request.response_model.__name__]), model="f")


def use(answers: dict[str, Any]) -> Recorder:
    ai = Recorder(answers)
    app.dependency_overrides[get_ai_client] = lambda: AIClient(ai)
    return ai


@pytest.fixture
async def nursing(db_session: AsyncSession) -> dict[str, Any]:
    health = Industry(
        slug="healthcare",
        name="Healthcare",
        impact_language="patient outcomes, patient safety, quality of care",
    )
    licence = Skill(
        slug="nursing-license",
        name="Nursing License",
        category="license",
        aliases=[],
        proof_types=["professional_license", "certificate"],
    )  # noqa: E501
    phlebotomy = Skill(slug="phlebotomy", name="Phlebotomy", category="clinical", aliases=[])
    role = TargetRole(
        name="Registered Nurse", slug="registered-nurse", seniority="mid", industry=health
    )
    db_session.add_all([health, licence, phlebotomy, role])
    await db_session.flush()
    for skill in (licence, phlebotomy):
        db_session.add(
            RoleSkill(
                role_id=role.id, skill_id=skill.id, importance=SkillImportance.CRITICAL, weight=9
            )
        )
    await db_session.commit()
    return {"role": role, "licence": licence, "phlebotomy": phlebotomy}


async def resume(client: AsyncClient, headers: dict[str, str], role: TargetRole, level: str) -> str:
    body = {"title": "CV", "target_role_id": str(role.id), "experience_level": level}
    return (await client.post("/api/resumes", json=body, headers=headers)).json()["id"]


BULLETS = {
    "options": [
        {
            "text": "Assessed and monitored [X patients] per shift on a busy surgical ward",
            "rationale": "Adds scope",
        }
    ]
}  # noqa: E501


async def test_bullet_help_uses_the_resumes_field_and_stage(
    client: AsyncClient, nursing: dict[str, Any]
) -> None:
    ai = use({"BulletOptions": BULLETS})
    headers = await signup(client)
    resume_id = await resume(client, headers, nursing["role"], "career_changer")

    response = await client.post(
        f"/api/resumes/{resume_id}/ai/improve-bullet",
        json={"text": "Looked after customers in a busy shop", "section": "experience"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    prompt = ai.requests[0].prompt
    assert "Field: Healthcare" in prompt
    assert "Results that matter in this field: patient outcomes" in prompt
    assert "Career changer mode" in prompt and "moving into Healthcare" in prompt


IDEA = {
    "proof_type": "github_repo",  # not a proof type that suits a nursing licence
    "deliverable": "a study plan and exam booking confirmation",
    "title": "NCLEX preparation plan",
    "summary": "A six-week plan to pass the licensing exam.",
    "steps": ["Book the exam", "Work through practice questions"],
    "reviewer_checks": ["A current licence number from the board"],
    "est_hours": 30,
    "stretch": None,
}


async def test_proof_projects_fit_the_skill_and_field(
    client: AsyncClient, nursing: dict[str, Any]
) -> None:
    ai = use({"ProjectIdea": IDEA})
    headers = await signup(client)
    resume_id = await resume(client, headers, nursing["role"], "student")

    response = await client.post(
        f"/api/resumes/{resume_id}/roadmap/{nursing['licence'].id}/project", headers=headers
    )

    assert response.status_code == 200, response.text
    idea = response.json()
    # Coerced to proof the checker accepts for this skill.
    assert idea["proof_type"] == "professional_license"
    assert idea["deliverable"] == "a study plan and exam booking confirmation"
    prompt = ai.requests[0].prompt
    assert "- professional_license: Licence or registration" in prompt
    assert "- certificate: Certificate" in prompt
    assert "expiry date" in prompt  # what the best proof must include
    assert "Fresher mode" in prompt
    assert "a teacher: a lesson plan" in (ai.requests[0].system or "")


async def test_no_curated_resource_gives_a_search_phrase(
    client: AsyncClient, nursing: dict[str, Any]
) -> None:
    use({})
    headers = await signup(client)
    resume_id = await resume(client, headers, nursing["role"], "mid")

    roadmap = (await client.get(f"/api/resumes/{resume_id}/roadmap", headers=headers)).json()
    resources = (
        await client.get(
            f"/api/skills/{nursing['phlebotomy'].id}/learning-resources", headers=headers
        )
    ).json()

    item = next(i for i in roadmap["items"] if i["slug"] == "phlebotomy")
    assert item["resources"] == []
    assert item["search_phrase"] == "Phlebotomy free course for beginners"
    assert resources["search_phrase"] == "Phlebotomy free course for beginners"


def test_search_phrases_fit_the_kind_of_skill() -> None:
    assert (
        search_phrase("Plumbing License", "license") == "Plumbing License requirements how to apply"
    )
    assert search_phrase("Empathy", "soft_skill") == "how to improve empathy at work free course"


# --- seeded resources -------------------------------------------------------------------------


def test_every_industry_has_curated_resources() -> None:
    data = load_seed_data()
    industry_of: dict[str, str] = {}
    for path in (SEED_DIR / "skills").glob("*.json"):
        for row in json.loads(path.read_text()):
            industry_of[row["slug"]] = path.stem
    covered: dict[str, int] = defaultdict(int)
    for resource in data.resources:
        covered[industry_of[resource.skill]] += 1

    for industry in (i.slug for i in data.industries):
        assert covered[industry] >= 2, industry


def test_uncertain_resource_urls_are_flagged_for_review() -> None:
    rows = json.loads(Path(SEED_DIR / "learning_resources.json").read_text())

    flagged = [r for r in rows if r.get("todo")]
    assert flagged, "resources whose path wasn't confirmed must carry a todo"
    assert all(r["url"].startswith("https://") and r["is_free"] for r in rows)


@pytest.mark.parametrize(
    "verb",
    ["Assessed", "Triaged", "Prospected", "Reconciled", "Audited", "Cooked", "Taught", "Welded"],
)
def test_action_verbs_cover_every_field(verb: str) -> None:
    from app.services.ats.checks import _is_action_led

    assert _is_action_led(f"{verb} something measurable")
