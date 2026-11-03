import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.ai.client import AIClient, get_ai_client
from app.ai.rate_limit import try_consume_ai_budget
from app.api.deps import CurrentUser, SessionDep
from app.models import ATSAnalysis
from app.schemas.ats import AtsAnalysisRead, AtsAnalysisRequest, AtsPrevious
from app.services.ats.service import AtsService
from app.services.resume_service import ResumeNotFoundError

router = APIRouter(prefix="/resumes/{resume_id}/ats-analyses", tags=["ats"])

_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")


def _read(analysis: ATSAnalysis, previous: ATSAnalysis | None) -> AtsAnalysisRead:
    read = AtsAnalysisRead.model_validate(analysis)
    if previous is not None:
        read.previous = AtsPrevious(
            score=previous.score,
            categories=previous.report.categories,
            created_at=previous.created_at,
        )
    return read


@router.post("", response_model=AtsAnalysisRead, status_code=status.HTTP_201_CREATED)
async def analyze_resume(
    request: Request,
    resume_id: uuid.UUID,
    body: AtsAnalysisRequest,
    user: CurrentUser,
    session: SessionDep,
    ai: Annotated[AIClient, Depends(get_ai_client)],
) -> AtsAnalysisRead:
    """Score the saved resume: deterministic checks + keywords + an AI recruiter review.

    The AI parts are best-effort: if the provider is unavailable the score is still computed
    from the deterministic checks and `report.ai_status` says why the review is missing.
    """
    try:
        analysis, previous = await AtsService(session, ai).analyze(
            user,
            resume_id,
            body.job_description,
            review=body.review,
            # Charged only when an AI call will actually run (not for plain re-checks).
            consume_ai_budget=lambda: try_consume_ai_budget(request),
        )
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc
    return _read(analysis, previous)


@router.get("/latest", response_model=AtsAnalysisRead)
async def latest_analysis(
    resume_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    ai: Annotated[AIClient, Depends(get_ai_client)],
) -> AtsAnalysisRead:
    try:
        analysis, previous = await AtsService(session, ai).latest(user, resume_id)
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No analysis yet")
    return _read(analysis, previous)
