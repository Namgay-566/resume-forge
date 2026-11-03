"""Flexible resume sections: the model's rules, suggested layouts, role- and stage-aware
requirements in the ATS checker, and the API."""

from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Industry, RoleSkill, Skill, TargetRole
from app.models.enums import ExperienceLevel as Level
from app.models.enums import ResumeType, SkillImportance
from app.schemas.resume_data import DEFAULT_SECTION_ORDER, ResumeData
from app.schemas.section_kind import SectionKind as K
from app.services.ats.checks import run_checks, years_of_experience
from app.services.sections.catalog import get_catalog
from app.services.sections.layout import RoleSections, section_requirements, suggest_layout
from app.tests.test_resumes import signup


def data(raw: dict[str, Any]) -> ResumeData:
    return ResumeData.model_validate(raw)


def ids(d: ResumeData) -> list[str]:
    return [s.id for s in d.sections]


# --- the model ------------------------------------------------------------------------


def test_resumes_saved_before_sections_get_the_old_export_order() -> None:
    assert ids(data({"summary": "Hi"})) == [k.value for k in DEFAULT_SECTION_ORDER]


def test_core_content_is_never_hidden_by_a_missing_section() -> None:
    d = data(
        {
            "projects": [{"name": "Garden redesign"}],
            "sections": [{"id": "summary", "kind": "summary"}],
        }
    )

    assert ids(d) == ["summary", "projects"]


@pytest.mark.parametrize(
    ("sections", "error"),
    [
        ([{"id": "summary", "kind": "summary"}] * 2, "only once"),
        ([{"id": "experience", "kind": "experience", "entries": [{"title": "x"}]}], "own field"),
        ([{"id": "custom-1", "kind": "custom"}], "name"),
        ([{"id": "hobbies", "kind": "custom", "title": "Hobbies"}], "custom-"),
        ([{"id": "pubs", "kind": "publications"}], "must be 'publications'"),
        ([{"id": "x", "kind": "astrology"}], "Input should be"),
    ],
)
def test_section_rules(sections: list[dict[str, Any]], error: str) -> None:
    with pytest.raises(ValidationError, match=error):
        data({"sections": sections})


def test_several_custom_sections_can_coexist() -> None:
    d = data(
        {
            "sections": [
                {"id": "custom-a", "kind": "custom", "title": "Hobbies"},
                {"id": "custom-b", "kind": "custom", "title": "References"},
            ]
        }
    )

    assert ids(d) == ["custom-a", "custom-b"]


def test_blank_rename_falls_back_to_the_standard_heading() -> None:
    d = data({"sections": [{"id": "skills", "kind": "skills", "title": "  "}]})

    assert d.sections[0].title is None


def test_catalog_describes_every_kind_with_labels() -> None:
    catalog = get_catalog()

    assert {k.kind for k in catalog.kinds} == set(K)
    assert catalog.heading(K.CERTIFICATIONS) == "Licenses & Certifications"
    assert catalog.spec(K.PUBLICATIONS).fields.dates == "single"  # type: ignore[union-attr]
    assert catalog.spec(K.LANGUAGES).layout == "inline"


# --- suggested layouts -------------------------------------------------------------------

NURSE = RoleSections(
    role_name="Registered Nurse",
    layout=(
        K.SUMMARY,
        K.CERTIFICATIONS,
        K.CLINICAL_EXPERIENCE,
        K.EXPERIENCE,
        K.EDUCATION,
        K.SKILLS,
    ),
    required=(K.CERTIFICATIONS,),
)
LECTURER = RoleSections(
    role_name="Lecturer",
    layout=(K.SUMMARY, K.EDUCATION, K.RESEARCH, K.PUBLICATIONS, K.CONFERENCES, K.SKILLS),
    required=(K.PUBLICATIONS,),
)


def test_nurse_layout_leads_with_licences_and_clinical_experience() -> None:
    layout = suggest_layout(ResumeType.RESUME, Level.MID, NURSE)

    assert layout[:3] == [K.SUMMARY, K.CERTIFICATIONS, K.CLINICAL_EXPERIENCE]


def test_fresher_layout_puts_education_first_then_projects_and_internships() -> None:
    layout = suggest_layout(ResumeType.RESUME, Level.STUDENT, NURSE)

    assert layout[:4] == [K.SUMMARY, K.EDUCATION, K.PROJECTS, K.INTERNSHIPS]
    assert layout[-1] == K.EXTRACURRICULARS
    assert K.CLINICAL_EXPERIENCE in layout  # the role's own sections stay


