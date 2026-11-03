"""Seed industries, the skills catalog, target roles and curated learning resources.

Usage (from backend/):
    python -m app.db.seed             # validate JSON and upsert into the database
    python -m app.db.seed --check     # validate JSON only, no database access

Layout of seed_data/:
    industries.json            every industry, in picker order
    skills/<file>.json         skills, grouped by the industry that introduced them
                               (common.json holds soft skills and shared licences)
    roles/<industry>.json      that industry's target roles
    learning_resources.json    curated, human-checked resources (never invented)

Idempotent: every row is upserted on its natural key (industry slug, skill slug, role
slug, role+skill, skill+url). Re-running updates changed fields and inserts nothing new.
A role's skill list is synced to the JSON: role_skills not listed there are removed.
"""

import argparse
import asyncio
import json
from collections import Counter
from collections.abc import Hashable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator
from sqlalchemy import Boolean, delete, func, literal_column, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Industry, LearningResource, RoleSkill, Skill, SkillGroup, TargetRole
from app.models.enums import (
    ContentSource,
    ProofType,
    ResourceType,
    ResumeTemplate,
    SkillImportance,
)
from app.schemas.section_kind import SectionKind
from app.services.proofs.rules import get_rules
from app.services.sections.catalog import get_catalog

SEED_DIR = Path(__file__).parent / "seed_data"

Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=120)]


class SeedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# Resume sections, in order. Kinds are validated against SectionKind.
SectionList = Annotated[list[SectionKind], Field(max_length=20)]


def _no_repeats(kinds: list[SectionKind]) -> list[SectionKind]:
    if len(set(kinds)) != len(kinds):
        raise ValueError("a section is listed twice")
    return kinds


class IndustrySeed(SeedModel):
    slug: Slug
    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: str
    # The resume layout suggested for this industry's roles.
    sections: Annotated[SectionList, Field(min_length=1)]
    required_sections: SectionList = []
    # Profile links suggested on resumes in this field (labels from the section catalog).
    profile_links: list[str] = []
    # Who reviews proof in this field (the AI reviewer's persona).
    reviewer: Annotated[str, Field(min_length=10, max_length=300)]
    # What results mean in this field, for AI writing help.
    impact: Annotated[str, Field(min_length=10, max_length=400)]
    template: ResumeTemplate

    _sections = field_validator("sections", "required_sections")(_no_repeats)


class SkillSeed(SeedModel):
    slug: Slug
    name: Annotated[str, Field(min_length=1, max_length=120)]
    category: Annotated[str, Field(min_length=1, max_length=64)]
    aliases: list[Annotated[str, Field(min_length=1, max_length=120)]]
    # Suitable proof types, best first. Computed from the proof rules when left out.
    proof_types: list[ProofType] = []
    # The skill group (a slug from skill_groups.json). Assigned while loading: listed
    # explicitly in a group, else by category within the skill's industry, else shared.
    group: Slug | None = None

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, aliases: list[str]) -> list[str]:
        # Lowercase and de-duplicate, keeping the author's order.
        return list(dict.fromkeys(alias.strip().lower() for alias in aliases))

    def all_aliases(self) -> list[str]:
        """Aliases plus the lowercased name, so the name itself always matches."""
        return list(dict.fromkeys([self.name.lower(), *self.aliases]))


class RoleSkillSeed(SeedModel):
    skill: Slug
    importance: SkillImportance
    weight: Annotated[int, Field(ge=1, le=10)] | None = None

    @property
    def effective_weight(self) -> int:
        return self.weight if self.weight is not None else self.importance.default_weight


class RoleSeed(SeedModel):
    industry: Slug
    slug: Slug
    name: Annotated[str, Field(min_length=1, max_length=120)]
    seniority: Annotated[str, Field(min_length=1, max_length=32)]
    description: str
    skills: Annotated[list[RoleSkillSeed], Field(min_length=1)]
    # Overrides the industry's layout; empty means use the industry's.
    sections: SectionList = []
    required_sections: SectionList = []

    _sections = field_validator("sections", "required_sections")(_no_repeats)


class ResourceSeed(SeedModel):
    skill: Slug
    title: Annotated[str, Field(min_length=1, max_length=200)]
    provider: Annotated[str, Field(min_length=1, max_length=120)]
    url: HttpUrl
    type: ResourceType
    level: Annotated[str, Field(min_length=1, max_length=32)]
    is_free: bool
    est_hours: Annotated[Decimal, Field(gt=0, max_digits=5, decimal_places=1)] | None = None
    # Set when a URL still needs a human to confirm it. JSON has no comments, so it lives here.
    todo: str | None = None

    @field_validator("url")
    @classmethod
    def require_https(cls, url: HttpUrl) -> HttpUrl:
        if url.scheme != "https":
            raise ValueError("resource URLs must use https")
        return url


