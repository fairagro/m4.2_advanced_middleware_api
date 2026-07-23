"""Unit tests for process-local HTTP admission control."""

from __future__ import annotations

import asyncio
from http import HTTPStatus

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from middleware.api.api.admission_control import (
    AdmissionControlMiddleware,
    choose_retry_after_seconds,
    is_admission_exempt_path,
)
from middleware.api.api.fastapi_app import Api
from middleware.api.business_logic import BusinessLogic
from middleware.api.config import Config


def _minimal_config(**overrides: object) -> Config:
    data: dict[str, object] = {
        "log_level": "DEBUG",
        "celery": {"broker_url": "memory://"},
        "couchdb": {"url": "http://localhost:5984"},
        "git_repo": {
            "url": "https://localhost/",
            "branch": "dummy",
            "group": "dummy-group",
        },
    }
    data.update(overrides)
    return Config.from_data(data)


def _app_with_admission(*, max_concurrent: int, retry_after: int = 7) -> FastAPI:
    app = FastAPI()

    @app.get("/work")
    async def work() -> dict[str, str]:
        await asyncio.sleep(0.05)
        return {"status": "ok"}

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("handler failed")

    @app.get("/v3/liveness")
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v3/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.add_middleware(
        AdmissionControlMiddleware,
        max_concurrent_requests=max_concurrent,
        retry_after_seconds=retry_after,
    )
    return app


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/v3/liveness", True),
        ("/v3/liveness/", True),
        ("/v3/readiness", True),
        ("/v3/health", True),
        ("/v1/health", True),
        ("/v2/health", True),
        ("/v3/arcs", False),
        ("/v3/harvests/h1/arcs", False),
        ("/", False),
    ],
)
def test_is_admission_exempt_path(path: str, expected: bool) -> None:
    """Probe paths are exempt; business paths are not."""
    assert is_admission_exempt_path(path) is expected


def test_config_defaults_disable_admission() -> None:
    """Unset max_concurrent_requests leaves admission control off."""
    config = _minimal_config()
    assert config.max_concurrent_requests is None
    assert config.retry_after_seconds == 5  # noqa: PLR2004


def test_config_accepts_positive_limit() -> None:
    """Positive max_concurrent_requests is stored on Config."""
    config = _minimal_config(max_concurrent_requests=10, retry_after_seconds=3)
    assert config.max_concurrent_requests == 10  # noqa: PLR2004
    assert config.retry_after_seconds == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_under_limit_succeeds() -> None:
    """Requests under the limit are handled normally."""
    app = _app_with_admission(max_concurrent=2)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/work")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_at_capacity_returns_503_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    """Surplus requests receive 503 and a jittered Retry-After without running the handler."""
    monkeypatch.setattr(
        "middleware.api.api.admission_control.choose_retry_after_seconds",
        lambda _max: 9,
    )
    app = _app_with_admission(max_concurrent=1, retry_after=9)
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = asyncio.create_task(client.get("/work"))
        await asyncio.sleep(0.01)  # let first request acquire the slot
        second = await client.get("/work")
        first_response = await first

    assert first_response.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert second.headers["retry-after"] == "9"
    assert second.json()["detail"] == "Service temporarily unavailable"


def test_choose_retry_after_seconds_stays_within_bounds() -> None:
    """Jittered Retry-After values are in the inclusive range 1..max."""
    samples = {choose_retry_after_seconds(5) for _ in range(40)}
    assert samples <= {1, 2, 3, 4, 5}
    assert min(samples) >= 1
    assert max(samples) <= 5  # noqa: PLR2004


@pytest.mark.asyncio
async def test_probe_exempt_at_capacity() -> None:
    """Health/liveness probes succeed even when the admission limit is saturated."""
    app = _app_with_admission(max_concurrent=1)
    transport = ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        busy = asyncio.create_task(client.get("/work"))
        await asyncio.sleep(0.01)
        probe = await client.get("/v3/liveness")
        health = await client.get("/v3/health")
        await busy

    assert probe.status_code == HTTPStatus.OK
    assert health.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_slot_released_after_handler_error() -> None:
    """A failing handler still releases its admission slot."""
    app = _app_with_admission(max_concurrent=1)
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        boom = await client.get("/boom")
        assert boom.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        ok = await client.get("/work")

    assert ok.status_code == HTTPStatus.OK


def test_middleware_rejects_non_positive_limit() -> None:
    """Constructing middleware with a non-positive limit raises ValueError."""
    app = FastAPI()
    with pytest.raises(ValueError, match="max_concurrent_requests must be positive"):
        AdmissionControlMiddleware(app, max_concurrent_requests=0, retry_after_seconds=5)


def test_api_wires_middleware_when_configured(config: Config, service: BusinessLogic) -> None:
    """Api registers admission middleware when max_concurrent_requests is positive."""
    limited = config.model_copy(update={"max_concurrent_requests": 2, "retry_after_seconds": 4})
    api = Api(limited)
    api.business_logic = service
    assert any(m.cls is AdmissionControlMiddleware for m in api.app.user_middleware)


def test_api_skips_middleware_when_disabled(config: Config, service: BusinessLogic) -> None:
    """Api does not register admission middleware when limit is unset."""
    api = Api(config)
    api.business_logic = service
    assert config.max_concurrent_requests is None
    assert all(m.cls is not AdmissionControlMiddleware for m in api.app.user_middleware)


def test_api_skips_middleware_when_non_positive(config: Config, service: BusinessLogic) -> None:
    """Api does not register admission middleware when limit is <= 0."""
    disabled = config.model_copy(update={"max_concurrent_requests": 0})
    api = Api(disabled)
    api.business_logic = service
    assert all(m.cls is not AdmissionControlMiddleware for m in api.app.user_middleware)
