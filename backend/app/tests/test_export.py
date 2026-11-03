"""Export tests. The PDF tests extract text with pdfplumber, which is roughly what an
ATS does, and check that every section comes out complete and in the right order."""

from io import BytesIO
from typing import Any

import pdfplumber
import pytest
from docx import Document
from httpx import AsyncClient

from app.models.enums import ResumeTemplate, ResumeType
from app.schemas.resume_data import ResumeData
from app.services.export.document import build_document, format_date_range
from app.services.export.docx_builder import render_docx
from app.services.export.html_pdf import render_html, render_pdf
from app.services.export_service import ExportFormat, export_filename

RESUME_DATA = ResumeData.model_validate(
    {
        "personal_info": {
            "full_name": "Ada Lovelace",
            "headline": "Full Stack Developer",
            "email": "ada@example.com",
            "phone": "+1 555 0100",
            "profile_links": [{"label": "GitHub", "url": "github.com/ada"}],
        },
        "summary": "SUMMARYMARK Full stack developer who ships.",
        "experience": [
            {
                "company": "Acme Corp",
                "title": "Software Engineer",
                "start_date": "2022-03",
                "is_current": True,
                "bullets": ["EXPMARK1 Built the billing API", "EXPMARK2 Cut latency by 40%"],
                "tools_and_skills": ["Python", "FastAPI"],
            },
            {
                "company": "Startup Ltd",
                "title": "Junior Developer",
                "start_date": "2020-06",
                "end_date": "2022-02",
            },
        ],
        "education": [
            {
                "institution": "EDUMARK University of London",
                "degree": "BSc",
                "field_of_study": "Computer Science",
                "start_date": "2016-09",
                "end_date": "2020-06",
            }
        ],
        "projects": [{"name": "PROJMARK ResumeForge", "bullets": ["Generates ATS-safe PDFs"]}],
        "skills": [{"name": "SKILLMARK"}, {"name": "TypeScript"}],
        "certifications": [{"name": "CERTMARK AWS Cloud Practitioner", "issue_date": "2023-05"}],
        "achievements": ["ACHMARK 1st place, London Hackathon 2023"],
    }
)

# (heading, a marker from that section's content), in the expected order per document type.
RESUME_ORDER = [
    ("SUMMARY", "SUMMARYMARK"),
    ("SKILLS", "SKILLMARK"),
    ("EXPERIENCE", "EXPMARK2"),
    ("PROJECTS", "PROJMARK"),
    ("EDUCATION", "EDUMARK"),
    ("LICENSES & CERTIFICATIONS", "CERTMARK"),
    ("ACHIEVEMENTS", "ACHMARK"),
]
CV_ORDER = [
    ("SUMMARY", "SUMMARYMARK"),
    ("EDUCATION", "EDUMARK"),
    ("EXPERIENCE", "EXPMARK2"),
    ("PROJECTS", "PROJMARK"),
    ("SKILLS", "SKILLMARK"),
    ("LICENSES & CERTIFICATIONS", "CERTMARK"),
    ("ACHIEVEMENTS", "ACHMARK"),
]


def arranged(data: ResumeData, sections: list[dict[str, Any]]) -> ResumeData:
    """`data` with this section list (ids, kinds, renames, extra entries)."""
    return ResumeData.model_validate(
        {**data.model_dump(exclude={"sections"}), "sections": sections}
    )


def in_order(*kinds: str) -> list[dict[str, Any]]:
    return [{"id": kind, "kind": kind} for kind in kinds]


# How a CV is arranged (education first); migrated CVs got exactly this list.
CV_DATA = arranged(
    RESUME_DATA,
    in_order(
        "summary", "education", "experience", "projects", "skills", "certifications", "achievements"
    ),
)  # fmt: skip


def make_pdf(data: ResumeData, resume_type: ResumeType, template: ResumeTemplate) -> bytes:
    return render_pdf(render_html(build_document(data, resume_type), template, "Test"))


def extract_text(pdf: bytes) -> str:
    with pdfplumber.open(BytesIO(pdf)) as document:
        return "\n".join(page.extract_text() or "" for page in document.pages)


def assert_in_order(text: str, needles: list[str]) -> None:
    # Case-insensitive: some templates capitalise the name or print headings in title case,
    # which is how an ATS reads them too.
    positions = []
    folded = text.casefold()
    for needle in needles:
        assert needle.casefold() in folded, f"{needle!r} missing from extracted text:\n{text}"
        positions.append(folded.index(needle.casefold()))
    assert positions == sorted(positions), f"out of order: {needles}\n{text}"


# --- PDF is machine-readable ----------------------------------------------------


