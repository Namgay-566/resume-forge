"""Employer email check: the user shows they can read mail at a work address, which adds
"Employment email verified (@domain)" to the experience entries at that company.

Codes are 6 digits, stored as an HMAC (a bare hash of a 6-digit code is trivially
reversed), expire after CODE_MINUTES and allow MAX_ATTEMPTS guesses. Personal and
disposable addresses are refused: they can't show where someone works.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import EmailSuppression, EmploymentEmailCheck, User
from app.services.email.sender import EmailMessage, EmailSender, EmailSendError
from app.services.verification.email_domains import (
    InvalidEmailError,
    classify,
    domain_matches_organization,
    email_domain,
    normalize_email,
)
from app.services.verification.referees import email_hash

CODE_MINUTES = 15
MAX_ATTEMPTS = 5
RESEND_AFTER = timedelta(seconds=60)
MAX_SENDS_PER_CHECK = 5
MAX_PER_ADDRESS_PER_DAY = 5  # codes to one address, from anyone
MAX_OPEN_CHECKS = 10


class EmploymentCheckError(Exception):
    """User-facing problem; str(exc) is safe to show."""


class EmploymentCheckNotFoundError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _code_hash(check_id: uuid.UUID, code: str) -> str:
    key = get_settings().jwt_secret_key.get_secret_value().encode()
    return hmac.new(key, f"{check_id}:{code}".encode(), hashlib.sha256).hexdigest()


class EmploymentCheckService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, user: User) -> list[EmploymentEmailCheck]:
        return list(
            await self.session.scalars(
                select(EmploymentEmailCheck)
                .where(EmploymentEmailCheck.user_id == user.id)
                .order_by(EmploymentEmailCheck.created_at)
            )
        )

    async def get(self, user: User, check_id: uuid.UUID) -> EmploymentEmailCheck:
        check = await self.session.get(EmploymentEmailCheck, check_id)
        if check is None or check.user_id != user.id:
            raise EmploymentCheckNotFoundError
        return check

    async def start(
        self, user: User, *, company: str, email: str, sender: EmailSender
    ) -> EmploymentEmailCheck:
        company = " ".join(company.split())[:200]
        if not company:
            raise EmploymentCheckError("Add the company name first.")
        try:
            email = normalize_email(email)
        except InvalidEmailError as exc:
            raise EmploymentCheckError(str(exc)) from exc
        kind = classify(email)
        if kind != "company":
            raise EmploymentCheckError(
                f"Use your work email at {company}. Personal addresses like Gmail or Outlook "
                "can't show where you work."
            )
        if await self.session.get(EmailSuppression, email_hash(email)):
            raise EmploymentCheckError("This address has asked not to receive email from us.")

        check = await self.session.scalar(
            select(EmploymentEmailCheck).where(
                EmploymentEmailCheck.user_id == user.id,
                EmploymentEmailCheck.email == email,
                EmploymentEmailCheck.company == company,
            )
        )
        if check is not None and check.verified_at is not None:
            return check  # already done
        if check is None:
            open_checks = await self.session.scalar(
                select(func.count())
                .select_from(EmploymentEmailCheck)
                .where(
                    EmploymentEmailCheck.user_id == user.id,
                    EmploymentEmailCheck.verified_at.is_(None),
                )
            )
            if (open_checks or 0) >= MAX_OPEN_CHECKS:
                raise EmploymentCheckError("Finish or remove your other email checks first.")
            check = EmploymentEmailCheck(
                user_id=user.id,
                company=company,
                email=email,
                email_domain=email_domain(email),
                domain_matches_company=domain_matches_organization(email, company),
                attempts=0,
                sent_count=0,
            )
            self.session.add(check)
            await self.session.flush()
        await self._send_code(user, check, sender)
        await self.session.commit()
        return check

    async def resend(
        self, user: User, check_id: uuid.UUID, sender: EmailSender
    ) -> EmploymentEmailCheck:
        check = await self.get(user, check_id)
        if check.verified_at is not None:
            return check
        await self._send_code(user, check, sender)
        await self.session.commit()
        return check

    async def _send_code(
        self, user: User, check: EmploymentEmailCheck, sender: EmailSender
    ) -> None:
        now = _now()
        if check.last_sent_at and now - check.last_sent_at < RESEND_AFTER:
            raise EmploymentCheckError("A code was just sent. Wait a minute before asking again.")
        if check.sent_count >= MAX_SENDS_PER_CHECK:
            raise EmploymentCheckError("Too many codes for this address. Try again tomorrow.")
        sent_today = await self.session.scalar(
            select(func.coalesce(func.sum(EmploymentEmailCheck.sent_count), 0)).where(
                EmploymentEmailCheck.email == check.email,
                EmploymentEmailCheck.last_sent_at >= now - timedelta(days=1),
            )
        )
        if (sent_today or 0) >= MAX_PER_ADDRESS_PER_DAY:
            raise EmploymentCheckError("Too many codes for this address. Try again tomorrow.")
        code = f"{secrets.randbelow(10**6):06d}"
        check.code_hash = _code_hash(check.id, code)
        check.code_expires_at = now + timedelta(minutes=CODE_MINUTES)
        check.attempts = 0
        check.last_sent_at = now
        check.sent_count += 1
        message = EmailMessage(
            to=check.email,
            subject=f"Your ResumeForge code: {code}",
            text=(
                f"Hello {user.name},\n\n"
                f"Enter this code in ResumeForge to confirm you work at {check.company}:\n\n"
                f"{code}\n\n"
                f"It expires in {CODE_MINUTES} minutes. If you didn't ask for this, you can "
                "ignore this email; nothing changes without the code."
            ),
        )
        try:
            await sender.send(message)
        except EmailSendError as exc:
            check.code_hash = None
            await self.session.commit()
            raise EmploymentCheckError(str(exc)) from exc

    async def confirm(self, user: User, check_id: uuid.UUID, code: str) -> EmploymentEmailCheck:
        check = await self.get(user, check_id)
        if check.verified_at is not None:
            return check
        if check.code_hash is None or not check.code_expires_at or check.code_expires_at < _now():
            raise EmploymentCheckError("That code has expired. Send a new one.")
        if check.attempts >= MAX_ATTEMPTS:
            raise EmploymentCheckError("Too many wrong codes. Send a new one.")
        check.attempts += 1
        if not hmac.compare_digest(check.code_hash, _code_hash(check.id, code.strip())):
            await self.session.commit()
            left = MAX_ATTEMPTS - check.attempts
            raise EmploymentCheckError(
                f"That code isn't right. {left} {'try' if left == 1 else 'tries'} left."
                if left
                else "Too many wrong codes. Send a new one."
            )
        check.verified_at = _now()
        check.code_hash = None
        await self.session.commit()
        return check

    async def delete(self, user: User, check_id: uuid.UUID) -> None:
        await self.session.delete(await self.get(user, check_id))
        await self.session.commit()
