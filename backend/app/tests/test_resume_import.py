import json
from io import BytesIO

import pytest
from docx import Document
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.ai.client import AIClient, get_ai_client
from app.ai.errors import AIUnavailableError
from app.ai.resume_parser import ParsedResume, to_resume_data
from app.main import app
from app.models import Skill, User, UserSkill
from app.models.enums import UserSkillSource, VerificationStatus
from app.services.resume_import.extract import (
    MAX_UPLOAD_BYTES,
    FileKind,
    ScannedPdfError,
    UnreadableDocumentError,
    UnsupportedFileError,
    detect_kind,
    extract_text,
)
from app.services.resume_import.matching import term_variants
from app.tests.fakes import FakeProvider

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

PARSED = {
    "document_type": "resume",
    "personal_info": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
    "summary": "Backend developer.",
    "experience": [
        {
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2022-03",
            "is_current": True,
            "bullets": ["Built APIs"],
            "tools_and_skills": ["PostgreSQL", "Docker", "FastAPI"],
        }
    ],
    "skills": ["Python 3.11", "GitHub", "js", "Quantum Knitting"],
}


# --- sample files ---------------------------------------------------------------------


def text_pdf(
    text: str = "Ada Lovelace\nSoftware Engineer at Acme since 2022. Python, SQL.",
) -> bytes:
    body = "".join(f"<p>{line}</p>" for line in text.splitlines())
    return HTML(string=f"<html><body>{body}</body></html>").write_pdf()  # type: ignore[return-value]


def scanned_pdf() -> bytes:
    """An image-only PDF, like a scan: a picture of text but no text layer."""
    png = (  # 1x1 grey pixel, stretched to page size
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGA"
        "WjR9awAAAABJRU5ErkJggg=="
    )
    html = f'<img src="data:image/png;base64,{png}" style="width:500px;height:700px">'
    return HTML(string=html).write_pdf()  # type: ignore[return-value]


def docx_file() -> bytes:
    document = Document()
    document.sections[0].header.paragraphs[0].text = "ada@example.com | +1 555 0100"
    document.add_paragraph("Ada Lovelace")
    document.add_paragraph("Experience: Engineer at Acme, building payment APIs since 2022.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Skills"
    table.cell(0, 1).text = "Python, PostgreSQL, Docker"
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


# --- normalisation into ResumeData ------------------------------------------------------------


def test_to_resume_data_normalises_messy_ai_output() -> None:
    parsed = ParsedResume.model_validate(
        {
            "personal_info": {"full_name": "  Ada  ", "email": "not an email", "phone": "1" * 60},
            "experience": [
                {
                    "company": "Acme",
                    "start_date": "2021",
                    "end_date": "2019-05",  # before start: dropped
                    "bullets": ["• Built APIs", "  ", "- Cut costs"],
                },
                {
                    "title": "Lead",
                    "start_date": "March 2020",
                    "end_date": "2022-13",
                    "is_current": True,
                },
                {"company": " ", "title": ""},  # empty: dropped
            ],
            "skills": ["Python", "python", " ", "SQL"],
            "summary": "x" * 5000,
        }
    )

    data = to_resume_data(parsed)

    assert data.personal_info.full_name == "Ada"
    assert data.personal_info.email is None
    assert len(data.personal_info.phone or "") == 40
    assert len(data.experience) == 2
    first, second = data.experience
    assert (first.start_date, first.end_date) == ("2021-01", None)
    assert first.bullets == ["Built APIs", "Cut costs"]
    assert (second.start_date, second.end_date, second.is_current) == (None, None, True)
    assert [s.name for s in data.skills] == ["Python", "SQL"]
    assert len(data.summary) == 2000


def test_term_variants_strip_versions() -> None:
    assert term_variants(" Python 3.11 ") == ["python 3.11", "python"]
    assert term_variants("React.js") == ["react.js"]


# --- file validation and text extraction ---------------------------------------------------------


def test_extracts_text_from_pdf() -> None:
    assert "Software Engineer at Acme" in extract_text(FileKind.PDF, text_pdf())


def test_scanned_pdf_gets_a_clear_error() -> None:
    with pytest.raises(ScannedPdfError, match="text-based PDF .* or a .docx"):
        extract_text(FileKind.PDF, scanned_pdf())


def test_extracts_docx_body_tables_and_header() -> None:
    text = extract_text(FileKind.DOCX, docx_file())

    assert "ada@example.com" in text  # from the page header
    assert "Python, PostgreSQL, Docker" in text  # from a table
    assert text.index("Ada Lovelace") < text.index("Python, PostgreSQL")


def test_corrupt_pdf_is_unreadable() -> None:
    with pytest.raises(UnreadableDocumentError):
        extract_text(FileKind.PDF, b"%PDF-1.7\ngarbage garbage garbage")


@pytest.mark.parametrize(
    ("content_type", "content"),
    [
        ("text/plain", b"just some text"),
        (PDF, b"PK\x03\x04 not really a pdf"),  # declared PDF, actually something else
        (DOCX, b"%PDF-1.7 pretending"),  # declared DOCX, actually a PDF
        ("image/png", b"%PDF-1.7"),  # PDF bytes with a wrong declared type
    ],
)
def test_detect_kind_rejects_mismatched_files(content_type: str, content: bytes) -> None:
    with pytest.raises(UnsupportedFileError):
        detect_kind(content_type, content)


def test_detect_kind_accepts_generic_mime_when_signature_matches() -> None:
    assert detect_kind("application/octet-stream", text_pdf()) is FileKind.PDF
    assert detect_kind(DOCX, docx_file()) is FileKind.DOCX


# --- endpoint ----------------------------------------------------------------------------------


@pytest.fixture
async def catalog(db_session: AsyncSession) -> dict[str, Skill]:
    skills = {
        "python": Skill(name="Python", slug="python", category="language", aliases=["python"]),
        "git": Skill(name="Git", slug="git", category="tool", aliases=["git", "github"]),
        "javascript": Skill(
            name="JavaScript", slug="javascript", category="language", aliases=["javascript", "js"]
        ),
        "sql": Skill(name="SQL", slug="sql", category="database", aliases=["sql", "postgresql"]),
        "docker": Skill(name="Docker", slug="docker", category="tool", aliases=["docker"]),
        # Same alias on two skills, as in the seed data.
        "backend": Skill(
            name="Backend Framework",
            slug="backend-framework",
            category="framework",
            aliases=["backend framework", "fastapi"],
        ),
        "pyweb": Skill(
            name="Python Web Framework",
            slug="python-web-framework",
            category="framework",
            aliases=["python web framework", "fastapi"],
        ),
    }
    db_session.add_all(skills.values())
    await db_session.commit()
    return skills


@pytest.fixture
def fake_ai() -> FakeProvider:
    provider = FakeProvider(json.dumps(PARSED))
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)
    return provider


