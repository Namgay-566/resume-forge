"""Plain ASGI middleware (no BaseHTTPMiddleware) so uploads and downloads stream through."""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _TooLarge(Exception):
    pass


async def _reject(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    """Refuse request bodies over `max_bytes` before the app parses them: checked against
    Content-Length up front, and counted while streaming for chunked uploads. Without this, a
    multipart upload is spooled in full before the endpoint's own 5 MB check runs."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > self.max_bytes):
            await _reject(send, 413, "Request is too large.")
            return

        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _TooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _TooLarge:
            if not started:
                await _reject(send, 413, "Request is too large.")


_BASE_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
# The API only ever returns JSON and files; nothing it serves should run scripts or be framed.
_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")
_HSTS = (b"strict-transport-security", b"max-age=63072000; includeSubDomains")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool, docs_paths: tuple[str, ...] = ()) -> None:
        self.app = app
        self.hsts = hsts
        self.docs_paths = docs_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = list(_BASE_HEADERS)
        # Swagger UI (dev only) needs its scripts and styles.
        if not scope["path"].startswith(self.docs_paths or ("\0",)):
            extra.append(_CSP)
        if self.hsts:
            extra.append(_HSTS)

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                present = {name.lower() for name, _ in message.get("headers", [])}
                message["headers"] = [
                    *message.get("headers", []),
                    *(h for h in extra if h[0] not in present),
                ]
            await send(message)

        await self.app(scope, receive, with_headers)
