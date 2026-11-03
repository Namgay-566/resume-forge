"""Proof for every profession: licences, portfolios, work samples, publications and letters.
The levels must never claim more than we could check."""

import io
import json
from datetime import date
from typing import Any

import httpx
import pytest
from docx import Document
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient, get_ai_client
from app.ai.types import AIRequest, AIResponse
from app.db.seed import load_seed_data
from app.main import app
from app.models import Industry, RoleSkill, Skill, TargetRole, UserSkill
from app.models.enums import ProofType, SkillImportance, VerificationStatus
from app.schemas.proof_report import (
    LetterInfo,
    LicenseInfo,
    NameMatch,
    PortfolioInfo,
    PublicationInfo,
    SkillVerdict,
    UrlCheck,
    WorkSampleInfo,
)
from app.services.proofs.certificates import trusted_register
from app.services.proofs.evidence import (
    best_author_match,
    check_expiry,
    decide_letter,
    decide_license,
    decide_portfolio,
    decide_publication,
    decide_work_sample,
    parse_date,
    parse_doi,
    portfolio_platform,
)
from app.services.proofs.rules import get_rules
from app.services.storage.files import get_file_storage
from app.services.web.fetch import FetchResult, get_fetcher
from app.tests.test_proof_extras import FakeFetcher, MemoryStorage, page, text_pdf

TODAY = date(2026, 9, 26)

# --- dates and licences ---------------------------------------------------------------------


def test_parse_date() -> None:
    assert parse_date("2027-03-31") == date(2027, 3, 31)
    assert parse_date("2027-02", end_of_month=True) == date(2027, 2, 28)
    assert parse_date("2027-02") == date(2027, 2, 1)
    assert parse_date("31/03/2027") is None


@pytest.mark.parametrize(
    ("expiry", "expired", "soon"),
    [("2026-09-01", True, False), ("2026-11-30", False, True), ("2029-01", False, False)],
)
def test_licence_expiry(expiry: str, expired: bool, soon: bool) -> None:
    info = LicenseInfo(expiry_date=expiry)

    check_expiry(info, TODAY)

    assert (info.expired, info.expires_soon) == (expired, soon)


def licence(**overrides: Any) -> LicenseInfo:
    base: dict[str, Any] = {
        "license_type": "Registered Nurse",
        "license_number": "12A3456E",
        "issuing_body": "Nursing and Midwifery Council",
        "name_match": NameMatch(status="match", detail="ok"),
    }
    return LicenseInfo(**{**base, **overrides})


def register(**overrides: Any) -> UrlCheck:
    base: dict[str, Any] = {
        "url": "https://www.nmc.org.uk/registration/search-the-register/",
        "reachable": True,
        "on_trusted_domain": True,
        "details_on_page": True,
    }
    return UrlCheck(**{**base, **overrides})


@pytest.mark.parametrize(
    ("info", "level", "rejected"),
    [
        (licence(register_check=register()), "verified", False),
        (licence(register_check=register(details_on_page=False)), "partially_verified", False),
        (licence(register_check=register(on_trusted_domain=False)), "self_reported", False),
        (
            licence(register_check=register(reachable=False, detail="HTTP 404")),
            "self_reported",
            False,
        ),
        (licence(), "self_reported", False),  # no register link: employers can still look it up
        (licence(expired=True, expiry_detail="Expired on 2026-01-01."), None, False),
        (licence(name_match=NameMatch(status="mismatch", detail="Not you.")), None, True),
        (licence(is_license=False), None, True),
    ],
)
def test_licence_levels(info: LicenseInfo, level: str | None, rejected: bool) -> None:
    outcome = decide_license(info)

    assert (outcome.level, outcome.rejected) == (level, rejected)


def test_self_reported_licence_says_how_to_check_it() -> None:
    reason = decide_license(licence()).reason

    assert "12A3456E" in reason and "Nursing and Midwifery Council" in reason


