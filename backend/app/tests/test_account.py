"""Settings: profile, preferences, password and sessions, email change, connected sign-in
methods, data export and account deletion. Plus the places preferences take effect: new
resumes, export page size, AI spelling and proof emails."""

import io
import json
import re
import uuid
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from docx import Document
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context import CandidateContext
from app.ai.prompts import render_prompt
from app.ai.writing import EXPERIENCE_SECTION
from app.api.routers.auth import REFRESH_COOKIE
from app.core.config import get_settings
from app.main import app
from app.models import Proof, RefreshToken, Resume, User
from app.models.enums import PageSize, ProofStatus, ProofType, ResumeTemplate, ResumeType
from app.schemas.proof_report import ProofReport
from app.schemas.resume_data import PersonalInfo, ResumeData
from app.services import github_oauth
from app.services.account_service import AccountService, ProviderInUseError
from app.services.auth_service import AuthService, GitHubProfile
from app.services.email.notifications import notify_proof_update, proof_update_message
from app.services.email.sender import MemoryEmailSender, get_email_sender
from app.services.export.document import build_document
from app.services.export.docx_builder import render_docx
from app.services.export.html_pdf import render_html
from app.services.storage.files import get_file_storage
from app.tests.test_proof_extras import MemoryStorage

PASSWORD = "correct horse battery"


@pytest.fixture
def outbox() -> Iterator[MemoryEmailSender]:
    sender = MemoryEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    yield sender


@pytest.fixture
def storage() -> Iterator[MemoryStorage]:
    memory = MemoryStorage()
    app.dependency_overrides[get_file_storage] = lambda: memory
    yield memory