@pytest.mark.parametrize("template", list(ResumeTemplate))
@pytest.mark.parametrize(
    ("resume_type", "data", "order"),
    [(ResumeType.RESUME, RESUME_DATA, RESUME_ORDER), (ResumeType.CV, CV_DATA, CV_ORDER)],
)
def test_pdf_text_extracts_every_section_in_order(
    template: ResumeTemplate,
    resume_type: ResumeType,
    data: ResumeData,
    order: list[tuple[str, str]],
) -> None:
    text = extract_text(make_pdf(data, resume_type, template))

    # Identity first, then each heading immediately followed by its own content.
    assert_in_order(text, ["Ada Lovelace", "Full Stack Developer", "ada@example.com"])
    assert_in_order(text, ["Ada Lovelace"] + [item for pair in order for item in pair])
    # Entries within a section keep their order, and dates read naturally.
    assert_in_order(text, ["Software Engineer, Acme Corp", "EXPMARK1", "EXPMARK2", "Startup Ltd"])
    assert "Mar 2022 – Present" in text
    assert "Jun 2020 – Feb 2022" in text


@pytest.mark.parametrize("template", list(ResumeTemplate))
def test_pdf_has_no_images_and_uses_standard_fonts(template: ResumeTemplate) -> None:
    pdf = make_pdf(RESUME_DATA, ResumeType.RESUME, template)

    with pdfplumber.open(BytesIO(pdf)) as document:
        assert all(page.images == [] for page in document.pages)
        fonts = {c["fontname"].split("+")[-1] for page in document.pages for c in page.chars}
    # Liberation Sans/Serif are the metric-compatible Arial/Times New Roman installed on Linux.
    assert fonts, "no text found: PDF must contain real, selectable text"
    assert all(f.startswith(("Liberation", "Arial", "Times", "Helvetica")) for f in fonts), fonts


def test_pdf_text_stays_in_order_across_page_breaks() -> None:
    long = RESUME_DATA.model_copy(deep=True)
    long.experience = long.experience * 12  # forces several pages
    pdf = make_pdf(long, ResumeType.RESUME, ResumeTemplate.CLASSIC)

    with pdfplumber.open(BytesIO(pdf)) as document:
        assert len(document.pages) > 1
    assert_in_order(extract_text(pdf), [item for pair in RESUME_ORDER for item in pair])


def test_empty_sections_are_left_out() -> None:
    text = extract_text(
        make_pdf(
            ResumeData.model_validate({"personal_info": {"full_name": "Solo"}, "summary": "Hi"}),
            ResumeType.RESUME,
            ResumeTemplate.COMPACT,
        )
    )

    assert "SUMMARY" in text
    assert "EXPERIENCE" not in text
    assert "SKILLS" not in text


def test_user_text_is_html_escaped() -> None:
    data = ResumeData.model_validate({"summary": "<script>alert(1)</script> & <b>bold</b>"})

    html = render_html(build_document(data, ResumeType.RESUME), ResumeTemplate.CLASSIC, "t")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# --- DOCX follows the same structure ----------------------------------------------------


@pytest.mark.parametrize("template", list(ResumeTemplate))
def test_docx_has_same_sections_in_order_and_no_ats_traps(template: ResumeTemplate) -> None:
    content = render_docx(build_document(RESUME_DATA, ResumeType.RESUME), template, "Test")
    document = Document(BytesIO(content))

    text = "\n".join(p.text for p in document.paragraphs)
    # Word stores headings as typed ("Experience"); all-caps is display formatting only.
    needles = [part for heading, marker in RESUME_ORDER for part in (heading.title(), marker)]
    assert_in_order(text, ["Ada Lovelace", *needles])
    headings = [p.text for p in document.paragraphs if p.style.name == "Heading 1"]
    assert headings == [h.title() for h, _ in RESUME_ORDER]
    assert "Software Engineer, Acme Corp\tMar 2022 – Present" in text

    assert document.tables == []
    assert document.inline_shapes._inline_lst == []  # type: ignore[attr-defined]
    for section in document.sections:
        assert all(not p.text for p in section.header.paragraphs)
        assert all(not p.text for p in section.footer.paragraphs)


# --- helpers ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end", "current", "expected"),
    [
        ("2022-03", None, True, "Mar 2022 – Present"),
        ("2020-06", "2022-02", False, "Jun 2020 – Feb 2022"),
        ("2020-06", None, False, "Jun 2020"),
        (None, None, True, "Present"),
        (None, None, False, ""),
    ],
)
def test_date_range_format(
    start: str | None, end: str | None, current: bool, expected: str
) -> None:
    assert format_date_range(start, end, current) == expected


def test_export_filename() -> None:
    assert export_filename("Ada Lovelace", "x", ResumeType.RESUME, ExportFormat.PDF) == (
        "Ada-Lovelace-Resume.pdf"
    )
    assert export_filename("", "My CV!", ResumeType.CV, ExportFormat.DOCX) == "My-CV-CV.docx"
    assert export_filename("Zoë Ñúñez", "x", ResumeType.RESUME, ExportFormat.PDF) == (
        "Zoë-Ñúñez-Resume.pdf"
    )


