"""Outgoing email behind one small interface. Messages are plain text plus a minimal HTML
part built from escaped text, so nothing a user typed can become markup or a hidden link.

EMAIL_BACKEND=console logs messages (dev: the link is in the backend log); smtp sends them.
Tests override `get_email_sender` with an in-memory outbox."""

import asyncio
import html
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import make_msgid
from typing import Protocol

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    pass


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    # Where replies go (never the candidate: their address isn't shared with the referee).
    reply_to: str | None = None


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


def _mime(message: EmailMessage, settings: Settings) -> MimeMessage:
    mime = MimeMessage()
    mime["From"] = settings.email_from
    mime["To"] = message.to
    mime["Subject"] = message.subject.replace("\r", " ").replace("\n", " ")[:200]
    mime["Message-ID"] = make_msgid(domain="resumeforge")
    if message.reply_to:
        mime["Reply-To"] = message.reply_to
    mime["Auto-Submitted"] = "auto-generated"
    mime.set_content(message.text)
    paragraphs = "".join(
        f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in message.text.split("\n\n")
    )
    mime.add_alternative(
        f'<!doctype html><html><body style="font-family:sans-serif;line-height:1.5">'
        f"{paragraphs}</body></html>",
        subtype="html",
    )
    return mime


class ConsoleEmailSender:
    """Development: writes the message to the log instead of sending it."""

    async def send(self, message: EmailMessage) -> None:
        logger.warning(
            "EMAIL (console backend, not sent)\nTo: %s\nSubject: %s\n\n%s",
            message.to,
            message.subject,
            message.text,
        )


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _send_sync(self, mime: MimeMessage) -> None:
        s = self.settings
        context = ssl.create_default_context()
        smtp: smtplib.SMTP
        if s.smtp_security == "ssl":
            smtp = smtplib.SMTP_SSL(
                s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds, context=context
            )
        else:
            smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds)
        with smtp:
            if s.smtp_security == "starttls":
                smtp.starttls(context=context)
            if s.smtp_username and s.smtp_password:
                smtp.login(s.smtp_username, s.smtp_password.get_secret_value())
            smtp.send_message(mime)

    async def send(self, message: EmailMessage) -> None:
        try:
            await asyncio.to_thread(self._send_sync, _mime(message, self.settings))
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("Email to %s failed: %s", message.to.split("@")[-1], exc)
            raise EmailSendError("The email couldn't be sent. Please try again later.") from exc


class MemoryEmailSender:
    """Tests: keeps every message."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        _mime(message, get_settings())  # fails like SMTP would on a malformed message
        self.outbox.append(message)


def get_email_sender() -> EmailSender:
    """FastAPI dependency. Tests override it."""
    settings = get_settings()
    if settings.email_backend == "smtp":
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()
