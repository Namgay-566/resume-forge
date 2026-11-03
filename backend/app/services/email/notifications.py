"""Emails to the account holder: proof results (optional, see Settings) and security notices
(always sent: a password or email change the user didn't make must reach them).

Sending never fails the action that triggered it; a failed email is only logged."""

import logging

from app.core.config import get_settings
from app.models import Proof, User
from app.models.enums import ProofStatus
from app.services.email.sender import EmailMessage, EmailSender, EmailSendError
from app.services.proofs.rules import get_rules

logger = logging.getLogger(__name__)

# Placeholder addresses given to OAuth accounts that shared no email. Nothing can be sent.
_UNDELIVERABLE_SUFFIXES = ("@users.noreply.github.com", ".invalid")


def can_email(address: str) -> bool:
    return not address.lower().endswith(_UNDELIVERABLE_SUFFIXES)


async def send_quietly(sender: EmailSender, message: EmailMessage) -> bool:
    if not can_email(message.to):
        return False
    try:
        await sender.send(message)
    except EmailSendError:
        logger.warning("Notification email not sent (%s)", message.subject)
        return False
    return True


def _sign_off(text: str) -> str:
    settings_url = f"{get_settings().frontend_url}/settings"
    return f"{text}\n\nChange which emails you get: {settings_url}\n\nResumeForge"


_PROOF_OUTCOMES = {
    ProofStatus.VERIFIED: (
        "is verified",
        "It now counts as verified evidence, and you can add it to your resume.",
    ),
    ProofStatus.NEEDS_MORE: (
        "needs a little more",
        "Open it to see what's missing and how to fix it.",
    ),
    ProofStatus.REJECTED: (
        "couldn't be verified",
        "Open it to see why, and what kind of proof would work instead.",
    ),
}


def proof_update_message(user: User, proof: Proof) -> EmailMessage | None:
    outcome = _PROOF_OUTCOMES.get(proof.status)
    if outcome is None:
        return None
    headline, next_step = outcome
    label = get_rules().types[proof.type].label
    decision = proof.ai_report.decision if proof.ai_report and proof.ai_report.decision else ""
    link = f"{get_settings().frontend_url}/proof-vault/{proof.id}"
    body = f"Hi {user.name},\n\nYour proof ({label}) {headline}."
    if decision:
        body += f"\n\n{decision}"
    body += f"\n\n{next_step}\n{link}"
    return EmailMessage(
        to=user.email,
        subject=f"Your proof {headline}",
        text=_sign_off(body),
    )


async def notify_proof_update(sender: EmailSender, user: User, proof: Proof) -> None:
    """After an analysis finishes or a referee answers, if the user wants these emails."""
    if not user.email_proof_updates:
        return
    if (message := proof_update_message(user, proof)) is not None:
        await send_quietly(sender, message)


async def notify_security(sender: EmailSender, to: str, name: str, what: str) -> None:
    """`what` completes "…was changed" style sentences, e.g. "Your password was changed"."""
    text = (
        f"Hi {name},\n\n{what}.\n\n"
        "If this was you, there's nothing to do. If it wasn't, sign in straight away, change "
        'your password and choose "Sign out of all devices" in Settings.'
    )
    await send_quietly(
        sender,
        EmailMessage(to=to, subject="Security notice for your ResumeForge account", text=text),
    )
