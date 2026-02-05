"""Unit tests for the FastAPI middleware API endpoints."""

import http
import unittest.mock
from collections.abc import Callable
from unittest.mock import MagicMock

import pytest
import redis
import redis.exceptions
from cryptography import x509
from fastapi.testclient import TestClient

from middleware.api.api import Api
from middleware.shared.api_models.models import ArcTaskTicket


def test_whoami_success(client: TestClient, middleware_api: Api, cert: str) -> None:
    """Test the /v1/whoami endpoint with a valid certificate and accept header."""
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


def test_health_check_success(client: TestClient) -> None:
    """Test /v1/health success."""
    # Mock Redis
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    # Mock Celery connection
    mock_conn = MagicMock()

    with (
        unittest.mock.patch("middleware.api.api.redis.from_url", return_value=mock_redis),
        unittest.mock.patch("middleware.api.api.celery_app.connection_or_acquire") as mock_acquire,
    ):
        mock_acquire.return_value.__enter__.return_value = mock_conn

        r = client.get("/v1/health", headers={"accept": "application/json"})
        assert r.status_code == http.HTTPStatus.OK
        assert r.json() == {
            "status": "ok",
            "redis_reachable": True,
            "rabbitmq_reachable": True,
        }


def test_health_check_failure(client: TestClient) -> None:
    """Test /v1/health failure."""
    # Mock Redis failure
    with (
        unittest.mock.patch("middleware.api.api.redis.from_url", side_effect=redis.exceptions.RedisError("Redis down")),
        unittest.mock.patch(
            "middleware.api.api.celery_app.connection_or_acquire", side_effect=Exception("RabbitMQ down")
        ),
    ):
        r = client.get("/v1/health", headers={"accept": "application/json"})
        assert r.status_code == http.HTTPStatus.SERVICE_UNAVAILABLE
        assert r.json() == {
            "status": "error",
            "redis_reachable": False,
            "rabbitmq_reachable": False,
        }


# -------------------------------------------------------------------
# CREATE / UPDATE ARCS
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected_http_status",
    [
        (http.HTTPStatus.ACCEPTED),
    ],
)
def test_create_or_update_arcs_success(client: TestClient, cert: str, expected_http_status: int, middleware_api: Api) -> None:
    """Test creating a new ARC via the /v1/arcs endpoint."""
    # Mock the BusinessLogic response
    mock_ticket = ArcTaskTicket(
        rdi="rdi-1",
        task_id="task-123"
    )

    with (
        unittest.mock.patch.object(middleware_api.business_logic, "create_or_update_arc", new_callable=unittest.mock.AsyncMock) as mock_create
    ):
        mock_create.return_value = mock_ticket

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
        assert r.status_code == expected_http_status
        assert r.json()["task_id"] == "task-123"


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

    mock_task_ticket = ArcTaskTicket(rdi="rdi-1", task_id="task-no-cert")

    with (
        unittest.mock.patch.object(middleware_api.business_logic, "create_or_update_arc", new_callable=unittest.mock.AsyncMock) as mock_create
    ):
        mock_create.return_value = mock_task_ticket
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


def test_get_task_status_v1_transformation(client: TestClient) -> None:
    """Test getting task status via /v1/tasks (v1 endpoint) with singular result from worker."""
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.ready.return_value = True
    mock_result.successful.return_value = True
    mock_result.failed.return_value = False
    # Mock return value from worker (singular)
    mock_result.result = {
        "client_id": "test",
        "message": "ok",
        "rdi": "rdi-1",
        "arc": {"id": "arc-1", "status": "created", "timestamp": "2024-01-01T00:00:00Z"},
    }

    with pytest.MonkeyPatch.context() as mp:
        mock_async_result = MagicMock(return_value=mock_result)
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
        # Transformation: single 'arc' becomes 'arcs' list with 1 item
        assert len(body["result"]["arcs"]) == 1
        assert body["result"]["arcs"][0]["id"] == "arc-1"


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