@pytest.mark.parametrize(
    ("url", "body", "trusted"),
    [
        ("https://www.nmc.org.uk/search", "Nursing and Midwifery Council", True),
        ("https://www.bon.texas.gov/verify", "Texas Board of Nursing", True),  # government
        ("https://search.ahpra.gov.au/", "Nursing and Midwifery Board of Australia", True),
        ("https://my-licence-check.xyz/nurse", "Nursing and Midwifery Council", False),
    ],
)
def test_trusted_registers(url: str, body: str, trusted: bool) -> None:
    assert trusted_register(url, body) is trusted


# --- portfolios, work samples, letters --------------------------------------------------------

SHOWN = [
    SkillVerdict(
        skill_id="00000000-0000-0000-0000-000000000001",
        name="Graphic Design",
        verdict="demonstrated",
        evidence=["logo"],
    )
]  # type: ignore[arg-type]  # noqa: E501


def test_a_portfolio_is_never_verified() -> None:
    live = PortfolioInfo(url="https://behance.net/priya", reachable=True, name_on_page=True)

    assert decide_portfolio(live, SHOWN, True, False).level == "partially_verified"
    anonymous = live.model_copy(update={"name_on_page": False})
    assert decide_portfolio(anonymous, SHOWN, True, False).level == "self_reported"
    assert decide_portfolio(live, SHOWN, True, True).level == "self_reported"  # injection
    assert (
        decide_portfolio(live.model_copy(update={"reachable": False}), [], False, False).level
        is None
    )
    assert portfolio_platform("https://www.behance.net/priya") == "Behance"


def test_work_samples_and_letters_are_self_reported() -> None:
    assert decide_work_sample(WorkSampleInfo(kind="a lesson plan"), SHOWN).level == "self_reported"
    assert decide_work_sample(WorkSampleInfo(is_work_sample=False), []).rejected
    letter = LetterInfo(writer_name="Dr Jones", has_contact_details=True)
    outcome = decide_letter(letter)
    assert outcome.level == "self_reported" and "Dr Jones" in outcome.reason
    other = letter.model_copy(update={"name_match": NameMatch(status="mismatch", detail="x.")})
    assert decide_letter(other).rejected


# --- publications ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "doi"),
    [
        ("10.1234/ABC.5", "10.1234/abc.5"),
        ("doi:10.1234/abc", "10.1234/abc"),
        ("https://doi.org/10.1234/abc%2Fdef", "10.1234/abc/def"),
        ("https://journal.example.com/article/42", None),
    ],
)
def test_parse_doi(raw: str, doi: str | None) -> None:
    assert parse_doi(raw) == doi


def test_author_matching() -> None:
    match, author = best_author_match(["Jones, Alan", "Shah, Priya"], "Priya Shah")
    assert match.status == "match" and author == "Shah, Priya"
    assert best_author_match(["Alan Jones"], "Priya Shah")[0].status == "mismatch"


def publication(**overrides: Any) -> PublicationInfo:
    base: dict[str, Any] = {
        "input": "10.1234/abc",
        "doi": "10.1234/abc",
        "source": "crossref",
        "registered": True,
        "author_match": NameMatch(status="match", detail="ok"),
    }
    return PublicationInfo(**{**base, **overrides})


def test_publication_levels() -> None:
    assert decide_publication(publication(), SHOWN).level == "verified"
    page_only = publication(doi=None, source="page", registered=False)
    assert decide_publication(page_only, SHOWN).level == "partially_verified"
    stranger = publication(author_match=NameMatch(status="mismatch", detail="Not listed."))
    assert decide_publication(stranger, []).rejected
    unknown = publication(registered=False, source=None, author_match=None)
    assert decide_publication(unknown, []).level is None


# --- the rules --------------------------------------------------------------------------------


def test_every_seeded_skill_has_proof_types() -> None:
    for skill in load_seed_data().skills:
        assert skill.proof_types, skill.slug
    rules = get_rules()
    assert set(rules.types) == set(ProofType)


