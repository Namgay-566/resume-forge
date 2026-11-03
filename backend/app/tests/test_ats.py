import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ats import JdKeywords, RecruiterReview
from app.ai.client import AIClient, get_ai_client
from app.ai.errors import AIUnavailableError
from app.ai.types import AIRequest, AIResponse
from app.core.config import get_settings
from app.main import app
from app.models import ATSAnalysis, RoleSkill, Skill, TargetRole
from app.models.enums import ExperienceLevel, ResumeType, SkillImportance
from app.schemas.ats import KeywordHit, KeywordReport
from app.schemas.resume_data import ResumeData
from app.services.ats.checks import _is_quantified, run_checks, years_of_experience
from app.services.ats.keywords import AliasIndex, contains, match_keywords, normalize
from app.services.ats.scoring import CATEGORY_WEIGHTS, build_fixes, keyword_score, score
from app.tests.fakes import an_industry

STRONG = {
    "personal_info": {
        "full_name": "Ada Lovelace",
        "headline": "Full Stack Developer",
        "email": "ada@example.com",
        "phone": "+1 555 0100",
        "location": "London, UK",
        "profile_links": [{"label": "GitHub", "url": "github.com/ada"}],
    },
    "summary": "Full stack developer with four years building Python and React products used by "
    "fifty thousand people. I care about reliable APIs, fast pages and clean, tested code.",
    "experience": [
        {
            "company": "Acme",
            "title": "Software Engineer",
            "start_date": "2022-03",
            "is_current": True,
            "bullets": [
                "Built the billing API in FastAPI that now handles 2M requests a day",
                "Reduced p95 latency by 40% with Redis caching and query tuning",
                "Led the migration of 30 partners from polling to signed webhooks",
                "Designed the Postgres invoice schema, cutting reconciliation to 2 hours",
                "Mentored 3 junior engineers through code reviews and weekly pairing sessions",
            ],
            "tools_and_skills": ["Python", "FastAPI"],
        },
        {
            "company": "Startup",
            "title": "Junior Developer",
            "start_date": "2020-06",
            "end_date": "2022-02",
            "bullets": [
                "Shipped 12 React features end to end with product and design",
                "Automated the release pipeline with GitHub Actions, saving 5 hours a week",
                "Improved checkout conversion by 8% by rebuilding the cart page in React",
                "Wrote 200 integration tests that caught regressions before every release",
            ],
        },
    ],
    "education": [
        {
            "institution": "University of London",
            "degree": "BSc",
            "start_date": "2016-09",
            "end_date": "2020-06",
        }
    ],
    "skills": [
        {"name": n}
        for n in ["Python", "TypeScript", "React", "FastAPI", "Postgres", "Docker", "Git"]
    ],
}

WEAK = {
    "personal_info": {"full_name": "Sam"},
    "experience": [
        {
            "company": "Shop",
            "title": "Dev",
            "bullets": ["Responsible for the website", "Worked on bugs", "Helped the team"],
        },
        {"company": "Agency", "title": "Intern", "start_date": "2019-01", "end_date": "2019-06"},
        {
            "company": "Later Co",
            "title": "Engineer",
            "start_date": "2023-01",
            "is_current": True,
            "bullets": ["Did stuff ☎ ✉"],
        },
    ],
}


def data(raw: dict[str, Any]) -> ResumeData:
    return ResumeData.model_validate(raw)


def by_id(raw: dict[str, Any]) -> dict[str, Any]:
    return {c.id: c for c in run_checks(data(raw), ResumeType.RESUME)}


# --- deterministic checks -------------------------------------------------------------


def test_strong_resume_passes_every_check() -> None:
    failing = {k: (c.status, c.title) for k, c in by_id(STRONG).items() if c.status != "pass"}

    assert failing == {}


def test_weak_resume_fails_with_located_reasons() -> None:
    checks = by_id(WEAK)

    assert checks["section_summary"].status == "fail"
    assert checks["section_education"].status == "fail"
    assert checks["contact_essentials"].status == "fail"
    assert "email" in checks["contact_essentials"].title
    assert checks["dates_complete"].status == "fail"
    assert checks["dates_complete"].location.item_index == 0  # type: ignore[union-attr]
    assert checks["action_verbs"].status == "fail"
    assert checks["quantified"].status == "fail"
    assert checks["bullets_per_role"].status == "fail"
    assert checks["bullets_per_role"].location.item_index == 1  # type: ignore[union-attr]
    assert checks["reverse_chronological"].status == "warn"
    assert checks["reverse_chronological"].location.item_index == 2  # type: ignore[union-attr]
    assert checks["special_characters"].status == "warn"
    assert "☎" in checks["special_characters"].detail
    assert checks["length"].status == "fail"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cut latency by 40%", True),
        ("Saved $2M a year", True),
        ("Grew traffic 3x", True),
        ("Served 1,200 customers", True),
        ("Mentored 4 engineers", True),
        ("Joined in 2023 as lead", False),  # a year is not a result
        ("Improved the onboarding flow", False),
    ],
)
def test_quantified_detection(text: str, expected: bool) -> None:
    assert _is_quantified(text) is expected


