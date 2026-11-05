"""Unit tests for the v3/system endpoints."""

import http
import unittest.mock
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from middleware.api.api.fastapi_app import Api

_VERSION = "9.9.9-test"


def test_v3_version_get(client: TestClient) -> None:
    """GET /v3/version returns the resolved package version."""
    with patch(
        "middleware.api.api.v3.system.resolve_api_package_version",
        return_value=_VERSION,
    ):
        response = client.get("/v3/version", headers={"accept": "application/json"})

    assert response.status_code == http.HTTPStatus.OK
    assert response.json() == {"version": _VERSION}


def test_v3_version_head(client: TestClient) -> None:
    """HEAD /v3/version returns 200 with an empty body."""
    with patch(
        "middleware.api.api.v3.system.resolve_api_package_version",
        return_value=_VERSION,
    ):
        response = client.head("/v3/version", headers={"accept": "application/json"})

    assert response.status_code == http.HTTPStatus.OK
    assert response.content == b""


def test_v3_liveness_success(client: TestClient, middleware_api: Api) -> None:
    """Test /v3/liveness returns process liveness."""
    with unittest.mock.patch.object(
        middleware_api.health_service,
        "liveness_checks",
        side_effect=AsyncMock(return_value={"api_process": True}),
    ):
        response = client.get("/v3/liveness", headers={"accept": "application/json"})

    assert response.status_code == http.HTTPStatus.OK
    assert response.json() == {
        "status": "ok",
        "services": {"api_process": True},
    }


def test_v3_readiness_success(client: TestClient, middleware_api: Api) -> None:
    """Test /v3/readiness returns 200 if all direct dependencies are ready."""
    with unittest.mock.patch.object(
        middleware_api.health_service,
        "readiness_checks",
        side_effect=AsyncMock(return_value={"couchdb_reachable": True, "rabbitmq": True}),
    ):
        response = client.get("/v3/readiness", headers={"accept": "application/json"})

    assert response.status_code == http.HTTPStatus.OK
    assert response.json() == {
        "status": "ok",
        "services": {"couchdb_reachable": True, "rabbitmq": True},
    }


def test_v3_readiness_failure(client: TestClient, middleware_api: Api) -> None:
    """Test /v3/readiness returns 503 if any direct dependency is not ready."""
    with unittest.mock.patch.object(
        middleware_api.health_service,
        "readiness_checks",
        side_effect=AsyncMock(return_value={"couchdb_reachable": False, "rabbitmq": True}),
    ):
        response = client.get("/v3/readiness", headers={"accept": "application/json"})

    assert response.status_code == http.HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {
        "status": "error",
        "services": {"couchdb_reachable": False, "rabbitmq": True},
    }


def test_v3_health_failure(client: TestClient, middleware_api: Api) -> None:
    """Test /v3/health returns 503 if any global component check fails."""
    with (
        unittest.mock.patch.object(
            middleware_api.health_service,
            "global_health_checks",
            side_effect=AsyncMock(
                return_value={"couchdb_reachable": True, "rabbitmq": True, "celery_workers": False},
            ),
        ),
        patch(
            "middleware.api.api.v3.system.resolve_api_package_version",
            return_value=_VERSION,
        ),
    ):
        response = client.get("/v3/health", headers={"accept": "application/json"})

    assert response.status_code == http.HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {
        "status": "error",
        "services": {"couchdb_reachable": True, "rabbitmq": True, "celery_workers": False},
        "version": _VERSION,
    }


def test_v3_health_success(client: TestClient, middleware_api: Api) -> None:
    """Test /v3/health returns 200 if all global checks are healthy."""
    with (
        unittest.mock.patch.object(
            middleware_api.health_service,
            "global_health_checks",
            side_effect=AsyncMock(
                return_value={"couchdb_reachable": True, "rabbitmq": True, "celery_workers": True},
            ),
        ),
        patch(
            "middleware.api.api.v3.system.resolve_api_package_version",
            return_value=_VERSION,
        ),
    ):
        response = client.get("/v3/health", headers={"accept": "application/json"})

    assert response.status_code == http.HTTPStatus.OK
    assert response.json() == {
        "status": "ok",
        "services": {"couchdb_reachable": True, "rabbitmq": True, "celery_workers": True},
        "version": _VERSION,
    }


def test_v3_health_head_success(client: TestClient, middleware_api: Api) -> None:
    """HEAD /v3/health returns the same status as GET without a body."""
    with (
        unittest.mock.patch.object(
            middleware_api.health_service,
            "global_health_checks",
            side_effect=AsyncMock(
                return_value={"couchdb_reachable": True, "rabbitmq": True, "celery_workers": True},
            ),
        ),
        patch(
            "middleware.api.api.v3.system.resolve_api_package_version",
            return_value=_VERSION,
        ),
    ):
        response = client.head("/v3/health", headers={"accept": "application/json"})

    assert response.status_code == http.HTTPStatus.OK
    assert response.content == b""