class SkillGroupSeed(SeedModel):
    slug: Slug
    name: Annotated[str, Field(min_length=1, max_length=80)]
    # Generic skill categories the group takes by default ("clinical", "tool"...).
    categories: list[str] = []
    # Skills placed here explicitly (by slug), whatever their category.
    skills: list[Slug] = []


class PlacedGroup(SeedModel):
    """A skill group with where it belongs: an industry slug, or None for shared groups."""

    industry: Slug | None
    sort_order: int
    group: SkillGroupSeed


class SeedData(SeedModel):
    industries: list[IndustrySeed]
    skill_groups: list[PlacedGroup] = []
    skills: list[SkillSeed]
    roles: list[RoleSeed]
    resources: list[ResourceSeed]

    def check_references(self) -> Self:
        industry_slugs = _unique([i.slug for i in self.industries], "industry slug")
        _unique([g.group.slug for g in self.skill_groups], "skill group slug")
        grouped_industries = {g.industry for g in self.skill_groups if g.industry}
        if unknown := sorted(grouped_industries - industry_slugs):
            raise ValueError(f"skill groups for unknown industries: {unknown}")
        if ungrouped := sorted(s.slug for s in self.skills if s.group is None):
            raise ValueError(f"skills without a skill group: {ungrouped}")
        link_labels = {link.label for link in get_catalog().profile_links}
        for industry in self.industries:
            if unknown_links := sorted(set(industry.profile_links) - link_labels):
                raise ValueError(f"unknown profile links in {industry.slug!r}: {unknown_links}")
        _unique([i.name.lower() for i in self.industries], "industry name")
        skill_slugs = _unique([s.slug for s in self.skills], "skill slug")
        _unique([s.name.lower() for s in self.skills], "skill name")
        _unique([r.slug for r in self.roles], "role slug")
        _unique([(r.skill, str(r.url)) for r in self.resources], "resource (skill, url)")

        for role in self.roles:
            role_skill_slugs = [rs.skill for rs in role.skills]
            _unique(role_skill_slugs, f"skill in role {role.slug!r}")
            _known(role_skill_slugs, skill_slugs, f"role {role.slug!r}")
            if role.industry not in industry_slugs:
                raise ValueError(f"unknown industry {role.industry!r} in role {role.slug!r}")
            if not any(rs.importance is SkillImportance.CRITICAL for rs in role.skills):
                raise ValueError(f"role {role.slug!r} has no critical skill")
        _known([r.skill for r in self.resources], skill_slugs, "learning_resources.json")
        self._check_shared_aliases()
        return self

    def _check_shared_aliases(self) -> None:
        """Skills sharing an alias are treated as one keyword group by ATS matching, so an
        accidental overlap ("typing" on two skills) would silently merge them."""
        owners: dict[str, set[str]] = {}
        for skill in self.skills:
            for alias in skill.all_aliases():
                owners.setdefault(alias, set()).add(skill.slug)
        shared = {a: s for a, s in owners.items() if len(s) > 1 and a not in SHARED_ALIASES}
        if shared:
            raise ValueError(f"aliases on more than one skill: {sorted(shared)}")

    def skills_without_resources(self) -> list[str]:
        """Required skills with nothing curated to learn from yet. Reported, not refused:
        a resource must be a real, human-checked link, and those are added over time."""
        with_resources = {r.skill for r in self.resources}
        required = {rs.skill for role in self.roles for rs in role.skills}
        return sorted(required - with_resources)


# Frameworks that deliberately belong to both "backend framework" and "Python web framework".
SHARED_ALIASES = frozenset({"django", "flask", "fastapi"})


def _unique(values: list[Any], label: str) -> set[Any]:
    counts: Counter[Hashable] = Counter(values)
    if dupes := sorted(str(v) for v, n in counts.items() if n > 1):
        raise ValueError(f"duplicate {label}: {dupes}")
    return set(counts)


def _known(slugs: list[str], known: set[str], where: str) -> None:
    if unknown := sorted(set(slugs) - known):
        raise ValueError(f"unknown skill slugs in {where}: {unknown}")


