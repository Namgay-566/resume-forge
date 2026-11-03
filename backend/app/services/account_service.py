"""The Settings page: profile, sign-in methods, sessions, preferences, data export and
account deletion.

Sensitive changes (password, email, deletion) ask for the current password when the
account has one. Accounts made with Google, LinkedIn or GitHub have none; for them being
signed in, plus typing the email to delete, is the check. An account always keeps at
least one way to sign in."""

import asyncio
import hashlib
import hmac
import io
import json
import logging
import re
import secrets
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import burn_password_check, hash_password, verify_password
from app.models import (
    ATSAnalysis,
    EmailChangeRequest,
    EmploymentEmailCheck,
    LearningPlanItem,
    Proof,
    ReadinessSnapshot,
    RefereeRequest,
    Resume,
    User,
    UserSkill,
)
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.account import (
    AccountDelete,
    EmailChangeStart,
    PasswordChange,
    PreferencesUpdate,
    ProfileUpdate,
    Provider,
)
from app.services.auth_service import GitHubProfile, OidcProfile
from app.services.email.notifications import can_email, notify_security
from app.services.email.sender import EmailMessage, EmailSender, EmailSendError
from app.services.storage.files import FileStorage, StorageError

logger = logging.getLogger(__name__)

CODE_MINUTES = 15
MAX_ATTEMPTS = 5
RESEND_AFTER = timedelta(seconds=60)
MAX_SENDS = 5

PROVIDER_NAMES = {"github": "GitHub", "google": "Google", "linkedin": "LinkedIn"}


class AccountError(Exception):
    """User-facing problem; str(exc) is safe to show."""


class WrongPasswordError(AccountError):
    def __init__(self) -> None:
        super().__init__("Your current password isn't right.")


class ProviderInUseError(AccountError):
    """That Google, LinkedIn or GitHub account already signs in to another ResumeForge account."""


def _now() -> datetime:
    return datetime.now(UTC)


def _code_hash(user_id: uuid.UUID, email: str, code: str) -> str:
    key = get_settings().jwt_secret_key.get_secret_value().encode()
    return hmac.new(
        key, f"email-change:{user_id}:{email}:{code}".encode(), hashlib.sha256
    ).hexdigest()


# --- data export helpers ------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _row(obj: object, exclude: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Every column of an ORM row, as JSON-ready values."""
    return {
        attr.key: _jsonable(getattr(obj, attr.key))
        for attr in inspect(obj).mapper.column_attrs
        if attr.key not in exclude
    }


# Secrets and data that isn't the user's to see (a referee's private answers).
_USER_SECRET = frozenset({"hashed_password"})
_REFEREE_PRIVATE = frozenset({"token_hash", "answers", "decline_reason"})
_CHECK_SECRET = frozenset({"code_hash"})

_README = """Your ResumeForge data
======================

Exported {date}.

account.json            Your profile, sign-in methods and preferences
resumes.json            Every resume and CV, with its full content
ats_analyses.json       Every ATS score and report
readiness.json          Your readiness score history per resume
skills.json             Your skills and their verification status
roadmap.json            Your learning roadmap progress and saved practice ideas
proofs.json             Every proof you added and its review
referee_requests.json   Referee requests you sent (the referee's private answers are theirs)
employment_checks.json  Work email checks
proof-files/            The files you uploaded as proof
"""