# --- endpoint --------------------------------------------------------------------------------


async def _signup_with_resume(
    client: AsyncClient, email: str = "exp@example.com"
) -> tuple[dict, str]:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": "password123", "name": "Ada"}
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    created = await client.post(
        "/api/resumes",
        json={"title": "Main", "template": "compact", "data": RESUME_DATA.model_dump(mode="json")},
        headers=headers,
    )
    return headers, created.json()["id"]


async def test_export_pdf_endpoint(client: AsyncClient) -> None:
    headers, resume_id = await _signup_with_resume(client)

    response = await client.get(f"/api/resumes/{resume_id}/export?format=pdf", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="Ada-Lovelace-Resume.pdf"' in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")
    assert "EXPERIENCE" in extract_text(response.content)


async def test_export_docx_endpoint_with_template_override(client: AsyncClient) -> None:
    headers, resume_id = await _signup_with_resume(client)

    response = await client.get(
        f"/api/resumes/{resume_id}/export",
        params={"format": "docx", "template": "classic"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml"
    )
    document = Document(BytesIO(response.content))
    assert document.styles["Normal"].font.name == "Times New Roman"  # classic, not compact


@pytest.mark.parametrize("query", ["format=txt", "template=fancy"])
async def test_export_rejects_unknown_format_or_template(client: AsyncClient, query: str) -> None:
    headers, resume_id = await _signup_with_resume(client)

    response = await client.get(f"/api/resumes/{resume_id}/export?{query}", headers=headers)

    assert response.status_code == 422


async def test_export_is_owner_only(client: AsyncClient) -> None:
    _, resume_id = await _signup_with_resume(client, "owner-exp@example.com")
    intruder, _ = await _signup_with_resume(client, "intruder-exp@example.com")

    response = await client.get(f"/api/resumes/{resume_id}/export", headers=intruder)

    assert response.status_code == 404


# --- sections follow the user's arrangement -----------------------------------------------

NURSE = arranged(
    RESUME_DATA,
    [
        {"id": "summary", "kind": "summary"},
        {"id": "certifications", "kind": "certifications", "title": "Registrations"},
        {
            "id": "clinical_experience",
            "kind": "clinical_experience",
            "entries": [
                {
                    "title": "Student Nurse",
                    "organization": "CLINMARK St Mary's Hospital",
                    "location": "Cardiology ward",
                    "start_date": "2024-01",
                    "end_date": "2024-06",
                    "bullets": ["Monitored vital signs for 8 patients per shift"],
                }
            ],
        },
        {"id": "experience", "kind": "experience"},
        {"id": "education", "kind": "education"},
        {"id": "skills", "kind": "skills", "title": "Key Skills"},
        {
            "id": "languages",
            "kind": "languages",
            "entries": [
                {"title": "LANGMARK Spanish", "organization": "Fluent"},
                {"title": "Welsh"},
            ],
        },
        {
            "id": "custom-a1b2",
            "kind": "custom",
            "title": "Hobbies",
            "entries": [{"title": "HOBMARK"}],
        },
        # Empty sections are listed but don't print.
        {"id": "publications", "kind": "publications"},
    ],
)
NURSE_ORDER = [
    ("SUMMARY", "SUMMARYMARK"),
    ("REGISTRATIONS", "CERTMARK"),
    ("CLINICAL EXPERIENCE", "CLINMARK"),
    ("\nEXPERIENCE\n", "EXPMARK2"),  # its own line, not the end of "CLINICAL EXPERIENCE"
    ("EDUCATION", "EDUMARK"),
    ("KEY SKILLS", "SKILLMARK"),
    ("LANGUAGES", "LANGMARK Spanish (Fluent), Welsh"),
    ("HOBBIES", "HOBMARK"),
    # Not in the list, but has content: never silently dropped.
    ("PROJECTS", "PROJMARK"),
    ("ACHIEVEMENTS", "ACHMARK"),
]


def test_pdf_follows_the_users_order_headings_and_extra_sections() -> None:
    text = extract_text(make_pdf(NURSE, ResumeType.RESUME, ResumeTemplate.CLASSIC))

    assert_in_order(text, [item for pair in NURSE_ORDER for item in pair])
    assert "Student Nurse, CLINMARK St Mary's Hospital" in text
    assert "Jan 2024 – Jun 2024" in text
    assert "PUBLICATIONS" not in text


def test_docx_follows_the_users_order_too() -> None:
    document = Document(
        BytesIO(render_docx(build_document(NURSE, ResumeType.RESUME), "classic", "t"))
    )

    headings = [p.text for p in document.paragraphs if p.style.name == "Heading 1"]
    assert headings == [
        "Summary", "Registrations", "Clinical Experience", "Experience", "Education",
        "Key Skills", "Languages", "Hobbies", "Projects", "Achievements",
    ]  # fmt: skip
