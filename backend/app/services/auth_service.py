from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository

# Two tabs refreshing at the same moment both send the same cookie. A token rotated this
# recently is treated as that race, not as theft.
ROTATION_GRACE = timedelta(seconds=30)


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True)
class GitHubProfile:
    id: int
    login: str
    name: str | None
    # Primary verified email, if the user has one.
    verified_email: str | None


@dataclass(frozen=True)
class OidcProfile:
    """A Google or LinkedIn account, from its OpenID Connect userinfo."""

    provider: Literal["google", "linkedin"]
    subject: str  # the provider's stable account id ("sub")
    name: str | None
    verified_email: str | None
    # The public profile page, when the provider shares it (LinkedIn usually doesn't).
    profile_url: str | None = None


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def register(self, *, email: str, password: str, name: str) -> User:
        if await self.users.get_by_email(email):
            raise EmailAlreadyRegisteredError
        try:
            user = await self.users.add(
                User(email=email.lower(), hashed_password=hash_password(password), name=name)
            )
        except IntegrityError as exc:  # concurrent registration with the same email
            await self.session.rollback()
            raise EmailAlreadyRegisteredError from exc
        await self.session.commit()
        return user

    async def authenticate(self, *, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)
        # Users created via GitHub, Google or LinkedIn have no password and cannot log in this way.
        if user is None or user.hashed_password is None:
            burn_password_check(password)
            raise InvalidCredentialsError
        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError
        return user

    async def issue_tokens(self, user: User) -> IssuedTokens:
        await self.refresh_tokens.delete_expired_for_user(user.id)
        raw = new_refresh_token()
        expires_at = datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days)
        await self.refresh_tokens.add(
            RefreshToken(user_id=user.id, token_hash=hash_refresh_token(raw), expires_at=expires_at)
        )
        await self.session.commit()

        access_token, expires_in = create_access_token(user.id)
        return IssuedTokens(access_token, expires_in, raw, expires_at)

    async def refresh(self, raw_token: str) -> tuple[User, IssuedTokens]:
        """Rotate a refresh token: the presented one is retired and a new pair is issued."""
        stored = await self.refresh_tokens.get_by_hash(hash_refresh_token(raw_token))
        now = datetime.now(UTC)
        if stored is None or stored.expires_at <= now:
            raise InvalidRefreshTokenError

        if stored.revoked_at is not None and now - stored.revoked_at > ROTATION_GRACE:
            # An old, already-rotated token came back: assume it was stolen and end every session.
            # Delete rather than revoke, so no token lands inside the grace window.
            await self.refresh_tokens.delete_all_for_user(stored.user_id)
            await self.session.commit()
            raise InvalidRefreshTokenError

        user = await self.users.get_by_id(stored.user_id)
        if user is None:
            raise InvalidRefreshTokenError
        if stored.revoked_at is None:
            stored.revoked_at = now
        return user, await self.issue_tokens(user)

    async def user_for_refresh_token(self, raw_token: str) -> User | None:
        """The signed-in user behind a live refresh cookie, without rotating it. Used when
        connecting another sign-in method from Settings (a full-page OAuth redirect carries
        no access token, only the cookie)."""
        stored = await self.refresh_tokens.get_by_hash(hash_refresh_token(raw_token))
        if (
            stored is None
            or stored.revoked_at is not None
            or stored.expires_at <= datetime.now(UTC)
        ):
            return None
        return await self.users.get_by_id(stored.user_id)

    async def logout(self, raw_token: str) -> None:
        stored = await self.refresh_tokens.get_by_hash(hash_refresh_token(raw_token))
        if stored is not None:
            # Deleted, not revoked, so a replayed logout token is simply unknown.
            await self.refresh_tokens.delete(stored)
            await self.session.commit()

    async def login_with_github(self, profile: GitHubProfile) -> User:
        """Find the user by GitHub id, else link by verified email, else create one."""
        user = await self.users.get_by_github_id(profile.id)
        if user is None and profile.verified_email:
            user = await self.users.get_by_email(profile.verified_email)

        if user is None:
            # GitHub's documented no-reply address keeps email unique when none is public.
            email = (
                profile.verified_email or f"{profile.id}+{profile.login}@users.noreply.github.com"
            )
            user = await self.users.add(
                User(email=email.lower(), name=profile.name or profile.login, hashed_password=None)
            )

        user.github_id = profile.id
        user.github_username = profile.login  # refreshed on every login in case it was renamed
        await self.session.commit()
        return user

    async def login_with_oidc(self, profile: OidcProfile) -> User:
        """Google or LinkedIn: find the user by provider id, else link by verified email,
        else create one. Same rules as GitHub."""
        if profile.provider == "google":
            user = await self.users.get_by_google_id(profile.subject)
        else:
            user = await self.users.get_by_linkedin_id(profile.subject)
        if user is None and profile.verified_email:
            user = await self.users.get_by_email(profile.verified_email)

        if user is None:
            # No verified email shared: a unique placeholder on the reserved .invalid domain.
            email = profile.verified_email or (
                f"{profile.provider}-{profile.subject}@users.noreply.invalid"
            )
            user = await self.users.add(
                User(
                    email=email.lower()[:320],
                    name=profile.name or email.split("@")[0][:200],
                    hashed_password=None,
                )
            )

        if profile.provider == "google":
            user.google_id = profile.subject
        else:
            user.linkedin_id = profile.subject
            if profile.profile_url:
                user.linkedin_url = profile.profile_url
        await self.session.commit()
        return user
