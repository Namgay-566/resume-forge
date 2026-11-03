"""Which sections a resume should show, in what order, and which ones the ATS checker
requires. Pure functions over the catalog plus the role's and industry's section data."""

from collections.abc import Iterable
from dataclasses import dataclass

from app.models.enums import ExperienceLevel, ResumeType
from app.schemas.resume_data import MAX_SECTIONS, ResumeData, SectionConfig
from app.schemas.section_kind import SectionKind
from app.services.sections.catalog import Severity, get_catalog


@dataclass(frozen=True)
class RoleSections:
    """Section data for a target role: its own, else its industry's."""

    role_name: str | None = None
    # Suggested layout, in order. Empty: use the catalog's default layout.
    layout: tuple[SectionKind, ...] = ()
    # Sections the role screens for (beyond the base requirements).
    required: tuple[SectionKind, ...] = ()


def _unique(kinds: Iterable[SectionKind]) -> list[SectionKind]:
    return list(dict.fromkeys(kinds))


def suggest_layout(
    resume_type: ResumeType, level: ExperienceLevel | None, role: RoleSections | None = None
) -> list[SectionKind]:
    """E.g. a nurse: Summary, Licenses & Certifications, Clinical Experience, Experience...
    A student: Summary, Education, Projects, Internships, ..., Extracurricular Activities."""
    catalog = get_catalog()
    role = role or RoleSections()
    base = _unique([*(role.layout or catalog.default_layout), *role.required])
    type_preset = catalog.type_presets.get(resume_type.value)
    level_preset = catalog.level_presets.get(level) if level else None
    first = _unique(
        [*(level_preset.first if level_preset else []), *(type_preset.first if type_preset else [])]
    )
    last = [k for k in _unique(level_preset.last if level_preset else []) if k not in first]
    moved = set(first) | set(last)
    head = [SectionKind.SUMMARY] if SectionKind.SUMMARY in base else []
    rest = [k for k in base if k not in moved and k is not SectionKind.SUMMARY]
    return _unique([*head, *first, *rest, *last])


def with_layout(data: ResumeData, kinds: list[SectionKind]) -> ResumeData:
    """`data` with these sections in this order. Nothing is lost: a section in the layout
    keeps the entries `data` already has for it (an imported CV's Publications, say), and
    sections with content that the layout leaves out follow, in their original order.
    Core sections with content are kept too (see ResumeData)."""
    existing = {s.id: s for s in data.sections if s.has_content()}
    sections = [
        existing.pop(k.value, SectionConfig(id=k.value, kind=k))
        for k in kinds
        if k is not SectionKind.CUSTOM
    ]
    sections += list(existing.values())
    # Over the limit: drop empty suggested sections (last first), never content.
    while len(sections) > MAX_SECTIONS:
        empty = next(
            (i for i in range(len(sections) - 1, -1, -1) if not data.has_content(sections[i].kind)),
            None,
        )
        if empty is None:
            break
        del sections[empty]
    return ResumeData.model_validate(
        {**data.model_dump(exclude={"sections"}), "sections": [s.model_dump() for s in sections]}
    )


@dataclass(frozen=True)
class SectionRequirement:
    id: str
    label: str
    kinds: tuple[SectionKind, ...]
    severity: Severity
    advice: str


def section_requirements(
    level: ExperienceLevel | None, role: RoleSections | None = None
) -> list[SectionRequirement]:
    """The sections a resume must have. The base set (summary, some kind of experience,
    education, skills) bends to the career stage; the role adds its own (a licence, say)."""
    catalog = get_catalog()
    role = role or RoleSections()
    found: list[SectionRequirement] = []
    for req in catalog.requirements:
        override = req.levels.get(level) if level else None
        found.append(
            SectionRequirement(
                id=req.id,
                label=req.label,
                kinds=tuple(_unique([*req.kinds, *(override.add_kinds if override else [])])),
                severity=(override.severity if override and override.severity else req.severity),
                advice=(override.advice if override and override.advice else req.advice),
            )
        )
    covered = {k for r in found for k in r.kinds}
    template = catalog.role_requirement
    override = template.levels.get(level) if level else None
    for kind in _unique(role.required):
        if kind in covered:
            continue
        heading = catalog.heading(kind)
        advice = override.advice if override and override.advice else template.advice
        found.append(
            SectionRequirement(
                id=kind.value,
                label=heading,
                kinds=(kind,),
                severity=override.severity if override and override.severity else template.severity,
                advice=advice.format(role=role.role_name or "This", heading=heading),
            )
        )
    return found