async def signup(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/auth/register",
        json={"email": "importer@example.com", "password": "password123", "name": "Importer"},
    )
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def upload(
    client: AsyncClient, headers: dict[str, str], content: bytes, content_type: str, name: str
) -> object:
    return await client.post(
        "/api/resumes/import", files={"file": (name, content, content_type)}, headers=headers
    )


async def test_import_creates_resume_and_unverified_user_skills(
    client: AsyncClient,
    db_session: AsyncSession,
    catalog: dict[str, Skill],
    fake_ai: FakeProvider,
) -> None:
    headers = await signup(client)

    response = await upload(client, headers, docx_file(), DOCX, "Ada CV 2024.docx")

    assert response.status_code == 201, response.text  # type: ignore[attr-defined]
    body = response.json()  # type: ignore[attr-defined]
    assert body["resume"]["title"] == "Ada CV 2024"
    assert body["resume"]["data"]["experience"][0]["company"] == "Acme"
    # Skills section + job tech matched via names and aliases ("js", "GitHub", "Python 3.11").
    assert body["matched_skills"] == [
        "Backend Framework",  # FastAPI counts for both framework skills
        "Docker",
        "Git",
        "JavaScript",
        "Python",
        "Python Web Framework",
        "SQL",
    ]
    assert body["unmatched_skills"] == ["Quantum Knitting"]
    skills = {s["name"]: s["skill_id"] for s in body["resume"]["data"]["skills"]}
    assert skills["GitHub"] == str(catalog["git"].id)
    assert skills["Quantum Knitting"] is None
    # The document text reached the AI.
    assert "Python, PostgreSQL, Docker" in fake_ai.prompts[0]

    rows = (await db_session.scalars(select(UserSkill))).all()
    assert len(rows) == 7
    assert {r.source for r in rows} == {UserSkillSource.RESUME}
    assert {r.verification_status for r in rows} == {VerificationStatus.UNVERIFIED}


async def test_import_keeps_already_verified_skills(
    client: AsyncClient,
    db_session: AsyncSession,
    catalog: dict[str, Skill],
    fake_ai: FakeProvider,
) -> None:
    headers = await signup(client)
    user = await db_session.scalar(select(User).where(User.email == "importer@example.com"))
    assert user is not None
    db_session.add(
        UserSkill(
            user_id=user.id,
            skill_id=catalog["python"].id,
            source=UserSkillSource.VERIFIED_PROOF,
            verification_status=VerificationStatus.VERIFIED,
        )
    )
    await db_session.commit()

    response = await upload(client, headers, text_pdf(), PDF, "resume.pdf")

    assert response.status_code == 201  # type: ignore[attr-defined]
    python_row = await db_session.scalar(
        select(UserSkill)
        .where(UserSkill.skill_id == catalog["python"].id)
        .execution_options(populate_existing=True)
    )
    assert python_row is not None
    assert python_row.verification_status is VerificationStatus.VERIFIED


async def test_import_rejects_scanned_pdf_with_helpful_message(
    client: AsyncClient, fake_ai: FakeProvider
) -> None:
    headers = await signup(client)

    response = await upload(client, headers, scanned_pdf(), PDF, "scan.pdf")

    assert response.status_code == 422  # type: ignore[attr-defined]
    assert "text-based PDF" in response.json()["detail"]  # type: ignore[attr-defined]
    assert fake_ai.prompts == []  # never sent to the AI


async def test_import_rejects_wrong_type_and_oversized_files(
    client: AsyncClient, fake_ai: FakeProvider
) -> None:
    headers = await signup(client)

    wrong = await upload(client, headers, b"hello", "text/plain", "notes.txt")
    big = await upload(client, headers, b"%PDF-" + b"0" * MAX_UPLOAD_BYTES, PDF, "big.pdf")

    assert wrong.status_code == 415  # type: ignore[attr-defined]
    assert big.status_code == 413  # type: ignore[attr-defined]


async def test_import_reports_ai_outage_as_503(client: AsyncClient) -> None:
    headers = await signup(client)
    provider = FakeProvider(AIUnavailableError("no key"))
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)

    response = await upload(client, headers, docx_file(), DOCX, "cv.docx")

    assert response.status_code == 503  # type: ignore[attr-defined]


async def test_import_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/resumes/import", files={"file": ("a.pdf", b"%PDF-", PDF)})

    assert response.status_code == 401
