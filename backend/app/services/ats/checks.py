"""Deterministic ATS checks. Pure Python on ResumeData: no AI, no database.

Every check returns pass/warn/fail with a human-readable reason and, when it can, the
editor location to fix it, so the score is fully explainable.

The resume's experience level (if set) adjusts expectations: a student isn't failed for
having no work history yet, and a senior isn't held to one page.
"""

import re
import unicodedata
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from app.models.enums import PageSize, ResumeTemplate
from app.services.export.html_pdf import count_pdf_pages, render_html

from app.models.enums import ExperienceLevel, ResumeType
from app.schemas.ats import CategoryKey, CheckResult, CheckStatus, Location
from app.schemas.resume_data import ResumeData
from app.schemas.section_kind import SectionKind
from app.services.export.document import build_document
from app.services.sections.catalog import get_catalog
from app.services.sections.layout import RoleSections, section_requirements

# Strong openers recruiters and ATS rankers look for (lowercase, past or present tense).
ACTION_VERBS = frozenset(
    """
    accelerated achieved added administered advised analysed analyzed architected assembled
    automated boosted built captured championed coached collaborated completed configured
    consolidated constructed contributed converted coordinated created cut debugged decreased
    defined delivered deployed designed developed devised diagnosed directed discovered doubled
    drafted drove eliminated enabled engineered enhanced established evaluated executed expanded
    expedited facilitated fixed formulated founded generated grew guided halved identified
    implemented improved increased influenced initiated innovated installed instituted integrated
    introduced invented launched led maintained managed mentored migrated minimised minimized
    modernised modernized monitored negotiated optimised optimized orchestrated organised
    organized overhauled owned partnered piloted pioneered planned presented prioritised
    prioritized produced programmed prototyped published raised rebuilt recruited redesigned
    reduced refactored remodeled replaced resolved restructured revamped reviewed saved scaled
    secured shipped simplified solved spearheaded standardised standardized streamlined
    strengthened supervised taught tested trained transformed tripled troubleshot unified upgraded
    validated wrote
    """.split()
) | frozenset(
    # Strong openers from other fields: care, teaching, sales, finance, hospitality, trades,
    # law, research and service work.
    """
    assessed triaged monitored nursed cared treated diagnosed screened vaccinated dispensed
    counselled counseled supported rehabilitated safeguarded escalated documented charted
    tutored instructed differentiated assessed marked graded supervised invigilated
    prospected closed sold upsold negotiated retained onboarded pitched converted exceeded
    reconciled audited budgeted forecast forecasted invoiced processed filed prepared
    cooked baked served hosted catered welcomed greeted cleaned inspected
    repaired maintained wired plumbed welded fitted fabricated serviced surveyed drafted
    litigated advocated represented researched analysed published presented authored
    coordinated scheduled handled dispatched delivered stocked sourced purchased procured
    recruited hired interviewed coached resolved answered assisted volunteered fundraised
    """.split()
)
WEAK_OPENERS = (
    "responsible for",
    "worked on",
    "helped",
    "assisted",
    "duties included",
    "tasked with",
    "participated in",
    "involved in",
    "in charge of",
    "handled",
)
_WORD = re.compile(r"[A-Za-z][A-Za-z'+#.-]*")
# A number that isn't just a year: 40%, $2M, 3x, 1,200, 15 users, 0.5s ...
_QUANTIFIED = re.compile(
    r"(\d+(\.\d+)?\s?(%|x\b|k\b|m\b|b\b|ms\b|s\b|million|billion|thousand))|([$€£¥]\s?\d)"
    r"|(\b\d{1,3}(,\d{3})+\b)|(\b(?!(19|20)\d{2}\b)\d+(\.\d+)?\b)",
    re.IGNORECASE,
)


EARLY_CAREER = frozenset({ExperienceLevel.STUDENT, ExperienceLevel.ENTRY})


@dataclass(frozen=True)
class Bullet:
    text: str
    section: str  # a section id
    item_index: int


