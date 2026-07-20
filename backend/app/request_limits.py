"""Reject oversized request bodies before Starlette parses them.

Layering: the check inside the upload handler is the *guarantee* — Content-Length
is absent on chunked uploads, so this middleware can't be the only one. This is
the cheap outer layer that stops a large body from being spooled to disk at all,
which is what the handler-level check cannot do (FastAPI parses the full
multipart body before the handler is entered).

Pure ASGI rather than BaseHTTPMiddleware: this only reads a header and either
short-circuits or delegates, so it has no reason to pay for the request/response
wrapping BaseHTTPMiddleware does.
"""

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_MESSAGE


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            declared = Headers(scope=scope).get("content-length")
            # A non-numeric Content-Length is left to the server to reject.
            if declared and declared.isdigit() and int(declared) > self.max_bytes:
                response = JSONResponse({"detail": MAX_UPLOAD_MESSAGE}, status_code=413)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
