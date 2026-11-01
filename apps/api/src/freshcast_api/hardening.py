"""Response headers, request size limit and rate limiting for the API."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from freshcast.byod.ingest import MAX_BYTES
from freshcast_api.config import Settings

# Two files plus form overhead; anything larger is refused before it is read.
MAX_REQUEST_BYTES = 2 * MAX_BYTES + 1024 * 1024
DOC_PATHS = ("/docs", "/redoc", "/openapi.json")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class RateLimiter:
    """Sliding one-minute window per (client, bucket); in memory."""

    def __init__(self) -> None:
        """Start with no recorded requests."""
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def allow(
        self, client: str, bucket: str, limit: int, now: float | None = None
    ) -> bool:
        """Record a request and say whether it is within ``limit`` per minute."""
        now = time.monotonic() if now is None else now
        hits = self._hits[(client, bucket)]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


def install(app: FastAPI, settings: Settings) -> None:
    """Add the hardening middleware to ``app``."""
    limiter = RateLimiter()

    @app.middleware("http")
    async def harden(request: Request, call_next):  # type: ignore[no-untyped-def]
        length = request.headers.get("content-length")
        if length is not None and (
            not length.isdigit() or int(length) > MAX_REQUEST_BYTES
        ):
            return JSONResponse({"detail": "request too large"}, status_code=413)
        client = request.client.host if request.client else "unknown"
        analyze = request.url.path.startswith("/v1/analyze")
        limit = (
            settings.analyze_rate_limit_per_minute
            if analyze
            else settings.rate_limit_per_minute
        )
        if not limiter.allow(client, "analyze" if analyze else "api", limit):
            return JSONResponse(
                {"detail": "too many requests"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        response: Response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            if name == "Content-Security-Policy" and request.url.path in DOC_PATHS:
                continue  # the interactive docs load their own scripts
            response.headers.setdefault(name, value)
        return response
