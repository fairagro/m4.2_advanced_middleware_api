"""Unit tests for the FastAPI middleware API endpoints."""

import http
from collections.abc import Callable
from typing import Any

import pytest
from cryptography import x509
from fastapi.testclient import TestClient

from middleware.api.api import Api
from unittest.mock import MagicMock
import unittest.mock 

from middleware.api.business_logic import BusinessLogicError
from middleware.shared.api_models.models import ArcResponse, ArcStatus, CreateOrUpdateArcsResponse


class SimpleBusinessLogicMock:
    """Straight forward mock of BusinessLogic for testing purposes."""

    def __init__(self, is_healthy: bool = True) -> None:
        """Initialize the mock with a health status.

        Args:
            is_healthy: Whether the mock should report as healthy. Defaults to True.
        """
        self._is_healthy = is_healthy

    def check_health(self) -> dict[str, bool]:
        """Mock check_health."""
        return {
            "backend_reachable": self._is_healthy,
            "redis_reachable": self._is_healthy,
            "rabbitmq_reachable": self._is_healthy,
        }

    async def create_or_update_arcs(self, rdi: str, _arcs: list[Any], client_id: str) -> CreateOrUpdateArcsResponse:
        """Mock create_or_update_arcs that captures the RDI."""
        return CreateOrUpdateArcsResponse(
            client_id=client_id,
            rdi=rdi,
            message="ok",
            arcs=[
                ArcResponse(
                    id="test-arc-id",
                    status=ArcStatus.CREATED,
                    timestamp="2025-01-01T00:00:00Z",
                )
            ],
        )


def test_whoami_success(client: TestClient, middleware_api: Api, cert: str) -> None:
    """Test the /v1/whoami endpoint with a valid certificate and accept header."""
    # pylint: disable=protected-access
    middleware_api.app.dependency_overrides[middleware_api._get_business_logic] = SimpleBusinessLogicMock

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert, "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == http.HTTPStatus.OK
    body = r.json()
    assert body["client_id"] == "TestClient"

    middleware_api.app.dependency_overrides.clear()


def test_whoami_invalid_accept(client: TestClient, cert: str) -> None:
    """Test the /v1/whoami endpoint with an invalid accept header."""
    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert, "ssl-client-verify": "SUCCESS", "accept": "application/xml"},
    )
    assert r.status_code == http.HTTPStatus.NOT_ACCEPTABLE


def test_whoami_no_cert(client: TestClient) -> None:
    """Test the /v1/whoami endpoint without a client certificate."""
    r = client.get(
        "/v1/whoami",
        headers={"accept": "application/json"},
    )
    assert r.status_code == http.HTTPStatus.UNAUTHORIZED


def test_whoami_invalid_cert(client: TestClient, middleware_api: Api) -> None:
    """Test the /v1/whoami endpoint with an invalid client certificate."""
    # pylint: disable=protected-access
    middleware_api.app.dependency_overrides[middleware_api._get_business_logic] = SimpleBusinessLogicMock

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": "dummy cert", "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == http.HTTPStatus.BAD_REQUEST

    middleware_api.app.dependency_overrides.clear()


@pytest.mark.parametrize("verify_status", ["FAILED", "NONE"])
def test_whoami_cert_verify_not_success(client: TestClient, cert: str, verify_status: str) -> None:
    """Test the /v1/whoami endpoint with failed or no certificate verification."""
    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert, "ssl-client-verify": verify_status, "accept": "application/json"},
    )
    assert r.status_code == http.HTTPStatus.UNAUTHORIZED


def test_health_check_success(client: TestClient, middleware_api: Api) -> None:
    """Test /v1/health success."""
    # pylint: disable=protected-access
    mock_logic = SimpleBusinessLogicMock(is_healthy=True)
    middleware_api.app.dependency_overrides[middleware_api._get_business_logic] = lambda: mock_logic

    r = client.get("/v1/health", headers={"accept": "application/json"})
    assert r.status_code == http.HTTPStatus.OK
    assert r.json() == {
        "status": "ok",
        "backend_reachable": True,
        "redis_reachable": True,
        "rabbitmq_reachable": True,
    }

    middleware_api.app.dependency_overrides.clear()


def test_health_check_failure(client: TestClient, middleware_api: Api) -> None:
    """Test /v1/health failure."""
    # pylint: disable=protected-access
    mock_logic = SimpleBusinessLogicMock(is_healthy=False)
    middleware_api.app.dependency_overrides[middleware_api._get_business_logic] = lambda: mock_logic

    r = client.get("/v1/health", headers={"accept": "application/json"})
    assert r.status_code == http.HTTPStatus.SERVICE_UNAVAILABLE
    assert r.json() == {
        "status": "error",
        "backend_reachable": False,
        "redis_reachable": False,
        "rabbitmq_reachable": False,
    }

    middleware_api.app.dependency_overrides.clear()


