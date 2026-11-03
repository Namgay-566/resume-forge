from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    InvalidAccessTokenError,
    decode_access_claims,
    issued_before_revocation,
)
from app.db.session import get_session
from app.models import User
from app.repositories.user_repository import UserRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise _unauthorized()
    try:
        claims = decode_access_claims(credentials.credentials)
    except InvalidAccessTokenError as exc:
        raise _unauthorized("Invalid or expired token") from exc

    user = await UserRepository(session).get_by_id(claims.user_id)
    if user is None or issued_before_revocation(claims.issued_at, user.sessions_revoked_at):
        raise _unauthorized("Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
