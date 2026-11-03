"""Which kinds of proof suit a skill, and what each must include. Data-driven (rules.json)
and deterministic: the checker holds proofs to exactly these requirements, so they must be
stable and the same for everyone."""

from functools import cache
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.enums import ProofType

RULES_PATH = Path(__file__).with_name("rules.json")


class RulesModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TypeRule(RulesModel):
    label: str
    # "{skill}" is replaced with the skill's name.
    must_include: list[str]


class SlugRequirement(RulesModel):
    must_include: list[str]


class ProofRules(RulesModel):
    types: dict[ProofType, TypeRule]
    # Skill category -> proof types, best first. "*" is the fallback.
    category_defaults: dict[str, list[ProofType]]
    # Industry slug -> category -> proof types, for fields where a category means something
    # else (a technology "practice" is proven with code, a design "practice" with a portfolio).
    industry_overrides: dict[str, dict[str, list[ProofType]]] = {}
    # Skill slug -> proof types; wins over everything.
    skill_overrides: dict[str, list[ProofType]] = {}
    requirements_by_slug: dict[str, SlugRequirement] = {}

    @model_validator(mode="after")
    def check(self) -> Self:
        if set(self.types) != set(ProofType):
            raise ValueError(
                f"describe every proof type; missing {set(ProofType) - set(self.types)}"
            )
        if "*" not in self.category_defaults:
            raise ValueError("category_defaults needs a '*' fallback")
        lists = [
            *self.category_defaults.values(),
            *(v for per in self.industry_overrides.values() for v in per.values()),
            *self.skill_overrides.values(),
        ]
        if any(not v for v in lists):
            raise ValueError("every rule needs at least one proof type")
        return self

    def proof_types(
        self, *, slug: str, category: str, industry: str | None = None
    ) -> list[ProofType]:
        """Proof types for a skill, best first."""
        if slug in self.skill_overrides:
            return self.skill_overrides[slug]
        per_industry = self.industry_overrides.get(industry or "", {})
        if category in per_industry:
            return per_industry[category]
        return self.category_defaults.get(category) or self.category_defaults["*"]

    def must_include(self, proof_type: ProofType, skill_name: str, slug: str) -> list[str]:
        if slug in self.requirements_by_slug:
            return self.requirements_by_slug[slug].must_include
        return [line.replace("{skill}", skill_name) for line in self.types[proof_type].must_include]


@cache
def get_rules() -> ProofRules:
    return ProofRules.model_validate_json(RULES_PATH.read_text(encoding="utf-8"))


def skill_proof_types(slug: str, category: str, stored: list[str]) -> list[ProofType]:
    """A skill's proof types: as stored by the seed (which knows its industry), else from
    its category."""
    known = [ProofType(v) for v in stored if v in ProofType._value2member_map_]
    return known or get_rules().proof_types(slug=slug, category=category)
