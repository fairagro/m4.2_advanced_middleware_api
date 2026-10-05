"""Unit tests for process-local per-client rate limiting."""

from __future__ import annotations

import datetime
from http import HTTPStatus

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from httpx import ASGITransport
from pydantic import ValidationError

from middleware.api.api.fastapi_app import Api
from middleware.api.api.rate_limiting import (
    ANONYMOUS_CLIENT_KEY,
    RateLimitingMiddleware,
    classify_rate_limited_request,
    resolve_rate_limit_client_key,
)
from middleware.api.business_logic import BusinessLogic
from middleware.api.config import Config, RateLimitingConfig


def _minimal_config(**overrides: object) -> Config:
    data: dict[str, object] = {
        "log_level": "DEBUG",
        "celery": {"broker_url": "memory://"},
        "couchdb": {"url": "http://localhost:5984"},
        "arc_store": {
            "git_repo": {
                "url": "https://localhost/",
                "branch": "dummy",
                "group": "dummy-group",
            },
        },
    }
    data.update(overrides)
    return Config.from_data(data)


def _pem_cert_with_cn(common_name: str) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509
        .CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


def _app_with_rate_limit(
    *,
    harvest_create_per_minute: int = 10,
    arc_submit_per_minute: int = 60,
    retry_after_seconds: int = 7,
) -> FastAPI:
    app = FastAPI()

    @app.post("/v3/harvests")
    async def create_harvest() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v3/arcs")
    async def create_arc() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v2/arcs")
    async def create_arc_v2() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v3/harvests/{harvest_id}/arcs")
    async def create_harvest_arc(harvest_id: str) -> dict[str, str]:
        return {"status": "ok", "harvest_id": harvest_id}

    @app.get("/v3/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.add_middleware(
        RateLimitingMiddleware,
        harvest_create_per_minute=harvest_create_per_minute,
        arc_submit_per_minute=arc_submit_per_minute,
        retry_after_seconds=retry_after_seconds,
    )
    return app


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/v3/harvests", "harvest_create"),
        ("POST", "/v3/harvests/", "harvest_create"),
        ("POST", "/v3/arcs", "arc_submit"),
        ("POST", "/v2/arcs", "arc_submit"),
        ("POST", "/v3/harvests/h1/arcs", "arc_submit"),
        ("POST", "/v3/harvests/h1/arcs/", "arc_submit"),
        ("GET", "/v3/harvests", None),
        ("POST", "/v3/health", None),
        ("POST", "/v3/harvests/h1", None),
        ("POST", "/v1/arcs", None),
    ],
)
def test_classify_rate_limited_request(method: str, path: str, expected: str | None) -> None:
    """Only the scoped write POSTs map to a limit class."""
    assert classify_rate_limited_request(method, path) == expected


def test_config_defaults_disable_rate_limiting() -> None:
    """Rate limiting is off by default with issue default rates."""
    config = _minimal_config()
    assert config.rate_limiting.enabled is False
    assert config.rate_limiting.harvest_create_per_minute == 10  # noqa: PLR2004
    assert config.rate_limiting.arc_submit_per_minute == 60  # noqa: PLR2004
    assert config.rate_limiting.retry_after_seconds == 60  # noqa: PLR2004


def test_config_accepts_nested_rate_limiting() -> None:
    """Nested rate_limiting block is parsed into RateLimitingConfig."""
    config = _minimal_config(
        rate_limiting={
            "enabled": True,
            "harvest_create_per_minute": 3,
            "arc_submit_per_minute": 5,
            "retry_after_seconds": 9,
        }
    )
    assert config.rate_limiting.enabled is True
    assert config.rate_limiting.harvest_create_per_minute == 3  # noqa: PLR2004
    assert config.rate_limiting.arc_submit_per_minute == 5  # noqa: PLR2004
    assert config.rate_limiting.retry_after_seconds == 9  # noqa: PLR2004


def test_config_rejects_unknown_rate_limiting_keys() -> None:
    """Unknown keys under rate_limiting are rejected (extra=forbid)."""
    with pytest.raises(ValidationError):
        _minimal_config(rate_limiting={"enabled_typo": True})


@pytest.mark.asyncio
async def test_under_limit_succeeds() -> None:
    """Requests under the class limit are handled normally."""
    app = _app_with_rate_limit(harvest_create_per_minute=2)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/v3/harvests")
        second = await client.post("/v3/harvests")
    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_over_limit_returns_429_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    """Over-quota POSTs receive 429 and Retry-After without running the handler."""
    monkeypatch.setattr(
        "middleware.api.api.rate_limiting.choose_retry_after_seconds",
        lambda _max: 9,
    )
    hit = {"count": 0}
    app = FastAPI()

    @app.post("/v3/harvests")
    async def create_harvest() -> dict[str, str]:
        hit["count"] += 1
        return {"status": "ok"}

    app.add_middleware(
        RateLimitingMiddleware,
        harvest_create_per_minute=1,
        arc_submit_per_minute=60,
        retry_after_seconds=9,
    )
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/v3/harvests")
        second = await client.post("/v3/harvests")

    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert second.headers["retry-after"] == "9"
    assert second.json()["detail"] == "Too many requests"
    assert hit["count"] == 1


