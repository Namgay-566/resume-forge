"""Certificate checks: file validation, text/image preparation, recipient-name matching,
issuer-domain matching and the verification level. Pure functions (no DB, network or AI)."""

import io
import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import cache
from pathlib import Path
from urllib.parse import urlsplit

import pdfplumber
from docx import Document
from PIL import Image, UnidentifiedImageError

from app.schemas.proof_report import CertificateInfo, NameMatch, VerificationLevel

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_SIDE = 1568  # vision models downscale beyond this anyway
# A 5 MB PNG can declare a gigapixel canvas. Check dimensions before decoding.
MAX_IMAGE_PIXELS = 40_000_000
MIN_PDF_TEXT = 40

TYPES = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "png": "image/png",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
GENERIC = {"", "application/octet-stream", "binary/octet-stream"}


class CertificateFileError(Exception):
    """User-facing problem with the upload."""


def detect_file(
    content_type: str | None, data: bytes, *, allow_docx: bool = False, noun: str = "certificate"
) -> str:
    """Return 'pdf' | 'jpg' | 'png' (| 'docx') from the file's own bytes; the declared type
    must agree."""
    formats = "PDF, Word, JPG or PNG" if allow_docx else "PDF, JPG or PNG"
    if len(data) > MAX_UPLOAD_BYTES:
        raise CertificateFileError(f"That file is over 5 MB. Upload a smaller {formats} file.")
    if data.startswith(b"%PDF-"):
        kind = "pdf"
    elif data.startswith(b"\xff\xd8\xff"):
        kind = "jpg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "png"
    elif allow_docx and data.startswith(b"PK\x03\x04") and _is_docx(data):
        kind = "docx"
    else:
        raise CertificateFileError(f"Upload a {formats} {noun}.")
    declared = (content_type or "").split(";")[0].strip().lower()
    if (
        declared not in GENERIC
        and declared != TYPES[kind]
        and not (kind == "jpg" and declared == "image/jpg")
    ):
        raise CertificateFileError(f"Upload a {formats} {noun}.")
    return kind


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False


def read_docx(data: bytes) -> str:
    """Paragraphs and table cells of a Word document, in order."""
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:  # python-docx surfaces zip/xml errors of several types
        raise CertificateFileError("That Word file couldn't be read. It may be damaged.") from exc
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    text = "\n".join(part for part in parts if part.strip())
    if len(text.strip()) < MIN_PDF_TEXT:
        raise CertificateFileError("That Word file is empty.")
    return text


