import re
from dataclasses import dataclass

from app.ai.client import AIClient
from app.ai.context import CandidateContext
from app.ai.prompts import render_prompt
from app.models.enums import ProofType
from app.schemas.project_idea import ProjectIdea
from app.services.proofs.rules import get_rules

# CLAUDE.md: never let AI produce URLs. The prompt forbids them; this removes any that slip in.
_URL = re.compile(
    r"(?i)\b(?:https?://|www\.)[^\s)\]]+"
    r"|\b(?:[\w-]+\.)+(?:com|io|dev|org|net|app)(?:/[^\s)\]]*)?"  # bare hosts, incl. subdomains
)
_TRAILING_PUNCT = ".,;:!?"


def _drop_url(match: re.Match[str]) -> str:
    # Keep sentence punctuation that the greedy match swallowed ("see https://x.com." -> "see.").
    url = match.group()
    return url[len(url.rstrip(_TRAILING_PUNCT)) :]


def strip_urls(text: str) -> str:
    cleaned = " ".join(_URL.sub(_drop_url, text).split())
    cleaned = re.sub(r"\s+([),.;:])", r"\1", cleaned)  # "see ." -> "see."
    return re.sub(r"\(\s*\)", "", cleaned).strip()


def _clean(idea: ProjectIdea) -> ProjectIdea:
    return idea.model_copy(
        update={
            "title": strip_urls(idea.title),
            "summary": strip_urls(idea.summary),
            "steps": [s for s in (strip_urls(x) for x in idea.steps) if s],
            "reviewer_checks": [c for c in (strip_urls(x) for x in idea.reviewer_checks) if c],
            "stretch": strip_urls(idea.stretch) if idea.stretch else None,
        }
    )


async def generate_project_idea(
    ai: AIClient,
    *,
    skill: str,
    slug: str,
    category: str,
    importance: str,
    context: CandidateContext,
    already_listed: bool,
    known_skills: list[str],
    proof_types: list[ProofType],
) -> ProjectIdea:
    rules = get_rules()
    offered = proof_types or rules.proof_types(slug=slug, category=category)
    idea = await ai.generate_structured(
        render_prompt(
            "project_idea_user",
            skill=skill,
            category=category,
            importance=importance.replace("_", " "),
            ctx=context,
            already_listed=already_listed,
            known_skills=known_skills,
            proof_types=[_Offered(t.value, rules.types[t].label) for t in offered],
            must_include=rules.must_include(offered[0], skill, slug),
        ),
        ProjectIdea,
        system=render_prompt("project_idea_system"),
        task="project_idea",
        max_tokens=3000,
    )
    # The idea must produce proof the checker accepts for this skill.
    proof_type = idea.proof_type if idea.proof_type in {t.value for t in offered} else None
    return _clean(idea).model_copy(
        update={
            "tailored_for": context.target_role,
            "proof_type": proof_type or offered[0].value,
            "deliverable": strip_urls(idea.deliverable) if idea.deliverable else None,
        }
    )


@dataclass(frozen=True)
class _Offered:
    value: str
    label: str