def test_seeded_proof_types_fit_the_field() -> None:
    types = {s.slug: s.proof_types[0] for s in load_seed_data().skills}

    assert types["nursing-license"] is ProofType.PROFESSIONAL_LICENSE
    assert types["spreadsheets"] is ProofType.WORK_SAMPLE
    assert types["graphic-design"] is ProofType.PORTFOLIO_LINK
    assert types["react"] is ProofType.GITHUB_REPO
    assert types["teamwork"] is ProofType.REFEREE_CONFIRMATION
    assert types["academic-writing"] is ProofType.PUBLICATION


# --- endpoints ---------------------------------------------------------------------------------


class FieldAI:
    """Answers by response model; records every request."""

    name, model = "fake", "fake-1"

    def __init__(self, answers: dict[str, dict[str, Any]]) -> None:
        self.answers = answers
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        return AIResponse(text=json.dumps(self.answers[request.response_model.__name__]), model="f")


def wire(
    answers: dict[str, dict[str, Any]], pages: dict[str, FetchResult | Exception] | None = None
) -> tuple[FieldAI, FakeFetcher]:
    ai, fetcher, storage = FieldAI(answers), FakeFetcher(pages or {}), MemoryStorage()
    app.dependency_overrides[get_ai_client] = lambda: AIClient(ai)
    app.dependency_overrides[get_fetcher] = lambda: fetcher
    app.dependency_overrides[get_file_storage] = lambda: storage
    return ai, fetcher


@pytest.fixture
async def nursing(db_session: AsyncSession) -> dict[str, Any]:
    health = Industry(
        slug="healthcare",
        name="Healthcare",
        reviewer_persona="a senior nurse and clinical educator",
    )
    skills = {
        "licence": Skill(
            slug="nursing-license",
            name="Nursing License",
            category="license",
            aliases=[],
            proof_types=["professional_license", "certificate"],
        ),  # noqa: E501
        "assessment": Skill(
            slug="patient-assessment", name="Patient Assessment", category="clinical", aliases=[]
        ),  # noqa: E501
        "writing": Skill(
            slug="academic-writing", name="Academic Writing", category="practice", aliases=[]
        ),  # noqa: E501
        "teamwork": Skill(slug="teamwork", name="Teamwork", category="soft_skill", aliases=[]),
    }
    role = TargetRole(
        name="Registered Nurse", slug="registered-nurse", seniority="mid", industry=health
    )
    db_session.add_all([health, role, *skills.values()])
    await db_session.flush()
    db_session.add(
        RoleSkill(
            role_id=role.id,
            skill_id=skills["licence"].id,
            importance=SkillImportance.CRITICAL,
            weight=9,
        )
    )
    await db_session.commit()
    return {"role": role, **skills}