async def signup(client: AsyncClient, email: str = "ada@example.com") -> dict[str, str]:
    response = await client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, "name": "Ada Obi"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def old_token(user_id: object, seconds_ago: int = 60) -> dict[str, str]:
    """An access token issued a while back (tokens from the same second as a sign-out
    deliberately still work, so revocation tests need an older one)."""
    settings = get_settings()
    issued = datetime.now(UTC) - timedelta(seconds=seconds_ago)
    token = jwt.encode(
        {"sub": str(user_id), "type": "access", "iat": issued, "exp": issued + timedelta(hours=1)},
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


async def github_user(db_session: AsyncSession) -> tuple[User, dict[str, str]]:
    """An account made with GitHub: no password."""
    service = AuthService(db_session)
    user = await service.login_with_github(
        GitHubProfile(id=42, login="ada-o", name="Ada Obi", verified_email="ada@example.com")
    )
    tokens = await service.issue_tokens(user)
    return user, {"Authorization": f"Bearer {tokens.access_token}"}


# --- profile and preferences ----------------------------------------------------------------


async def test_me_shows_sign_in_methods_and_default_preferences(client: AsyncClient) -> None:
    me = (await client.get("/api/me", headers=await signup(client))).json()

    assert me["has_password"] is True
    assert me["github_connected"] is me["google_connected"] is me["linkedin_connected"] is False
    assert me["preferences"] == {
        "default_resume_type": "resume",
        "default_experience_level": None,
        "default_template": None,
        "page_size": "a4",
        "spelling": None,
        "email_proof_updates": True,
    }


async def test_update_profile_name_and_linkedin(client: AsyncClient) -> None:
    headers = await signup(client)

    updated = await client.patch(
        "/api/me",
        headers=headers,
        json={"name": "  Ada N. Obi ", "linkedin_url": "https://www.linkedin.com/in/ada-obi"},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Ada N. Obi"
    assert updated.json()["linkedin_url"] == "https://www.linkedin.com/in/ada-obi"
    cleared = await client.patch("/api/me", headers=headers, json={"linkedin_url": None})
    assert cleared.json()["linkedin_url"] is None


@pytest.mark.parametrize(
    "body",
    [{"name": ""}, {"name": None}, {"linkedin_url": "https://example.com/me"}, {"email": "x@y.z"}],
)
async def test_update_profile_rejects_bad_input(
    client: AsyncClient, body: dict[str, object]
) -> None:
    response = await client.patch("/api/me", headers=await signup(client), json=body)

    assert response.status_code == 422


async def test_preferences_update_and_null_rules(client: AsyncClient) -> None:
    headers = await signup(client)

    response = await client.patch(
        "/api/me/preferences",
        headers=headers,
        json={
            "default_resume_type": "cv",
            "default_experience_level": "career_changer",
            "default_template": "academic",
            "page_size": "letter",
            "spelling": "en_gb",
            "email_proof_updates": False,
        },
    )

    assert response.status_code == 200
    prefs = response.json()["preferences"]
    assert prefs["page_size"] == "letter" and prefs["spelling"] == "en_gb"
    assert prefs["email_proof_updates"] is False
    # Nullable ones go back to "not set"; required ones can't be null.
    reset = await client.patch(
        "/api/me/preferences", headers=headers, json={"spelling": None, "default_template": None}
    )
    assert reset.json()["preferences"]["spelling"] is None
    assert reset.json()["preferences"]["page_size"] == "letter"  # untouched
    bad = await client.patch("/api/me/preferences", headers=headers, json={"page_size": None})
    assert bad.status_code == 422


async def test_new_resumes_start_from_the_defaults(client: AsyncClient) -> None:
    headers = await signup(client)
    await client.patch(
        "/api/me/preferences",
        headers=headers,
        json={
            "default_resume_type": "cv",
            "default_experience_level": "student",
            "default_template": "compact",
        },
    )

    from_defaults = (await client.post("/api/resumes", headers=headers, json={"title": "A"})).json()
    explicit = (
        await client.post(
            "/api/resumes",
            headers=headers,
            json={"title": "B", "type": "resume", "experience_level": None, "template": "classic"},
        )
    ).json()

    assert (from_defaults["type"], from_defaults["experience_level"]) == ("cv", "student")
    assert from_defaults["template"] == "compact"
    # What the request says wins, including an explicit "not set".
    assert (explicit["type"], explicit["experience_level"]) == ("resume", None)
    assert explicit["template"] == "classic"


# --- password and sessions ------------------------------------------------------------------


async def test_change_password_needs_the_current_one(
    client: AsyncClient, outbox: MemoryEmailSender
) -> None:
    headers = await signup(client)

    wrong = await client.post(
        "/api/me/password",
        headers=headers,
        json={"current_password": "not it", "new_password": "a brand new password"},
    )
    missing = await client.post(
        "/api/me/password", headers=headers, json={"new_password": "a brand new password"}
    )

    assert wrong.status_code == missing.status_code == 400
    assert wrong.json()["detail"] == "Your current password isn't right."
    assert outbox.outbox == []


async def test_change_password_signs_out_other_sessions_and_keeps_this_one(
    client: AsyncClient, db_session: AsyncSession, outbox: MemoryEmailSender
) -> None:
    headers = await signup(client)
    user = await db_session.scalar(select(User))
    assert user is not None

    changed = await client.post(
        "/api/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "a brand new password"},
    )

    assert changed.status_code == 200
    fresh = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    assert (await client.get("/api/me", headers=fresh)).status_code == 200
    assert (await client.get("/api/me", headers=old_token(user.id))).status_code == 401
    assert await db_session.scalar(select(func.count(RefreshToken.id))) == 1  # this device's
    login = await client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": "a brand new password"}
    )
    assert login.status_code == 200
    assert outbox.outbox[0].to == "ada@example.com"
    assert "Your password was changed" in outbox.outbox[0].text


async def test_account_without_password_can_set_one(
    client: AsyncClient, db_session: AsyncSession, outbox: MemoryEmailSender
) -> None:
    _, headers = await github_user(db_session)

    response = await client.post(
        "/api/me/password", headers=headers, json={"new_password": "my first password"}
    )

    assert response.status_code == 200
    assert response.json()["user"]["has_password"] is True
    assert "A password was added" in outbox.outbox[0].text


async def test_sign_out_everywhere_ends_every_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await signup(client)
    refresh = client.cookies[REFRESH_COOKIE]
    user = await db_session.scalar(select(User))
    assert user is not None

    response = await client.post("/api/me/sign-out-everywhere", headers=headers)

    assert response.status_code == 204
    assert REFRESH_COOKIE in response.headers["set-cookie"]  # cleared
    assert await db_session.scalar(select(func.count(RefreshToken.id))) == 0
    assert (await client.get("/api/me", headers=old_token(user.id))).status_code == 401
    client.cookies.set(REFRESH_COOKIE, refresh, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401


# --- email change ---------------------------------------------------------------------------


def code_in(outbox: MemoryEmailSender) -> str:
    match = re.search(r"\b(\d{6})\b", outbox.outbox[-1].subject)
    assert match
    return match.group(1)


async def test_email_change_with_a_code(client: AsyncClient, outbox: MemoryEmailSender) -> None:
    headers = await signup(client)

    started = await client.post(
        "/api/me/email-change",
        headers=headers,
        json={"new_email": "Ada.Obi@Work.example", "current_password": PASSWORD},
    )

    assert started.status_code == 200 and started.json() == {"new_email": "ada.obi@work.example"}
    assert outbox.outbox[-1].to == "ada.obi@work.example"
    pending = await client.get("/api/me/email-change", headers=headers)
    assert pending.json() == {"new_email": "ada.obi@work.example"}
    # Nothing changes until the code is entered.
    assert (await client.get("/api/me", headers=headers)).json()["email"] == "ada@example.com"

    code = code_in(outbox)
    wrong = "000000" if code != "000000" else "111111"
    bad = await client.post("/api/me/email-change/confirm", headers=headers, json={"code": wrong})
    assert bad.status_code == 400 and "4 tries left" in bad.json()["detail"]

    confirmed = await client.post(
        "/api/me/email-change/confirm", headers=headers, json={"code": code}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["email"] == "ada.obi@work.example"
    # The old address hears about it, and sign-in uses the new one.
    assert outbox.outbox[-1].to == "ada@example.com"
    assert "changed to ada.obi@work.example" in outbox.outbox[-1].text
    login = await client.post(
        "/api/auth/login", json={"email": "ada.obi@work.example", "password": PASSWORD}
    )
    assert login.status_code == 200
    assert (await client.get("/api/me/email-change", headers=headers)).json() is None


@pytest.mark.parametrize(
    ("new_email", "password", "message"),
    [
        ("ada@example.com", PASSWORD, "already your email"),
        ("taken@example.com", PASSWORD, "already used by another account"),
        ("new@example.com", "wrong", "current password"),
        ("new@example.com", None, "current password"),
    ],
)
async def test_email_change_refusals(
    client: AsyncClient,
    outbox: MemoryEmailSender,
    new_email: str,
    password: str | None,
    message: str,
) -> None:
    await signup(client, "taken@example.com")
    headers = await signup(client)
    sent_before = len(outbox.outbox)

    response = await client.post(
        "/api/me/email-change",
        headers=headers,
        json={"new_email": new_email, "current_password": password},
    )

    assert response.status_code == 400 and message in response.json()["detail"]
    assert len(outbox.outbox) == sent_before


async def test_email_change_code_locks_after_five_wrong_tries(
    client: AsyncClient, outbox: MemoryEmailSender
) -> None:
    headers = await signup(client)
    await client.post(
        "/api/me/email-change",
        headers=headers,
        json={"new_email": "new@example.com", "current_password": PASSWORD},
    )
    code = code_in(outbox)
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(5):
        await client.post("/api/me/email-change/confirm", headers=headers, json={"code": wrong})
    right = await client.post("/api/me/email-change/confirm", headers=headers, json={"code": code})

    assert right.status_code == 400 and "Too many wrong codes" in right.json()["detail"]


async def test_email_change_resend_waits_a_minute_and_cancel_works(
    client: AsyncClient, outbox: MemoryEmailSender
) -> None:
    headers = await signup(client)
    body = {"new_email": "new@example.com", "current_password": PASSWORD}

    assert (
        await client.post("/api/me/email-change", headers=headers, json=body)
    ).status_code == 200
    again = await client.post("/api/me/email-change", headers=headers, json=body)
    assert again.status_code == 400 and "Wait a minute" in again.json()["detail"]

    assert (await client.delete("/api/me/email-change", headers=headers)).status_code == 204
    assert (await client.get("/api/me/email-change", headers=headers)).json() is None


# --- connected sign-in methods --------------------------------------------------------------


async def test_cannot_disconnect_the_only_way_to_sign_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, headers = await github_user(db_session)

    response = await client.delete("/api/me/providers/github", headers=headers)

    assert response.status_code == 400
    assert "only way to sign in" in response.json()["detail"]


async def test_disconnect_after_setting_a_password(
    client: AsyncClient, db_session: AsyncSession, outbox: MemoryEmailSender
) -> None:
    _, headers = await github_user(db_session)
    changed = await client.post(
        "/api/me/password", headers=headers, json={"new_password": "my first password"}
    )
    headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}

    response = await client.delete("/api/me/providers/github", headers=headers)

    assert response.status_code == 200
    assert response.json()["github_connected"] is False
    assert response.json()["github_username"] is None
    assert "GitHub sign-in was removed" in outbox.outbox[-1].text
    not_connected = await client.delete("/api/me/providers/google", headers=headers)
    assert not_connected.status_code == 400


async def test_link_refuses_an_account_already_used_elsewhere(db_session: AsyncSession) -> None:
    owner, _ = await github_user(db_session)
    other = await AuthService(db_session).register(
        email="other@example.com", password=PASSWORD, name="Other"
    )
    profile = GitHubProfile(id=owner.github_id or 0, login="ada-o", name=None, verified_email=None)

    with pytest.raises(ProviderInUseError):
        await AccountService(db_session).link_github(other, profile)
    # Linking your own account again is harmless.
    await AccountService(db_session).link_github(owner, profile)


@pytest.fixture
def github_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "github_client_id", "gh-client")
    monkeypatch.setattr(settings, "github_client_secret", SecretStr("gh-secret"))


async def test_connect_github_from_settings_links_the_signed_in_account(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    github_configured: None,
) -> None:
    await signup(client)  # leaves the refresh cookie on the client

    async def fake_profile(code: str) -> GitHubProfile:
        # A different email from the account's: linking goes by session, not by email.
        return GitHubProfile(id=7, login="ada-codes", name="Ada", verified_email="a@elsewhere.org")

    monkeypatch.setattr(github_oauth, "fetch_profile", fake_profile)
    start = await client.get("/api/auth/github/login", params={"link": "true"})
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    assert state.startswith("link.")

    done = await client.get("/api/auth/github/callback", params={"code": "c", "state": state})

    assert done.status_code == 307
    assert done.headers["location"].endswith("/settings?connected=github")
    users = list(await db_session.scalars(select(User)))
    assert len(users) == 1 and users[0].github_username == "ada-codes"


async def test_connect_without_a_session_goes_back_to_settings(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, github_configured: None
) -> None:
    async def fake_profile(code: str) -> GitHubProfile:
        return GitHubProfile(id=7, login="ada-codes", name="Ada", verified_email=None)

    monkeypatch.setattr(github_oauth, "fetch_profile", fake_profile)
    start = await client.get("/api/auth/github/login", params={"link": "true"})
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

    done = await client.get("/api/auth/github/callback", params={"code": "c", "state": state})

    assert "/settings?connect_error=github_session" in done.headers["location"]


# --- your data ------------------------------------------------------------------------------


async def add_file_proof(db_session: AsyncSession, storage: MemoryStorage, user: User) -> Proof:
    key = f"proofs/{user.id.hex}/cert.pdf"
    await storage.save(key, b"%PDF-1.4 certificate", "application/pdf")
    proof = Proof(
        user_id=user.id, type=ProofType.CERTIFICATE, file_path=key, status=ProofStatus.VERIFIED
    )
    db_session.add(proof)
    await db_session.commit()
    return proof


async def test_export_contains_everything_but_secrets(
    client: AsyncClient, db_session: AsyncSession, storage: MemoryStorage
) -> None:
    headers = await signup(client)
    await client.post("/api/resumes", headers=headers, json={"title": "Nursing resume"})
    user = await db_session.scalar(select(User))
    assert user is not None
    proof = await add_file_proof(db_session, storage, user)

    response = await client.get("/api/me/export", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "ResumeForge-data-Ada-Obi-" in response.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert {"README.txt", "account.json", "resumes.json", "proofs.json"} <= names
    account = json.loads(archive.read("account.json"))
    assert account["email"] == "ada@example.com" and "hashed_password" not in account
    assert json.loads(archive.read("resumes.json"))[0]["title"] == "Nursing resume"
    assert archive.read(f"proof-files/{proof.id}.pdf") == b"%PDF-1.4 certificate"


async def test_delete_account_needs_the_email_and_password(
    client: AsyncClient, storage: MemoryStorage
) -> None:
    headers = await signup(client)

    wrong_email = await client.post(
        "/api/me/delete",
        headers=headers,
        json={"confirm_email": "someone@else.com", "current_password": PASSWORD},
    )
    wrong_password = await client.post(
        "/api/me/delete",
        headers=headers,
        json={"confirm_email": "ada@example.com", "current_password": "nope"},
    )

    assert wrong_email.status_code == wrong_password.status_code == 400
    assert (await client.get("/api/me", headers=headers)).status_code == 200


async def test_delete_account_removes_everything(
    client: AsyncClient, db_session: AsyncSession, storage: MemoryStorage
) -> None:
    headers = await signup(client)
    await client.post("/api/resumes", headers=headers, json={"title": "Mine"})
    user = await db_session.scalar(select(User))
    assert user is not None
    await add_file_proof(db_session, storage, user)
    other = await signup(client, "other@example.com")
    await client.post("/api/resumes", headers=other, json={"title": "Theirs"})

    response = await client.post(
        "/api/me/delete",
        headers=headers,
        json={"confirm_email": " ADA@example.com ", "current_password": PASSWORD},
    )

    assert response.status_code == 204
    assert REFRESH_COOKIE in response.headers["set-cookie"]
    db_session.expunge_all()
    emails = list(await db_session.scalars(select(User.email)))
    assert emails == ["other@example.com"]
    assert [r.title for r in await db_session.scalars(select(Resume))] == ["Theirs"]
    assert await db_session.scalar(select(func.count(Proof.id))) == 0
    assert storage.files == {}
    assert (await client.get("/api/me", headers=headers)).status_code == 401


async def test_account_without_password_deletes_by_typing_email(
    client: AsyncClient, db_session: AsyncSession, storage: MemoryStorage
) -> None:
    _, headers = await github_user(db_session)

    response = await client.post(
        "/api/me/delete", headers=headers, json={"confirm_email": "ada@example.com"}
    )

    assert response.status_code == 204


# --- where preferences take effect ----------------------------------------------------------


def test_letter_page_size_in_both_exports() -> None:
    doc = build_document(ResumeData(personal_info=PersonalInfo(full_name="Ada")), ResumeType.RESUME)

    html = render_html(doc, ResumeTemplate.CLASSIC, "t", PageSize.LETTER)
    assert html.rstrip().count("size: letter") == 1
    assert "size: letter" not in render_html(doc, ResumeTemplate.CLASSIC, "t")

    section = Document(
        io.BytesIO(render_docx(doc, ResumeTemplate.CLASSIC, "t", PageSize.LETTER))
    ).sections[0]
    assert round(section.page_width.mm, 1) == 215.9 and round(section.page_height.mm, 1) == 279.4


def test_spelling_reaches_the_ai_prompt() -> None:
    uk = render_prompt(
        "bullet_improve_user",
        bullet="Organized rota",
        position="",
        tools=[],
        section=EXPERIENCE_SECTION,
        ctx=CandidateContext(spelling="en_gb"),
    )
    none = render_prompt(
        "bullet_improve_user",
        bullet="Organized rota",
        position="",
        tools=[],
        section=EXPERIENCE_SECTION,
        ctx=CandidateContext(),
    )

    assert "British English" in uk
    assert "Spelling:" not in none


async def test_proof_emails_follow_the_setting() -> None:
    user = User(email="ada@example.com", name="Ada", email_proof_updates=True)
    proof = Proof(
        id=uuid.uuid4(),
        type=ProofType.PROFESSIONAL_LICENSE,
        status=ProofStatus.VERIFIED,
        ai_report=ProofReport(decision="Found on the nursing register."),
    )
    sender = MemoryEmailSender()

    await notify_proof_update(sender, user, proof)
    user.email_proof_updates = False
    await notify_proof_update(sender, user, proof)

    assert len(sender.outbox) == 1
    message = sender.outbox[0]
    assert message.subject == "Your proof is verified"
    assert "Licence or registration" in message.text
    assert "Found on the nursing register." in message.text
    assert f"/proof-vault/{proof.id}" in message.text
    # Still running: nothing to say yet. Placeholder addresses are never emailed.
    proof.status = ProofStatus.ANALYZING
    assert proof_update_message(user, proof) is None
    user.email, user.email_proof_updates = "1+x@users.noreply.github.com", True
    proof.status = ProofStatus.REJECTED
    await notify_proof_update(sender, user, proof)
    assert len(sender.outbox) == 1
