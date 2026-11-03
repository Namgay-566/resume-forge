"""Password hashing, JWT access tokens and opaque refresh tokens."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hash = PasswordHash.recommended()  # Argon2id


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


@lru_cache
def _dummy_hash() -> str:
    return _password_hash.hash(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check so login timing doesn't reveal which emails exist."""
    _password_hash.verify(password, _dummy_hash())


class InvalidAccessTokenError(Exception):
    pass


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Return (jwt, lifetime_in_seconds)."""
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(UTC)
    payload = {"sub": str(user_id), "type": "access", "iat": now, "exp": now + lifetime}
    token = jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, int(lifetime.total_seconds())


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    issued_at: datetime


def decode_access_claims(token: str) -> AccessClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
        if payload["type"] != "access":
            raise InvalidAccessTokenError("wrong token type")
        return AccessClaims(
            user_id=uuid.UUID(payload["sub"]),
            issued_at=datetime.fromtimestamp(payload["iat"], UTC),
        )
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise InvalidAccessTokenError(str(exc)) from exc


def decode_access_token(token: str) -> uuid.UUID:
    return decode_access_claims(token).user_id


def issued_before_revocation(issued_at: datetime, revoked_at: datetime | None) -> bool:
    """True if a token predates "sign out everywhere". `iat` has whole-second precision, so
    the cut-off is rounded down: a token issued right after, in the same second, still works."""
    return revoked_at is not None and issued_at < revoked_at.replace(microsecond=0)


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    # Tokens are high-entropy random strings, so a fast hash is sufficient (no salt needed).
    return hashlib.sha256(token.encode()).hexdigest()


def new_oauth_state() -> str:
    return secrets.token_urlsafe(32)
