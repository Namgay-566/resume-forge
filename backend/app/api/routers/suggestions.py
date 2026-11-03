import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.ai.client import AIClient, get_ai_client
from app.ai.rate_limit import try_consume_ai_budget
from app.api.ai_errors import ai_http_errors
from app.api.deps import CurrentUser, SessionDep
from app.schemas.proof_report import ProjectDraft
from app.schemas.suggestions import ProjectDraftRequest, SuggestionsResponse
from app.services.resume_service import ResumeNotFoundError
from app.services.suggestions.service import (
    AIBudgetExhaustedError,
    ProofNotSuggestableError,
    SuggestionService,
)

router = APIRouter(prefix="/resumes/{resume_id}/suggestions", tags=["suggestions"])
AIDep = Annotated[AIClient, Depends(get_ai_client)]
_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")


@router.get("", response_model=SuggestionsResponse)
async def list_suggestions(
    resume_id: uuid.UUID, user: CurrentUser, session: SessionDep, ai: AIDep
) -> SuggestionsResponse:
    """What verified proofs could add to this resume, plus every proof's citation link.
    Deterministic (no AI); nothing is applied until the user accepts in the editor."""
    try:
        return await SuggestionService(session, ai).suggestions(user, resume_id)
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.post("/project-draft", response_model=ProjectDraft)
async def project_draft(
    request: Request,
    resume_id: uuid.UUID,
    body: ProjectDraftRequest,
    user: CurrentUser,
    session: SessionDep,
    ai: AIDep,
) -> ProjectDraft:
    """AI-drafted Projects entry for a verified repo, cached with the proof."""
    try:
        with ai_http_errors("project-draft"):
            return await SuggestionService(session, ai).project_draft(
                user,
                resume_id,
                body.proof_id,
                regenerate=body.regenerate,
                consume_ai_budget=lambda: try_consume_ai_budget(request),
            )
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc
    except ProofNotSuggestableError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No verified repository proof with that id"
        ) from exc
    except AIBudgetExhaustedError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You've reached the limit for AI features. Please try again later.",
        ) from exc


@router.post("/{suggestion_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_suggestion(
    resume_id: uuid.UUID, suggestion_id: str, user: CurrentUser, session: SessionDep, ai: AIDep
) -> None:
    try:
        await SuggestionService(session, ai).dismiss(user, resume_id, suggestion_id)
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc
