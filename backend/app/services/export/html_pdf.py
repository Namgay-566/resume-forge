import re
from functools import cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from weasyprint import HTML

from app.models.enums import PageSize, ResumeTemplate
from app.services.export.document import ResumeDocument

TEMPLATES_DIR = Path(__file__).parent / "templates"
CSS_DIR = TEMPLATES_DIR / "css"

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(enabled_extensions=("html", "j2")),
)


@cache
def template_css(template: ResumeTemplate) -> str:
    """Shared base layout + the template's typography (same files the live preview uses)."""
    base = (CSS_DIR / "base.css").read_text(encoding="utf-8")
    theme = (CSS_DIR / f"{template.value}.css").read_text(encoding="utf-8")
    return f"{base}\n{theme}"


# The template CSS sets A4; a later @page rule overrides only the size, keeping margins.
PAGE_SIZE_CSS = {PageSize.A4: "", PageSize.LETTER: "\n@page { size: letter; }"}


def render_html(
    doc: ResumeDocument, template: ResumeTemplate, title: str, page_size: PageSize = PageSize.A4
) -> str:
    return _env.get_template("resume.html.j2").render(
        doc=doc,
        template=template.value,
        title=title,
        # Our own static CSS file; marking it safe keeps quotes in font names intact.
        css=Markup(template_css(template) + PAGE_SIZE_CSS[page_size]),
    )


def render_pdf(html: str) -> bytes:
    pdf = HTML(string=html).write_pdf()
    assert pdf is not None
    return pdf


def count_pdf_pages(html: str) -> int:
    """Render HTML to PDF in memory and return the page count."""
    pdf = HTML(string=html).write_pdf()
    assert pdf is not None
    # Count occurrences of the PDF page object marker
    matches = re.findall(rb"/Type\s*/Page\b", pdf)
    return len(matches)