def _bullets(data: ResumeData) -> list[Bullet]:
    out = [Bullet(b, "experience", i) for i, e in enumerate(data.experience) for b in e.bullets]
    out += [Bullet(b, "projects", i) for i, p in enumerate(data.projects) for b in p.bullets]
    # Placements, volunteering, research... are written like jobs and read the same way.
    for section in data.extra_sections():
        for i, entry in enumerate(section.entries):
            out += [Bullet(b, section.id, i) for b in entry.bullets]
    return out


def _location(data: ResumeData, section_id: str, item_index: int | None = None) -> Location:
    """Location in the editor, labelled with the heading when it's not a core section."""
    config = next((s for s in data.sections if s.id == section_id), None)
    label = None
    if config is not None and (config.title or not config.kind.is_core):
        label = config.title or get_catalog().heading(config.kind)
    return Location(section=section_id, item_index=item_index, label=label)


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def _first_word(text: str) -> str:
    words = _words(text)
    return words[0].lower() if words else ""


def _is_action_led(text: str) -> bool:
    return _first_word(text) in ACTION_VERBS


def _is_quantified(text: str) -> bool:
    return bool(_QUANTIFIED.search(text))


def _ratio_status(ratio: float, good: float, ok: float) -> CheckStatus:
    return "pass" if ratio >= good else "warn" if ratio >= ok else "fail"


def _this_month() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def _months(ym: str) -> int:
    year, month = ym.split("-")
    return int(year) * 12 + int(month)


def years_of_experience(data: ResumeData) -> float:
    """Total employed time from experience dates (and sections that count as work, such as
    clinical or teaching experience), merging overlapping roles."""
    now = _months(_this_month())
    catalog = get_catalog()
    dated = [*data.experience]
    dated += [
        entry
        for s in data.extra_sections()
        if catalog.spec(s.kind).counts_as_experience
        for entry in s.entries
    ]
    spans = sorted(
        (_months(e.start_date), now if e.is_current or not e.end_date else _months(e.end_date))
        for e in dated
        if e.start_date
    )
    total, current_start, current_end = 0, None, None
    for start, end in spans:
        if current_end is None or start > current_end:
            if current_end is not None and current_start is not None:
                total += current_end - current_start
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_end is not None and current_start is not None:
        total += current_end - current_start
    return round(total / 12, 1)


def resume_word_count(data: ResumeData, resume_type: ResumeType) -> int:
    doc = build_document(data, resume_type)
    parts = [doc.name, doc.headline, *doc.contact]
    for section in doc.sections:
        parts += [section.heading, section.text, *section.items]
        for e in section.entries:
            parts += [e.title, e.date, e.subtitle, e.link, e.description, *e.bullets, *e.tools]
    return sum(len(_words(p)) for p in parts if p)


def _check(
    id: str,
    category: CategoryKey,
    status: CheckStatus,
    title: str,
    detail: str,
    weight: float,
    location: Location | None = None,
) -> CheckResult:
    return CheckResult(
        id=id,
        category=category,
        status=status,
        title=title,
        detail=detail,
        weight=weight,
        location=location,
    )


# --- Completeness -------------------------------------------------------------------


def check_sections(
    data: ResumeData,
    resume_type: ResumeType,
    level: ExperienceLevel | None = None,
    role: RoleSections | None = None,
) -> Iterator[CheckResult]:
    """Required sections come from the catalog, the career stage and the target role: a
    student's volunteering counts as experience, a nurse needs a licence section, a
    researcher's CV needs publications."""
    for req in section_requirements(level, role):
        present = next((k for k in req.kinds if data.has_content(k)), None)
        listed = next((s.id for s in data.sections if s.kind in req.kinds), None)
        target = present or listed or req.kinds[0]
        yield _check(
            f"section_{req.id}",
            "completeness",
            "pass" if present else req.severity,
            f"{req.label} section present" if present else f"Missing {req.label} section",
            f"Standard '{req.label}' heading found." if present else req.advice,
            weight=3,
            location=_location(data, target),
        )