def test_health_check_exception(client: TestClient, middleware_api: Api) -> None:
    """Test /v1/health when logic raises exception."""

    # pylint: disable=protected-access
    class ExceptionMock(SimpleBusinessLogicMock):
        def check_health(self) -> dict[str, bool]:
            raise BusinessLogicError("Oops")

    mock_logic = ExceptionMock()
    middleware_api.app.dependency_overrides[middleware_api._get_business_logic] = lambda: mock_logic

    r = client.get("/v1/health", headers={"accept": "application/json"})
    assert r.status_code == http.HTTPStatus.SERVICE_UNAVAILABLE
    assert r.json() == {
        "status": "error",
        "backend_reachable": False,
        "redis_reachable": False,
        "rabbitmq_reachable": False,
    }

    middleware_api.app.dependency_overrides.clear()


# -------------------------------------------------------------------
# CREATE / UPDATE ARCS
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected_http_status",
    [
        (http.HTTPStatus.ACCEPTED),
    ],
)
def test_create_or_update_arcs_success(
    client: TestClient, middleware_api: Api, cert: str, expected_http_status: int
) -> None:
    """Test creating a new ARC via the /v1/arcs endpoint."""

    # Mock the Celery task
    mock_task = MagicMock()
    mock_task.id = "task-123"
    
    # Check where process_arc is imported in api.py. It is imported as: from .worker import process_arc
    # We need to patch the one in api.py
    with pytest.MonkeyPatch.context() as mp:
        mock_process_arc = MagicMock()
        mock_process_arc.delay.return_value = mock_task
        mp.setattr("middleware.api.api.process_arc", mock_process_arc)

        r = client.post(
            "/v1/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
        )
        assert r.status_code == http.HTTPStatus.ACCEPTED


def test_create_or_update_arcs_invalid_cert_format(client: TestClient) -> None:
    """Test error handling for invalid certificate format."""
    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": "NOT%20A%20VALID%20CERT",  # Properly URL encoded but content invalid
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == http.HTTPStatus.BAD_REQUEST
    assert "Certificate parsing error" in r.json()["detail"]


def test_create_or_update_arcs_no_cert_allowed(client: TestClient, middleware_api: Api) -> None:
    """Test successful submission without cert when not required."""
    # pylint: disable=protected-access
    # Disable client cert requirement
    middleware_api._config.require_client_cert = False
    
    # Needs to be known RDI
    middleware_api._config.known_rdis = ["rdi-1"]
    
    # We must mock process_arc.delay since we expect success
    mock_task = MagicMock()
    mock_task.id = "task-no-cert"
    
    with unittest.mock.patch("middleware.api.api.process_arc.delay", return_value=mock_task):
        r = client.post(
            "/v1/arcs",
            headers={
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
        )
        assert r.status_code == http.HTTPStatus.ACCEPTED
        body = r.json()
        assert body["task_id"] == "task-no-cert"

    # Reset config
    middleware_api._config.require_client_cert = True


def test_get_task_status(client: TestClient, middleware_api: Api) -> None:
    """Test getting task status."""
    
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.ready.return_value = True
    mock_result.failed.return_value = False
    mock_result.result = {"client_id": "test", "message": "ok", "rdi": "rdi-1", "arcs": []}

    with pytest.MonkeyPatch.context() as mp:
        mock_async_result = MagicMock(return_value=mock_result)
        # Verify import path in api.py: from .celery_app import celery_app
        mp.setattr("middleware.api.api.celery_app.AsyncResult", mock_async_result)

        r = client.get(
            "/v1/tasks/task-123",
            headers={"accept": "application/json"},
        )
        assert r.status_code == http.HTTPStatus.OK
        body = r.json()
        assert body["task_id"] == "task-123"
        assert body["status"] == "SUCCESS"
        assert body["result"]["message"] == "ok"
        assert body["result"]["client_id"] == "test"


# Removed test_create_or_update_arcs_invalid_json_semantic as validation runs async now


def test_create_or_update_arcs_invalid_body(client: TestClient, cert: str) -> None:
    """Test error handling in the /v1/arcs endpoint."""
    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": cert,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == http.HTTPStatus.UNPROCESSABLE_ENTITY  # unprocessable entity by FastAPI


def test_create_or_update_arcs_invalid_accept(client: TestClient, cert: str) -> None:
    """Test the /v1/arcs endpoint with an invalid accept header."""
    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": cert,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/xml",
        },
        json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == http.HTTPStatus.NOT_ACCEPTABLE