def load_seed_data(seed_dir: Path = SEED_DIR) -> SeedData:
    def read(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def read_dir(name: str) -> list[Any]:
        files = sorted((seed_dir / name).glob("*.json"))
        if not files:
            raise ValueError(f"no seed files in {name}/")
        return [row for path in files for row in read(path)]

    def read_skills() -> list[Any]:
        # A skill's file names its industry ("common" has none), which the proof rules use:
        # a technology "practice" is shown with code, a design "practice" with a portfolio.
        rules = get_rules()
        rows = []
        for path in sorted((seed_dir / "skills").glob("*.json")):
            industry = None if path.stem == "common" else path.stem
            for row in read(path):
                if not row.get("proof_types"):
                    types = rules.proof_types(
                        slug=row["slug"], category=row["category"], industry=industry
                    )
                    row = {**row, "proof_types": [t.value for t in types]}
                rows.append({**row, "_industry": industry})
        if not rows:
            raise ValueError("no seed files in skills/")
        return rows

    groups = _read_groups(read(seed_dir / "skill_groups.json"))
    data = SeedData(
        industries=TypeAdapter(list[IndustrySeed]).validate_python(
            read(seed_dir / "industries.json")
        ),
        skill_groups=groups,
        skills=_place_skills(read_skills(), groups),
        roles=TypeAdapter(list[RoleSeed]).validate_python(read_dir("roles")),
        resources=TypeAdapter(list[ResourceSeed]).validate_python(
            read(seed_dir / "learning_resources.json")
        ),
    )
    return data.check_references()


SHARED_GROUP_ORDER = 100  # shared groups (soft skills...) list after the field's own


def _read_groups(raw: dict[str, Any]) -> list[PlacedGroup]:
    placed = []
    for key, groups in raw.items():
        industry = None if key == "common" else key
        base = SHARED_GROUP_ORDER if industry is None else 0
        for order, group in enumerate(TypeAdapter(list[SkillGroupSeed]).validate_python(groups)):
            placed.append(PlacedGroup(industry=industry, sort_order=base + order, group=group))
    return placed


def _place_skills(rows: list[dict[str, Any]], groups: list[PlacedGroup]) -> list[SkillSeed]:
    """Give every skill its group: explicit listing, else by category in its industry's
    groups, else by category in the shared groups."""
    explicit: dict[str, str] = {}
    for placed in groups:
        for slug in placed.group.skills:
            if slug in explicit:
                raise ValueError(f"skill {slug!r} is listed in two skill groups")
            explicit[slug] = placed.group.slug
    known = {row["slug"] for row in rows}
    if unknown := sorted(set(explicit) - known):
        raise ValueError(f"unknown skills in skill groups: {unknown}")

    def by_category(industry: str | None, category: str) -> str | None:
        return next(
            (
                p.group.slug
                for p in groups
                if p.industry == industry and category in p.group.categories
            ),
            None,
        )

    skills = []
    for row in rows:
        industry = row.pop("_industry")
        group = (
            explicit.get(row["slug"])
            or (by_category(industry, row["category"]) if industry else None)
            or by_category(None, row["category"])
        )
        skills.append(SkillSeed.model_validate({**row, "group": group}))
    return skills


@dataclass
class UpsertCount:
    inserted: int = 0
    updated: int = 0

    def add(self, inserted: bool) -> None:
        if inserted:
            self.inserted += 1
        else:
            self.updated += 1

    def __str__(self) -> str:
        return f"{self.inserted} inserted, {self.updated} updated"


# Postgres sets xmax = 0 on freshly inserted rows, so RETURNING it tells inserts from updates.
_WAS_INSERTED = literal_column("(xmax = 0)", Boolean).label("inserted")


async def apply_seed(session: AsyncSession, data: SeedData) -> dict[str, UpsertCount]:
    tables = ("industries", "skill_groups", "skills", "roles", "role_skills", "resources")
    counts = {name: UpsertCount() for name in tables}

    industry_ids: dict[str, Any] = {}
    for order, industry in enumerate(data.industries):
        stmt = insert(Industry).values(
            slug=industry.slug,
            name=industry.name,
            description=industry.description,
            sort_order=order,
            default_sections=[k.value for k in industry.sections],
            required_sections=[k.value for k in industry.required_sections],
            reviewer_persona=industry.reviewer,
            impact_language=industry.impact,
            recommended_template=industry.template.value,
            profile_links=industry.profile_links,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Industry.slug],
            set_={
                col: stmt.excluded[col]
                for col in (
                    "name",
                    "description",
                    "sort_order",
                    "default_sections",
                    "required_sections",
                    "reviewer_persona",
                    "impact_language",
                    "recommended_template",
                    "profile_links",
                )
            },
        ).returning(Industry.id, _WAS_INSERTED)
        row = (await session.execute(stmt)).one()
        industry_ids[industry.slug] = row.id
        counts["industries"].add(row.inserted)

    group_ids: dict[str, Any] = {}
    for placed in data.skill_groups:
        stmt = insert(SkillGroup).values(
            slug=placed.group.slug,
            name=placed.group.name,
            sort_order=placed.sort_order,
            industry_id=industry_ids[placed.industry] if placed.industry else None,
            categories=placed.group.categories,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SkillGroup.slug],
            set_={
                col: stmt.excluded[col]
                for col in ("name", "sort_order", "industry_id", "categories")
            },
        ).returning(SkillGroup.id, _WAS_INSERTED)
        row = (await session.execute(stmt)).one()
        group_ids[placed.group.slug] = row.id
        counts["skill_groups"].add(row.inserted)

    skill_ids: dict[str, Any] = {}
    for skill in data.skills:
        # A skill an AI role profile created earlier becomes this curated one, keeping the
        # links users already have to it (names are unique, so it can't be inserted twice).
        await session.execute(
            update(Skill)
            .where(
                func.lower(Skill.name) == skill.name.lower(),
                Skill.slug != skill.slug,
                Skill.source == ContentSource.AI_GENERATED,
            )
            .values(slug=skill.slug)
        )
        stmt = insert(Skill).values(
            slug=skill.slug,
            name=skill.name,
            category=skill.category,
            aliases=skill.all_aliases(),
            source=ContentSource.CURATED,
            proof_types=[t.value for t in skill.proof_types],
            group_id=group_ids[skill.group] if skill.group else None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Skill.slug],
            set_={
                "group_id": stmt.excluded.group_id,
                "name": stmt.excluded.name,
                "category": stmt.excluded.category,
                "aliases": stmt.excluded.aliases,
                "source": stmt.excluded.source,
                "proof_types": stmt.excluded.proof_types,
            },
        ).returning(Skill.id, _WAS_INSERTED)
        row = (await session.execute(stmt)).one()
        skill_ids[skill.slug] = row.id
        counts["skills"].add(row.inserted)

    for role in data.roles:
        stmt = insert(TargetRole).values(
            slug=role.slug,
            name=role.name,
            seniority=role.seniority,
            description=role.description,
            industry_id=industry_ids[role.industry],
            source=ContentSource.CURATED,
            default_sections=[k.value for k in role.sections],
            required_sections=[k.value for k in role.required_sections],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[TargetRole.slug],
            set_={
                col: stmt.excluded[col]
                for col in (
                    "name",
                    "seniority",
                    "description",
                    "industry_id",
                    "source",
                    "default_sections",
                    "required_sections",
                )
            },
        ).returning(TargetRole.id, _WAS_INSERTED)
        row = (await session.execute(stmt)).one()
        role_id = row.id
        counts["roles"].add(row.inserted)

        wanted_skill_ids = [skill_ids[rs.skill] for rs in role.skills]
        for role_skill, skill_id in zip(role.skills, wanted_skill_ids, strict=True):
            stmt = insert(RoleSkill).values(
                role_id=role_id,
                skill_id=skill_id,
                importance=role_skill.importance,
                weight=role_skill.effective_weight,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[RoleSkill.role_id, RoleSkill.skill_id],
                set_={"importance": stmt.excluded.importance, "weight": stmt.excluded.weight},
            ).returning(_WAS_INSERTED)
            counts["role_skills"].add((await session.execute(stmt)).scalar_one())

        await session.execute(
            delete(RoleSkill).where(
                RoleSkill.role_id == role_id, RoleSkill.skill_id.not_in(wanted_skill_ids)
            )
        )

    for resource in data.resources:
        stmt = insert(LearningResource).values(
            skill_id=skill_ids[resource.skill],
            url=str(resource.url),
            title=resource.title,
            provider=resource.provider,
            type=resource.type,
            level=resource.level,
            is_free=resource.is_free,
            est_hours=resource.est_hours,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[LearningResource.skill_id, LearningResource.url],
            set_={
                col: stmt.excluded[col]
                for col in ("title", "provider", "type", "level", "is_free", "est_hours")
            },
        ).returning(_WAS_INSERTED)
        counts["resources"].add((await session.execute(stmt)).scalar_one())

    return counts


def print_report(data: SeedData) -> None:
    if missing := data.skills_without_resources():
        print(
            f"\n{len(missing)} required skill(s) have no curated learning resources yet "
            "(add real, checked links to learning_resources.json; never invent them):"
        )
        print("  " + ", ".join(missing))
    todos = [r for r in data.resources if r.todo]
    if not todos:
        return
    print(f"\n{len(todos)} resource URL(s) marked TODO for manual verification:")
    for r in todos:
        print(f"  - [{r.skill}] {r.url}\n      {r.todo}")


async def run() -> None:
    # Imported here so `--check` works without a database configured.
    from app.db.session import SessionLocal, engine

    data = load_seed_data()
    try:
        async with SessionLocal() as session, session.begin():
            counts = await apply_seed(session, data)
    finally:
        await engine.dispose()

    for table, count in counts.items():
        print(f"{table:<12} {count}")
    print_report(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="validate seed JSON only")
    args = parser.parse_args()

    if args.check:
        data = load_seed_data()
        print(
            f"OK: {len(data.industries)} industries, {len(data.skills)} skills, "
            f"{len(data.roles)} roles, "
            f"{len(data.resources)} resources"
        )
        print_report(data)
        return
    asyncio.run(run())


if __name__ == "__main__":
    main()