def check_headings(data: ResumeData) -> Iterator[CheckResult]:
    """Renamed sections must still use a heading ATS parsers recognise."""
    catalog = get_catalog()
    odd = [
        s
        for s in data.sections
        if s.title
        and s.kind is not SectionKind.CUSTOM
        and " ".join(s.title.lower().split())
        not in {*catalog.spec(s.kind).standard_headings, catalog.heading(s.kind).lower()}
    ]
    if not any(s.title for s in data.sections):
        return
    first = odd[0] if odd else None
    yield _check(
        "standard_headings",
        "formatting",
        "warn" if odd else "pass",
        "Section headings are standard" if not odd else "Some headings may confuse an ATS",
        "Every renamed section still uses a heading ATS systems recognise."
        if not odd
        else f"'{first.title}' isn't a heading ATS systems look for. Try "  # type: ignore[union-attr]
        f"'{catalog.heading(first.kind)}' instead.",  # type: ignore[union-attr]
        weight=1,
        location=_location(data, first.id) if first else None,
    )


def check_contact(data: ResumeData) -> Iterator[CheckResult]:
    p = data.personal_info
    essentials = {
        "full name": p.full_name,
        "email": p.email,
        "phone": p.phone,
        "location": p.location,
    }
    missing = [label for label, value in essentials.items() if not value]
    yield _check(
        "contact_essentials",
        "completeness",
        "pass"
        if not missing
        else "fail"
        if ("email" in missing or "full name" in missing)
        else "warn",
        "Contact details complete"
        if not missing
        else f"Missing contact details: {', '.join(missing)}",
        "Name, email, phone and location are all present."
        if not missing
        else "Recruiters and ATS need a name, email, phone and city/country to contact you.",
        weight=3,
        location=Location(section="personal_info"),
    )
    profiles = [link.url for link in p.profile_links]
    yield _check(
        "contact_profiles",
        "completeness",
        "pass" if profiles else "warn",
        "Profile link included" if profiles else "No profile or portfolio link",
        "Links let recruiters verify your work."
        if profiles
        else "Add a LinkedIn profile, or a portfolio or website that shows your work.",
        weight=1,
        location=Location(section="personal_info"),
    )
    yield _check(
        "headline",
        "completeness",
        "pass" if p.headline.strip() else "warn",
        "Headline present" if p.headline.strip() else "No headline under your name",
        "A headline with the job title you want (e.g. 'Registered Nurse') matches what "
        "recruiters search for."
        if not p.headline.strip()
        else f"'{p.headline}'",
        weight=1,
        location=Location(section="personal_info"),
    )


def check_skills_depth(data: ResumeData) -> Iterator[CheckResult]:
    count = len(data.skills)
    if count == 0:
        return  # already reported by check_sections
    yield _check(
        "skills_depth",
        "completeness",
        "pass" if count >= 6 else "warn",
        f"{count} skills listed" if count >= 6 else f"Only {count} skills listed",
        "Good coverage for keyword matching."
        if count >= 6
        else "List 6-15 specific skills (tools, methods, certifications) the role asks for.",
        weight=1,
        location=Location(section="skills"),
    )


# --- Formatting -------------------------------------------------------------------------


def check_dates(data: ResumeData) -> Iterator[CheckResult]:
    undated = [i for i, e in enumerate(data.experience) if not e.start_date]
    undated_edu = [i for i, e in enumerate(data.education) if not (e.start_date or e.end_date)]
    open_ended = [
        i
        for i, e in enumerate(data.experience)
        if e.start_date and not e.end_date and not e.is_current
    ]
    problems = len(undated) + len(undated_edu) + len(open_ended)
    first: Location | None = None
    if undated or open_ended:
        first = Location(section="experience", item_index=min(undated + open_ended))
    elif undated_edu:
        first = Location(section="education", item_index=undated_edu[0])
    detail_parts = []
    if undated:
        detail_parts.append(f"{len(undated)} position(s) have no start date")
    if open_ended:
        detail_parts.append(
            f"{len(open_ended)} position(s) have no end date and aren't marked current"
        )
    if undated_edu:
        detail_parts.append(f"{len(undated_edu)} education entr(ies) have no dates")
    yield _check(
        "dates_complete",
        "formatting",
        "pass" if not problems else "fail" if undated else "warn",
        "Every entry is dated" if not problems else "Some entries are missing dates",
        "ATS calculate your experience from dates, so every role needs them."
        if not problems
        else "; ".join(detail_parts) + ".",
        weight=3,
        location=first,
    )

    now = _this_month()
    future = [i for i, e in enumerate(data.experience) if e.start_date and e.start_date > now]
    if future:
        yield _check(
            "dates_future",
            "formatting",
            "warn",
            "A start date is in the future",
            "Check the dates. Future start dates look like typos to recruiters.",
            weight=1,
            location=Location(section="experience", item_index=future[0]),
        )

    starts = [(i, e.start_date) for i, e in enumerate(data.experience) if e.start_date]
    unordered = next((b[0] for a, b in zip(starts, starts[1:], strict=False) if b[1] > a[1]), None)
    if len(starts) > 1:
        yield _check(
            "reverse_chronological",
            "formatting",
            "pass" if unordered is None else "warn",
            "Experience is most-recent-first"
            if unordered is None
            else "Experience isn't in reverse-chronological order",
            "ATS and recruiters expect your latest role first."
            if unordered is not None
            else "Latest role comes first.",
            weight=2,
            location=Location(section="experience", item_index=unordered)
            if unordered is not None
            else None,
        )