def test_years_of_experience_merges_overlaps() -> None:
    resume = data(
        {
            "experience": [
                {"company": "A", "title": "x", "start_date": "2018-01", "end_date": "2020-01"},
                {"company": "B", "title": "y", "start_date": "2019-01", "end_date": "2021-01"},
                {"company": "C", "title": "z", "start_date": "2022-01", "end_date": "2023-01"},
            ]
        }
    )

    assert years_of_experience(resume) == 4.0  # 2018-2021 merged (3y) + 1y


def test_long_resume_for_junior_is_flagged() -> None:
    raw = json.loads(json.dumps(STRONG))
    job = raw["experience"][0]
    job["start_date"] = "2025-01"  # under 3 years: one page expected
    job["bullets"] = ["Built a very detailed thing " + "word " * 25] * 10
    raw["experience"] = [job] * 4  # 40 long bullets in all, within the per-entry cap
    checks = {c.id: c for c in run_checks(data(raw), ResumeType.RESUME)}
    cv_checks = {c.id: c for c in run_checks(data(raw), ResumeType.CV)}

    assert checks["length"].status == "warn"
    assert cv_checks["length"].status == "pass"  # CVs may run long


# --- keyword matching ------------------------------------------------------------------------


def skills_index() -> AliasIndex:
    return AliasIndex.from_skills(
        [
            Skill(name="SQL", slug="sql", category="db", aliases=["sql", "postgres", "postgresql"]),
            Skill(name="JavaScript", slug="js", category="lang", aliases=["javascript", "js"]),
            Skill(name="Java", slug="java", category="lang", aliases=["java"]),
            Skill(name="Git", slug="git", category="tool", aliases=["git", "github"]),
        ]
    )


def test_keywords_match_through_aliases_and_report_how() -> None:
    text = normalize("Built services with Postgres and GitHub Actions.")
    wanted = [
        KeywordHit(keyword="PostgreSQL"),
        KeywordHit(keyword="Git"),
        KeywordHit(keyword="Kubernetes"),
    ]

    matched, missing = match_keywords(wanted, text, skills_index())

    assert [(m.keyword, m.matched_as) for m in matched] == [
        ("PostgreSQL", "postgres"),
        ("Git", "github"),
    ]
    assert [m.keyword for m in missing] == ["Kubernetes"]


@pytest.mark.parametrize(
    ("text", "phrase", "expected"),
    [
        ("i write javascript daily", "java", False),  # no substring false positives
        ("c++ and c# developer", "c++", True),
        ("c++ and c# developer", "c#", True),
        ("apis in node.js.", "node.js", True),
        ("ci / cd pipelines", "ci / cd", True),
        ("golang services at google", "go", False),
    ],
)
def test_phrase_matching_boundaries(text: str, phrase: str, expected: bool) -> None:
    assert contains(normalize(text), normalize(phrase)) is expected


# --- scoring is explainable -----------------------------------------------------------------------


@pytest.mark.parametrize("raw", [STRONG, WEAK])
def test_points_lost_add_up_to_the_gap(raw: dict[str, Any]) -> None:
    keywords = KeywordReport(
        source="target_role",
        matched=[KeywordHit(keyword="Python", weight=3)],
        missing=[KeywordHit(keyword="Docker", weight=2), KeywordHit(keyword="AWS", weight=1)],
    )

    total, categories, checks = score(run_checks(data(raw), ResumeType.RESUME), keywords)

    kw_lost = CATEGORY_WEIGHTS["keywords"] * (100 - (keyword_score(keywords) or 0))
    explained = sum(c.points_lost for c in checks) + kw_lost
    assert abs((100 - total) - explained) <= 1.5  # only rounding differs
    assert {c.key for c in categories} == {"formatting", "keywords", "impact", "completeness"}