def test_academic_cv_has_publications_research_and_conferences() -> None:
    layout = suggest_layout(ResumeType.CV, Level.SENIOR, LECTURER)

    assert layout[:2] == [K.SUMMARY, K.EDUCATION]  # a CV keeps education up front
    assert {K.RESEARCH, K.PUBLICATIONS, K.CONFERENCES} <= set(layout)


def test_career_changer_leads_with_transferable_skills() -> None:
    layout = suggest_layout(ResumeType.RESUME, Level.CAREER_CHANGER, NURSE)

    assert layout[:2] == [K.SUMMARY, K.SKILLS]
    assert layout[-1] == K.TRAINING


def test_no_role_uses_the_default_layout() -> None:
    assert suggest_layout(ResumeType.RESUME, None) == get_catalog().default_layout


def test_required_sections_are_always_in_the_layout() -> None:
    role = RoleSections(
        role_name="Electrician", layout=(K.SUMMARY, K.EXPERIENCE), required=(K.CERTIFICATIONS,)
    )

    assert K.CERTIFICATIONS in suggest_layout(ResumeType.RESUME, None, role)


# --- requirements ---------------------------------------------------------------------


def severities(level: Level | None, role: RoleSections | None = None) -> dict[str, str]:
    return {r.id: r.severity for r in section_requirements(level, role)}


def test_requirements_depend_on_role_and_level() -> None:
    assert severities(None) == {
        "summary": "fail", "experience": "fail", "education": "fail", "skills": "fail"
    }  # fmt: skip
    assert severities(Level.MID, NURSE)["certifications"] == "fail"
    # A nursing student is still working towards the licence.
    assert severities(Level.STUDENT, NURSE)["certifications"] == "warn"
    assert severities(Level.STUDENT)["experience"] == "warn"
    assert severities(Level.SENIOR)["education"] == "warn"
    assert severities(Level.SENIOR, LECTURER)["publications"] == "fail"


def test_role_advice_names_the_role_and_section() -> None:
    advice = next(r.advice for r in section_requirements(None, NURSE) if r.id == "certifications")

    assert advice == (
        "Registered Nurse roles usually screen for this. Add a Licenses & Certifications section."
    )


# --- the ATS checker --------------------------------------------------------------------

CLINICAL = {
    "id": "clinical_experience",
    "kind": "clinical_experience",
    "entries": [
        {
            "title": "Staff Nurse",
            "organization": "St Mary's",
            "start_date": "2020-01",
            "end_date": "2023-01",
            "bullets": ["responsible for patients", "Triaged 30 patients a shift in A&E"],
        }
    ],
}
NURSE_RESUME = {
    "summary": "Registered nurse with three years in emergency care.",
    "education": [{"institution": "City University", "degree": "BSc Nursing"}],
    "skills": [{"name": "Triage"}],
    "sections": [
        {"id": "summary", "kind": "summary"},
        CLINICAL,
        {"id": "education", "kind": "education"},
    ],
}


def checks(
    raw: dict[str, Any], level: Level | None = None, role: RoleSections | None = None
) -> dict[str, Any]:
    return {c.id: c for c in run_checks(data(raw), ResumeType.RESUME, level, role)}


def test_clinical_experience_satisfies_the_experience_requirement() -> None:
    result = checks(NURSE_RESUME)["section_experience"]

    assert result.status == "pass"
    assert result.location.section == "clinical_experience"
    assert result.location.label == "Clinical Experience"


def test_a_nurse_without_a_licence_section_fails() -> None:
    result = checks(NURSE_RESUME, Level.MID, NURSE)["section_certifications"]

    assert result.status == "fail"
    assert result.title == "Missing Licenses & Certifications section"

    licensed = {**NURSE_RESUME, "certifications": [{"name": "NMC Registration"}]}
    assert checks(licensed, Level.MID, NURSE)["section_certifications"].status == "pass"


def test_a_student_can_rely_on_volunteering() -> None:
    raw = {
        **NURSE_RESUME,
        "sections": [
            {"id": "volunteer", "kind": "volunteer", "entries": [{"title": "Ward Volunteer"}]}
        ],
    }

    assert checks(raw, None)["section_experience"].status == "fail"
    assert checks(raw, Level.STUDENT)["section_experience"].status == "pass"


def test_bullets_in_new_sections_are_checked_like_jobs() -> None:
    result = checks(NURSE_RESUME)["action_verbs"]

    # "responsible for patients" is a weak opener, found inside Clinical Experience.
    assert result.status != "pass"
    assert result.location.section == "clinical_experience"


