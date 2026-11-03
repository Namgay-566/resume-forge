"""The signed-in user's own account: everything on the Settings page."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.ai.rate_limit import auth_rate_limit, employment_code_rate_limit, export_rate_limit
from app.api.deps import CurrentUser, SessionDep
from app.api.routers.auth import check_origin, clear_refresh_cookie, token_response
from app.schemas.account import (
    AccountDelete,
    EmailChangeConfirm,
    EmailChangePending,
    EmailChangeStart,
    PasswordChange,
    PreferencesUpdate,
    ProfileUpdate,
    Provider,
)
from app.schemas.auth import TokenResponse, UserRead
from app.services.account_service import AccountError, AccountService
from app.services.auth_service import AuthService
from app.services.email.sender import EmailSender, get_email_sender
from app.services.storage.files import FileStorage, get_file_storage

router = APIRouter(prefix="/me", tags=["account"])

EmailDep = Annotated[EmailSender, Depends(get_email_sender)]
StorageDep = Annotated[FileStorage, Depends(get_file_storage)]


def _bad_request(exc: AccountError) -> HTTPException:
    # 400, not 401/403: the frontend treats 401 as "session expired" and signs out.
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("", response_model=UserRead)
async def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("", response_model=UserRead)
async def update_profile(body: ProfileUpdate, user: CurrentUser, session: SessionDep) -> UserRead:
    return UserRead.model_validate(await AccountService(session).update_profile(user, body))


@router.patch("/preferences", response_model=UserRead)
async def update_preferences(
    body: PreferencesUpdate, user: CurrentUser, session: SessionDep
) -> UserRead:
    return UserRead.model_validate(await AccountService(session).update_preferences(user, body))


# --- password and sessions ------------------------------------------------------------


@router.post("/password", response_model=TokenResponse)
@auth_rate_limit
async def change_password(
    request: Request,  # required by the rate limiter
    body: PasswordChange,
    response: Response,
    user: CurrentUser,
    session: SessionDep,
    sender: EmailDep,
) -> TokenResponse:
    """Change (or set a first) password. Every other device is signed out; this one gets a
    fresh session."""
    try:
        await AccountService(session).change_password(user, body, sender)
    except AccountError as exc:
        raise _bad_request(exc) from exc
    return token_response(response, user, await AuthService(session).issue_tokens(user))


@router.post("/sign-out-everywhere", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out_everywhere(
    request: Request, response: Response, user: CurrentUser, session: SessionDep
) -> None:
    """Ends every session, including this one."""
    check_origin(request)
    await AccountService(session).sign_out_everywhere(user)
    clear_refresh_cookie(response)


# --- email change ---------------------------------------------------------------------


@router.get("/email-change", response_model=EmailChangePending | None)
async def pending_email_change(user: CurrentUser, session: SessionDep) -> EmailChangePending | None:
    pending = await AccountService(session).pending_email_change(user)
    return EmailChangePending(new_email=pending.new_email) if pending else None


@router.post("/email-change", response_model=EmailChangePending)
@auth_rate_limit
@employment_code_rate_limit
async def start_email_change(
    request: Request,
    body: EmailChangeStart,
    user: CurrentUser,
    session: SessionDep,
    sender: EmailDep,
) -> EmailChangePending:
    """Send a 6-digit code to the new address. Nothing changes until it's entered."""
    try:
        pending = await AccountService(session).start_email_change(user, body, sender)
    except AccountError as exc:
        raise _bad_request(exc) from exc
    return EmailChangePending(new_email=pending.new_email)


@router.post("/email-change/confirm", response_model=UserRead)
@auth_rate_limit
async def confirm_email_change(
    request: Request,
    body: EmailChangeConfirm,
    user: CurrentUser,
    session: SessionDep,
    sender: EmailDep,
) -> UserRead:
    try:
        updated = await AccountService(session).confirm_email_change(user, body.code, sender)
    except AccountError as exc:
        raise _bad_request(exc) from exc
    return UserRead.model_validate(updated)


@router.delete("/email-change", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_email_change(user: CurrentUser, session: SessionDep) -> None:
    await AccountService(session).cancel_email_change(user)


# --- connected sign-in providers --------------------------------------------------------
# Connecting is a full-page redirect: GET /api/auth/{provider}/login?link=true


@router.delete("/providers/{provider}", response_model=UserRead)
async def disconnect_provider(
    provider: Provider, user: CurrentUser, session: SessionDep, sender: EmailDep
) -> UserRead:
    try:
        return UserRead.model_validate(
            await AccountService(session).disconnect(user, provider, sender)
        )
    except AccountError as exc:
        raise _bad_request(exc) from exc


# --- your data --------------------------------------------------------------------------


@router.get(
    "/export",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}}},
)
@export_rate_limit
async def export_data(
    request: Request, user: CurrentUser, session: SessionDep, storage: StorageDep
) -> Response:
    """Everything stored about you: a ZIP of JSON files plus your uploaded proof files."""
    exported = await AccountService(session).export_data(user, storage)
    ascii_name = exported.filename.encode("ascii", "ignore").decode() or "ResumeForge-data.zip"
    return Response(
        content=exported.content,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}"; '
                f"filename*=UTF-8''{quote(exported.filename)}"
            ),
            "Cache-Control": "no-store",
        },
    )


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
@auth_rate_limit
async def delete_account(
    request: Request,
    body: AccountDelete,
    response: Response,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
) -> None:
    """Permanently delete the account and everything in it. POST, not DELETE: it has a body."""
    check_origin(request)
    try:
        await AccountService(session).delete_account(user, body, storage)
    except AccountError as exc:
        raise _bad_request(exc) from exc
    clear_refresh_cookie(response)
