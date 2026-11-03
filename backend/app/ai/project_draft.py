import re

from pydantic import BaseModel, Field

from app.ai.client import AIClient
from app.ai.context import NO_CONTEXT, CandidateContext
from app.ai.project_ideas import strip_urls
from app.ai.prompts import render_prompt
from app.schemas.proof_report import ProjectDraft, ProofReport
from app.services.writing.guard import guard_numbers, number_keys


class _Draft(BaseModel):
    name: str
    description: str
    bullets: list[str] = Field(min_length=1, max_length=4)
    tools_and_skills: list[str] = Field(default_factory=list, max_length=10)


# What's left of "…; see https://x" once the URL is gone.
_DANGLING = re.compile(r"[\s;:,(—-]*\b(?:see|at|visit|via|here)\s*[:.]?$", re.IGNORECASE)


def _tidy(text: str, limit: int) -> str:
    cleaned = " ".join(strip_urls(text).split())
    if cleaned != " ".join(text.split()):  # only trim words a removed link left hanging
        cleaned = _DANGLING.sub("", cleaned)
    return cleaned.rstrip(" .;:,")[:limit]


async def draft_project(
    ai: AIClient, *, report: ProofReport, repo_url: str, context: CandidateContext = NO_CONTEXT
) -> ProjectDraft:
    repo = report.repo
    assert repo is not None
    evidence = [
        f"{s.name}: {'; '.join(s.evidence)}" for s in report.skills if s.verdict == "demonstrated"
    ]
    raw = await ai.generate_structured(
        render_prompt(
            "project_draft_user",
            repo=repo,
            readme=repo.readme_excerpt,
            summary=report.summary,
            evidence=evidence,
            ctx=context,
        ),
        _Draft,
        system=render_prompt("project_draft_system"),
        task="project_draft",
        max_tokens=2000,
    )
    # Numbers must come from the repo's own words; links come from the proof, never the model.
    allowed = number_keys(repo.readme_excerpt or "", repo.description or "", report.summary)
    bullets = [guard_numbers(_tidy(b, 500), allowed).text for b in raw.bullets[:3]]
    return ProjectDraft(
        name=_tidy(raw.name, 200) or repo.full_name.split("/")[-1],
        description=guard_numbers(_tidy(raw.description, 1000), allowed).text,
        bullets=[b for b in bullets if b],
        tools_and_skills=list(
            dict.fromkeys(t.strip()[:200] for t in raw.tools_and_skills if t.strip())
        )[:8],
        link=repo_url,
    )
