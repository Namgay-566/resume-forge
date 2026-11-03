"""Importing CVs from every field fills every section: clinical placements, publications,
teaching, languages... and keeps anything unrecognised as a custom section under its own
heading. The AI is scripted with what a faithful parse of each sample CV returns.

To check a real model on the same CVs (costs a few AI calls):
    .venv/bin/python -m app.tests.test_import_sections
"""

import json
from io import BytesIO
from typing import Any

import pytest
from docx import Document
from httpx import AsyncClient

from app.ai.client import AIClient, get_ai_client
from app.ai.resume_parser import ParsedResume, extra_sections, section_guide, to_resume_data
from app.main import app
from app.models.enums import ResumeType
from app.schemas.resume_data import ResumeData, SectionConfig, SectionItem
from app.schemas.section_kind import SectionKind
from app.services.sections.layout import suggest_layout, with_layout
from app.tests.fakes import FakeProvider
from app.tests.sample_cvs import (
    NURSE_CV,
    NURSE_PARSED,
    RESEARCHER_CV,
    RESEARCHER_PARSED,
    TEACHER_CV,
    TEACHER_PARSED,
)

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def as_docx(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


async def import_cv(client: AsyncClient, text: str, parsed: dict[str, Any]) -> dict[str, Any]:
    provider = FakeProvider(json.dumps(parsed))
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)
    signup = await client.post(
        "/api/auth/register",
        json={"email": "cv@example.com", "password": "password123", "name": "CV"},
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    response = await client.post(
        "/api/resumes/import", files={"file": ("cv.docx", as_docx(text), DOCX)}, headers=headers
    )
    assert response.status_code == 201, response.text
    # The CV text and the full section list reached the AI.
    request = provider.requests[0]
    assert text.splitlines()[0] in request.prompt
    for kind in SectionKind:
        if not kind.is_core:
            assert f"- {kind.value} (" in (request.system or ""), kind
    data: dict[str, Any] = response.json()["resume"]["data"]
    return data


def sections(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["id"]: s for s in data["sections"]}


def titles(section: dict[str, Any]) -> list[str]:
    return [e["title"] for e in section["entries"]]


async def test_nurse_cv_keeps_clinical_volunteer_languages_and_the_rest(
    client: AsyncClient,
) -> None:
    data = await import_cv(client, NURSE_CV, NURSE_PARSED)
    found = sections(data)

    assert titles(found["clinical_experience"]) == ["Student Nurse"]
    assert found["clinical_experience"]["entries"][0]["bullets"] == [
        "Triaged walk-in patients under supervision"
    ]
    assert titles(found["volunteer"]) == ["First Aid Volunteer"]
    assert [(e["title"], e["organization"]) for e in found["languages"]["entries"]] == [
        ("Gujarati", "Native"),
        ("Spanish", "Conversational"),
    ]
    assert found["memberships"]["entries"][0]["is_current"] is True
    # Licences land in Licenses & Certifications.
    assert [c["name"] for c in data["certifications"]] == [
        "NMC Registered Nurse (Adult)",
        "Basic Life Support (BLS)",
    ]
    # Unrecognised headings survive as custom sections under the CV's own words.
    custom = {s["title"]: titles(s) for s in data["sections"] if s["kind"] == "custom"}
    assert custom == {
        "Interests": ["Half-marathon running and community choir"],
        "Referees": ["Available on request"],
    }
    assert found["custom-interests"]["kind"] == "custom"
    # Known sections print under the standard (ATS-safe) heading.
    assert found["clinical_experience"]["title"] is None
    assert data["experience"][0]["company"] == "St Mary's Hospital"


async def test_researcher_cv_keeps_publications_talks_teaching_and_grants(
    client: AsyncClient,
) -> None:
    data = await import_cv(client, RESEARCHER_CV, RESEARCHER_PARSED)
    found = sections(data)

    publications = found["publications"]["entries"]
    assert [p["title"] for p in publications] == [
        "Drought shifts the wheat root microbiome",
        "Sampling soil microbes at scale",
    ]
    assert publications[0]["link"] == "doi.org/10.1234/jps.2023.44"
    assert publications[0]["start_date"] == "2023-01"
    # "Research Interests" and "Research Experience" merge into one Research section.
    assert len(found["research"]["entries"]) == 2
    assert titles(found["conferences"]) == ["Invited talk: Microbes and drought"]
    assert titles(found["teaching_experience"]) == ["Seminar Leader, Plant Biology (Year 2)"]
    assert titles(found["awards"]) == ["BBSRC Discovery Fellowship"]
    assert found["custom-fieldwork-sites"]["title"] == "Fieldwork Sites"
    assert data["personal_info"]["profile_links"][0]["label"] == "ORCID"
    # A CV leads with education, and every imported section is in the layout.
    ids = [s["id"] for s in data["sections"]]
    assert ids.index("education") < ids.index("publications")


async def test_teacher_cv_keeps_teaching_training_activities_and_awards(
    client: AsyncClient,
) -> None:
    data = await import_cv(client, TEACHER_CV, TEACHER_PARSED)
    found = sections(data)

    teaching = found["teaching_experience"]["entries"][0]
    assert teaching["organization"] == "Oakfield Primary School"
    assert teaching["is_current"] is True and teaching["end_date"] is None
    assert len(teaching["bullets"]) == 2
    assert titles(found["training"]) == [
        "Safeguarding Level 2",
        "Teaching Phonics with Read Write Inc",
    ]
    assert titles(found["extracurriculars"]) == ["Chess Club Lead"]
    assert titles(found["awards"]) == ["Teacher of the Year"]
    assert found["custom-dbs"]["title"] == "DBS"
    assert [c["name"] for c in data["certifications"]][0] == "Qualified Teacher Status (QTS)"
    assert data["experience"] == []  # no generic jobs: teaching carries the resume


def test_same_kind_and_same_heading_sections_merge() -> None:
    parsed = ParsedResume.model_validate(
        {
            "sections": [
                {"kind": "awards", "heading": "Awards", "entries": [{"title": "A"}]},
                {"kind": "custom", "heading": "Interests", "entries": [{"title": "Chess"}]},
                {"kind": "awards", "heading": "Honours", "entries": [{"title": "B"}]},
                {"kind": "custom", "heading": "interests", "entries": [{"title": "Choir"}]},
                {"kind": "custom", "heading": "Hobbies!", "entries": [{"title": "Baking"}]},
                {"kind": "custom", "heading": "Empty", "entries": [{"title": " "}]},
            ]
        }
    )

    found = extra_sections(parsed)

    assert [(s.id, s.title, [e.title for e in s.entries]) for s in found] == [
        ("awards", None, ["A", "B"]),
        ("custom-interests", "Interests", ["Chess", "Choir"]),
        ("custom-hobbies", "Hobbies!", ["Baking"]),
    ]


def test_custom_ids_stay_unique_and_valid() -> None:
    parsed = ParsedResume.model_validate(
        {
            "sections": [
                {"kind": "custom", "heading": "Driving licence", "entries": [{"title": "Full"}]},
                {"kind": "custom", "heading": "Driving  Licence!", "entries": [{"title": "B"}]},
                {"kind": "custom", "heading": "日本語", "entries": [{"title": "N2"}]},
                {"kind": "custom", "heading": "", "entries": [{"title": "Misc"}]},
            ]
        }
    )

    data = to_resume_data(parsed)  # validates ids and titles

    custom = [s for s in data.sections if s.kind is SectionKind.CUSTOM]
    assert len({s.id for s in custom}) == 4
    assert custom[1].id == "custom-driving-licence-2"
    assert custom[3].title == "Additional Information"


def test_layout_keeps_imported_content_in_order() -> None:
    data = to_resume_data(ParsedResume.model_validate(NURSE_PARSED))

    laid_out = with_layout(data, suggest_layout(ResumeType.RESUME, None))

    ids = [s.id for s in laid_out.sections]
    # Suggested sections first, then the imported ones the layout doesn't include.
    assert ids[0] == "summary"
    for section in data.sections:
        placed = next(s for s in laid_out.sections if s.id == section.id)
        assert placed.entries == section.entries
    assert ids.index("custom-interests") < ids.index("custom-referees")


def test_layout_drops_empty_sections_before_content_when_full() -> None:
    extra = [
        SectionConfig(
            id=f"custom-s{i}",
            kind=SectionKind.CUSTOM,
            title=f"S{i}",
            entries=[SectionItem(title="x")],
        )
        for i in range(28)
    ]
    data = ResumeData(sections=extra)

    laid_out = with_layout(data, suggest_layout(ResumeType.RESUME, None))

    assert len(laid_out.sections) <= 30
    assert sum(1 for s in laid_out.sections if s.kind is SectionKind.CUSTOM) == 28


def test_guide_describes_every_non_core_kind_from_the_catalog() -> None:
    guide = {g["kind"]: g for g in section_guide()}

    assert set(guide) == {k.value for k in SectionKind if not k.is_core}
    assert guide["publications"]["fields"] == {
        "title": "Title",
        "organization": "Journal, publisher or venue",
        "description": "Authors and details",
        "link": "Link or DOI",
        "start_date": "date",
    }
    assert "clinical placements" in guide["clinical_experience"]["headings"]  # type: ignore[operator]


@pytest.mark.parametrize("kind", ["experience", "summary", "made_up"])
def test_parser_only_accepts_non_core_kinds_in_sections(kind: str) -> None:
    with pytest.raises(ValueError):
        ParsedResume.model_validate({"sections": [{"kind": kind, "heading": "X"}]})


# --- manual check against a real model ------------------------------------------------------


async def _live() -> None:  # pragma: no cover
    from app.ai.client import get_ai_client as real_client
    from app.ai.resume_parser import parse_resume_text

    ai = real_client()
    for name, text in [("nurse", NURSE_CV), ("researcher", RESEARCHER_CV), ("teacher", TEACHER_CV)]:
        data = to_resume_data(await parse_resume_text(ai, text))
        print(f"\n== {name}")
        print("  experience:", [e.title for e in data.experience])
        print("  certifications:", [c.name for c in data.certifications])
        for s in data.sections:
            if s.entries:
                print(f"  {s.id} [{s.title or s.kind.value}]:", [e.title for e in s.entries])


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    asyncio.run(_live())