def check_bullet_length(data: ResumeData) -> Iterator[CheckResult]:
    bullets = _bullets(data)
    if not bullets:
        return
    short = [b for b in bullets if len(_words(b.text)) < 6]
    long = [b for b in bullets if len(_words(b.text)) > 35 or len(b.text) > 230]
    bad = short + long
    ratio = 1 - len(bad) / len(bullets)
    parts = []
    if short:
        parts.append(f"{len(short)} too short (under 6 words)")
    if long:
        parts.append(f"{len(long)} too long (over ~2 lines)")
    yield _check(
        "bullet_length",
        "formatting",
        _ratio_status(ratio, 0.9, 0.7),
        "Bullets are a readable length" if not bad else "Some bullets are too short or too long",
        "Aim for one to two lines per bullet: " + ", ".join(parts) + "."
        if bad
        else "All bullets are one to two lines.",
        weight=2,
        location=_location(data, bad[0].section, bad[0].item_index) if bad else None,
    )


def check_length(
    data: ResumeData, 
    resume_type: ResumeType, 
    level: ExperienceLevel | None = None,
    template: ResumeTemplate = ResumeTemplate.CLASSIC,
    page_size: PageSize = PageSize.A4
) -> Iterator[CheckResult]:
    # 1. Render the exact PDF the user sees
    html = render_html(build_document(data, resume_type), template, data.personal_info.full_name, page_size)
    pages = count_pdf_pages(html)
    
    # 2. Also grab the word count for the detail text
    words = resume_word_count(data, resume_type)
    years = years_of_experience(data)
    
    if words < 150:
        yield _check(
            "length",
            "formatting",
            "fail",
            "Resume is very thin",
            f"About {words} words. Add detail to your experience, projects and skills.",
            weight=2,
            location=Location(section="experience"),
        )
        return

    if resume_type is ResumeType.CV:
        yield _check(
            "length",
            "formatting",
            "pass",
            "Length suits a CV",
            f"About {words} words across {pages} page(s). CVs may run longer than resumes.",
            weight=2,
        )
        return

    # 3. Determine the limit based on experience
    if level in EARLY_CAREER:
        years = min(years, 2)
    elif level is ExperienceLevel.SENIOR:
        years = max(years, 10)
        
    max_pages = 1 if years < 3 else 2
    
    # 4. Check the *actual* page count, not the word count
    status: CheckStatus = "pass" if pages <= max_pages else "warn"
    
    if status == "warn":
        detail = f"Your resume is {pages} pages long. For ~{years:g} years of experience, it should be {max_pages} page(s). Try the 'Compact' template or trim a few bullets."
    else:
        detail = f"Your resume fits on {pages} page(s), which is perfect for ~{years:g} years of experience."
        
    yield _check(
        "length",
        "formatting",
        status,
        "Length fits your experience" if status == "pass" else "Resume is too long",
        detail,
        weight=2,
        location=Location(section="experience") if status == "warn" else None,
    )