def test_keywords_weight_is_redistributed_when_not_scored() -> None:
    total, categories, _ = score(
        run_checks(data(STRONG), ResumeType.RESUME), KeywordReport(source=None)
    )

    kw = next(c for c in categories if c.key == "keywords")
    assert kw.score is None and kw.weight == 0
    assert abs(sum(c.weight for c in categories) - 1) < 0.01
    assert total >= 95


def test_fixes_are_ranked_by_points_then_ai() -> None:
    keywords = KeywordReport(
        source="job_description", matched=[], missing=[KeywordHit(keyword="Docker", weight=2)]
    )
    _, _, checks = score(run_checks(data(WEAK), ResumeType.RESUME), keywords)
    review = RecruiterReview.model_validate(
        {
            "overall": "ok",
            "sections": [
                {
                    "section": "summary",
                    "rating": "weak",
                    "feedback": "Missing.",
                    "suggestions": ["Write a summary."],
                },
            ],
        }
    )
    from app.schemas.ats import AIReview

    fixes = build_fixes(checks, keywords, AIReview.model_validate(review.model_dump()))

    assert [f.priority for f in fixes] == list(range(1, len(fixes) + 1))
    scored = [f.points for f in fixes if f.source != "ai"]
    assert scored == sorted(scored, reverse=True)
    assert fixes[-1].source == "ai" and fixes[-1].location.section == "summary"  # type: ignore[union-attr]
    assert any(f.source == "keywords" and "Docker" in f.title for f in fixes)
    assert fixes[0].severity == "high"


# --- endpoint ----------


class RoutingProvider:
    """Mocked provider answering by response model, so parallel calls can't swap answers."""

    name = "fake"
    model = "fake-1"

    def __init__(self, answers: dict[type, str | Exception]) -> None:
        self.answers = answers
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        answer = self.answers[request.response_model]
        if isinstance(answer, Exception):
            raise answer
        return AIResponse(text=answer, model=self.model, input_tokens=10, output_tokens=5)


REVIEW = json.dumps(
    {
        "overall": "Solid backend profile; add cloud experience.",
        "sections": [
            {
                "section": "experience",
                "rating": "strong",
                "feedback": "Clear impact.",
                "suggestions": [],
            },
            {
                "section": "skills",
                "rating": "weak",
                "feedback": "No cloud skills.",
                "suggestions": ["Add the AWS services you have used.", "Group skills by type."],
            },
        ],
    }
)
JD_KEYWORDS = json.dumps(
    {
        "keywords": [
            {"keyword": "Python", "importance": "required"},
            {"keyword": "PostgreSQL", "importance": "required"},
            {"keyword": "Kubernetes", "importance": "required"},
            {"keyword": "GraphQL", "importance": "preferred"},
        ]
    }
)


def use_provider(answers: dict[type, str | Exception]) -> RoutingProvider:
    provider = RoutingProvider(answers)
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)
    return provider


@pytest.fixture
async def catalog(db_session: AsyncSession) -> TargetRole:
    sql = Skill(name="SQL", slug="sql", category="db", aliases=["sql", "postgres", "postgresql"])
    python = Skill(name="Python", slug="python", category="lang", aliases=["python"])
    docker = Skill(name="Docker", slug="docker", category="tool", aliases=["docker"])
    k8s = Skill(
        name="Kubernetes", slug="kubernetes", category="tool", aliases=["kubernetes", "k8s"]
    )
    role = TargetRole(
        name="Backend Developer",
        slug="backend",
        description="",
        seniority="junior",
        industry=an_industry(),
    )
    db_session.add_all([sql, python, docker, k8s, role])
    await db_session.flush()
    db_session.add_all(
        [
            RoleSkill(
                role_id=role.id, skill_id=python.id, importance=SkillImportance.CRITICAL, weight=10
            ),
            RoleSkill(
                role_id=role.id, skill_id=sql.id, importance=SkillImportance.CRITICAL, weight=9
            ),
            RoleSkill(
                role_id=role.id, skill_id=k8s.id, importance=SkillImportance.NICE_TO_HAVE, weight=2
            ),
        ]
    )
    await db_session.commit()
    return role


async def setup_resume(
    client: AsyncClient, role: TargetRole | None, email: str = "ats@example.com"
):  # type: ignore[no-untyped-def]
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123", "name": "Ada"}
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    body: dict[str, Any] = {"title": "Main", "data": STRONG}
    if role:
        body["target_role_id"] = str(role.id)
    resume = await client.post("/api/resumes", json=body, headers=headers)
    return headers, resume.json()["id"]