@pytest.mark.asyncio
async def test_expired_windows_are_pruned(monkeypatch: pytest.MonkeyPatch) -> None:
    """Idle (client, class) windows are removed after the fixed interval."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        "middleware.api.api.rate_limiting.time.monotonic",
        lambda: clock["now"],
    )
    middleware = RateLimitingMiddleware(
        FastAPI(),
        harvest_create_per_minute=10,
        arc_submit_per_minute=60,
        retry_after_seconds=7,
    )
    # pylint: disable=protected-access
    assert await middleware._try_acquire("client-a", "harvest_create", 10)
    assert await middleware._try_acquire("client-b", "harvest_create", 10)
    assert len(middleware._windows) == 2

    clock["now"] += 60.0
    assert await middleware._try_acquire("client-c", "harvest_create", 10)
    assert set(middleware._windows) == {("client-c", "harvest_create")}


@pytest.mark.asyncio
async def test_window_resets_after_one_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    """After the fixed window elapses, a new request is allowed again."""
    clock = {"now": 1000.0}
    monkeypatch.setattr(
        "middleware.api.api.rate_limiting.time.monotonic",
        lambda: clock["now"],
    )
    app = _app_with_rate_limit(harvest_create_per_minute=1)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/v3/harvests")
        blocked = await client.post("/v3/harvests")
        clock["now"] += 60.0
        after_reset = await client.post("/v3/harvests")

    assert first.status_code == HTTPStatus.OK
    assert blocked.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert after_reset.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_unlimited_class_when_non_positive() -> None:
    """Non-positive class limit disables limiting for that class only."""
    app = _app_with_rate_limit(harvest_create_per_minute=0, arc_submit_per_minute=1)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            response = await client.post("/v3/harvests")
            assert response.status_code == HTTPStatus.OK
        first_arc = await client.post("/v3/arcs")
        second_arc = await client.post("/v3/arcs")
    assert first_arc.status_code == HTTPStatus.OK
    assert second_arc.status_code == HTTPStatus.TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_arc_submit_paths_share_bucket() -> None:
    """v2/v3 arcs and harvest-scoped arcs share the arc-submit class limit."""
    app = _app_with_rate_limit(arc_submit_per_minute=2)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/v3/arcs")).status_code == HTTPStatus.OK
        assert (await client.post("/v2/arcs")).status_code == HTTPStatus.OK
        rejected = await client.post("/v3/harvests/h1/arcs")
    assert rejected.status_code == HTTPStatus.TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_unlisted_route_not_limited() -> None:
    """Routes outside the scoped write POSTs are not rate-limited."""
    app = _app_with_rate_limit(harvest_create_per_minute=1, arc_submit_per_minute=1)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            response = await client.get("/v3/health")
            assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_anonymous_callers_share_bucket() -> None:
    """Requests without a usable client cert share the anonymous bucket."""
    app = _app_with_rate_limit(harvest_create_per_minute=1)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/v3/harvests")
        second = await client.post("/v3/harvests")
    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_distinct_client_cns_have_separate_buckets() -> None:
    """Different certificate CNs do not share a rate-limit bucket."""
    app = _app_with_rate_limit(harvest_create_per_minute=1)
    transport = ASGITransport(app=app)
    cert_a = _pem_cert_with_cn("client-a")
    cert_b = _pem_cert_with_cn("client-b")
    headers_a = {"ssl-client-cert": cert_a, "ssl-client-verify": "SUCCESS"}
    headers_b = {"ssl-client-cert": cert_b, "ssl-client-verify": "SUCCESS"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/v3/harvests", headers=headers_a)).status_code == HTTPStatus.OK
        assert (await client.post("/v3/harvests", headers=headers_b)).status_code == HTTPStatus.OK
        rejected_a = await client.post("/v3/harvests", headers=headers_a)
    assert rejected_a.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_resolve_rate_limit_client_key_from_cert() -> None:
    """CN from a verified client cert becomes the bucket key."""
    cert = _pem_cert_with_cn("rate-limit-client")
    scope: dict[str, object] = {
        "type": "http",
        "headers": [
            (b"ssl-client-cert", cert.encode("latin-1")),
            (b"ssl-client-verify", b"SUCCESS"),
        ],
    }
    assert resolve_rate_limit_client_key(scope) == "rate-limit-client"
    state = scope.get("state")
    assert isinstance(state, dict)
    assert isinstance(state.get("cert"), x509.Certificate)


def test_resolve_rate_limit_client_key_anonymous_without_cert() -> None:
    """Missing cert falls back to the anonymous key without caching cert=None."""
    scope: dict[str, object] = {"type": "http", "headers": []}
    assert resolve_rate_limit_client_key(scope) == ANONYMOUS_CLIENT_KEY
    assert "state" not in scope


def test_middleware_rejects_non_positive_retry_after() -> None:
    """Constructing middleware with a non-positive Retry-After bound raises ValueError."""
    app = FastAPI()
    with pytest.raises(ValueError, match="retry_after_seconds must be positive"):
        RateLimitingMiddleware(
            app,
            harvest_create_per_minute=10,
            arc_submit_per_minute=60,
            retry_after_seconds=0,
        )


def test_api_wires_middleware_when_enabled(config: Config, service: BusinessLogic) -> None:
    """Api registers rate-limiting middleware when enabled."""
    limited = config.model_copy(update={"rate_limiting": RateLimitingConfig(enabled=True, harvest_create_per_minute=2)})
    api = Api(limited)
    api.business_logic = service
    assert any(m.cls is RateLimitingMiddleware for m in api.app.user_middleware)


def test_api_skips_middleware_when_disabled(config: Config, service: BusinessLogic) -> None:
    """Api does not register rate-limiting middleware when disabled (default)."""
    api = Api(config)
    api.business_logic = service
    assert config.rate_limiting.enabled is False
    assert all(m.cls is not RateLimitingMiddleware for m in api.app.user_middleware)
