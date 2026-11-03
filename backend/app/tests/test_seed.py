import json
import shutil
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.db.seed import SEED_DIR, SkillSeed, load_seed_data
from app.models.enums import SkillImportance

REQUIRED_ROLES = {
    "full-stack-developer",
    "frontend-developer",
    "backend-developer-python",
    "data-analyst",
    "devops-engineer",
}


INDUSTRIES = {
    "technology",
    "healthcare",
    "education",
    "finance-accounting",
    "marketing",
    "sales",
    "design-creative",
    "engineering",
    "hospitality",
    "skilled-trades",
    "legal",
    "government",
    "research-academia",
    "customer-service",
    "operations-logistics",
    "human-resources",
}


def test_real_seed_files_are_valid() -> None:
    data = load_seed_data()

    assert REQUIRED_ROLES.issubset(role.slug for role in data.roles)
    assert {i.slug for i in data.industries} == INDUSTRIES


def test_every_industry_has_five_to_eight_roles() -> None:
    data = load_seed_data()
    per_industry = Counter(role.industry for role in data.roles)

    for industry in INDUSTRIES:
        assert 5 <= per_industry[industry] <= 8, (industry, per_industry[industry])


def test_every_role_needs_a_soft_skill() -> None:
    data = load_seed_data()
    soft = {s.slug for s in data.skills if s.category == "soft_skill"}

    for role in data.roles:
        assert soft & {rs.skill for rs in role.skills}, role.slug


@pytest.mark.parametrize(
    ("role", "licence"),
    [
        ("registered-nurse", "nursing-license"),
        ("accountant", "cpa-ca-acca"),
        ("primary-school-teacher", "teaching-certification"),
        ("secondary-school-teacher", "teaching-certification"),
        ("electrician", "electrician-license"),
        ("lawyer", "bar-admission"),
        ("social-worker", "social-work-license"),
    ],
)
def test_licensed_jobs_require_their_licence(role: str, licence: str) -> None:
    found = next(r for r in load_seed_data().roles if r.slug == role)
    importance = {rs.skill: rs.importance for rs in found.skills}

    assert importance[licence] is SkillImportance.CRITICAL


def test_weight_defaults_from_importance() -> None:
    role = next(r for r in load_seed_data().roles if r.slug == "registered-nurse")
    weights = {rs.importance: rs.effective_weight for rs in role.skills}

    assert weights[SkillImportance.CRITICAL] == 9
    assert weights[SkillImportance.IMPORTANT] == 6


def test_every_role_has_a_critical_skill() -> None:
    for role in load_seed_data().roles:
        assert any(rs.importance is SkillImportance.CRITICAL for rs in role.skills), role.slug


def test_full_stack_matches_the_brief() -> None:
    role = next(r for r in load_seed_data().roles if r.slug == "full-stack-developer")
    importance = {rs.skill: rs.importance for rs in role.skills}

    assert importance["git"] is SkillImportance.CRITICAL
    assert importance["react"] is SkillImportance.CRITICAL
    assert importance["docker"] is SkillImportance.IMPORTANT
    assert importance["typescript"] is SkillImportance.NICE_TO_HAVE


@pytest.mark.parametrize(
    ("alias", "skill_slug"),
    [("js", "javascript"), ("postgres", "sql"), ("version control", "git"), ("k8s", "kubernetes")],
)
def test_common_aliases_resolve(alias: str, skill_slug: str) -> None:
    skills = {s.slug: s for s in load_seed_data().skills}

    assert alias in skills[skill_slug].all_aliases()


def test_all_resources_are_free_and_https() -> None:
    for resource in load_seed_data().resources:
        assert resource.is_free, resource.url
        assert resource.url.scheme == "https"


def test_aliases_are_normalized_and_include_name() -> None:
    skill = SkillSeed(
        slug="git", name="Git", category="tool", aliases=["  GitHub ", "github", "VCS"]
    )

    assert skill.aliases == ["github", "vcs"]
    assert skill.all_aliases() == ["git", "github", "vcs"]


@pytest.fixture
def seed_copy(tmp_path: Path) -> Path:
    shutil.copytree(SEED_DIR, tmp_path, dirs_exist_ok=True)
    return tmp_path


def _edit(seed_dir: Path, name: str, mutate: object) -> None:
    path = seed_dir / name
    rows = json.loads(path.read_text())
    mutate(rows)  # type: ignore[operator]
    path.write_text(json.dumps(rows))


def test_unknown_skill_in_role_is_rejected(seed_copy: Path) -> None:
    _edit(
        seed_copy,
        "roles/technology.json",
        lambda rows: rows[0]["skills"].append(
            {"skill": "cobol", "importance": "critical", "weight": 5}
        ),
    )

    with pytest.raises(ValueError, match="unknown skill slugs"):
        load_seed_data(seed_copy)


def test_duplicate_skill_slug_is_rejected(seed_copy: Path) -> None:
    _edit(
        seed_copy,
        "skills/common.json",
        lambda rows: rows.append({**rows[0], "name": "Other", "aliases": []}),
    )

    with pytest.raises(ValueError, match="duplicate skill slug"):
        load_seed_data(seed_copy)


def test_unknown_industry_is_rejected(seed_copy: Path) -> None:
    _edit(seed_copy, "roles/legal.json", lambda rows: rows[0].__setitem__("industry", "space"))

    with pytest.raises(ValueError, match="unknown industry"):
        load_seed_data(seed_copy)


def test_alias_on_two_skills_is_rejected(seed_copy: Path) -> None:
    # Shared aliases would silently merge two skills in ATS keyword matching.
    _edit(seed_copy, "skills/common.json", lambda rows: rows[0]["aliases"].append("git"))

    with pytest.raises(ValueError, match="aliases on more than one skill"):
        load_seed_data(seed_copy)


def test_skills_without_resources_are_reported_not_refused(seed_copy: Path) -> None:
    # Resources must be real, checked links, so a gap is a to-do, never a reason to invent one.
    _edit(
        seed_copy,
        "learning_resources.json",
        lambda rows: rows.__setitem__(slice(None), [r for r in rows if r["skill"] != "git"]),
    )

    data = load_seed_data(seed_copy)

    assert "git" in data.skills_without_resources()
    assert "phlebotomy" in data.skills_without_resources()  # nothing curated yet


def test_http_resource_url_is_rejected(seed_copy: Path) -> None:
    _edit(
        seed_copy,
        "learning_resources.json",
        lambda rows: rows[0].__setitem__("url", "http://example.com/course"),
    )

    with pytest.raises(ValidationError, match="https"):
        load_seed_data(seed_copy)
