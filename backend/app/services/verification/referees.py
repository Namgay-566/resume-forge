"""Referee confirmation: a named referee confirms the candidate's role, dates and skills
through a secure one-time link.

- The token is 256 random bits; only its sha256 is stored. It works once, for 14 days.
- The candidate sees the outcome (verified or not, which skills) but never the answers.
- A referee on a company domain can fully verify; a personal address (gmail...) is lower
  trust and only partly verifies. Disposable addresses are refused.
- Abuse limits: per-user rate limit on the endpoint (REFEREE_RATE_LIMIT), at most
  MAX_AWAITING open requests per user, at most MAX_PER_RECIPIENT requests to one address
  in RECIPIENT_WINDOW from anyone, capped resends, and an opt-out list that any referee
  can join from the email. Emails carry only plain text from the candidate (no links).
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models import EmailSuppression, EmploymentEmailCheck, Proof, RefereeRequest, Skill, User
from app.models.enums import ProofStatus, ProofType
from app.schemas.proof_report import ProofReport, SkillVerdict
from app.schemas.referee import (
    ClaimedSkill,
    RefereeAnswers,
    RefereeClaim,
    RefereeDecline,
    RefereeRequestCreate,
    RefereeRequestInfo,
)
from app.services.email.notifications import notify_proof_update
from app.services.email.sender import EmailMessage, EmailSender, EmailSendError
from app.services.proofs.service import _mark_claimed, _settle_skills
from app.services.verification.email_domains import (
    InvalidEmailError,
    classify,
    domain_matches_organization,
    email_domain,
    normalize_email,
)

LINK_DAYS = 14
MAX_SENDS = 3  # the first email and two reminders
RESEND_AFTER = timedelta(hours=48)
MAX_AWAITING = 5
MAX_PER_RECIPIENT = 3
RECIPIENT_WINDOW = timedelta(days=30)


class RefereeError(Exception):
    """User-facing problem; str(exc) is safe to show."""


class RefereeLinkError(Exception):
    """The link is unknown, used or expired. One message for all, so links can't be probed."""


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def email_hash(email: str) -> str:
    return _hash(email.strip().lower())


def _now() -> datetime:
    return datetime.now(UTC)


def _dates(claim: RefereeClaim) -> str:
    def month(value: str | None) -> str:
        if not value:
            return ""
        year, mon = value.split("-")
        names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
        return f"{names[int(mon) - 1]} {year}"

    end = "present" if claim.is_current else month(claim.end_date)
    start = month(claim.start_date)
    return f"{start} to {end}" if start and end else start or end


def _email(user: User, request: RefereeRequest, token: str) -> EmailMessage:
    claim = request.claim
    link = f"{get_settings().frontend_url.rstrip('/')}/referee/{token}"
    dates = _dates(claim)
    skills = ", ".join(s.name for s in claim.skills)
    expires = (request.expires_at or _now()).strftime("%d %B %Y")
    text = (
        f"Hello {request.referee_name},\n\n"
        f"{user.name} has named you as a referee for their role as {claim.role_title} at "
        f"{claim.organization}{f' ({dates})' if dates else ''}.\n\n"
        f"Could you confirm their role, dates and these skills: {skills}? It takes about a "
        f"minute, and {user.name} won't see your answers or comments, only whether their "
        f"experience was confirmed.\n\n"
        f"Confirm here: {link}\n\n"
        f"The link works once and expires on {expires}.\n\n"
        f"If you don't know {user.name}, or you'd rather not be asked, open the link and "
        f"choose \"I can't confirm this\". You can also stop all future requests from "
        f"ResumeForge there.\n\n"
        f"ResumeForge (resume builder). This message was sent at {user.name}'s request."
    )
    return EmailMessage(
        to=request.referee_email,
        subject=f"{user.name} asked you to confirm their work at {claim.organization}"[:200],
        text=text,
    )