async def signup(
    client: AsyncClient, db_session: AsyncSession, role: TargetRole | None = None
) -> dict[str, str]:
    response = await client.post(
        "/api/auth/register",
        json={"email": "priya@example.com", "password": "password123", "name": "Priya Shah"},
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    if role is not None:
        await client.post(
            "/api/resumes", json={"title": "CV", "target_role_id": str(role.id)}, headers=headers
        )
    return headers


async def upload(
    client: AsyncClient,
    headers: dict[str, str],
    proof_type: str,
    data: bytes,
    content_type: str = "application/pdf",
    name: str = "file.pdf",
    **form: Any,
) -> httpx.Response:
    return await client.post(
        "/api/proofs/upload",
        files={"file": (name, data, content_type)},
        data={"type": proof_type, **form},
        headers=headers,
    )


async def detail(
    client: AsyncClient, headers: dict[str, str], response: httpx.Response
) -> dict[str, Any]:
    assert response.status_code == 202, response.text
    return (await client.get(f"/api/proofs/{response.json()['id']}", headers=headers)).json()


async def verification(db_session: AsyncSession, skill: Skill) -> VerificationStatus | None:
    # The analysis ran in another session: read the column fresh.
    return await db_session.scalar(
        select(UserSkill.verification_status).where(UserSkill.skill_id == skill.id)
    )


LICENCE_PDF = text_pdf(
    "<h1>Nursing and Midwifery Council</h1><p>Registered Nurse (Adult)</p>"
    "<p>Priya Shah</p><p>PIN 12A3456E</p><p>Renewal due 2029-01-31</p>"
)
LICENCE = {
    "is_license": True,
    "license_type": "Registered Nurse (Adult)",
    "holder_name": "Priya Shah",
    "license_number": "12A3456E",
    "issuing_body": "Nursing and Midwifery Council",
    "jurisdiction": "United Kingdom",
    "expiry_date": "2029-01-31",
    "register_url": None,
    "skills": ["Nursing License"],
}
REGISTER = "https://www.nmc.org.uk/register/12A3456E"


async def test_licence_confirmed_on_the_public_register_is_verified(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    wire(
        {"LicenseFields": LICENCE},
        {REGISTER: page(REGISTER, "<p>Priya Shah</p><p>12A3456E: registered</p>")},
    )
    headers = await signup(client, db_session)

    body = await detail(
        client,
        headers,
        await upload(client, headers, "professional_license", LICENCE_PDF, register_url=REGISTER),
    )

    assert body["type"] == "professional_license"
    assert body["status"] == "verified" and body["verification_level"] == "verified"
    info = body["report"]["license"]
    assert info["license_number"] == "12A3456E" and info["register_source"] == "user"
    assert info["expiry_detail"] == "Valid until 2029-01-31."
    assert await verification(db_session, nursing["licence"]) is VerificationStatus.VERIFIED
    assert body["file_name"] == "file.pdf"


async def test_expired_licence_is_flagged_and_verifies_nothing(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    wire(
        {"LicenseFields": {**LICENCE, "expiry_date": "2025-01-31"}},
        {REGISTER: page(REGISTER, "12A3456E")},
    )
    headers = await signup(client, db_session)

    body = await detail(
        client,
        headers,
        await upload(client, headers, "professional_license", LICENCE_PDF, register_url=REGISTER),
    )

    assert body["status"] == "needs_more" and body["verification_level"] is None
    assert body["report"]["license"]["expired"] is True
    assert "expired" in body["decision"]
    assert await verification(db_session, nursing["licence"]) is not VerificationStatus.VERIFIED


async def test_licence_without_register_link_is_self_reported(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    ai, fetcher = wire({"LicenseFields": {**LICENCE, "license_number": "INVENTED999"}})
    headers = await signup(client, db_session)

    body = await detail(
        client, headers, await upload(client, headers, "professional_license", LICENCE_PDF)
    )

    assert body["verification_level"] == "self_reported"
    # A number that isn't on the page is dropped, not trusted.
    assert body["report"]["license"]["license_number"] is None
    assert fetcher.urls == []


REVIEW = {
    "is_relevant": True,
    "kind": "a falls-prevention care plan",
    "summary": "A thorough, person-centred care plan.",
    "skills": [
        {"skill": "Patient Assessment", "verdict": "demonstrated", "evidence": ["Morse scale"]}
    ],
    "strengths": ["Clear risk scoring"],
    "red_flags": [],
    "suggestions": ["Add review dates"],
    "score": 82,
}


def docx_bytes(text: str) -> bytes:
    document = Document()
    for line in text.split("\n"):
        document.add_paragraph(line)
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def test_work_sample_is_reviewed_by_a_professional_in_the_field(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    ai, _ = wire({"EvidenceReview": REVIEW})
    headers = await signup(client, db_session, nursing["role"])

    response = await upload(
        client, headers, "work_sample",
        docx_bytes("Falls care plan\nMorse Fall Scale score 55: high risk\nHourly rounding"),
        DOCX, "care-plan.docx", skill_ids=[str(nursing["assessment"].id)],
    )  # fmt: skip
    body = await detail(client, headers, response)

    assert body["verification_level"] == "self_reported" and body["status"] == "needs_more"
    assert "can't confirm you produced it" in body["decision"]
    assert body["report"]["reviewer"] == "a senior nurse and clinical educator"
    assert body["report"]["work_sample"]["kind"] == "a falls-prevention care plan"
    request = ai.requests[0]
    assert request.system and request.system.startswith(
        "You are a senior nurse and clinical educator."
    )
    assert (
        "Target role: Registered Nurse" in request.prompt and "Field: Healthcare" in request.prompt
    )
    assert "Morse Fall Scale" in request.prompt
    # Self-reported evidence never verifies the skill.
    assert await verification(db_session, nursing["assessment"]) is not VerificationStatus.VERIFIED


PORTFOLIO = "https://www.behance.net/priyashah"


async def test_portfolio_is_at_most_partially_verified(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    html = (
        "<title>Priya Shah | Patient education leaflets</title><p>"
        + "Leaflet design. " * 30
        + "</p>"
    )
    wire({"EvidenceReview": REVIEW}, {PORTFOLIO: page(PORTFOLIO, html)})
    headers = await signup(client, db_session)

    response = await client.post(
        "/api/proofs",
        json={
            "type": "portfolio_link",
            "url": PORTFOLIO,
            "skill_ids": [str(nursing["assessment"].id)],
        },
        headers=headers,
    )
    body = await detail(client, headers, response)

    assert body["verification_level"] == "partially_verified" and body["status"] == "needs_more"
    assert body["report"]["portfolio"]["platform"] == "Behance"
    assert body["report"]["portfolio"]["name_on_page"] is True
    assert await verification(db_session, nursing["assessment"]) is not VerificationStatus.VERIFIED


CROSSREF = "https://api.crossref.org/works/10.1234/falls.2024"


def crossref(authors: list[dict[str, str]]) -> FetchResult:
    body = {
        "message": {
            "title": ["Hourly rounding and falls in older inpatients"],
            "container-title": ["Journal of Clinical Nursing"],
            "published": {"date-parts": [[2024, 3]]},
            "author": authors,
            "abstract": "<jats:p>We used structured patient assessment...</jats:p>",
        }
    }
    return FetchResult(
        url=CROSSREF,
        final_url=CROSSREF,
        status_code=200,
        content_type="application/json",
        text=json.dumps(body),
        elapsed_ms=10,
    )  # noqa: E501


async def test_publication_with_doi_and_author_match_is_verified(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    review = {
        **REVIEW,
        "skills": [
            {"skill": "Academic Writing", "verdict": "demonstrated", "evidence": ["peer-reviewed"]}
        ],
    }
    wire(
        {"EvidenceReview": review},
        {
            CROSSREF: crossref(
                [{"given": "Alan", "family": "Jones"}, {"given": "Priya", "family": "Shah"}]
            )
        },
    )
    headers = await signup(client, db_session)

    response = await client.post(
        "/api/proofs",
        json={
            "type": "publication",
            "url": "doi:10.1234/FALLS.2024",
            "skill_ids": [str(nursing["writing"].id)],
        },
        headers=headers,
    )
    body = await detail(client, headers, response)

    assert body["url"] == "https://doi.org/10.1234/falls.2024"
    assert body["status"] == "verified" and body["verification_level"] == "verified"
    info = body["report"]["publication"]
    assert info["matched_author"] == "Priya Shah" and info["venue"] == "Journal of Clinical Nursing"
    assert await verification(db_session, nursing["writing"]) is VerificationStatus.VERIFIED


async def test_publication_by_someone_else_is_rejected(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    ai, _ = wire(
        {"EvidenceReview": REVIEW}, {CROSSREF: crossref([{"given": "Alan", "family": "Jones"}])}
    )
    headers = await signup(client, db_session)

    response = await client.post(
        "/api/proofs",
        json={
            "type": "publication",
            "url": "10.1234/falls.2024",
            "skill_ids": [str(nursing["writing"].id)],
        },
        headers=headers,
    )
    body = await detail(client, headers, response)

    assert body["status"] == "rejected" and "Alan Jones" in body["decision"]
    assert ai.requests == []  # no review for someone else's paper


LETTER_TEXT = (
    "To whom it may concern,\nI managed Priya Shah on Ward 7 for two years. She works "
    "brilliantly as part of a team, and her patient assessment is thorough.\n"
    "Dr Alan Jones, Ward Manager, St Mary's Hospital. alan.jones@example.org"
)
LETTER = {
    "is_letter": True,
    "letter_kind": "reference",
    "writer_name": "Dr Alan Jones",
    "writer_title": "Ward Manager",
    "organization": "St Mary's Hospital",
    "subject_name": "Priya Shah",
    "relationship": "line manager for two years",
    "has_contact_details": True,
    "skills": [
        {"skill": "Teamwork", "quote": "She works brilliantly as part of a team"},
        {"skill": "Patient Assessment", "quote": "her patient assessment is thorough"},
        {"skill": "Nursing License", "quote": "holds a valid PIN"},  # not in the letter
    ],
}


async def test_reference_letter_is_self_reported_with_the_skills_it_mentions(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    wire({"LetterFields": LETTER})
    headers = await signup(client, db_session)

    body = await detail(
        client,
        headers,
        await upload(
            client, headers, "reference_letter", docx_bytes(LETTER_TEXT), DOCX, "ref.docx"
        ),
    )

    assert body["verification_level"] == "self_reported"
    info = body["report"]["letter"]
    assert info["writer_name"] == "Dr Alan Jones" and info["has_contact_details"] is True
    # A quote that isn't in the letter is dropped.
    assert [m["name"] for m in info["skills_mentioned"]] == ["Teamwork", "Patient Assessment"]
    assert {s["name"] for s in body["skills"]} == {"Teamwork", "Patient Assessment"}
    assert await verification(db_session, nursing["teamwork"]) is None


async def test_letter_about_someone_else_is_rejected(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    wire({"LetterFields": {**LETTER, "subject_name": "Maria Lopez"}})
    headers = await signup(client, db_session)
    text = LETTER_TEXT.replace("Priya Shah", "Maria Lopez")

    body = await detail(
        client,
        headers,
        await upload(client, headers, "experience_letter", docx_bytes(text), DOCX, "l.docx"),
    )

    assert body["status"] == "rejected" and "Maria Lopez" in body["decision"]


async def test_upload_validation(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    wire({})
    headers = await signup(client, db_session)
    doc = docx_bytes("A lesson plan\n" * 10)

    no_skills = await upload(client, headers, "work_sample", doc, DOCX, "plan.docx")
    docx_licence = await upload(client, headers, "professional_license", doc, DOCX, "licence.docx")
    stray_link = await upload(
        client, headers, "work_sample", doc, DOCX, "plan.docx",
        skill_ids=[str(nursing["assessment"].id)], register_url="https://nmc.org.uk",
    )  # fmt: skip
    bad_type = await upload(client, headers, "github_repo", doc, DOCX, "plan.docx")

    assert no_skills.status_code == 422 and "at least one skill" in no_skills.json()["detail"]
    assert docx_licence.status_code == 415
    assert stray_link.status_code == 422
    assert bad_type.status_code == 422


async def test_skill_gap_suggests_the_right_proof(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    wire({})
    headers = await signup(client, db_session, nursing["role"])
    resume_id = (await client.get("/api/resumes", headers=headers)).json()[0]["id"]

    report = (await client.get(f"/api/resumes/{resume_id}/skill-gap", headers=headers)).json()

    licence = next(s for s in report["skills"] if s["slug"] == "nursing-license")
    assert licence["proof_types"] == ["professional_license", "certificate"]


async def test_verified_licence_is_suggested_for_the_resume(
    client: AsyncClient, db_session: AsyncSession, nursing: dict[str, Any]
) -> None:
    wire({"LicenseFields": LICENCE}, {REGISTER: page(REGISTER, "<p>Priya Shah 12A3456E</p>")})
    headers = await signup(client, db_session, nursing["role"])
    await detail(
        client,
        headers,
        await upload(client, headers, "professional_license", LICENCE_PDF, register_url=REGISTER),
    )
    resume_id = (await client.get("/api/resumes", headers=headers)).json()[0]["id"]

    suggestions = (
        await client.get(f"/api/resumes/{resume_id}/suggestions", headers=headers)
    ).json()

    cert = next(s for s in suggestions["suggestions"] if s["kind"] == "add_certification")
    assert cert["certification"]["credential_id"] == "12A3456E"
    assert cert["certification"]["issuer"] == "Nursing and Midwifery Council"
    assert cert["level"] == "verified"
