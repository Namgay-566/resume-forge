import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.ai.client import AIClient, get_ai_client
from app.ai.rate_limit import ai_rate_limit
from app.api.ai_errors import ai_http_errors
from app.api.deps import CurrentUser, SessionDep
from app.schemas.writing import BulletImproveRequest, TailorRequest, TailorResult, WritingOptions
from app.services.resume_service import ResumeNotFoundError
from app.services.writing.service import WritingService

router = APIRouter(prefix="/resumes/{resume_id}/ai", tags=["ai writing"])

AIDep = Annotated[AIClient, Depends(get_ai_client)]


def _not_found(exc: ResumeNotFoundError) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")


@router.post("/improve-bullet", response_model=WritingOptions)
@ai_rate_limit
async def improve_bullet(
    request: Request,  # required by the rate limiter
    resume_id: uuid.UUID,
    body: BulletImproveRequest,
    user: CurrentUser,
    session: SessionDep,
    ai: AIDep,
) -> WritingOptions:
    """Three rewrites of one bullet. Invented numbers are replaced with [X]-style placeholders."""
    try:
        with ai_http_errors("improve-bullet"):
            return await WritingService(session, ai).improve_bullet(user, resume_id, body)
    except ResumeNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/summary", response_model=WritingOptions)
@ai_rate_limit
async def generate_summary(
    request: Request, resume_id: uuid.UUID, user: CurrentUser, session: SessionDep, ai: AIDep
) -> WritingOptions:
    """Two summary options from the saved resume, aimed at its target role."""
    try:
        with ai_http_errors("summary"):
            return await WritingService(session, ai).generate_summary(user, resume_id)
    except ResumeNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/tailor", response_model=TailorResult)
@ai_rate_limit
async def tailor(
    request: Request,
    resume_id: uuid.UUID,
    body: TailorRequest,
    user: CurrentUser,
    session: SessionDep,
    ai: AIDep,
) -> TailorResult:
    """Suggestions for the saved resume against a job description. Nothing is applied here."""
    try:
        with ai_http_errors("tailor"):
            return await WritingService(session, ai).tailor(user, resume_id, body.job_description)
    except ResumeNotFoundError as exc:
        raise _not_found(exc) from exc