def test_clinical_and_teaching_time_counts_as_experience() -> None:
    assert years_of_experience(data(NURSE_RESUME)) == 3.0


def test_renamed_headings_must_stay_recognisable() -> None:
    fine = {**NURSE_RESUME, "sections": [{"id": "skills", "kind": "skills", "title": "Key Skills"}]}
    odd = {
        **NURSE_RESUME,
        "sections": [{"id": "skills", "kind": "skills", "title": "My Superpowers"}],
    }

    assert checks(fine)["standard_headings"].status == "pass"
    result = checks(odd)["standard_headings"]
    assert result.status == "warn"
    assert "'Skills'" in result.detail
    # Custom sections are named by the user and exempt.
    custom = {
        **NURSE_RESUME,
        "sections": [{"id": "custom-a", "kind": "custom", "title": "Hobbies"}],
    }
    assert checks(custom)["standard_headings"].status == "pass"


# --- API --------------------------------------------------------------------------------


@pytest.fixture
async def nurse_role(db_session: AsyncSession) -> TargetRole:
    health = Industry(
        slug="healthcare",
        name="Healthcare",
        default_sections=[k.value for k in NURSE.layout],
    )
    licence = Skill(slug="nursing-license", name="Nursing License", category="license", aliases=[])
    role = TargetRole(
        name="Registered Nurse", slug="registered-nurse", seniority="mid", industry=health
    )
    db_session.add_all([health, licence, role])
    await db_session.flush()
    db_session.add(
        RoleSkill(
            role_id=role.id, skill_id=licence.id, importance=SkillImportance.CRITICAL, weight=9
        )
    )
    await db_session.commit()
    return role


async def test_new_resume_starts_with_the_roles_sections(
    client: AsyncClient, nurse_role: TargetRole
) -> None:
    headers = await signup(client)

    body = (
        await client.post(
            "/api/resumes",
            json={
                "title": "CV",
                "target_role_id": str(nurse_role.id),
                "experience_level": "student",
            },
            headers=headers,
        )
    ).json()

    kinds = [s["kind"] for s in body["data"]["sections"]]
    assert kinds[:4] == ["summary", "education", "projects", "internships"]
    assert "clinical_experience" in kinds and "certifications" in kinds


async def test_suggestions_endpoint(client: AsyncClient, nurse_role: TargetRole) -> None:
    headers = await signup(client)

    body = (
        await client.get(
            f"/api/resume-sections/suggestions?target_role_id={nurse_role.id}", headers=headers
        )
    ).json()

    assert body["role_name"] == "Registered Nurse"
    assert body["sections"][:3] == ["summary", "certifications", "clinical_experience"]
    # The licence is required because the role's critical skills include one.
    assert "certifications" in body["required"]


async def test_catalog_endpoint(client: AsyncClient) -> None:
    headers = await signup(client)

    kinds = {
        k["kind"]: k
        for k in (await client.get("/api/resume-sections", headers=headers)).json()["kinds"]
    }

    assert kinds["clinical_experience"]["fields"]["organization"]["label"] == "Hospital or clinic"
    assert kinds["custom"]["repeatable"] is True


async def test_ats_analysis_uses_the_roles_requirements(
    client: AsyncClient, nurse_role: TargetRole
) -> None:
    headers = await signup(client)
    resume = (
        await client.post(
            "/api/resumes",
            json={"title": "CV", "target_role_id": str(nurse_role.id), "data": NURSE_RESUME},
            headers=headers,
        )
    ).json()

    report = (
        await client.post(
            f"/api/resumes/{resume['id']}/ats-analyses", json={"review": False}, headers=headers
        )
    ).json()["report"]

    by_id = {c["id"]: c for c in report["checks"]}
    assert by_id["section_certifications"]["status"] == "fail"
    assert by_id["section_experience"]["status"] == "pass"


async def test_sections_round_trip_through_the_api(client: AsyncClient) -> None:
    headers = await signup(client)
    resume = (await client.post("/api/resumes", json={"title": "CV"}, headers=headers)).json()
    sections = [
        {
            "id": "custom-x9",
            "kind": "custom",
            "title": "References",
            "entries": [{"title": "On request"}],
        },
        {"id": "summary", "kind": "summary", "title": "Profile"},
    ]

    saved = (
        await client.patch(
            f"/api/resumes/{resume['id']}",
            json={"data": {**resume["data"], "sections": sections}},
            headers=headers,
        )
    ).json()

    assert [(s["id"], s["title"]) for s in saved["data"]["sections"]] == [
        ("custom-x9", "References"),
        ("summary", "Profile"),
    ]
