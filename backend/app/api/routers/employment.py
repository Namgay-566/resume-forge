"""Employer email checks: prove you can read mail at a work address at a company."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.ai.rate_limit import employment_code_rate_limit
from app.api.deps import CurrentUser, SessionDep
from app.models import EmploymentEmailCheck
from app.schemas.employment import EmploymentCheckConfirm, EmploymentCheckRead, EmploymentCheckStart
from app.services.email.sender import EmailSender, get_email_sender
from app.services.verification.employment import (
    EmploymentCheckError,
    EmploymentCheckNotFoundError,
    EmploymentCheckService,
)

router = APIRouter(prefix="/employment-checks", tags=["employment-checks"])
EmailDep = Annotated[EmailSender, Depends(get_email_sender)]
_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Email check not found")


def _mask(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}•••@{domain}"


def _read(check: EmploymentEmailCheck) -> EmploymentCheckRead:
    return EmploymentCheckRead(
        id=check.id,
        company=check.company,
        email_masked=_mask(check.email),
        email_domain=check.email_domain,
        domain_matches_company=check.domain_matches_company,
        verified=check.verified_at is not None,
        verified_at=check.verified_at,
        code_sent_at=check.last_sent_at if check.verified_at is None else None,
        code_expires_at=check.code_expires_at if check.verified_at is None else None,
    )


def _unprocessable(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("", response_model=list[EmploymentCheckRead])
async def list_checks(user: CurrentUser, session: SessionDep) -> list[EmploymentCheckRead]:
    return [_read(c) for c in await EmploymentCheckService(session).list(user)]


@router.post("", response_model=EmploymentCheckRead, status_code=status.HTTP_201_CREATED)
@employment_code_rate_limit
async def start_check(
    request: Request,
    body: EmploymentCheckStart,
    user: CurrentUser,
    session: SessionDep,
    email: EmailDep,
) -> EmploymentCheckRead:
    """Email a 6-digit code to a work address (personal addresses are refused)."""
    try:
        check = await EmploymentCheckService(session).start(
            user, company=body.company, email=body.email, sender=email
        )
    except EmploymentCheckError as exc:
        raise _unprocessable(exc) from exc
    return _read(check)


@router.post("/{check_id}/resend", response_model=EmploymentCheckRead)
@employment_code_rate_limit
async def resend_code(
    request: Request, check_id: uuid.UUID, user: CurrentUser, session: SessionDep, email: EmailDep
) -> EmploymentCheckRead:
    try:
        return _read(await EmploymentCheckService(session).resend(user, check_id, email))
    except EmploymentCheckNotFoundError as exc:
        raise _NOT_FOUND from exc
    except EmploymentCheckError as exc:
        raise _unprocessable(exc) from exc


@router.post("/{check_id}/confirm", response_model=EmploymentCheckRead)
async def confirm_code(
    check_id: uuid.UUID, body: EmploymentCheckConfirm, user: CurrentUser, session: SessionDep
) -> EmploymentCheckRead:
    try:
        return _read(await EmploymentCheckService(session).confirm(user, check_id, body.code))
    except EmploymentCheckNotFoundError as exc:
        raise _NOT_FOUND from exc
    except EmploymentCheckError as exc:
        raise _unprocessable(exc) from exc


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_check(check_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    try:
        await EmploymentCheckService(session).delete(user, check_id)
    except EmploymentCheckNotFoundError as exc:
        raise _NOT_FOUND from exc