def _symbol_chars(text: str) -> set[str]:
    """Emoji, dingbats and private-use icon glyphs (e.g. icon-font phone/mail symbols)."""
    return {
        ch
        for ch in text
        if unicodedata.category(ch) in {"So", "Co"} or 0x1F000 <= ord(ch) <= 0x1FFFF
    }


def check_file_safety(data: ResumeData) -> Iterator[CheckResult]:
    # Our exports are single-column, real text, no tables/images/header content (see export
    # tests), so the remaining risk is characters inside the content itself.
    yield _check(
        "export_format",
        "formatting",
        "pass",
        "ATS-safe export format",
        "Exports use a single-column template with real text, standard headings and fonts, "
        "and no tables, images or header/footer content.",
        weight=2,
    )
    fields: list[tuple[str, Location]] = [
        (
            " ".join(
                [
                    *(
                        v
                        for v in data.personal_info.model_dump(exclude={"profile_links"}).values()
                        if v
                    ),
                    *(f"{link.label} {link.url}" for link in data.personal_info.profile_links),
                ]
            ),
            Location(section="personal_info"),
        ),
        (data.summary, Location(section="summary")),
    ]
    fields += [
        (" ".join([e.title, e.company, *e.bullets]), Location(section="experience", item_index=i))
        for i, e in enumerate(data.experience)
    ]
    fields += [
        (" ".join([p.name, p.description, *p.bullets]), Location(section="projects", item_index=i))
        for i, p in enumerate(data.projects)
    ]
    fields.append((" ".join(s.name for s in data.skills), Location(section="skills")))
    offenders = [(loc, _symbol_chars(text)) for text, loc in fields if _symbol_chars(text)]
    symbols = sorted({ch for _, chars in offenders for ch in chars})
    yield _check(
        "special_characters",
        "formatting",
        "pass" if not offenders else "warn",
        "No icons or emoji in the text" if not offenders else "Icons or emoji found in the text",
        "ATS often drop or garble symbols like " + " ".join(symbols[:6]) + ". Use plain words."
        if offenders
        else "Only plain text characters are used.",
        weight=1,
        location=offenders[0][0] if offenders else None,
    )


# --- Impact ---------------------------------------------------------------------------------


def check_action_verbs(data: ResumeData) -> Iterator[CheckResult]:
    bullets = _bullets(data)
    if not bullets:
        return
    weak = [b for b in bullets if b.text.lower().startswith(WEAK_OPENERS)]
    led = [b for b in bullets if _is_action_led(b.text)]
    ratio = len(led) / len(bullets)
    first_bad = weak[0] if weak else next((b for b in bullets if not _is_action_led(b.text)), None)
    detail = f"{len(led)} of {len(bullets)} bullets start with a strong action verb."
    if weak:
        detail += f" {len(weak)} start with weak phrases like 'Responsible for' or 'Worked on'."
    yield _check(
        "action_verbs",
        "impact",
        "fail" if ratio < 0.4 or len(weak) >= 3 else _ratio_status(ratio, 0.75, 0.4),
        "Bullets lead with action verbs"
        if ratio >= 0.75 and not weak
        else "Start more bullets with action verbs",
        detail
        + (
            ""
            if ratio >= 0.75 and not weak
            else " Try verbs like Built, Led, Reduced, Shipped, Automated."
        ),
        weight=3,
        location=_location(data, first_bad.section, first_bad.item_index)
        if first_bad and (ratio < 0.75 or weak)
        else None,
    )


def check_quantified(
    data: ResumeData, level: ExperienceLevel | None = None
) -> Iterator[CheckResult]:
    bullets = _bullets(data)
    if not bullets:
        return
    counted = [b for b in bullets if _is_quantified(b.text)]
    ratio = len(counted) / len(bullets)
    first_bad = next((b for b in bullets if not _is_quantified(b.text)), None)
    # Early-career work rarely comes with revenue figures; a few numbers are enough.
    good, ok = (0.25, 0.1) if level in EARLY_CAREER else (0.4, 0.2)
    tip = (
        " Even small numbers help: customers served, hours a week, grades, group size."
        if level in EARLY_CAREER
        else " Show scale and results: people served, %, time or money saved, targets hit."
    )
    yield _check(
        "quantified",
        "impact",
        _ratio_status(ratio, good, ok),
        "Achievements are quantified" if ratio >= good else "Add numbers to your achievements",
        f"{len(counted)} of {len(bullets)} bullets include a number, % or amount."
        + ("" if ratio >= good else tip),
        weight=3,
        location=_location(data, first_bad.section, first_bad.item_index)
        if first_bad and ratio < good
        else None,
    )


