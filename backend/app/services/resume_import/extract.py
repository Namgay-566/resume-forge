"""Validate an uploaded resume file and pull its text out (PDF via pdfplumber, DOCX via
python-docx). Pure functions: no DB, no AI."""

import zipfile
from enum import StrEnum
from io import BytesIO

import pdfplumber
from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from pdfminer.pdfparser import PDFSyntaxError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# A real resume has far more; anything below this is an image-only (scanned) PDF.
MIN_TEXT_CHARS = 50
# Resumes are short. Refuse rather than silently truncate what the AI sees.
MAX_TEXT_CHARS = 60_000
MAX_PDF_PAGES = 30  # text extraction is CPU-bound; a 5 MB PDF can hold thousands of pages

PDF_TYPES = {"application/pdf", "application/x-pdf"}
DOCX_TYPES = {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
# Some browsers/OSes send a generic type; the file signature check below decides then.
GENERIC_TYPES = {"application/octet-stream", "binary/octet-stream", ""}


class FileKind(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class ImportFileError(Exception):
    """User-facing problem with the uploaded file. `str(exc)` is safe to show."""


class UnsupportedFileError(ImportFileError):
    pass


class FileTooLargeError(ImportFileError):
    pass


class UnreadableDocumentError(ImportFileError):
    pass


class ScannedPdfError(ImportFileError):
    pass


class DocumentTooLongError(ImportFileError):
    pass


UNSUPPORTED_MESSAGE = "Upload a PDF or Word (.docx) file."
SCANNED_MESSAGE = (
    "This PDF has no selectable text. It looks like a scanned image or photo. "
    "Upload a text-based PDF (for example, exported from Word or Google Docs) or a .docx file."
)


def detect_kind(content_type: str | None, content: bytes) -> FileKind:
    """Trust the file's signature, and require the declared MIME type to agree with it."""
    declared = (content_type or "").split(";")[0].strip().lower()
    if content.startswith(b"%PDF-"):
        kind = FileKind.PDF
        allowed = PDF_TYPES
    elif content.startswith(b"PK\x03\x04") and _is_docx(content):
        kind = FileKind.DOCX
        allowed = DOCX_TYPES
    else:
        raise UnsupportedFileError(UNSUPPORTED_MESSAGE)

    if declared not in allowed | GENERIC_TYPES:
        raise UnsupportedFileError(UNSUPPORTED_MESSAGE)
    return kind


def _is_docx(content: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def extract_text(kind: FileKind, content: bytes) -> str:
    text = _extract_pdf(content) if kind is FileKind.PDF else _extract_docx(content)
    text = "\n".join(line.rstrip() for line in text.splitlines()).strip()

    visible = sum(1 for char in text if not char.isspace())
    if visible < MIN_TEXT_CHARS:
        if kind is FileKind.PDF:
            raise ScannedPdfError(SCANNED_MESSAGE)
        raise UnreadableDocumentError("This document is empty. Add your resume content and retry.")
    if len(text) > MAX_TEXT_CHARS:
        raise DocumentTooLongError(
            "This document is too long to be a resume. Upload a resume or CV under ~15 pages."
        )
    return text


def _extract_pdf(content: bytes) -> str:
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise DocumentTooLongError(
                    f"This document has over {MAX_PDF_PAGES} pages, which is too long for a "
                    "resume. Upload a resume or CV under ~15 pages."
                )
            return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
    except DocumentTooLongError:
        raise
    except (PDFSyntaxError, ValueError, KeyError, TypeError) as exc:
        raise UnreadableDocumentError(
            "This PDF couldn't be read. It may be damaged or password-protected."
        ) from exc
    except Exception as exc:  # pdfminer raises assorted internal errors on malformed files
        if exc.__class__.__module__.startswith(("pdfminer", "pdfplumber", "pypdfium2")):
            raise UnreadableDocumentError(
                "This PDF couldn't be read. It may be damaged or password-protected."
            ) from exc
        raise


def _extract_docx(content: bytes) -> str:
    try:
        document = Document(BytesIO(content))
    except Exception as exc:  # python-docx surfaces zip/xml errors of several types
        raise UnreadableDocumentError(
            "This Word file couldn't be read. It may be damaged."
        ) from exc

    parts: list[str] = []
    # Contact details often live in the page header of resume templates.
    for section in document.sections:
        parts.extend(p.text for p in section.header.paragraphs)
    parts.extend(_body_text(document))
    for section in document.sections:
        parts.extend(p.text for p in section.footer.paragraphs)
    return "\n".join(part for part in parts if part.strip())


def _body_text(document: DocxDocument) -> list[str]:
    """Paragraphs and table cells in reading order (many templates lay out with tables)."""
    lines: list[str] = []
    for element in document.element.body.iterchildren():
        if element.tag == qn("w:p"):
            lines.append("".join(t.text or "" for t in element.iter(qn("w:t"))))
        elif element.tag == qn("w:tbl"):
            for row in element.iter(qn("w:tr")):
                seen: list[str] = []
                for cell in row.iter(qn("w:tc")):
                    text = "\n".join(
                        "".join(t.text or "" for t in p.iter(qn("w:t")))
                        for p in cell.iter(qn("w:p"))
                    ).strip()
                    if text and text not in seen:  # merged cells repeat their text
                        seen.append(text)
                lines.extend(seen)
    return lines
