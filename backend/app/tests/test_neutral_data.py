"""Industry-neutral resume data: profile links and tools replace GitHub and tech; every
field groups its skills its own way; industries suggest their own profile links."""

import importlib.util
import json
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.demo_data import DEMO_USERS
from app.db.seed import SEED_DIR, apply_seed, load_seed_data
from app.models.enums import ResumeType
from app.schemas.resume_data import ResumeData
from app.services.export.document import build_document, plain_text
from app.tests.test_demo_users import run_demo

MIGRATION = next(
    Path(__file__).parents[2].glob("alembic/versions/*_neutral_resume_data_skill_groups_*.py")
)


def migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("neutral_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OLD_RESUME: dict[str, Any] = {
    "personal_info": {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "linkedin": "linkedin.com/in/ada",
        "github": "github.com/ada",
        "website": "ada.dev",
    },
    "experience": [{"company": "Acme", "title": "Dev", "tech": ["Python", "SQL"]}],
    "projects": [{"name": "Tracker", "tech": ["React"]}],
}


# --- the data migration ----------------------------------------------------------------


def test_migration_converts_old_resumes_without_losing_data() -> None:
    new = migration().upgrade_resume(json.loads(json.dumps(OLD_RESUME)))

    assert new["personal_info"]["profile_links"] == [
        {"label": "LinkedIn", "url": "linkedin.com/in/ada"},
        {"label": "GitHub", "url": "github.com/ada"},
        {"label": "Personal website", "url": "ada.dev"},
    ]
    assert not {"linkedin", "github", "website"} & set(new["personal_info"])
    assert new["experience"][0]["tools_and_skills"] == ["Python", "SQL"]
    assert new["projects"][0]["tools_and_skills"] == ["React"]
    # And the result is a valid resume for the new model.
    assert ResumeData.model_validate(new).personal_info.profile_links[1].url == "github.com/ada"


def test_migration_is_idempotent_and_reversible() -> None:
    module = migration()
    once = module.upgrade_resume(json.loads(json.dumps(OLD_RESUME)))
    twice = module.upgrade_resume(json.loads(json.dumps(once)))

    assert twice == once
    assert module.downgrade_resume(json.loads(json.dumps(once))) == {
        **OLD_RESUME,
        "personal_info": {**OLD_RESUME["personal_info"]},
    }


def test_downgrade_keeps_an_extra_link_in_the_website_slot() -> None:
    new = {"personal_info": {"profile_links": [{"label": "ORCID", "url": "orcid.org/0000-0001"}]}}

    old = migration().downgrade_resume(new)["personal_info"]

    assert old == {"linkedin": None, "github": None, "website": "orcid.org/0000-0001"}


# --- the model and exports -----------------------------------------------------------------


def test_profile_links_print_after_contact_details() -> None:
    data = ResumeData.model_validate(
        {
            "personal_info": {
                "full_name": "Dr Mei Chen",
                "email": "mei@example.com",
                "profile_links": [
                    {"label": "ORCID", "url": "orcid.org/0000-0002-1825-0097"},
                    {"label": "Google Scholar", "url": "scholar.google.com/citations?user=abc"},
                ],
            },
            "experience": [{"company": "Lab", "title": "Postdoc", "tools_and_skills": ["SPSS"]}],
        }
    )

    doc = build_document(data, ResumeType.CV)

    assert doc.contact == [
        "mei@example.com",
        "orcid.org/0000-0002-1825-0097",
        "scholar.google.com/citations?user=abc",
    ]
    assert "Tools: SPSS" in plain_text(data, ResumeType.CV)


def test_old_field_names_are_refused() -> None:
    with pytest.raises(ValueError):
        ResumeData.model_validate({"personal_info": {"github": "github.com/ada"}})
    with pytest.raises(ValueError):
        ResumeData.model_validate({"experience": [{"company": "A", "title": "B", "tech": ["x"]}]})


# --- skill groups ----------------------------------------------------------------------------