def request_info(request: RefereeRequest) -> RefereeRequestInfo:
    """The candidate's view of their request. Never includes the answers."""
    now = _now()
    can_resend = (
        request.status in ("sent", "expired", "failed")
        and request.sent_count < MAX_SENDS
        and (
            request.status != "sent"
            or request.last_sent_at is None
            or now - request.last_sent_at >= RESEND_AFTER
        )
    )
    return RefereeRequestInfo(
        referee_name=request.referee_name,
        referee_role=request.referee_role,
        referee_organization=request.referee_organization,
        email_domain=request.email_domain,
        domain_kind="free" if request.domain_kind == "free" else "company",
        domain_matches_organization=request.domain_matches_organization,
        status=request.status,  # type: ignore[arg-type]
        sent_at=request.last_sent_at,
        expires_at=request.expires_at if request.status == "sent" else None,
        responded_at=request.responded_at,
        can_resend=can_resend,
        claim=request.claim,
    )


class RefereeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- the candidate --------------------------------------------------------------------

    async def create(self, user: User, body: RefereeRequestCreate, sender: EmailSender) -> Proof:
        await self.expire_stale(user.id)
        try:
            email = normalize_email(body.referee_email)
        except InvalidEmailError as exc:
            raise RefereeError(str(exc)) from exc
        kind = classify(email)
        if kind == "disposable":
            raise RefereeError("That looks like a temporary inbox. Use the referee's real email.")
        await self._check_recipient(user, email)

        skills = list(await self.session.scalars(select(Skill).where(Skill.id.in_(body.skill_ids))))
        if len(skills) != len(set(body.skill_ids)):
            raise RefereeError("Unknown skill.")
        claim = RefereeClaim(
            role_title=body.role_title,
            organization=body.organization,
            start_date=body.start_date,
            end_date=body.end_date,
            is_current=body.is_current,
            skills=[ClaimedSkill(id=s.id, name=s.name) for s in skills],
        )
        proof = Proof(
            user_id=user.id,
            type=ProofType.REFEREE_CONFIRMATION,
            status=ProofStatus.AWAITING_RESPONSE,
            skills=skills,
            ai_report=ProofReport(
                referee_domain_kind="free" if kind == "free" else "company",
                decision=f"Waiting for {body.referee_name} to respond.",
            ),
        )
        self.session.add(proof)
        await self.session.flush()
        request = RefereeRequest(
            proof_id=proof.id,
            user_id=user.id,
            referee_name=body.referee_name,
            referee_role=body.referee_role,
            referee_organization=body.referee_organization,
            referee_email=email,
            email_domain=email_domain(email),
            domain_kind="free" if kind == "free" else "company",
            domain_matches_organization=kind == "company"
            and domain_matches_organization(email, body.referee_organization),
            claim=claim,
            status="sent",
            sent_count=0,
        )
        self.session.add(request)
        await _mark_claimed(self.session, user.id, [s.id for s in skills])
        await self._send(user, proof, request, sender)
        await self.session.commit()
        return proof

    async def _check_recipient(self, user: User, email: str) -> None:
        if email.lower() == user.email.lower():
            raise RefereeError("A referee has to be someone else, not your own email address.")
        own_work = await self.session.scalar(
            select(EmploymentEmailCheck.id).where(
                EmploymentEmailCheck.user_id == user.id,
                func.lower(EmploymentEmailCheck.email) == email.lower(),
            )
        )
        if own_work:
            raise RefereeError("That's one of your own work addresses. Ask someone else.")
        if await self.session.get(EmailSuppression, email_hash(email)):
            raise RefereeError(
                "This person has asked not to receive requests from ResumeForge. "
                "Please choose a different referee."
            )
        awaiting = await self.session.scalar(
            select(func.count())
            .select_from(RefereeRequest)
            .where(RefereeRequest.user_id == user.id, RefereeRequest.status == "sent")
        )
        if (awaiting or 0) >= MAX_AWAITING:
            raise RefereeError(
                f"You have {MAX_AWAITING} requests waiting for an answer. Wait for a reply "
                "(or for one to expire) before asking someone else."
            )
        same = await self.session.scalar(
            select(RefereeRequest.id).where(
                RefereeRequest.user_id == user.id,
                RefereeRequest.referee_email == email,
                RefereeRequest.status == "sent",
            )
        )
        if same:
            raise RefereeError("You already have a request waiting with this referee.")
        recent = await self.session.scalar(
            select(func.count())
            .select_from(RefereeRequest)
            .where(
                RefereeRequest.referee_email == email,
                RefereeRequest.created_at >= _now() - RECIPIENT_WINDOW,
            )
        )
        if (recent or 0) >= MAX_PER_RECIPIENT:
            raise RefereeError(
                "This referee has received several requests recently. "
                "Please try again later or ask someone else."
            )

    async def _send(
        self, user: User, proof: Proof, request: RefereeRequest, sender: EmailSender
    ) -> None:
        token = secrets.token_urlsafe(32)
        now = _now()
        request.token_hash = _hash(token)
        request.expires_at = now + timedelta(days=LINK_DAYS)
        request.last_sent_at = now
        request.sent_count += 1
        request.status = "sent"
        try:
            await sender.send(_email(user, request, token))
        except EmailSendError:
            request.status = "failed"
            request.token_hash = None
            proof.status = ProofStatus.NEEDS_MORE
            self._decide(proof, "We couldn't send the email. Use Resend to try again.")
            return
        proof.status = ProofStatus.AWAITING_RESPONSE
        self._decide(proof, f"Waiting for {request.referee_name} to respond.")

    async def resend(self, user: User, proof_id: uuid.UUID, sender: EmailSender) -> Proof:
        await self.expire_stale(user.id)
        request = await self._for_proof(user, proof_id)
        if not request_info(request).can_resend:
            if request.sent_count >= MAX_SENDS:
                raise RefereeError(
                    "This request has already been sent the maximum number of times."
                )
            raise RefereeError("You can send a reminder 48 hours after the last email.")
        if await self.session.get(EmailSuppression, email_hash(request.referee_email)):
            raise RefereeError("This person has asked not to receive requests from ResumeForge.")
        proof = await self._proof(user, proof_id)
        await _mark_claimed(self.session, user.id, [s.id for s in proof.skills])
        await self._send(user, proof, request, sender)
        await self.session.commit()
        return proof

    async def info(self, user: User, proof_id: uuid.UUID) -> RefereeRequestInfo:
        return request_info(await self._for_proof(user, proof_id))

    async def _for_proof(self, user: User, proof_id: uuid.UUID) -> RefereeRequest:
        request = await self.session.scalar(
            select(RefereeRequest).where(
                RefereeRequest.proof_id == proof_id, RefereeRequest.user_id == user.id
            )
        )
        if request is None:
            raise RefereeError("Referee request not found.")
        return request

    async def _proof(self, user: User, proof_id: uuid.UUID) -> Proof:
        proof = await self.session.scalar(
            select(Proof)
            .where(Proof.id == proof_id, Proof.user_id == user.id)
            .options(selectinload(Proof.skills))
        )
        assert proof is not None
        return proof

    async def expire_stale(self, user_id: uuid.UUID | None = None) -> None:
        """Requests past their 14 days: the link stops working and the proof says so."""
        query = select(RefereeRequest).where(
            RefereeRequest.status == "sent", RefereeRequest.expires_at < _now()
        )
        if user_id is not None:
            query = query.where(RefereeRequest.user_id == user_id)
        stale = list(await self.session.scalars(query))
        for request in stale:
            request.status = "expired"
            request.token_hash = None
            proof = await self.session.scalar(
                select(Proof)
                .where(Proof.id == request.proof_id)
                .options(selectinload(Proof.skills))
            )
            if proof is not None:
                proof.status = ProofStatus.NEEDS_MORE
                self._decide(
                    proof,
                    f"The link expired before {request.referee_name} responded. "
                    "Send a reminder or ask someone else.",
                )
                await _settle_skills(
                    self.session, request.user_id, [s.id for s in proof.skills], set()
                )
        if stale:
            await self.session.commit()

    @staticmethod
    def _decide(proof: Proof, decision: str, level: str | None = None) -> None:
        report = (proof.ai_report or ProofReport()).model_copy(
            update={"decision": decision, "verification_level": level}
        )
        proof.ai_report = report  # a new object, so it's saved

    # --- the referee (no sign-in: the token is the credential) ----------------------------

    async def open(self, token: str) -> tuple[RefereeRequest, User]:
        await self.expire_stale()
        request = await self.session.scalar(
            select(RefereeRequest).where(RefereeRequest.token_hash == _hash(token))
        )
        if request is None or request.status != "sent" or not request.expires_at:
            raise RefereeLinkError
        if request.expires_at <= _now():
            raise RefereeLinkError
        user = await self.session.get(User, request.user_id)
        assert user is not None
        if request.opened_at is None:
            request.opened_at = _now()
            await self.session.commit()
        return request, user

    async def answer(
        self, token: str, answers: RefereeAnswers, sender: EmailSender | None = None
    ) -> None:
        request, user = await self.open(token)
        claimed = {s.id for s in request.claim.skills}
        if {a.skill_id for a in answers.skills} != claimed or len(answers.skills) != len(claimed):
            raise RefereeError("Answer yes or no for each skill.")
        now = _now()
        request.answers = answers
        request.responded_at = now
        request.status = "confirmed" if answers.role_confirmed else "declined"
        request.token_hash = None  # one-time
        proof = await self._proof(user, request.proof_id)
        name = request.referee_name
        verified: set[uuid.UUID] = set()
        if not answers.role_confirmed:
            proof.status = ProofStatus.REJECTED
            self._decide(proof, f"{name} couldn't confirm this role.")
        elif request.domain_kind == "free":
            proof.status = ProofStatus.NEEDS_MORE
            self._decide(
                proof,
                f"Confirmed by {name}, but from a personal email address, which we can't tie "
                f"to {request.referee_organization}. A referee with a work email can fully "
                "verify it.",
                "partially_verified",
            )
        elif not answers.dates_confirmed:
            proof.status = ProofStatus.NEEDS_MORE
            self._decide(
                proof,
                f"{name} confirmed part of what you listed. Check the details and ask again, "
                "or ask someone else.",
                "partially_verified",
            )
        else:
            verified = {a.skill_id for a in answers.skills if a.confirmed}
            names = {s.id: s.name for s in request.claim.skills}
            # Only what was verified (never which skills the referee said no to).
            proof.ai_report = (proof.ai_report or ProofReport()).model_copy(
                update={
                    "skills": [
                        SkillVerdict(skill_id=i, name=names[i], verdict="demonstrated", evidence=[])
                        for i in verified
                    ]
                }
            )
            proof.status = ProofStatus.VERIFIED
            self._decide(
                proof,
                f"Confirmed by {name} ({request.referee_role}, {request.referee_organization}) "
                f"on {now.strftime('%d %B %Y')}.",
                "verified",
            )
        await _settle_skills(self.session, user.id, list(claimed), verified)
        await self.session.commit()
        if sender is not None:
            await notify_proof_update(sender, user, proof)

    async def decline(
        self, token: str, body: RefereeDecline, sender: EmailSender | None = None
    ) -> None:
        request, user = await self.open(token)
        request.status = "declined"
        request.decline_reason = body.reason
        request.responded_at = _now()
        request.token_hash = None
        proof = await self._proof(user, request.proof_id)
        proof.status = ProofStatus.REJECTED
        self._decide(proof, f"{request.referee_name} couldn't confirm this.")
        await _settle_skills(self.session, user.id, [s.id for s in proof.skills], set())
        if body.stop_emails or body.reason == "not_me":
            key = email_hash(request.referee_email)
            if await self.session.get(EmailSuppression, key) is None:
                self.session.add(EmailSuppression(email_hash=key, reason=body.reason))
        await self.session.commit()
        if sender is not None:
            await notify_proof_update(sender, user, proof)