@dataclass(frozen=True)
class DataExport:
    content: bytes
    filename: str


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    # --- checks ---------------------------------------------------------------------------

    @staticmethod
    def _check_password(user: User, password: str | None) -> None:
        if user.hashed_password is None:
            return
        if not password:
            burn_password_check("")
            raise WrongPasswordError
        if not verify_password(password, user.hashed_password):
            raise WrongPasswordError

    # --- profile --------------------------------------------------------------------------

    async def update_profile(self, user: User, body: ProfileUpdate) -> User:
        changes = body.model_dump(exclude_unset=True)
        if "name" in changes:
            user.name = changes["name"]
        if "linkedin_url" in changes:
            user.linkedin_url = changes["linkedin_url"]
        await self.session.commit()
        return user

    async def update_preferences(self, user: User, body: PreferencesUpdate) -> User:
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await self.session.commit()
        return user

    # --- password and sessions ------------------------------------------------------------

    async def change_password(self, user: User, body: PasswordChange, sender: EmailSender) -> User:
        """Sets the new password and signs out every session; the caller then starts a new
        one for this device."""
        had_password = user.has_password
        self._check_password(user, body.current_password)
        user.hashed_password = hash_password(body.new_password)
        await self._revoke_sessions(user)
        await self.session.commit()
        await notify_security(
            sender,
            user.email,
            user.name,
            "Your password was changed" if had_password else "A password was added to your account",
        )
        return user

    async def sign_out_everywhere(self, user: User) -> None:
        await self._revoke_sessions(user)
        await self.session.commit()

    async def _revoke_sessions(self, user: User) -> None:
        await self.refresh_tokens.delete_all_for_user(user.id)
        user.sessions_revoked_at = _now()

    # --- email change ---------------------------------------------------------------------

    async def pending_email_change(self, user: User) -> EmailChangeRequest | None:
        pending = await self.session.get(EmailChangeRequest, user.id)
        if pending is not None and pending.expires_at <= _now():
            return None
        return pending

    async def start_email_change(
        self, user: User, body: EmailChangeStart, sender: EmailSender
    ) -> EmailChangeRequest:
        self._check_password(user, body.current_password)
        new_email = body.new_email
        if new_email == user.email:
            raise AccountError("That's already your email address.")
        if not can_email(new_email):
            raise AccountError("Use an address you can receive email at.")
        if await self.users.get_by_email(new_email):
            raise AccountError("That email is already used by another account.")

        now = _now()
        pending = await self.session.get(EmailChangeRequest, user.id)
        if pending is not None and pending.new_email == new_email and pending.expires_at > now:
            if now - pending.last_sent_at < RESEND_AFTER:
                raise AccountError("A code was just sent. Wait a minute before asking again.")
            if pending.sent_count >= MAX_SENDS:
                raise AccountError("Too many codes sent to this address. Try again tomorrow.")
        else:
            if pending is not None:
                await self.session.delete(pending)
                await self.session.flush()
            pending = EmailChangeRequest(
                user_id=user.id,
                new_email=new_email,
                code_hash="",
                sent_count=0,
                last_sent_at=now,
                expires_at=now,
            )
            self.session.add(pending)

        code = f"{secrets.randbelow(10**6):06d}"
        pending.code_hash = _code_hash(user.id, new_email, code)
        pending.attempts = 0
        pending.sent_count += 1
        pending.last_sent_at = now
        pending.expires_at = now + timedelta(minutes=CODE_MINUTES)
        message = EmailMessage(
            to=new_email,
            subject=f"Your ResumeForge code: {code}",
            text=(
                f"Hi {user.name},\n\n"
                f"Enter this code in ResumeForge Settings to make this your sign-in email:\n\n"
                f"{code}\n\n"
                f"It expires in {CODE_MINUTES} minutes. If you didn't ask for this, ignore "
                "this email; nothing changes without the code."
            ),
        )
        try:
            await sender.send(message)
        except EmailSendError as exc:
            await self.session.rollback()
            raise AccountError(str(exc)) from exc
        await self.session.commit()
        return pending

    async def confirm_email_change(self, user: User, code: str, sender: EmailSender) -> User:
        pending = await self.pending_email_change(user)
        if pending is None:
            raise AccountError("That code has expired. Ask for a new one.")
        if pending.attempts >= MAX_ATTEMPTS:
            raise AccountError("Too many wrong codes. Ask for a new one.")
        pending.attempts += 1
        expected = _code_hash(user.id, pending.new_email, code.strip())
        if not hmac.compare_digest(pending.code_hash, expected):
            await self.session.commit()
            left = MAX_ATTEMPTS - pending.attempts
            if left <= 0:
                raise AccountError("Too many wrong codes. Ask for a new one.")
            raise AccountError(
                f"That code isn't right. {left} {'try' if left == 1 else 'tries'} left."
            )

        old_email, new_email = user.email, pending.new_email
        user.email = new_email
        await self.session.delete(pending)
        try:
            await self.session.commit()
        except IntegrityError as exc:  # someone registered the address in the meantime
            await self.session.rollback()
            raise AccountError("That email is already used by another account.") from exc
        await notify_security(
            sender, old_email, user.name, f"Your sign-in email was changed to {new_email}"
        )
        return user

    async def cancel_email_change(self, user: User) -> None:
        await self.session.execute(
            delete(EmailChangeRequest).where(EmailChangeRequest.user_id == user.id)
        )
        await self.session.commit()

    # --- connected sign-in providers ------------------------------------------------------

    async def disconnect(self, user: User, provider: Provider, sender: EmailSender) -> User:
        connected = {
            "github": user.github_connected,
            "google": user.google_connected,
            "linkedin": user.linkedin_connected,
        }[provider]
        if not connected:
            raise AccountError(f"{PROVIDER_NAMES[provider]} isn't connected.")
        if user.sign_in_methods <= 1:
            raise AccountError(
                f"{PROVIDER_NAMES[provider]} is your only way to sign in. Set a password or "
                "connect another account first."
            )
        if provider == "github":
            user.github_id = None
            user.github_username = None
        elif provider == "google":
            user.google_id = None
        else:
            user.linkedin_id = None  # the profile URL stays: it's on the user's profile
        await self.session.commit()
        await notify_security(
            sender,
            user.email,
            user.name,
            f"{PROVIDER_NAMES[provider]} sign-in was removed from your account",
        )
        return user

    async def link_github(self, user: User, profile: GitHubProfile) -> User:
        owner = await self.users.get_by_github_id(profile.id)
        if owner is not None and owner.id != user.id:
            raise ProviderInUseError
        user.github_id = profile.id
        user.github_username = profile.login
        await self.session.commit()
        return user

    async def link_oidc(self, user: User, profile: OidcProfile) -> User:
        if profile.provider == "google":
            owner = await self.users.get_by_google_id(profile.subject)
        else:
            owner = await self.users.get_by_linkedin_id(profile.subject)
        if owner is not None and owner.id != user.id:
            raise ProviderInUseError
        if profile.provider == "google":
            user.google_id = profile.subject
        else:
            user.linkedin_id = profile.subject
            if profile.profile_url and not user.linkedin_url:
                user.linkedin_url = profile.profile_url
        await self.session.commit()
        return user

    # --- your data ------------------------------------------------------------------------

    async def export_data(self, user: User, storage: FileStorage) -> DataExport:
        """Everything stored about the user, as a ZIP of JSON files plus uploaded proofs."""
        uid = user.id

        async def rows(
            model: Any, *where: Any, exclude: frozenset[str] = frozenset()
        ) -> list[dict[str, Any]]:
            query = select(model).where(*where).order_by(model.created_at)
            return [_row(r, exclude) for r in await self.session.scalars(query)]

        resume_ids = select(Resume.id).where(Resume.user_id == uid)
        user_skills = await self.session.scalars(
            select(UserSkill).where(UserSkill.user_id == uid).options(selectinload(UserSkill.skill))
        )
        proofs = list(
            await self.session.scalars(
                select(Proof)
                .where(Proof.user_id == uid)
                .order_by(Proof.created_at)
                .options(selectinload(Proof.skills))
            )
        )
        documents: dict[str, Any] = {
            "account.json": _row(user, _USER_SECRET),
            "resumes.json": await rows(Resume, Resume.user_id == uid),
            "ats_analyses.json": await rows(ATSAnalysis, ATSAnalysis.resume_id.in_(resume_ids)),
            "readiness.json": await rows(
                ReadinessSnapshot, ReadinessSnapshot.resume_id.in_(resume_ids)
            ),
            "skills.json": [{**_row(s), "skill_name": s.skill.name} for s in user_skills],
            "roadmap.json": await rows(LearningPlanItem, LearningPlanItem.user_id == uid),
            "proofs.json": [{**_row(p), "skills": [s.name for s in p.skills]} for p in proofs],
            "referee_requests.json": await rows(
                RefereeRequest, RefereeRequest.user_id == uid, exclude=_REFEREE_PRIVATE
            ),
            "employment_checks.json": await rows(
                EmploymentEmailCheck, EmploymentEmailCheck.user_id == uid, exclude=_CHECK_SECRET
            ),
        }

        files: dict[str, bytes] = {}
        for proof in proofs:
            if not proof.file_path:
                continue
            try:
                data = await storage.read(proof.file_path)
            except StorageError:
                logger.warning("Data export: proof file missing for proof %s", proof.id)
                continue
            extension = proof.file_path.rsplit(".", 1)[-1]
            files[f"proof-files/{proof.id}.{extension}"] = data

        now = _now()

        def build() -> bytes:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("README.txt", _README.format(date=now.strftime("%d %B %Y")))
                for name, value in documents.items():
                    archive.writestr(name, json.dumps(value, indent=2, ensure_ascii=False))
                for name, data in files.items():
                    archive.writestr(name, data)
            return buffer.getvalue()

        slug = re.sub(r"[^\w]+", "-", user.name).strip("-_")[:60] or "account"
        return DataExport(
            content=await asyncio.to_thread(build),
            filename=f"ResumeForge-data-{slug}-{now:%Y-%m-%d}.zip",
        )

    async def delete_account(self, user: User, body: AccountDelete, storage: FileStorage) -> None:
        """Deletes the user and everything they own (the database cascades from users), then
        their uploaded files. Files go last: a failed file delete must not keep the account."""
        if body.confirm_email.strip().lower() != user.email:
            raise AccountError("Type your email address exactly as shown to confirm.")
        self._check_password(user, body.current_password)

        keys = list(
            await self.session.scalars(
                select(Proof.file_path).where(
                    Proof.user_id == user.id, Proof.file_path.is_not(None)
                )
            )
        )
        await self.session.execute(delete(User).where(User.id == user.id))
        await self.session.commit()
        for key in keys:
            try:
                await storage.delete(key)
            except (StorageError, OSError):
                logger.warning("Account deletion: couldn't delete a proof file (%s)", key)
