"""Employer email check (a 6-digit code to a work address) and the verification method
shown on every badge."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import app
from app.models import EmploymentEmailCheck
from app.models.enums import ProofType
from app.schemas.proof_report import ProofReport, PublicationInfo
from app.services.email.sender import MemoryEmailSender, get_email_sender
from app.services.proofs.methods import method_label
from app.services.verification.email_domains import classify, domain_matches_organization

CODE = re.compile(r"\b(\d{6})\b")


@pytest.fixture
def outbox() -> MemoryEmailSender:
    sender = MemoryEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    return sender


async def signup(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/auth/register",
        json={"email": "jo@example.com", "password": "password123", "name": "Jo Park"},
    )
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def start(client: AsyncClient, headers: dict[str, str], **body: Any) -> Any:
    payload = {"company": "Harbor Outfitters", "email": "jo.park@harboroutfitters.com", **body}
    return await client.post("/api/employment-checks", json=payload, headers=headers)


def code_in(outbox: MemoryEmailSender) -> str:
    match = CODE.search(outbox.outbox[-1].text)
    assert match
    return match.group(1)


async def test_work_email_code_verifies_employment(
    client: AsyncClient, outbox: MemoryEmailSender
) -> None:
    headers = await signup(client)

    started = await start(client, headers)

    assert started.status_code == 201, started.text
    check = started.json()
    assert check["verified"] is False
    assert check["email_masked"] == "j•••@harboroutfitters.com"
    assert check["domain_matches_company"] is True
    assert outbox.outbox[0].to == "jo.park@harboroutfitters.com"
    assert "confirm you work at Harbor Outfitters" in outbox.outbox[0].text

    confirmed = await client.post(
        f"/api/employment-checks/{check['id']}/confirm",
        json={"code": code_in(outbox)},
        headers=headers,
    )

    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["verified"] is True and confirmed.json()["code_expires_at"] is None
    listed = (await client.get("/api/employment-checks", headers=headers)).json()
    assert [(c["company"], c["verified"]) for c in listed] == [("Harbor Outfitters", True)]


@pytest.mark.parametrize(
    "email", ["jo.park@gmail.com", "jo@outlook.com", "jo@mail.yahoo.co.uk", "x@mailinator.com"]
)
async def test_personal_addresses_cannot_prove_employment(
    client: AsyncClient, outbox: MemoryEmailSender, email: str
) -> None:
    headers = await signup(client)

    response = await start(client, headers, email=email)

    assert response.status_code == 422
    assert "work email at Harbor Outfitters" in response.json()["detail"]
    assert outbox.outbox == []


async def test_wrong_codes_are_limited(client: AsyncClient, outbox: MemoryEmailSender) -> None:
    headers = await signup(client)
    check = (await start(client, headers)).json()
    right = code_in(outbox)
    wrong = "000000" if right != "000000" else "111111"
    url = f"/api/employment-checks/{check['id']}/confirm"

    details = [
        (await client.post(url, json={"code": wrong}, headers=headers)).json()["detail"]
        for _ in range(5)
    ]
    locked = await client.post(url, json={"code": right}, headers=headers)

    assert details[0] == "That code isn't right. 4 tries left."
    assert details[3] == "That code isn't right. 1 try left."
    assert details[4] == "Too many wrong codes. Send a new one."
    assert locked.status_code == 422  # even the right code, once locked


async def test_codes_expire_and_resends_wait_a_minute(
    client: AsyncClient, db_session: AsyncSession, outbox: MemoryEmailSender
) -> None:
    headers = await signup(client)
    check = (await start(client, headers)).json()
    code = code_in(outbox)

    soon = await client.post(f"/api/employment-checks/{check['id']}/resend", headers=headers)
    assert soon.status_code == 422 and "Wait a minute" in soon.json()["detail"]

    past = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.execute(update(EmploymentEmailCheck).values(code_expires_at=past))
    await db_session.commit()
    expired = await client.post(
        f"/api/employment-checks/{check['id']}/confirm", json={"code": code}, headers=headers
    )
    assert expired.status_code == 422 and "expired" in expired.json()["detail"]


async def test_codes_to_one_address_are_capped_per_day(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    outbox: MemoryEmailSender,
) -> None:
    monkeypatch.setattr(get_settings(), "employment_code_rate_limit", "50/hour")  # the DB cap
    headers = await signup(client)
    codes = []
    for i in range(6):
        await db_session.execute(
            update(EmploymentEmailCheck).values(
                last_sent_at=datetime.now(UTC) - timedelta(minutes=2)
            )
        )
        await db_session.commit()
        # A different company each time, same address: still one inbox being emailed.
        codes.append((await start(client, headers, company=f"Harbor Outfitters {i}")).status_code)

    assert codes == [201, 201, 201, 201, 201, 422]


async def test_code_requests_are_rate_limited(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, outbox: MemoryEmailSender
) -> None:
    monkeypatch.setattr(get_settings(), "employment_code_rate_limit", "2/hour")
    headers = await signup(client)

    codes = [
        (await start(client, headers, email=f"jo{i}@harboroutfitters.com")).status_code
        for i in range(3)
    ]

    assert codes == [201, 201, 429]


async def test_the_code_is_not_stored_as_a_plain_hash(
    client: AsyncClient, db_session: AsyncSession, outbox: MemoryEmailSender
) -> None:
    import hashlib

    headers = await signup(client)
    await start(client, headers)
    code = code_in(outbox)

    stored = await db_session.scalar(select(EmploymentEmailCheck))

    assert stored is not None and stored.code_hash
    assert stored.code_hash != hashlib.sha256(code.encode()).hexdigest()
    assert code not in stored.code_hash


async def test_checks_belong_to_their_owner(client: AsyncClient, outbox: MemoryEmailSender) -> None:
    headers = await signup(client)
    check = (await start(client, headers)).json()
    other = await client.post(
        "/api/auth/register",
        json={"email": "eve@example.com", "password": "password123", "name": "Eve"},
    )
    client.cookies.clear()
    eve = {"Authorization": f"Bearer {other.json()['access_token']}"}

    stolen = await client.post(
        f"/api/employment-checks/{check['id']}/confirm", json={"code": "123456"}, headers=eve
    )

    assert stolen.status_code == 404
    assert (await client.get("/api/employment-checks", headers=eve)).json() == []


# --- email domains ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "kind"),
    [
        ("a@gmail.com", "free"),
        ("a@hotmail.co.uk", "free"),
        ("a@proton.me", "free"),
        ("a@stmarys.nhs.uk", "company"),
        ("a@oakfield.sch.uk", "company"),
        ("a@yopmail.com", "disposable"),
    ],
)
def test_email_domain_kinds(email: str, kind: str) -> None:
    assert classify(email) == kind


def test_domain_hint_matches_distinctive_words() -> None:
    assert domain_matches_organization("a@stmarys.nhs.uk", "St Mary's Hospital")
    assert domain_matches_organization("a@harboroutfitters.com", "Harbor Outfitters")
    assert domain_matches_organization("a@oakfield.sch.uk", "Oakfield Primary School")
    assert not domain_matches_organization("a@acme.com", "Oakfield Primary School")
    assert not domain_matches_organization("a@school.org", "The School")


# --- the method on every badge --------------------------------------------------------------


@pytest.mark.parametrize(
    ("proof_type", "level", "label"),
    [
        (ProofType.REFEREE_CONFIRMATION, "verified", "Verified by referee"),
        (ProofType.GITHUB_REPO, "verified", "Verified via GitHub"),
        (ProofType.GITHUB_REPO, "partially_verified", "Partly verified via GitHub"),
        (ProofType.CERTIFICATE, "verified", "Verified on the issuer's site"),
        (ProofType.PROFESSIONAL_LICENSE, "verified", "Verified on the public register"),
        (ProofType.PUBLICATION, "verified", "Verified via the DOI registry"),
        (ProofType.PORTFOLIO_LINK, "partially_verified", "Partly verified via the portfolio page"),
        (ProofType.WORK_SAMPLE, "self_reported", "Self-reported"),
        (ProofType.REFERENCE_LETTER, "self_reported", "Self-reported"),
        (ProofType.CERTIFICATE, None, None),
    ],
)
def test_method_labels(proof_type: ProofType, level: Any, label: str | None) -> None:
    assert method_label(proof_type, level, ProofReport()) == label


def test_method_labels_follow_the_source() -> None:
    page = ProofReport(publication=PublicationInfo(input="x", source="page"))
    personal = ProofReport(referee_domain_kind="free")

    assert (
        method_label(ProofType.PUBLICATION, "partially_verified", page)
        == "Partly verified via the publisher's page"
    )
    assert (
        method_label(ProofType.REFEREE_CONFIRMATION, "partially_verified", personal)
        == "Partly verified by referee (personal email)"
    )