async def test_analysis_with_job_description(
    client: AsyncClient, db_session: AsyncSession, catalog: TargetRole
) -> None:
    provider = use_provider({JdKeywords: JD_KEYWORDS, RecruiterReview: REVIEW})
    headers, resume_id = await setup_resume(client, catalog)

    response = await client.post(
        f"/api/resumes/{resume_id}/ats-analyses",
        json={"job_description": "We need Python, PostgreSQL and Kubernetes. GraphQL a plus."},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    report = body["report"]
    assert body["score"] == report["score"]
    kw = report["keywords"]
    assert (kw["source"], kw["extraction"]) == ("job_description", "ai")
    assert {m["keyword"]: m["matched_as"] for m in kw["matched"]} == {
        "Python": None,
        "PostgreSQL": "postgres",
    }
    assert [m["keyword"] for m in kw["missing"]] == ["Kubernetes", "GraphQL"]
    assert report["ai_status"] == "ok"
    assert report["ai_review"]["sections"][1]["rating"] == "weak"
    assert {c["key"] for c in report["categories"]} == {
        "formatting",
        "keywords",
        "impact",
        "completeness",
    }
    assert report["fixes"][0]["priority"] == 1
    assert any(f["source"] == "keywords" and "Kubernetes" in f["title"] for f in report["fixes"])
    assert any(f["source"] == "ai" for f in report["fixes"])
    # The resume went to the AI as plain text in export order.
    review_prompt = next(r.prompt for r in provider.requests if r.response_model is RecruiterReview)
    assert "EXPERIENCE" in review_prompt and "Backend Developer" in review_prompt

    saved = await db_session.scalar(select(ATSAnalysis))
    assert saved is not None and saved.score == body["score"]
    latest = await client.get(f"/api/resumes/{resume_id}/ats-analyses/latest", headers=headers)
    assert latest.json()["id"] == body["id"]
    resume = await client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert resume.json()["ats_score"] == body["score"]


async def test_without_jd_uses_target_role_skills(client: AsyncClient, catalog: TargetRole) -> None:
    use_provider({RecruiterReview: REVIEW})
    headers, resume_id = await setup_resume(client, catalog)

    report = (
        await client.post(f"/api/resumes/{resume_id}/ats-analyses", json={}, headers=headers)
    ).json()["report"]

    assert report["keywords"]["source"] == "target_role"
    assert [m["keyword"] for m in report["keywords"]["matched"]] == ["Python", "SQL"]
    assert [m["keyword"] for m in report["keywords"]["missing"]] == ["Kubernetes"]
    assert report["keywords"]["missing"][0]["importance"] == "preferred"


async def test_ai_outage_still_scores_deterministically(
    client: AsyncClient, catalog: TargetRole
) -> None:
    down = AIUnavailableError("no key")
    use_provider({JdKeywords: down, RecruiterReview: down})
    headers, resume_id = await setup_resume(client, catalog)

    response = await client.post(
        f"/api/resumes/{resume_id}/ats-analyses",
        json={"job_description": "Python and Docker experience required, Kubernetes a plus."},
        headers=headers,
    )

    report = response.json()["report"]
    assert response.status_code == 201
    assert report["ai_status"] == "unavailable" and report["ai_review"] is None
    assert report["keywords"]["extraction"] == "catalog"  # fell back to a catalog scan
    assert {m["keyword"] for m in report["keywords"]["matched"]} == {"Python", "Docker"}
    assert [m["keyword"] for m in report["keywords"]["missing"]] == ["Kubernetes"]
    assert all(f["source"] != "ai" for f in report["fixes"])


async def test_no_role_no_jd_leaves_keywords_unscored(client: AsyncClient) -> None:
    use_provider({RecruiterReview: REVIEW})
    headers, resume_id = await setup_resume(client, None)

    report = (
        await client.post(f"/api/resumes/{resume_id}/ats-analyses", json={}, headers=headers)
    ).json()["report"]

    keywords = next(c for c in report["categories"] if c["key"] == "keywords")
    assert report["keywords"]["source"] is None
    assert keywords["score"] is None


async def test_ats_is_owner_only_and_latest_404s_before_first_run(client: AsyncClient) -> None:
    use_provider({RecruiterReview: REVIEW})
    owner, resume_id = await setup_resume(client, None, "owner-ats@example.com")
    intruder, _ = await setup_resume(client, None, "intruder-ats@example.com")
    url = f"/api/resumes/{resume_id}/ats-analyses"

    assert (await client.get(f"{url}/latest", headers=owner)).status_code == 404
    assert (await client.post(url, json={}, headers=intruder)).status_code == 404
    assert (await client.get(f"{url}/latest", headers=intruder)).status_code == 404


async def test_ai_endpoints_share_one_rate_limit_budget(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_rate_limit", "2/minute")
    use_provider({RecruiterReview: REVIEW})
    headers, resume_id = await setup_resume(client, None)

    first = await client.post(f"/api/resumes/{resume_id}/ats-analyses", json={}, headers=headers)
    second = await client.post(
        "/api/resumes/import", files={"file": ("a.txt", b"x", "text/plain")}, headers=headers
    )
    third = await client.post(f"/api/resumes/{resume_id}/ats-analyses", json={}, headers=headers)

    # The shared budget (ATS + import) is spent after two calls. The third check still scores
    # the resume (the score is deterministic) but skips the AI review.
    assert (first.status_code, second.status_code, third.status_code) == (201, 415, 201)
    assert first.json()["report"]["ai_status"] == "ok"
    assert third.json()["report"]["ai_status"] == "rate_limited"
    assert third.json()["report"]["ai_review"] is None


# --- experience level -----------------------------------------------------------------

STUDENT = {
    "personal_info": {"full_name": "Priya Shah", "email": "priya@example.com"},
    "summary": "Final-year nursing student looking for a newly qualified nurse post.",
    "education": [{"institution": "City University", "degree": "BSc Nursing"}],
    "skills": [{"name": "Patient care"}, {"name": "Communication"}],
}


def level_checks(raw: dict[str, Any], level: ExperienceLevel | None) -> dict[str, Any]:
    return {c.id: c for c in run_checks(data(raw), ResumeType.RESUME, level)}


def test_students_are_not_failed_for_having_no_work_history_yet() -> None:
    unknown = level_checks(STUDENT, None)["section_experience"]
    student = level_checks(STUDENT, ExperienceLevel.STUDENT)["section_experience"]

    assert unknown.status == "fail"
    assert student.status == "warn"
    assert "volunteering" in student.detail


def test_seniors_may_leave_out_education() -> None:
    raw = {**STRONG, "education": []}

    assert level_checks(raw, ExperienceLevel.MID)["section_education"].status == "fail"
    assert level_checks(raw, ExperienceLevel.SENIOR)["section_education"].status == "warn"


def test_career_changer_advice_is_about_transferable_skills() -> None:
    raw = {**STUDENT, "summary": "", "experience": [], "projects": []}
    checks = level_checks(raw, ExperienceLevel.CAREER_CHANGER)

    assert "carry over" in checks["section_summary"].detail
    assert "new role needs" in checks["section_experience"].detail
    assert checks["section_experience"].status == "fail"  # a past career is expected


def test_early_career_resumes_are_held_to_one_page() -> None:
    long_bullet = "Coordinated weekly rotas for twelve volunteers across three community sites"
    raw = {
        **STRONG,
        "experience": [
            {**STRONG["experience"][0], "bullets": [long_bullet] * 15, "start_date": "2012-01"}
        ]
        * 5,
    }

    assert level_checks(raw, None)["length"].status == "pass"  # ~14 years: two pages is fine
    entry = level_checks(raw, ExperienceLevel.ENTRY)["length"]
    assert entry.status == "warn" and "one page" in entry.detail


def test_early_career_needs_fewer_numbers() -> None:
    bullets = ["Served 40 customers a shift"] + ["Kept the stockroom tidy and labelled"] * 3
    raw = {**STRONG, "experience": [{**STRONG["experience"][0], "bullets": bullets}]}
    raw["projects"] = []

    assert level_checks(raw, ExperienceLevel.MID)["quantified"].status != "pass"
    assert level_checks(raw, ExperienceLevel.STUDENT)["quantified"].status == "pass"


async def test_experience_level_reaches_the_ai_review(client: AsyncClient) -> None:
    provider = use_provider({RecruiterReview: REVIEW})
    response = await client.post(
        "/api/auth/register",
        json={"email": "student@example.com", "password": "password123", "name": "Priya"},
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    resume = (
        await client.post(
            "/api/resumes",
            json={"title": "CV", "data": STUDENT, "experience_level": "student"},
            headers=headers,
        )
    ).json()

    await client.post(f"/api/resumes/{resume['id']}/ats-analyses", json={}, headers=headers)

    review_prompt = next(r.prompt for r in provider.requests if "Career stage" in r.prompt)
    assert "Career stage: student" in review_prompt