def prepare_image(data: bytes) -> bytes:
    """Decode, downscale and re-encode as JPEG. Re-encoding also drops EXIF/GPS metadata and
    anything smuggled after the image data."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size  # read from the header, nothing decoded yet
            if width * height > MAX_IMAGE_PIXELS:
                raise CertificateFileError("That image is too large. Upload a smaller photo.")
            
            image.load()
            image = image.convert("RGB")
            image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            
            # NEW: Check if the image is a solid color (blank page)
            # Calculate the variance of the image. A blank page has near-zero variance.
            extrema = image.convert("L").getextrema()
            if extrema[0] == extrema[1]:
                raise CertificateFileError(
                    "This image appears to be blank. Please upload a clear photo of your certificate or document."
                )
                
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=85)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise CertificateFileError("That image couldn't be read. Try another file.") from exc

@dataclass(frozen=True)
class PdfContent:
    text: str
    first_page_image: bytes | None  # rendered when the PDF has no text layer (scanned)


def read_pdf(data: bytes, pages: int = 5) -> PdfContent:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if not pdf.pages:
                raise CertificateFileError("That PDF has no pages.")
            text = "\n".join(page.extract_text() or "" for page in pdf.pages[:pages]).strip()
            if len(text) >= MIN_PDF_TEXT:
                return PdfContent(text=text, first_page_image=None)
            page = pdf.pages[0]
            # Pages can declare any size; keep the render within the image pixel budget.
            dpi = 150
            if (page.width / 72 * dpi) * (page.height / 72 * dpi) > MAX_IMAGE_PIXELS:
                raise CertificateFileError("That PDF page is too large to read.")
            rendered = page.to_image(resolution=dpi).original
            out = io.BytesIO()
            rendered.convert("RGB").save(out, format="PNG")
            return PdfContent(text=text, first_page_image=prepare_image(out.getvalue()))
    except CertificateFileError:
        raise
    except Exception as exc:  # pdfminer raises assorted errors on broken/encrypted files
        raise CertificateFileError(
            "That PDF couldn't be read. It may be damaged or password-protected."
        ) from exc


# --- recipient name ---------------------------------------------------------------------


def _name_tokens(name: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return [t for t in re.split(r"[^a-z]+", folded) if len(t) > 1]


def match_name(
    on_certificate: str | None,
    account_name: str,
    *,
    document: str = "certificate",
    relation: str = "is issued to",
) -> NameMatch:
    """match: same person; partial: plausibly the same (nickname, missing middle name, typo);
    mismatch: clearly someone else. Only a mismatch leads to rejection.
    `document` and `relation` word the details ("The letter is about ...")."""
    if not on_certificate or not _name_tokens(on_certificate):
        return NameMatch(status="missing", detail=f"No name could be read from the {document}.")
    cert, mine = _name_tokens(on_certificate), _name_tokens(account_name)
    if not mine:
        return NameMatch(
            status="missing", detail=f"Add your full name to your account to match {document}s."
        )
    shorter, longer = sorted([set(cert), set(mine)], key=len)
    ratio = SequenceMatcher(None, " ".join(cert), " ".join(mine)).ratio()
    # A lone first name on either side is too weak to count as a full match.
    if (shorter <= longer and (len(shorter) >= 2 or len(longer) == 1)) or ratio >= 0.9:
        return NameMatch(status="match", detail=f"“{on_certificate}” matches your name.")
    shared = set(cert) & set(mine)
    # "Sam" / "Samuel", "Liz" / "Elizabeth" is out of reach, but prefixes cover most nicknames.
    prefix = any(
        a.startswith(b) or b.startswith(a) for a in cert for b in mine if min(len(a), len(b)) >= 3
    )
    if shared or prefix or ratio >= 0.6:
        return NameMatch(
            status="partial", detail=f"“{on_certificate}” is similar to your name ({account_name})."
        )
    return NameMatch(
        status="mismatch",
        detail=f"The {document} {relation} “{on_certificate}”, not {account_name}.",
    )


# --- issuer domains ------------------------------------------------------------------------

ISSUERS_PATH = Path(__file__).with_name("issuers.json")


@dataclass(frozen=True)
class IssuerData:
    """Where issuers' verification pages and licensing bodies' public registers live."""

    issuers: dict[str, set[str]]
    credential_platforms: set[str]
    registers: dict[str, set[str]]
    government_suffixes: tuple[str, ...]


@cache
def issuer_data() -> IssuerData:
    raw = json.loads(ISSUERS_PATH.read_text(encoding="utf-8"))
    return IssuerData(
        issuers={k: set(v) for k, v in raw["issuers"].items()},
        credential_platforms=set(raw["credential_platforms"]),
        registers={k: set(v) for k, v in raw["registers"].items()},
        government_suffixes=tuple(raw["government_suffixes"]),
    )


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _host_in(host: str, domains: set[str]) -> bool:
    return any(host == d or host.endswith(f".{d}") for d in domains)


def _known_domains(table: dict[str, set[str]], name: str | None) -> set[str]:
    if not name:
        return set()
    lowered = name.lower()
    return {d for key, domains in table.items() if key in lowered for d in domains}


def issuer_domains(issuer: str | None) -> set[str]:
    return _known_domains(issuer_data().issuers, issuer)


def trusted_host(url: str, issuer: str | None) -> bool:
    host = _host(url)
    if not host:
        return False
    if _host_in(host, issuer_data().credential_platforms | issuer_domains(issuer)):
        return True
    # Unknown issuers: the domain's main label is a word of the issuer's name
    # ("Acme Academy" -> academy.acme.io counts, acme-certs.xyz doesn't).
    main_label = host.split(".")[-2] if "." in host else host
    return len(main_label) >= 4 and main_label in set(_name_tokens(issuer or ""))


def trusted_register(url: str, issuing_body: str | None) -> bool:
    """A public register we can trust for a licence: the licensing body's known register,
    a government domain, or (as for certificates) a domain named after the body."""
    host = _host(url)
    if not host:
        return False
    data = issuer_data()
    if _host_in(host, _known_domains(data.registers, issuing_body)):
        return True
    if any(host.endswith(suffix) for suffix in data.government_suffixes):
        return True
    return trusted_host(url, issuing_body)


def normalize_for_search(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKD", text).lower())


def url_appears_in(url: str | None, haystack: str) -> bool:
    """Certificates often print links without the scheme ("coursera.org/verify/ABC"), while the
    extracted URL has one; compare without scheme and "www."."""
    if not url:
        return False
    bare = re.sub(r"^(?:https?://)?(?:www\.)?", "", url.strip(), flags=re.IGNORECASE).rstrip("/")
    return appears_in(bare, haystack)


def appears_in(needle: str | None, haystack: str) -> bool:
    """Whitespace/punctuation-insensitive containment (credential IDs, URLs, names)."""
    if not needle:
        return False
    n = normalize_for_search(needle)
    return len(n) >= 4 and n in normalize_for_search(haystack)


# --- decision ------------------------------------------------------------------------------


@dataclass(frozen=True)
class CertificateOutcome:
    level: VerificationLevel | None  # None = rejected
    reason: str


def decide_certificate(info: CertificateInfo) -> CertificateOutcome:
    if not info.is_certificate:
        return CertificateOutcome(None, "This file doesn't look like a certificate.")
    name = info.name_match
    if name and name.status == "mismatch":
        return CertificateOutcome(None, name.detail + " Upload a certificate issued to you.")
    check = info.url_check
    if check and check.reachable and check.on_trusted_domain:
        if check.details_on_page and name and name.status == "match":
            return CertificateOutcome("verified", "Verified on the issuer's site.")
        why = (
            "the page doesn't show your name or credential ID (it may need a login or JavaScript)"
            if not check.details_on_page
            else "the recipient name is only a partial match"
        )
        return CertificateOutcome("partially_verified", f"The verification link works, but {why}.")
    if check and check.reachable and not check.on_trusted_domain:
        return CertificateOutcome(
            "self_reported",
            "The verification link isn't on the issuer's website or a known credential "
            "platform, so it can't confirm the certificate.",
        )
    if check and not check.reachable:
        return CertificateOutcome(
            "self_reported", f"The verification link couldn't be checked: {check.detail}"
        )
    if info.credential_id:
        return CertificateOutcome(
            "self_reported",
            f"Recorded as self-reported. It has a credential ID ({info.credential_id}) employers "
            "can check with the issuer, but no verification link.",
        )
    return CertificateOutcome(
        "self_reported", "Recorded as self-reported: there's no verification link or credential ID."
    )
