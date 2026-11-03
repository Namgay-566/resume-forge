"""Proofs flow back into the resume: suggestions, project drafts, exports, ATS re-checks."""

import json
import uuid
from io import BytesIO
from typing import Any

import pdfplumber
import pytest
from docx import Document
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ats import JdKeywords, RecruiterReview
from app.ai.client import AIClient, get_ai_client
from app.ai.types import AIRequest, AIResponse
from app.core.config import get_settings
from app.main import app
from app.models import Proof, Skill, User, UserSkill
from app.models.enums import (
    ProofStatus,
    ProofType,
    ResumeType,
    UserSkillSource,
    VerificationStatus,
)
from app.schemas.proof_report import (
    CertificateInfo,
    ProofReport,
    RepoFacts,
    SkillVerdict,
    UrlCheck,
)
from app.schemas.resume_data import ResumeData
from app.schemas.suggestions import ProofLink
from app.services.export.document import build_document
from app.services.export.docx_builder import render_docx
from app.services.export.html_pdf import render_html, render_pdf
from app.services.suggestions.engine import ProofView, SkillView, suggest

GIT_ID, PY_ID, K8S_ID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
REPO_PROOF, CERT_PROOF, SELF_CERT, BAD_CERT = (uuid.uuid4() for _ in range(4))


def repo_facts(**overrides: Any) -> RepoFacts:
    base: dict[str, Any] = dict(
        full_name="ada/tracker",
        url="https://github.com/ada/tracker",
        description="Habit tracker API",
        default_branch="main",
        fork=False,
        stars=0,
        created_at=None,
        pushed_at=None,
        languages={"Python": 100.0},
        commit_count=20,
        commit_days=6,
        contributors=[],
        file_count=10,
        tree_truncated=False,
        has_readme=True,
        has_tests=True,
        has_ci=False,
        has_docker=True,
        key_files=["Dockerfile"],
        sampled_files=["src/app/main.py"],
        readme_excerpt="# Tracker\nA FastAPI + Postgres API used by 300 beta users.",
    )
    return RepoFacts(**{**base, **overrides})


def certificate(level: str, reachable: bool = True, **overrides: Any) -> ProofReport:
    fields: dict[str, Any] = {
        "filename": "c.pdf",
        "content_type": "application/pdf",
        "text_source": "pdf_text",
        "issuer": "Coursera",
        "recipient_name": "Ada Lovelace",
        "course_name": "Python for Everybody",
        "issue_date": "2024-05-02",
        "credential_id": "ABC123",
        "verification_url": "https://coursera.org/verify/ABC123",
        "url_check": UrlCheck(url="https://coursera.org/verify/ABC123", reachable=reachable),
    }
    info = CertificateInfo(**{**fields, **overrides})
    return ProofReport(certificate=info, verification_level=level)  # type: ignore[arg-type]


def views() -> list[ProofView]:
    return [
        ProofView(
            REPO_PROOF,
            ProofType.GITHUB_REPO,
            ProofStatus.VERIFIED,
            "https://github.com/ada/tracker",
            ProofReport(repo=repo_facts(), verification_level="verified"),
            frozenset({GIT_ID}),
            1,
        ),
        ProofView(
            CERT_PROOF,
            ProofType.CERTIFICATE,
            ProofStatus.VERIFIED,
            None,
            certificate("verified"),
            frozenset({PY_ID}),
            2,
        ),
        ProofView(
            SELF_CERT,
            ProofType.CERTIFICATE,
            ProofStatus.NEEDS_MORE,
            None,
            certificate(
                "self_reported",
                reachable=False,
                course_name="Docker Basics",
                credential_id="ZZZ999",
            ),
            frozenset(),
            3,
        ),
        ProofView(
            BAD_CERT,
            ProofType.CERTIFICATE,
            ProofStatus.REJECTED,
            None,
            certificate("self_reported", course_name="Someone else's cert"),
            frozenset(),
            4,
        ),
    ]


VERIFIED = [
    SkillView(GIT_ID, "Git", frozenset({"git", "github"})),
    SkillView(PY_ID, "Python", frozenset({"python"})),
]


# --- suggestions ----------


def test_suggestions_from_verified_proofs() -> None:
    data = ResumeData.model_validate({"skills": [{"name": "python 3.11"}]})

    by_id = {s.id: s for s in suggest(data, views(), VERIFIED)}

    git = by_id[f"skill:{GIT_ID}"]
    assert git.kind == "add_skill" and git.title == "Git is now verified. Add it to Skills?"
    assert git.proof_id == REPO_PROOF
    python = by_id[f"skill:{PY_ID}"]
    assert python.kind == "link_skill_proof"  # already listed (via alias), not yet linked
    assert (python.skill_index, python.resume_skill_name) == (0, "python 3.11")
    assert by_id[f"project:{REPO_PROOF}"].kind == "add_project"
    cert = by_id[f"cert:{CERT_PROOF}"].certification
    assert cert is not None
    assert (cert.name, cert.issuer, cert.issue_date, cert.credential_id) == (
        "Python for Everybody",
        "Coursera",
        "2024-05",
        "ABC123",
    )
    assert (
        cert.credential_url == "https://coursera.org/verify/ABC123" and cert.proof_id == CERT_PROOF
    )
    self_reported = by_id[f"cert:{SELF_CERT}"]
    assert self_reported.level == "self_reported" and "Self-reported" in self_reported.detail
    assert (
        self_reported.certification and self_reported.certification.credential_url is None
    )  # dead link
    assert f"cert:{BAD_CERT}" not in by_id  # rejected proofs are never suggested


def test_nothing_suggested_once_on_the_resume_or_dismissed() -> None:
    data = ResumeData.model_validate(
        {
            "skills": [
                {"name": "Git", "proof_id": str(REPO_PROOF)},
                {"name": "Python", "proof_id": str(CERT_PROOF)},
            ],
            "projects": [{"name": "Tracker", "link": "github.com/ada/tracker"}],
            "certifications": [{"name": "Python for Everybody"}],
        }
    )

    remaining = suggest(data, views(), VERIFIED, dismissed=[f"cert:{SELF_CERT}"])

    assert remaining == []


# --- exports carry proof links as plain text ----------


def links() -> dict[str, ProofLink]:
    return {
        str(REPO_PROOF): ProofLink(
            proof_id=REPO_PROOF,
            type="github_repo",
            url="https://github.com/ada/tracker",
            display_url="github.com/ada/tracker",
            verified=True,
            level="verified",
        ),
        str(CERT_PROOF): ProofLink(
            proof_id=CERT_PROOF,
            type="certificate",
            url="https://coursera.org/verify/ABC123",
            display_url="coursera.org/verify/ABC123",
            verified=True,
            level="verified",
        ),
    }


RESUME = {
    "personal_info": {"full_name": "Ada Lovelace", "email": "ada@example.com"},
    "skills": [
        {"name": "Git", "proof_id": str(REPO_PROOF)},
        {"name": "Python", "proof_id": str(CERT_PROOF)},
        {"name": "SQL"},
    ],
    "projects": [{"name": "Tracker", "proof_id": str(REPO_PROOF), "bullets": ["Built the API"]}],
    "certifications": [
        {
            "name": "Python for Everybody",
            "issuer": "Coursera",
            "credential_id": "ABC123",
            "proof_id": str(CERT_PROOF),
        }
    ],
}


def test_document_cites_proofs_and_verified_line_is_optional() -> None:
    off = build_document(ResumeData.model_validate(RESUME), ResumeType.RESUME, links())
    on = build_document(
        ResumeData.model_validate({**RESUME, "show_verified_skills": True}),
        ResumeType.RESUME,
        links(),
    )

    sections = {s.key: s for s in off.sections}
    assert sections["projects"].entries[0].link == "github.com/ada/tracker"  # filled from proof
    cert = sections["certifications"].entries[0]
    assert cert.link == "coursera.org/verify/ABC123" and cert.description == "Credential ID: ABC123"
    assert sections["skills"].extra == []
    skills_on = next(s for s in on.sections if s.key == "skills")
    assert skills_on.extra == [
        "Verified skills: Git (github.com/ada/tracker), Python (coursera.org/verify/ABC123)"
    ]


