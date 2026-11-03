"""The referee's side: a public page reached from the email. No sign-in; the one-time
token in the URL is the credential. Every failure looks the same, so links can't be probed."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status

from app.ai.rate_limit import referee_page_rate_limit
from app.api.deps import SessionDep
from app.schemas.referee import RefereeAnswers, RefereeDecline, RefereePage
from app.services.email.sender import EmailSender, get_email_sender
from app.services.verification.referees import RefereeError, RefereeLinkError, RefereeService

router = APIRouter(prefix="/referee", tags=["referee"])
# Tells the candidate the outcome, if they want proof emails.
EmailDep = Annotated[EmailSender, Depends(get_email_sender)]

Token = Annotated[str, Path(min_length=20, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]
_GONE = HTTPException(
    status.HTTP_404_NOT_FOUND,
    "This link has expired or has already been used. Nothing else is needed from you.",
)


@router.get("/{token}", response_model=RefereePage)
@referee_page_rate_limit
async def referee_page(request: Request, token: Token, session: SessionDep) -> RefereePage:
    try:
        ask, candidate = await RefereeService(session).open(token)
    except RefereeLinkError as exc:
        raise _GONE from exc
    assert ask.expires_at is not None
    return RefereePage(
        candidate_name=candidate.name,
        referee_name=ask.referee_name,
        claim=ask.claim,
        expires_at=ask.expires_at,
    )


@router.post("/{token}", status_code=status.HTTP_204_NO_CONTENT)
@referee_page_rate_limit
async def referee_answer(
    request: Request, token: Token, body: RefereeAnswers, session: SessionDep, sender: EmailDep
) -> None:
    try:
        await RefereeService(session).answer(token, body, sender)
    except RefereeLinkError as exc:
        raise _GONE from exc
    except RefereeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/{token}/decline", status_code=status.HTTP_204_NO_CONTENT)
@referee_page_rate_limit
async def referee_decline(
    request: Request, token: Token, body: RefereeDecline, session: SessionDep, sender: EmailDep
) -> None:
    try:
        await RefereeService(session).decline(token, body, sender)
    except RefereeLinkError as exc:
        raise _GONE from exc
