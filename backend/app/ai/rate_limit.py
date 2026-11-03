"""Per-user rate limiting for endpoints that call the AI, so one account can't run up costs.

Apply with `@ai_rate_limit` under the route decorator; the endpoint must take `request: Request`.
The limit is read from AI_RATE_LIMIT on every request (e.g. "10/hour;30/day").
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.security import InvalidAccessTokenError, decode_access_token


def user_or_ip_key(request: Request) -> str:
    """Rate-limit bucket: the signed-in user, or the client IP if the token is missing/invalid.

    AI endpoints also require auth, so the IP bucket only ever sees rejected requests.
    """
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            return f"user:{decode_access_token(token)}"
        except InvalidAccessTokenError:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=user_or_ip_key,
    storage_uri=get_settings().rate_limit_storage_uri,
)

# One shared budget across every AI endpoint, so users can't multiply it by switching features.
ai_rate_limit = limiter.shared_limit(lambda: get_settings().ai_rate_limit, scope="ai")


def client_ip_key(request: Request) -> str:
    """Per client IP. Behind a proxy, run uvicorn with --proxy-headers so this is the real
    client address rather than the load balancer's."""
    return f"ip:{get_remote_address(request)}"


# Login/register/refresh: per IP, to slow down password guessing and account spam.
auth_rate_limit = limiter.shared_limit(
    lambda: get_settings().auth_rate_limit, scope="auth", key_func=client_ip_key
)
refresh_rate_limit = limiter.shared_limit(
    lambda: get_settings().refresh_rate_limit, scope="refresh", key_func=client_ip_key
)
# File uploads and exports are CPU/storage heavy even when they don't call the AI.
upload_rate_limit = limiter.shared_limit(lambda: get_settings().upload_rate_limit, scope="upload")
export_rate_limit = limiter.shared_limit(lambda: get_settings().export_rate_limit, scope="export")
# Emails to other people (referees) and to the user's work address, per user.
referee_rate_limit = limiter.shared_limit(
    lambda: get_settings().referee_rate_limit, scope="referee"
)
employment_code_rate_limit = limiter.shared_limit(
    lambda: get_settings().employment_code_rate_limit, scope="employment_code"
)
# The public referee page has no sign-in: per client IP, against token guessing.
referee_page_rate_limit = limiter.shared_limit(
    lambda: get_settings().referee_page_rate_limit, scope="referee_page", key_func=client_ip_key
)


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RateLimitExceeded)
    scope = getattr(exc.limit, "scope", "ai")
    what = {
        "auth": "sign-in attempts",
        "refresh": "requests",
        "upload": "uploads",
        "export": "downloads",
        "referee": "referee requests",
        "employment_code": "email codes",
        "referee_page": "requests",
    }.get(scope, "AI features")
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"You've reached the limit for {what} ({exc.detail}). Please try again later."
        },
    )


def try_consume_ai_budget(request: Request) -> bool:
    """Charge one AI call to the caller's shared budget from inside an endpoint.

    For endpoints that only *sometimes* call the AI (e.g. when a cache misses), so plain page
    loads don't spend the budget. Uses the same counters as `@ai_rate_limit`.
    Returns False (and charges nothing) if the budget is exhausted.
    """
    from limits import parse_many

    key = user_or_ip_key(request)
    items = parse_many(get_settings().ai_rate_limit)
    if not all(limiter.limiter.test(item, key, "ai") for item in items):
        return False
    for item in items:
        limiter.limiter.hit(item, key, "ai")
    return True
