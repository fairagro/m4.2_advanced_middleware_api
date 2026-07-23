"""Process-local HTTP admission control (max concurrent in-flight requests)."""

from __future__ import annotations

import asyncio
import logging
import secrets
from http import HTTPStatus
from typing import Final

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("middleware_api")

# Probe paths must remain reachable under load (do not consume admission slots).
_EXEMPT_PATHS: Final[frozenset[str]] = frozenset({
    "/v3/liveness",
    "/v3/readiness",
    "/v3/health",
    "/v1/health",
    "/v2/health",
})


def is_admission_exempt_path(path: str) -> bool:
    """Return whether *path* is exempt from admission control."""
    normalized = path.rstrip("/") or "/"
    return normalized in _EXEMPT_PATHS


def choose_retry_after_seconds(max_seconds: int) -> int:
    """Pick a positive Retry-After delay uniformly from ``1..max_seconds``."""
    if max_seconds <= 0:
        msg = "max_seconds must be positive"
        raise ValueError(msg)
    return secrets.randbelow(max_seconds) + 1


class AdmissionControlMiddleware:
    """Reject surplus requests with ``503`` + ``Retry-After`` when at capacity.

    Fail-fast (never blocks waiting for a slot). Exempt probe paths bypass the
    limit and do not occupy a slot.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_concurrent_requests: int,
        retry_after_seconds: int,
    ) -> None:
        """Initialize middleware.

        Args:
            app: Downstream ASGI application.
            max_concurrent_requests: Positive max in-flight non-exempt requests.
            retry_after_seconds: Inclusive upper bound for jittered ``Retry-After``.
        """
        if max_concurrent_requests <= 0:
            msg = "max_concurrent_requests must be positive when admission control is enabled"
            raise ValueError(msg)
        if retry_after_seconds <= 0:
            msg = "retry_after_seconds must be positive"
            raise ValueError(msg)

        self.app = app
        self._max_concurrent_requests = max_concurrent_requests
        self._retry_after_seconds = retry_after_seconds
        self._in_flight = 0
        self._lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI entry point."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if is_admission_exempt_path(path):
            await self.app(scope, receive, send)
            return

        async with self._lock:
            if self._in_flight >= self._max_concurrent_requests:
                retry_after = choose_retry_after_seconds(self._retry_after_seconds)
                logger.warning(
                    "Admission rejected: at capacity (in_flight=%d, limit=%d) path=%s method=%s retry_after=%d",
                    self._in_flight,
                    self._max_concurrent_requests,
                    path,
                    scope.get("method", "?"),
                    retry_after,
                )
                response = JSONResponse(
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                    content={"detail": "Service temporarily unavailable"},
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return
            self._in_flight += 1

        try:
            await self.app(scope, receive, send)
        finally:
            async with self._lock:
                self._in_flight -= 1
