import asyncio
import re
import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.enums import ResumeTemplate, ResumeType
from app.services.export.document import build_document
from app.services.export.docx_builder import render_docx
from app.services.export.html_pdf import render_html, render_pdf
from app.services.resume_service import ResumeService
from app.services.suggestions.service import proof_links


class ExportFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


MEDIA_TYPES = {
    ExportFormat.PDF: "application/pdf",
    ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@dataclass(frozen=True)
class ExportedFile:
    content: bytes
    media_type: str
    filename: str


def export_filename(name: str, title: str, resume_type: ResumeType, fmt: ExportFormat) -> str:
    """'Ada Lovelace' -> 'Ada-Lovelace-Resume.pdf'. Keeps letters from any script."""
    base = re.sub(r"[^\w]+", "-", name or title).strip("-_") or "resume"
    label = "CV" if resume_type is ResumeType.CV else "Resume"
    return f"{base[:80]}-{label}.{fmt.value}"


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.resumes = ResumeService(session)

    async def export(
        self,
        user: User,
        resume_id: uuid.UUID,
        fmt: ExportFormat,
        template: ResumeTemplate | None = None,
    ) -> ExportedFile:
        resume = await self.resumes.get_resume(user, resume_id)
        chosen = template or resume.template
        # Proof-backed entries print their proof links as plain text (ATS-safe).
        doc = build_document(resume.data, resume.type, await proof_links(self.session, user.id))
        title = f"{doc.name or resume.title} - {'CV' if resume.type is ResumeType.CV else 'Resume'}"

        # Rendering is CPU-bound; keep it off the event loop.
        if fmt is ExportFormat.PDF:
            content = await asyncio.to_thread(
                render_pdf, render_html(doc, chosen, title, user.page_size)
            )
        else:
            content = await asyncio.to_thread(render_docx, doc, chosen, title, user.page_size)

        return ExportedFile(
            content=content,
            media_type=MEDIA_TYPES[fmt],
            filename=export_filename(doc.name, resume.title, resume.type, fmt),
        )