def test_create_or_update_arcs_no_cert(client: TestClient) -> None:
    """Test the /v1/arcs endpoint without a client certificate."""
    r = client.post(
        "/v1/arcs",
        headers={
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == http.HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    "client_verify, expected_status",
    [
        ("FAILED", http.HTTPStatus.UNAUTHORIZED),
        ("NONE", http.HTTPStatus.UNAUTHORIZED),
    ],
)
def test_create_or_update_arcs_cert_verification_state(
    cert: str, client: TestClient, client_verify: str, expected_status: int
) -> None:
    """Test the /v1/arcs endpoint with an invalid client certificate."""
    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": cert,
            "ssl-client-verify": client_verify,
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == expected_status


# -------------------------------------------------------------------
# RDI AUTHORIZATION IN CREATE_OR_UPDATE_ARCS
# -------------------------------------------------------------------


def test_create_or_update_arcs_rdi_not_known(client: TestClient, cert: str) -> None:
    """Test that requesting an unknown RDI returns 400."""
    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": cert,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-unknown", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == http.HTTPStatus.BAD_REQUEST


def test_create_or_update_arcs_rdi_not_allowed(
    client: TestClient,
    oid: x509.ObjectIdentifier,
    create_test_cert: Callable[[x509.ObjectIdentifier, list[str]], str],
) -> None:
    """Test that requesting an RDI not in client certificate returns 403."""
    cert = create_test_cert(oid, ["rdi-2"])

    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": cert,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == http.HTTPStatus.FORBIDDEN


# -------------------------------------------------------------------
# ACCESSIBLE RDIS COMPUTATION
# -------------------------------------------------------------------


def test_whoami_accessible_rdis_intersection(client: TestClient, middleware_api: Api) -> None:
    """Test that accessible_rdis is the intersection of allowed_rdis and known_rdis."""
    # Create certificate with RDIs that partially overlap with known_rdis
    # known_rdis fixture has ["rdi-1", "rdi-2"]
    # Let's create a cert with ["rdi-1", "rdi-3"] - only rdi-1 should be accessible
    # pylint: disable=protected-access
    middleware_api.app.dependency_overrides[middleware_api._validate_client_id] = lambda: "TestClient"
    middleware_api.app.dependency_overrides[middleware_api._get_authorized_rdis] = lambda: ["rdi-1", "rdi-3"]
    middleware_api.app.dependency_overrides[middleware_api._get_known_rdis] = lambda: ["rdi-1", "rdi-2"]

    r = client.get(
        "/v1/whoami",
        headers={
            "ssl-client-cert": "dummy-cert",
            "ssl-client-verify": "SUCCESS",
            "accept": "application/json",
        },
    )
    assert r.status_code == http.HTTPStatus.OK
    # Only rdi-1 should be in the intersection
    assert set(r.json()["accessible_rdis"]) == {"rdi-1"}

    # Cleanup
    middleware_api.app.dependency_overrides.clear()


def test_whoami_accessible_rdis_no_overlap(client: TestClient, middleware_api: Api) -> None:
    """Test that accessible_rdis is empty when there's no overlap between allowed and known RDIs."""
    # Create certificate with RDIs that don't overlap with known_rdis
    # known_rdis has ["rdi-1", "rdi-2"], create cert with ["rdi-3", "rdi-4"]
    # pylint: disable=protected-access
    middleware_api.app.dependency_overrides[middleware_api._validate_client_id] = lambda: "TestClient"
    middleware_api.app.dependency_overrides[middleware_api._get_authorized_rdis] = lambda: ["rdi-3", "rdi-4"]
    middleware_api.app.dependency_overrides[middleware_api._get_known_rdis] = lambda: ["rdi-1", "rdi-2"]

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": "dummy-cert", "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == http.HTTPStatus.OK
    # No overlap, should be empty
    assert r.json()["accessible_rdis"] == []

    # Cleanup
    middleware_api.app.dependency_overrides.clear()


def test_whoami_accessible_rdis_complete_overlap(client: TestClient, middleware_api: Api) -> None:
    """Test that accessible_rdis contains all RDIs when there's complete overlap."""
    # Create certificate with same RDIs as known_rdis
    # pylint: disable=protected-access
    middleware_api.app.dependency_overrides[middleware_api._validate_client_id] = lambda: "TestClient"
    middleware_api.app.dependency_overrides[middleware_api._get_authorized_rdis] = lambda: ["rdi-1", "rdi-2"]
    middleware_api.app.dependency_overrides[middleware_api._get_known_rdis] = lambda: ["rdi-1", "rdi-2"]

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": "dummy-cert", "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == http.HTTPStatus.OK
    # Complete overlap
    assert set(r.json()["accessible_rdis"]) == {"rdi-1", "rdi-2"}

    # Cleanup
    middleware_api.app.dependency_overrides.clear()


def test_whoami_accessible_rdis_superset_in_cert(client: TestClient, middleware_api: Api) -> None:
    """Test accessible_rdis when certificate contains more RDIs than known_rdis."""
    # Certificate has ["rdi-1", "rdi-2", "rdi-3", "rdi-4"]
    # known_rdis has ["rdi-1", "rdi-2"]
    # Result should be ["rdi-1", "rdi-2"]
    # pylint: disable=protected-access
    middleware_api.app.dependency_overrides[middleware_api._validate_client_id] = lambda: "TestClient"
    middleware_api.app.dependency_overrides[middleware_api._get_authorized_rdis] = lambda: [
        "rdi-1",
        "rdi-2",
        "rdi-3",
        "rdi-4",
    ]
    middleware_api.app.dependency_overrides[middleware_api._get_known_rdis] = lambda: ["rdi-1", "rdi-2"]

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": "dummy-cert", "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == http.HTTPStatus.OK
    # Only the intersection should be returned
    assert set(r.json()["accessible_rdis"]) == {"rdi-1", "rdi-2"}

    # Cleanup
    middleware_api.app.dependency_overrides.clear()
