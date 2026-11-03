"""Referee confirmation: a one-time link to a named referee, outcomes the candidate can see
(never the answers), lower trust for personal email, expiry, and abuse limits."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import app
from app.models import EmailSuppression, RefereeRequest, Skill, UserSkill
from app.models.enums import VerificationStatus
from app.services.email.sender import (
    EmailMessage,
    EmailSendError,
    MemoryEmailSender,
    get_email_sender,
)
from app.services.verification.referees import MAX_AWAITING

LINK = re.compile(r"/referee/([A-Za-z0-9_-]{20,})")


@pytest.fixture
def outbox() -> MemoryEmailSender:
    sender = MemoryEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    return sender


@pytest.fixture
async def skills(db_session: AsyncSession) -> dict[str, Skill]:
    rows = {
        slug: Skill(slug=slug, name=name, category="soft_skill", aliases=[name.lower()])
        for slug, name in [
            ("customer-service", "Customer Service"),
            ("upselling", "Upselling"),
            ("cash-handling", "Cash Handling"),
        ]
    }
    db_session.add_all(rows.values())
    await db_session.commit()
    return rows


async def signup(client: AsyncClient, email: str = "maria@example.com") -> dict[str, str]:
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "name": "Maria Lopez"},
    )
    client.cookies.clear()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def body(skills: dict[str, Skill], **overrides: Any) -> dict[str, Any]:
    return {
        "referee_name": "Sam Carter",
        "referee_role": "Store Manager",
        "referee_organization": "Harbor Outfitters",
        "referee_email": "sam.carter@harboroutfitters.com",
        "role_title": "Sales Associate",
        "organization": "Harbor Outfitters",
        "start_date": "2021-03",
        "end_date": "2024-06",
        "skill_ids": [str(s.id) for s in skills.values()],
        **overrides,
    }


async def ask(
    client: AsyncClient, headers: dict[str, str], skills: dict[str, Skill], **overrides: Any
) -> Any:
    return await client.post("/api/proofs/referee", json=body(skills, **overrides), headers=headers)


def token_of(message: EmailMessage) -> str:
    match = LINK.search(message.text)
    assert match, message.text
    return match.group(1)


def answers(skills: dict[str, Skill], yes: set[str], **overrides: Any) -> dict[str, Any]:
    return {
        "role_confirmed": True,
        "dates_confirmed": True,
        "relationship": "manager",
        "skills": [
            {"skill_id": str(s.id), "confirmed": slug in yes, "comment": f"secret note {slug}"}
            for slug, s in skills.items()
        ],
        "comment": "Private comment for the record",
        "attested": True,
        **overrides,
    }


async def statuses(db_session: AsyncSession) -> dict[uuid.UUID, VerificationStatus]:
    rows = await db_session.scalars(select(UserSkill).execution_options(populate_existing=True))
    return {r.skill_id: r.verification_status for r in rows}


# --- the happy path ------------------------------------------------------------------------


async def test_referee_confirms_and_the_candidate_sees_only_the_outcome(
    client: AsyncClient,
    db_session: AsyncSession,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
) -> None:
    headers = await signup(client)

    created = await ask(client, headers, skills)

    assert created.status_code == 201, created.text
    proof = created.json()
    assert (proof["type"], proof["status"]) == ("referee_confirmation", "awaiting_response")
    assert proof["referee"]["email_domain"] == "harboroutfitters.com"
    assert proof["referee"]["domain_kind"] == "company"
    assert proof["referee"]["domain_matches_organization"] is True
    assert "sam.carter" not in str(proof)  # the address isn't echoed back in full
    assert set((await statuses(db_session)).values()) == {VerificationStatus.PENDING}

    [message] = outbox.outbox
    assert message.to == "sam.carter@harboroutfitters.com"
    assert message.subject == "Maria Lopez asked you to confirm their work at Harbor Outfitters"
    assert "Sales Associate at Harbor Outfitters (Mar 2021 to Jun 2024)" in message.text
    assert "won't see your answers" in message.text
    token = token_of(message)

    page = await client.get(f"/api/referee/{token}")
    assert page.status_code == 200
    assert page.json()["candidate_name"] == "Maria Lopez"
    assert [s["name"] for s in page.json()["claim"]["skills"]] == [
        "Customer Service",
        "Upselling",
        "Cash Handling",
    ]

    sent = await client.post(
        f"/api/referee/{token}", json=answers(skills, {"customer-service", "cash-handling"})
    )
    assert sent.status_code == 204, sent.text

    detail = (await client.get(f"/api/proofs/{proof['id']}", headers=headers)).json()
    assert detail["status"] == "verified"
    assert detail["verification_level"] == "verified"
    assert detail["verification_method"] == "Verified by referee"
    assert detail["decision"].startswith(
        "Confirmed by Sam Carter (Store Manager, Harbor Outfitters)"
    )
    assert detail["referee"]["status"] == "confirmed"
    # Never the answers: no comments, no per-question yes/no, and no "no" skills.
    text = str(detail)
    assert "secret note" not in text and "Private comment" not in text
    assert "role_confirmed" not in text and "Upselling" not in str(detail["report"]["skills"])
    final = await statuses(db_session)
    assert final[skills["customer-service"].id] is VerificationStatus.VERIFIED
    assert final[skills["cash-handling"].id] is VerificationStatus.VERIFIED
    assert final[skills["upselling"].id] is VerificationStatus.UNVERIFIED

    # One-time: the link is dead now.
    assert (await client.get(f"/api/referee/{token}")).status_code == 404
    again = await client.post(f"/api/referee/{token}", json=answers(skills, set()))
    assert again.status_code == 404


async def test_skill_gap_and_badges_say_verified_by_referee(
    client: AsyncClient,
    db_session: AsyncSession,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
) -> None:
    from app.services.skill_gap.service import verification_methods

    headers = await signup(client)
    await ask(client, headers, skills)
    await client.post(
        f"/api/referee/{token_of(outbox.outbox[0])}", json=answers(skills, {"upselling"})
    )
    user_id = (await db_session.scalars(select(UserSkill.user_id))).first()
    assert user_id is not None

    methods = await verification_methods(db_session, user_id)

    assert methods == {skills["upselling"].id: "Verified by referee"}
    listed = (await client.get("/api/proofs", headers=headers)).json()
    assert listed[0]["verification_method"] == "Verified by referee"


# --- lower trust ---------------------------------------------------------------------------


async def test_personal_email_referee_only_partly_verifies(
    client: AsyncClient,
    db_session: AsyncSession,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
) -> None:
    headers = await signup(client)
    created = await ask(client, headers, skills, referee_email="sam.carter@gmail.com")
    assert created.json()["referee"]["domain_kind"] == "free"
    assert created.json()["referee"]["domain_matches_organization"] is False

    await client.post(
        f"/api/referee/{token_of(outbox.outbox[0])}", json=answers(skills, set(skills))
    )

    detail = (await client.get(f"/api/proofs/{created.json()['id']}", headers=headers)).json()
    assert detail["status"] == "needs_more"
    assert detail["verification_level"] == "partially_verified"
    assert detail["verification_method"] == "Partly verified by referee (personal email)"
    assert "personal email" in detail["decision"]
    assert VerificationStatus.VERIFIED not in (await statuses(db_session)).values()


async def test_unconfirmed_dates_partly_verify_and_unconfirmed_role_rejects(
    client: AsyncClient, outbox: MemoryEmailSender, skills: dict[str, Skill]
) -> None:
    headers = await signup(client)
    first = (await ask(client, headers, skills)).json()
    second = (await ask(client, headers, skills, referee_email="lee@harboroutfitters.com")).json()
    one, two = (token_of(m) for m in outbox.outbox)

    await client.post(
        f"/api/referee/{one}", json=answers(skills, set(skills), dates_confirmed=False)
    )
    await client.post(
        f"/api/referee/{two}", json=answers(skills, set(skills), role_confirmed=False)
    )

    dates = (await client.get(f"/api/proofs/{first['id']}", headers=headers)).json()
    role = (await client.get(f"/api/proofs/{second['id']}", headers=headers)).json()
    assert (dates["status"], dates["verification_level"]) == ("needs_more", "partially_verified")
    assert (role["status"], role["verification_level"]) == ("rejected", None)
    assert role["verification_method"] is None


async def test_referee_must_answer_every_skill_and_attest(
    client: AsyncClient, outbox: MemoryEmailSender, skills: dict[str, Skill]
) -> None:
    headers = await signup(client)
    await ask(client, headers, skills)
    token = token_of(outbox.outbox[0])
    partial = answers(skills, set())
    partial["skills"] = partial["skills"][:1]

    assert (await client.post(f"/api/referee/{token}", json=partial)).status_code == 422
    unattested = answers(skills, set(), attested=False)
    assert (await client.post(f"/api/referee/{token}", json=unattested)).status_code == 422
    assert (await client.get(f"/api/referee/{token}")).status_code == 200  # still usable


# --- declining and opting out ---------------------------------------------------------------


async def test_referee_can_decline_and_stop_all_future_requests(
    client: AsyncClient,
    db_session: AsyncSession,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
) -> None:
    headers = await signup(client)
    proof = (await ask(client, headers, skills)).json()

    declined = await client.post(
        f"/api/referee/{token_of(outbox.outbox[0])}/decline",
        json={"reason": "dont_know", "stop_emails": True},
    )

    assert declined.status_code == 204
    detail = (await client.get(f"/api/proofs/{proof['id']}", headers=headers)).json()
    assert (
        detail["status"] == "rejected" and detail["decision"] == "Sam Carter couldn't confirm this."
    )
    assert await db_session.scalar(select(EmailSuppression)) is not None
    # Nobody can email them again, in any letter case.
    other = await signup(client, "someone@example.com")
    refused = await ask(client, other, skills, referee_email="Sam.Carter@HarborOutfitters.com")
    assert refused.status_code == 422 and "asked not to receive" in refused.json()["detail"]
    recipients = [m.to for m in outbox.outbox]
    assert recipients.count("sam.carter@harboroutfitters.com") == 1
    # The candidate hears the outcome (proof emails are on by default).
    assert recipients.count("maria@example.com") == 1


# --- expiry and reminders -------------------------------------------------------------------


async def expire(db_session: AsyncSession) -> None:
    past = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.execute(update(RefereeRequest).values(expires_at=past))
    await db_session.commit()


async def test_links_expire_after_14_days_and_can_be_resent(
    client: AsyncClient,
    db_session: AsyncSession,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
) -> None:
    headers = await signup(client)
    proof = (await ask(client, headers, skills)).json()
    expires = datetime.fromisoformat(proof["referee"]["expires_at"])
    assert timedelta(days=13, hours=23) < expires - datetime.now(UTC) <= timedelta(days=14)
    old = token_of(outbox.outbox[0])
    await expire(db_session)

    assert (await client.get(f"/api/referee/{old}")).status_code == 404
    detail = (await client.get(f"/api/proofs/{proof['id']}", headers=headers)).json()
    assert detail["status"] == "needs_more" and "expired" in detail["decision"]
    assert detail["referee"]["status"] == "expired" and detail["referee"]["can_resend"] is True
    assert VerificationStatus.PENDING not in (await statuses(db_session)).values()

    resent = await client.post(f"/api/proofs/{proof['id']}/referee/resend", headers=headers)

    assert resent.status_code == 200, resent.text
    assert resent.json()["status"] == "awaiting_response"
    new = token_of(outbox.outbox[1])
    assert new != old
    assert (await client.get(f"/api/referee/{old}")).status_code == 404
    assert (await client.get(f"/api/referee/{new}")).status_code == 200


async def test_reminders_wait_48_hours_and_stop_after_three_emails(
    client: AsyncClient,
    db_session: AsyncSession,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
) -> None:
    headers = await signup(client)
    proof = (await ask(client, headers, skills)).json()
    resend = f"/api/proofs/{proof['id']}/referee/resend"

    too_soon = await client.post(resend, headers=headers)
    assert too_soon.status_code == 422 and "48 hours" in too_soon.json()["detail"]

    for _ in range(2):
        await db_session.execute(
            update(RefereeRequest).values(last_sent_at=datetime.now(UTC) - timedelta(days=3))
        )
        await db_session.commit()
        assert (await client.post(resend, headers=headers)).status_code == 200
    await db_session.execute(
        update(RefereeRequest).values(last_sent_at=datetime.now(UTC) - timedelta(days=3))
    )
    await db_session.commit()

    capped = await client.post(resend, headers=headers)
    assert capped.status_code == 422 and "maximum" in capped.json()["detail"]
    assert len(outbox.outbox) == 3


async def test_failed_email_can_be_resent_straight_away(
    client: AsyncClient, outbox: MemoryEmailSender, skills: dict[str, Skill]
) -> None:
    class Broken:
        async def send(self, message: EmailMessage) -> None:
            raise EmailSendError("down")

    app.dependency_overrides[get_email_sender] = lambda: Broken()
    headers = await signup(client)
    proof = (await ask(client, headers, skills)).json()
    assert proof["status"] == "needs_more" and proof["referee"]["status"] == "failed"
    assert "couldn't send" in proof["decision"]

    app.dependency_overrides[get_email_sender] = lambda: outbox
    resent = await client.post(f"/api/proofs/{proof['id']}/referee/resend", headers=headers)

    assert resent.json()["status"] == "awaiting_response"
    assert len(outbox.outbox) == 1


# --- abuse protection -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"referee_email": "maria@example.com"}, "someone else"),
        ({"referee_email": "x@mailinator.com"}, "temporary inbox"),
        ({"referee_email": "not-an-email"}, "valid email"),
    ],
)
async def test_bad_referee_addresses_are_refused(
    client: AsyncClient,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
    overrides: dict[str, str],
    message: str,
) -> None:
    headers = await signup(client)

    response = await ask(client, headers, skills, **overrides)

    assert response.status_code == 422 and message in response.json()["detail"]
    assert outbox.outbox == []


@pytest.mark.parametrize(
    "field", ["referee_name", "referee_role", "referee_organization", "role_title", "organization"]
)
async def test_no_links_in_text_that_goes_into_the_email(
    client: AsyncClient, outbox: MemoryEmailSender, skills: dict[str, Skill], field: str
) -> None:
    headers = await signup(client)

    response = await ask(client, headers, skills, **{field: "Win a prize at https://evil.example"})

    assert response.status_code == 422
    assert outbox.outbox == []


async def test_a_referee_address_can_only_be_asked_a_few_times(
    client: AsyncClient, outbox: MemoryEmailSender, skills: dict[str, Skill]
) -> None:
    codes = []
    for i in range(4):
        headers = await signup(client, f"user{i}@example.com")
        codes.append((await ask(client, headers, skills)).status_code)

    assert codes == [201, 201, 201, 422]
    assert len(outbox.outbox) == 3


async def test_open_requests_per_user_are_capped_and_not_duplicated(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
) -> None:
    monkeypatch.setattr(get_settings(), "referee_rate_limit", "50/day")  # test the DB caps
    headers = await signup(client)
    assert (await ask(client, headers, skills)).status_code == 201
    duplicate = await ask(client, headers, skills)
    assert duplicate.status_code == 422 and "already have a request" in duplicate.json()["detail"]

    for i in range(1, MAX_AWAITING):
        response = await ask(client, headers, skills, referee_email=f"ref{i}@harboroutfitters.com")
        assert response.status_code == 201
    over = await ask(client, headers, skills, referee_email="ref9@harboroutfitters.com")

    assert over.status_code == 422 and "waiting for an answer" in over.json()["detail"]


async def test_referee_requests_are_rate_limited_per_user(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
) -> None:
    monkeypatch.setattr(get_settings(), "referee_rate_limit", "2/day")
    headers = await signup(client)

    codes = [
        (await ask(client, headers, skills, referee_email=f"r{i}@acme.com")).status_code
        for i in range(3)
    ]

    assert codes == [201, 201, 429]


async def test_referee_page_is_rate_limited_per_ip(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "referee_page_rate_limit", "3/hour")

    codes = [(await client.get(f"/api/referee/{'x' * 43}")).status_code for _ in range(4)]

    assert codes == [404, 404, 404, 429]


async def test_referee_proofs_cannot_be_rerun_or_made_as_links(
    client: AsyncClient, outbox: MemoryEmailSender, skills: dict[str, Skill]
) -> None:
    headers = await signup(client)
    proof = (await ask(client, headers, skills)).json()

    rerun = await client.post(f"/api/proofs/{proof['id']}/reanalyze", headers=headers)
    as_link = await client.post(
        "/api/proofs",
        json={"type": "referee_confirmation", "url": "https://x.com", "skill_ids": []},
        headers=headers,
    )

    assert rerun.status_code == 422
    assert as_link.status_code == 422


async def test_only_the_token_hash_is_stored(
    client: AsyncClient,
    db_session: AsyncSession,
    outbox: MemoryEmailSender,
    skills: dict[str, Skill],
) -> None:
    headers = await signup(client)
    await ask(client, headers, skills)
    token = token_of(outbox.outbox[0])

    stored = await db_session.scalar(select(RefereeRequest))

    assert stored is not None and stored.token_hash and token not in stored.token_hash
    assert len(stored.token_hash) == 64