def test_pdf_and_docx_contain_proof_urls_as_text() -> None:
    data = ResumeData.model_validate({**RESUME, "show_verified_skills": True})
    doc = build_document(data, ResumeType.RESUME, links())

    pdf = render_pdf(render_html(doc, get_settings_template(), "t"))
    with pdfplumber.open(BytesIO(pdf)) as parsed:
        text = "\n".join(p.extract_text() or "" for p in parsed.pages)
        images = sum(len(p.images) for p in parsed.pages)
    docx_text = "\n".join(
        p.text for p in Document(BytesIO(render_docx(doc, get_settings_template(), "t"))).paragraphs
    )

    for needle in [
        "github.com/ada/tracker",
        "coursera.org/verify/ABC123",
        "Credential ID: ABC123",
        "Verified skills: Git (github.com/ada/tracker)",
    ]:
        assert needle in text, needle
        assert needle in docx_text, needle
    assert images == 0  # still no icons or images


def get_settings_template():  # type: ignore[no-untyped-def]
    from app.models.enums import ResumeTemplate

    return ResumeTemplate.CLASSIC


# --- endpoints ----------


class Provider:
    name, model = "fake", "fake-1"

    def __init__(self, answers: dict[type, Any]) -> None:
        self.answers = answers
        self.requests: list[AIRequest] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        return AIResponse(text=json.dumps(self.answers[request.response_model]), model=self.model)


def use(answers: dict[type, Any]) -> Provider:
    provider = Provider(answers)
    app.dependency_overrides[get_ai_client] = lambda: AIClient(provider)
    return provider


DRAFT = {
    "name": "Habit Tracker",
    "description": "A habit tracking API used by 300 beta users. See https://tracker.dev",
    "bullets": [
        "Built a FastAPI service handling 5,000 requests a day",
        "Containerised the app with Docker",
    ],
    "tools_and_skills": ["Python", "FastAPI", "Docker", "Python"],
}


async def setup(
    client: AsyncClient, db_session: AsyncSession, email: str = "loop@example.com"
) -> tuple[dict[str, str], str, dict[str, Any]]:
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "name": "Ada Lovelace"},
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    user = await db_session.scalar(select(User).where(User.email == email))
    git = Skill(name="Git", slug=f"git-{email}", category="tool", aliases=["git", "github"])
    db_session.add(git)
    await db_session.flush()
    assert user
    repo = Proof(
        user_id=user.id,
        type=ProofType.GITHUB_REPO,
        url="https://github.com/ada/tracker",
        status=ProofStatus.VERIFIED,
        skills=[git],
        ai_report=ProofReport(
            repo=repo_facts(),
            verification_level="verified",
            summary="Solid API.",
            skills=[
                SkillVerdict(
                    skill_id=git.id, name="Git", verdict="demonstrated", evidence=["20 commits"]
                )
            ],
        ),
    )
    pending = Proof(
        user_id=user.id,
        type=ProofType.GITHUB_REPO,
        url="https://github.com/ada/other",
        status=ProofStatus.NEEDS_MORE,
        ai_report=ProofReport(repo=repo_facts(full_name="ada/other")),
    )
    db_session.add_all([repo, pending])
    db_session.add(
        UserSkill(
            user_id=user.id,
            skill_id=git.id,
            source=UserSkillSource.VERIFIED_PROOF,
            verification_status=VerificationStatus.VERIFIED,
        )
    )
    await db_session.commit()
    resume = await client.post(
        "/api/resumes",
        json={"title": "Main", "data": {"personal_info": {"full_name": "Ada Lovelace"}}},
        headers=headers,
    )
    return (
        headers,
        resume.json()["id"],
        {"repo": str(repo.id), "pending": str(pending.id), "git": str(git.id)},
    )


