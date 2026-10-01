"""Process-local per-client rate limiting for harvest/ARC write POSTs."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Final, Literal, cast
from urllib.parse import unquote

from cryptography import x509
from cryptography.x509.oid import NameOID
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .admission_control import choose_retry_after_seconds

logger = logging.getLogger("middleware_api")

LimitClass = Literal["harvest_create", "arc_submit"]

ANONYMOUS_CLIENT_KEY: Final[str] = "anonymous"
_WINDOW_SECONDS: Final[float] = 60.0
_HARVEST_ARCS_PATH: Final[re.Pattern[str]] = re.compile(r"^/v3/harvests/[^/]+/arcs$")


@dataclass
class _WindowCounter:
    """Fixed one-minute window counter for a single (client, class) key."""

    start_monotonic: float
    count: int


def classify_rate_limited_request(method: str, path: str) -> LimitClass | None:
    """Return the limit class for a request, or ``None`` if not rate-limited."""
    if method.upper() != "POST":
        return None
    normalized = path.rstrip("/") or "/"
    if normalized == "/v3/harvests":
        return "harvest_create"
    if normalized in {"/v3/arcs", "/v2/arcs"}:
        return "arc_submit"
    if _HARVEST_ARCS_PATH.fullmatch(normalized):
        return "arc_submit"
    return None


def _header_value(scope: Scope, *names: str) -> str | None:
    headers = cast(list[tuple[bytes, bytes]], scope.get("headers") or [])
    wanted = {name.lower().encode("latin-1") for name in names}
    for key, value in headers:
        if key.lower() in wanted:
            return value.decode("latin-1")
    return None


def resolve_rate_limit_client_key(scope: Scope) -> str:
    """Resolve the rate-limit bucket key from mTLS headers (CN or ``anonymous``)."""
    client_cert = _header_value(scope, "ssl-client-cert", "x-ssl-client-cert")
    client_verify = _header_value(scope, "ssl-client-verify", "x-ssl-client-verify") or "NONE"
    if not client_cert or client_verify != "SUCCESS":
        return ANONYMOUS_CLIENT_KEY

    try:
        cert_pem = unquote(client_cert)
        cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        cn_attributes = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if not cn_attributes:
            return ANONYMOUS_CLIENT_KEY
        value = cn_attributes[0].value
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)
    except (ValueError, TypeError, UnicodeError):
        return ANONYMOUS_CLIENT_KEY


class RateLimitingMiddleware:
    """Reject over-quota write POSTs with ``429`` + ``Retry-After``.

    Process-local fixed one-minute windows keyed by ``(client_key, limit_class)``.
    Unlisted routes pass through unchanged.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        harvest_create_per_minute: int,
        arc_submit_per_minute: int,
        retry_after_seconds: int,
    ) -> None:
        """Initialize middleware.

        Args:
            app: Downstream ASGI application.
            harvest_create_per_minute: Limit for ``POST /v3/harvests`` (``<=0`` = unlimited).
            arc_submit_per_minute: Limit for ARC submit POSTs (``<=0`` = unlimited).
            retry_after_seconds: Inclusive upper bound for jittered ``Retry-After``.
        """
        if retry_after_seconds <= 0:
            msg = "retry_after_seconds must be positive"
            raise ValueError(msg)

        self.app = app
        self._harvest_create_per_minute = harvest_create_per_minute
        self._arc_submit_per_minute = arc_submit_per_minute
        self._retry_after_seconds = retry_after_seconds
        self._windows: dict[tuple[str, LimitClass], _WindowCounter] = {}
        self._lock = asyncio.Lock()

    def _limit_for_class(self, limit_class: LimitClass) -> int:
        if limit_class == "harvest_create":
            return self._harvest_create_per_minute
        return self._arc_submit_per_minute

    async def _try_acquire(self, client_key: str, limit_class: LimitClass, limit: int) -> bool:
        if limit <= 0:
            return True

        key = (client_key, limit_class)
        now = time.monotonic()
        async with self._lock:
            window = self._windows.get(key)
            if window is None or (now - window.start_monotonic) >= _WINDOW_SECONDS:
                self._windows[key] = _WindowCounter(start_monotonic=now, count=1)
                return True
            if window.count >= limit:
                return False
            window.count += 1
            return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI entry point."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "GET"))
        path = str(scope.get("path", ""))
        limit_class = classify_rate_limited_request(method, path)
        if limit_class is None:
            await self.app(scope, receive, send)
            return

        limit = self._limit_for_class(limit_class)
        client_key = resolve_rate_limit_client_key(scope)
        allowed = await self._try_acquire(client_key, limit_class, limit)
        if allowed:
            await self.app(scope, receive, send)
            return

        retry_after = choose_retry_after_seconds(self._retry_after_seconds)
        logger.warning(
            "Rate limit rejected: client=%s class=%s limit=%d path=%s method=%s retry_after=%d",
            client_key,
            limit_class,
            limit,
            path,
            method,
            retry_after,
        )
        response = JSONResponse(
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            content={"detail": "Too many requests"},
            headers={"Retry-After": str(retry_after)},
        )
        await response(scope, receive, send)