def check_bullets_per_role(
    data: ResumeData, level: ExperienceLevel | None = None
) -> Iterator[CheckResult]:
    if not data.experience:
        return
    bare = [i for i, e in enumerate(data.experience) if len(e.bullets) == 0]
    # One line is fine for a student's part-time job.
    thin = (
        []
        if level is ExperienceLevel.STUDENT
        else [i for i, e in enumerate(data.experience) if len(e.bullets) == 1]
    )
    status: CheckStatus = "fail" if bare else "warn" if thin else "pass"
    target = (bare or thin or [None])[0]
    yield _check(
        "bullets_per_role",
        "impact",
        status,
        "Every role describes your impact"
        if status == "pass"
        else "Some roles have too few bullets",
        "Each role has at least two bullets."
        if status == "pass"
        else f"{len(bare)} role(s) with no bullets, {len(thin)} with only one. Aim for 3-5.",
        weight=2,
        location=Location(section="experience", item_index=target) if target is not None else None,
    )


def check_summary(data: ResumeData) -> Iterator[CheckResult]:
    if not data.summary.strip():
        return
    words = len(_words(data.summary))
    status: CheckStatus = "pass" if 20 <= words <= 90 else "warn"
    yield _check(
        "summary_length",
        "impact",
        status,
        "Summary is focused"
        if status == "pass"
        else "Summary is too short"
        if words < 20
        else "Summary is too long",
        f"{words} words." + ("" if status == "pass" else " Aim for 20-90 words (2-4 sentences)."),
        weight=1,
        location=Location(section="summary"),
    )


_PLACEHOLDER = re.compile(r"\[[^\[\]\n]{1,24}\]")


def check_placeholders(data: ResumeData) -> Iterator[CheckResult]:
    """AI writing help leaves [X%]-style placeholders where a real number belongs."""
    found: list[tuple[Location, str]] = []
    if m := _PLACEHOLDER.search(data.summary):
        found.append((Location(section="summary"), m.group()))
    for section, entries in (("experience", data.experience), ("projects", data.projects)):
        for i, entry in enumerate(entries):
            for bullet in entry.bullets:
                if m := _PLACEHOLDER.search(bullet):
                    found.append((Location(section=section, item_index=i), m.group()))  # type: ignore[arg-type]
    if not found:
        return
    yield _check(
        "placeholders",
        "completeness",
        "fail",
        f"{len(found)} placeholder(s) left to fill in",
        f"Replace placeholders like {found[0][1]} with your real figures before sending. "
        "If you don't know the number, rephrase without it.",
        weight=3,
        location=found[0][0],
    )


CHECKS: list[Callable[..., Iterator[CheckResult]]] = [
    check_sections,
    check_headings,
    check_contact,
    check_skills_depth,
    check_dates,
    check_bullet_length,
    check_length,
    check_file_safety,
    check_action_verbs,
    check_quantified,
    check_bullets_per_role,
    check_summary,
    check_placeholders,
]


def run_checks(
    data: ResumeData,
    resume_type: ResumeType,
    level: ExperienceLevel | None = None,
    role: RoleSections | None = None,
    template: ResumeTemplate = ResumeTemplate.CLASSIC,
    page_size: PageSize = PageSize.A4,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in CHECKS:
        params = check.__code__.co_varnames[: check.__code__.co_argcount]
        kwargs: dict[str, object] = {}
        if "resume_type" in params:
            kwargs["resume_type"] = resume_type
        if "level" in params:
            kwargs["level"] = level
        if "role" in params:
            kwargs["role"] = role
        if "template" in params:
            kwargs["template"] = template
        if "page_size" in params:
            kwargs["page_size"] = page_size
        results.extend(check(data, **kwargs))
    return results
