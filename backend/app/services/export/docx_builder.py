"""DOCX export with the same structure as the PDF. Uses Word's own Heading/List styles
(which ATS parsers understand) and no tables, text boxes, images, headers or footers."""

from dataclasses import dataclass
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from docx.text.paragraph import Paragraph

from app.models.enums import PageSize, ResumeTemplate
from app.services.export.document import ResumeDocument

BLACK = RGBColor(0x11, 0x11, 0x11)
GREY = RGBColor(0x33, 0x33, 0x33)
NAVY = RGBColor(0x1F, 0x3A, 0x5F)
# Width and height, same as the PDF's @page size.
PAGE_SIZES = {
    PageSize.A4: (Mm(210), Mm(297)),
    PageSize.LETTER: (Mm(215.9), Mm(279.4)),
}


@dataclass(frozen=True)
class DocxStyle:
    """Mirrors the template CSS in templates/css/*.css."""

    font: str
    size: float
    name_size: float
    heading_size: float
    margin_y_mm: float
    margin_x_mm: float
    line_spacing: float
    section_gap: float
    entry_gap: float
    center_identity: bool
    heading_rule: bool
    heading_color: RGBColor


STYLES = {
    ResumeTemplate.CLASSIC: DocxStyle(
        "Times New Roman", 11, 20, 11, 16, 18, 1.15, 10, 7, True, True, BLACK
    ),
    ResumeTemplate.MODERN_MINIMAL: DocxStyle(
        "Arial", 10.5, 22, 9.5, 18, 20, 1.2, 13, 8, False, False, GREY
    ),
    ResumeTemplate.COMPACT: DocxStyle(
        "Arial", 9.5, 16, 9.5, 12, 14, 1.05, 7, 4, False, True, BLACK
    ),
    ResumeTemplate.CONSERVATIVE: DocxStyle(
        "Georgia", 10.5, 17, 10, 20, 22, 1.15, 11, 7, True, True, BLACK
    ),
    ResumeTemplate.PROFESSIONAL: DocxStyle(
        "Arial", 10.5, 23, 10.5, 16, 18, 1.2, 12, 8, False, True, NAVY
    ),
    ResumeTemplate.ACADEMIC: DocxStyle(
        "Times New Roman", 11, 18, 12, 22, 22, 1.25, 14, 6, False, True, BLACK
    ),
}


def _set_font(style_or_run_font: object, name: str) -> None:
    font = style_or_run_font.font  # type: ignore[attr-defined]
    font.name = name
    # Also set the East Asian slot, otherwise Word may substitute another font.
    rpr = style_or_run_font.element.get_or_add_rPr()  # type: ignore[attr-defined]
    rpr.get_or_add_rFonts().set(qn("w:eastAsia"), name)


def _bottom_border(paragraph_style: object) -> None:
    ppr = paragraph_style.element.get_or_add_pPr()  # type: ignore[attr-defined]
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for key, value in {"w:val": "single", "w:sz": "6", "w:space": "1", "w:color": "111111"}.items():
        bottom.set(qn(key), value)
    borders.append(bottom)
    ppr.append(borders)


def _configure_styles(document: Document, style: DocxStyle) -> None:  # type: ignore[valid-type]
    normal = document.styles["Normal"]
    _set_font(normal, style.font)
    normal.font.size = Pt(style.size)
    normal.font.color.rgb = BLACK
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = style.line_spacing

    heading = document.styles["Heading 1"]
    _set_font(heading, style.font)
    heading.font.size = Pt(style.heading_size)
    heading.font.bold = True
    heading.font.italic = False
    heading.font.all_caps = True
    heading.font.color.rgb = style.heading_color
    heading.paragraph_format.space_before = Pt(style.section_gap)
    heading.paragraph_format.space_after = Pt(3)
    heading.paragraph_format.keep_with_next = True
    if style.heading_rule:
        _bottom_border(heading)

    bullets = document.styles["List Bullet"]
    _set_font(bullets, style.font)
    bullets.font.size = Pt(style.size)


def _paragraph(document: Document, text: str = "", **run_format: object) -> Paragraph:  # type: ignore[valid-type]
    paragraph = document.add_paragraph()
    if text:
        run = paragraph.add_run(text)
        for key, value in run_format.items():
            setattr(run.font if key in {"size", "color"} else run, key, value)
    return paragraph


def render_docx(
    doc: ResumeDocument, template: ResumeTemplate, title: str, page_size: PageSize = PageSize.A4
) -> bytes:
    style = STYLES[template]
    document = Document()
    section = document.sections[0]
    page_width, page_height = PAGE_SIZES[page_size]
    section.page_width, section.page_height = page_width, page_height
    section.top_margin = section.bottom_margin = Mm(style.margin_y_mm)
    section.left_margin = section.right_margin = Mm(style.margin_x_mm)
    text_width = page_width - 2 * Mm(style.margin_x_mm)
    _configure_styles(document, style)

    document.core_properties.title = title
    document.core_properties.author = doc.name

    align = WD_ALIGN_PARAGRAPH.CENTER if style.center_identity else WD_ALIGN_PARAGRAPH.LEFT
    if doc.name:
        name = _paragraph(document, doc.name, bold=True, size=Pt(style.name_size))
        name.alignment = align
    if doc.headline:
        _paragraph(document, doc.headline).alignment = align
    if doc.contact:
        _paragraph(document, " | ".join(doc.contact), size=Pt(style.size * 0.92)).alignment = align

    for block in doc.sections:
        document.add_heading(block.heading, level=1)
        if block.text:
            _paragraph(document, block.text)
        for line in block.extra:
            _paragraph(document, line)
        for index, entry in enumerate(block.entries):
            head = _paragraph(document)
            head.paragraph_format.keep_with_next = True
            if index:
                head.paragraph_format.space_before = Pt(style.entry_gap)
            # Date sits on the same line, pushed right with a tab stop (not a table).
            head.paragraph_format.tab_stops.add_tab_stop(text_width, WD_TAB_ALIGNMENT.RIGHT)
            head.add_run(entry.title).bold = True
            if entry.date:
                head.add_run(f"\t{entry.date}")
            if entry.subtitle:
                _paragraph(document, entry.subtitle, italic=True)
            if entry.link:
                _paragraph(document, entry.link)
            if entry.description:
                _paragraph(document, entry.description)
            for bullet in entry.bullets:
                document.add_paragraph(bullet, style="List Bullet")
            if entry.tools:
                _paragraph(document, f"Tools: {', '.join(entry.tools)}", size=Pt(style.size * 0.92))
        for item in block.items:
            document.add_paragraph(item, style="List Bullet")

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