def test_every_skill_has_a_group_from_its_field() -> None:
    data = load_seed_data()
    by_slug = {s.slug: s.group for s in data.skills}
    names = {g.group.slug: g.group.name for g in data.skill_groups}

    assert all(by_slug.values())
    assert names[by_slug["patient-assessment"]] == "Clinical skills"
    assert names[by_slug["phlebotomy"]] == "Procedures"
    assert names[by_slug["nursing-license"]] == "Credentials"
    assert names[by_slug["gaap-ifrs"]] == "Accounting standards & regulations"
    assert names[by_slug["prospecting"]] == "Prospecting & pipeline"
    assert names[by_slug["crm-software"]] == "CRM & sales tools"
    assert names[by_slug["food-hygiene-certificate"]] == "Food & drink safety"
    assert names[by_slug["react"]] == "Frameworks & libraries"  # tech keeps its categories
    assert names[by_slug["communication"]] == "Soft skills"


def test_each_industry_has_its_own_groups() -> None:
    data = load_seed_data()
    per_industry = Counter(g.industry for g in data.skill_groups if g.industry)

    assert set(per_industry) == {i.slug for i in data.industries}
    assert all(n >= 3 for n in per_industry.values()), per_industry


def test_industries_suggest_their_own_profile_links() -> None:
    links = {i.slug: i.profile_links for i in load_seed_data().industries}

    assert "GitHub" in links["technology"]
    assert {"Behance", "Dribbble"} <= set(links["design-creative"])
    assert {"ORCID", "Google Scholar"} <= set(links["research-academia"])
    assert all(
        "LinkedIn" in v and ("Personal website" in v or "Portfolio" in v) for v in links.values()
    )
    assert "GitHub" not in links["healthcare"]


def test_seed_rejects_unknown_profile_links(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(SEED_DIR, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "industries.json"
    rows = json.loads(path.read_text())
    rows[0]["profile_links"] = ["MySpace"]
    path.write_text(json.dumps(rows))

    with pytest.raises(ValueError, match="unknown profile links"):
        load_seed_data(tmp_path)


@pytest.fixture
async def catalog(db_session: AsyncSession) -> None:
    await apply_seed(db_session, load_seed_data())
    await db_session.commit()


async def test_skill_gap_groups_the_nurses_skills_by_healthcare_categories(
    client: AsyncClient, db_session: AsyncSession, catalog: None
) -> None:
    nurse = next(d for d in DEMO_USERS if d.key == "nurse")

    skills = (await run_demo(client, db_session, nurse))["gap"]["skills"]

    groups = {s["slug"]: s["group"]["name"] for s in skills}
    assert groups["patient-assessment"] == "Clinical skills"
    assert groups["patient-care"] == "Patient care"
    assert groups["nursing-license"] == "Credentials"
    assert groups["communication"] == "Soft skills"
    # Field groups come before shared ones.
    order = {s["group"]["name"]: s["group"]["sort_order"] for s in skills}
    assert order["Clinical skills"] < order["Soft skills"]


async def test_roles_carry_their_industrys_profile_links(
    client: AsyncClient, db_session: AsyncSession, catalog: None
) -> None:
    from app.tests.test_resumes import signup

    headers = await signup(client)
    roles = {r["slug"]: r for r in (await client.get("/api/target-roles", headers=headers)).json()}

    assert roles["lecturer"]["industry"]["profile_links"][:3] == [
        "LinkedIn",
        "ORCID",
        "Google Scholar",
    ]
    catalog_links = (await client.get("/api/resume-sections", headers=headers)).json()[
        "profile_links"
    ]
    assert {"label": "ORCID", "placeholder": "orcid.org/0000-0000-0000-0000"} in catalog_links


async def test_ai_generated_skills_join_their_fields_groups(
    client: AsyncClient, db_session: AsyncSession, catalog: None
) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models import Skill
    from app.tests.test_resumes import signup
    from app.tests.test_target_roles import profile, use

    use(profile())
    headers = await signup(client)
    response = await client.post(
        "/api/target-roles/custom", json={"title": "Veterinary Nurse"}, headers=headers
    )
    assert response.status_code == 200, response.text

    skill = await db_session.scalar(
        select(Skill).where(Skill.name == "Animal Handling").options(selectinload(Skill.group))
    )
    assert skill and skill.group and skill.group.slug == "hc-records"  # healthcare "practice"