async def test_suggestions_endpoint_and_dismiss(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    use({})
    headers, resume_id, ids = await setup(client, db_session)
    url = f"/api/resumes/{resume_id}/suggestions"

    body = (await client.get(url, headers=headers)).json()

    kinds = {s["id"]: s["kind"] for s in body["suggestions"]}
    assert kinds == {f"skill:{ids['git']}": "add_skill", f"project:{ids['repo']}": "add_project"}
    assert body["proof_links"][ids["repo"]]["display_url"] == "github.com/ada/tracker"
    assert body["proof_links"][ids["repo"]]["verified"] is True
    assert (
        await client.post(f"{url}/skill:{ids['git']}/dismiss", headers=headers)
    ).status_code == 204
    after = (await client.get(url, headers=headers)).json()
    assert [s["id"] for s in after["suggestions"]] == [f"project:{ids['repo']}"]


async def test_project_draft_is_guarded_and_cached(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    provider = use({_draft_model(): DRAFT})
    headers, resume_id, ids = await setup(client, db_session)
    url = f"/api/resumes/{resume_id}/suggestions/project-draft"

    first = await client.post(url, json={"proof_id": ids["repo"]}, headers=headers)
    second = await client.post(url, json={"proof_id": ids["repo"]}, headers=headers)

    assert first.status_code == 200, first.text
    draft = first.json()
    assert draft["link"] == "https://github.com/ada/tracker"  # from the proof, not the model
    assert "300 beta users" in draft["description"]  # the README says 300
    # The link is gone and so is the "See" it left hanging.
    assert draft["description"] == "A habit tracking API used by 300 beta users"
    assert (
        draft["bullets"][0] == "Built a FastAPI service handling [X] requests a day"
    )  # 5,000 invented
    assert draft["tools_and_skills"] == ["Python", "FastAPI", "Docker"]
    assert second.json() == draft and len(provider.requests) == 1
    assert "A FastAPI + Postgres API" in provider.requests[0].prompt  # README excerpt used
    unverified = await client.post(url, json={"proof_id": ids["pending"]}, headers=headers)
    assert unverified.status_code == 404


def _draft_model() -> type:
    from app.ai.project_draft import _Draft

    return _Draft


async def test_export_includes_proof_links(client: AsyncClient, db_session: AsyncSession) -> None:
    use({})
    headers, resume_id, ids = await setup(client, db_session)
    await client.patch(
        f"/api/resumes/{resume_id}",
        json={
            "data": {
                "personal_info": {"full_name": "Ada Lovelace"},
                "show_verified_skills": True,
                "skills": [{"name": "Git", "skill_id": ids["git"], "proof_id": ids["repo"]}],
                "projects": [
                    {"name": "Tracker", "proof_id": ids["repo"], "bullets": ["Built the API"]}
                ],
            }
        },
        headers=headers,
    )

    pdf = await client.get(f"/api/resumes/{resume_id}/export?format=pdf", headers=headers)

    with pdfplumber.open(BytesIO(pdf.content)) as parsed:
        text = "\n".join(p.extract_text() or "" for p in parsed.pages)
    assert "github.com/ada/tracker" in text
    assert "Verified skills: Git (github.com/ada/tracker)" in text


async def test_ats_recheck_is_free_and_reports_the_difference(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = {"overall": "ok", "sections": []}
    provider = use(
        {
            RecruiterReview: review,
            JdKeywords: {
                "keywords": [
                    {"keyword": "Git", "importance": "required"},
                    {"keyword": "Docker", "importance": "required"},
                ]
            },
        }
    )
    headers, resume_id, _ = await setup(client, db_session)
    url = f"/api/resumes/{resume_id}/ats-analyses"
    jd = "We need Git and Docker experience for this backend role."

    before = (await client.post(url, json={"job_description": jd}, headers=headers)).json()
    calls_after_first = len(provider.requests)
    await client.patch(
        f"/api/resumes/{resume_id}",
        json={
            "data": {
                "personal_info": {"full_name": "Ada Lovelace"},
                "skills": [{"name": "Git"}, {"name": "Docker"}],
            }
        },
        headers=headers,
    )
    monkeypatch.setattr(get_settings(), "ai_rate_limit", "0/minute")  # no AI budget left at all
    after = (
        await client.post(url, json={"job_description": jd, "review": False}, headers=headers)
    ).json()

    assert calls_after_first == 2  # JD keywords + review the first time
    assert len(provider.requests) == 2  # re-check: no AI (same JD reuses the keyword list)
    assert after["report"]["ai_status"] == "skipped"
    assert after["previous"]["score"] == before["score"]
    assert after["score"] > before["score"]
    kw_before = next(c["score"] for c in after["previous"]["categories"] if c["key"] == "keywords")
    kw_after = next(c["score"] for c in after["report"]["categories"] if c["key"] == "keywords")
    assert (kw_before, kw_after) == (0, 100)
    latest = (await client.get(f"{url}/latest", headers=headers)).json()
    assert latest["previous"]["score"] == before["score"]
