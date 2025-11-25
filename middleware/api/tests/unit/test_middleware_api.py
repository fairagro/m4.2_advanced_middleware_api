"""Unit tests for the FastAPI middleware API endpoints."""

from collections.abc import Callable
from typing import Any

import pytest
from cryptography import x509
from fastapi.testclient import TestClient

from middleware.api.api import Api
from middleware.api.business_logic import (
    ArcResponse,
    ArcStatus,
    CreateOrUpdateArcsResponse,
    InvalidJsonSemanticError,
    WhoamiResponse,
)

# from ..conftest import create_test_cert


class SimpleBusinessLogicMock:
    """Straight forward mock of BusinessLogic for testing purposes."""

    async def whoami(self, client_id: str, accessible_rdis: list[str]) -> WhoamiResponse:
        """Mock whoami method."""
        return WhoamiResponse(client_id=client_id, accessible_rdis=accessible_rdis, message="ok")

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
    middleware_api.app.dependency_overrides[middleware_api._get_business_logic] = SimpleBusinessLogicMock

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert, "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["client_id"] == "TestClient"
    assert body["message"] == "ok"

    middleware_api.app.dependency_overrides.clear()


def test_whoami_invalid_accept(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test the /v1/whoami endpoint with an invalid accept header."""
    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert, "ssl-client-verify": "SUCCESS", "accept": "application/xml"},
    )
    assert r.status_code == 406


def test_whoami_no_cert(client: TestClient, middleware_api: Api) -> None:
    """Test the /v1/whoami endpoint without a client certificate."""
    r = client.get(
        "/v1/whoami",
        headers={"accept": "application/json"},
    )
    assert r.status_code == 401


def test_whoami_invalid_cert(client: TestClient, middleware_api: Api) -> None:
    """Test the /v1/whoami endpoint with an invalid client certificate."""
    middleware_api.app.dependency_overrides[middleware_api._get_business_logic] = SimpleBusinessLogicMock

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": "dummy cert", "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == 400

    middleware_api.app.dependency_overrides.clear()


@pytest.mark.parametrize("verify_status", ["FAILED", "NONE"])
def test_whoami_cert_verify_not_success(client: TestClient, cert: str, verify_status: str, middleware_api: Api) -> None:
    """Test the /v1/whoami endpoint with failed or no certificate verification."""
    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert, "ssl-client-verify": verify_status, "accept": "application/json"},
    )
    assert r.status_code == 401


# -------------------------------------------------------------------
# CREATE / UPDATE ARCS
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "arc_status, expected_http_status",
    [
        (ArcStatus.CREATED, 201),
        (ArcStatus.UPDATED, 200),
    ],
)
def test_create_or_update_arcs_success(
    client: TestClient, middleware_api: Api, cert: str, arc_status: ArcStatus, expected_http_status: int
) -> None:
    """Test creating a new ARC via the /v1/arcs endpoint."""

    class BusinessLogicMock:  # pylint: disable=too-few-public-methods
        """Service that always returns a created ARC."""

        async def create_or_update_arcs(self, rdi: str, _arcs: list[Any], client_id: str) -> CreateOrUpdateArcsResponse:
            """Mock create_or_update_arcs method."""
            return CreateOrUpdateArcsResponse(
                rdi=rdi,
                client_id=client_id,
                message="ok",
                arcs=[
                    ArcResponse(
                        id="abc123",
                        status=arc_status,
                        timestamp="2025-01-01T00:00:00Z",
                    )
                ],
            )

    middleware_api.app.dependency_overrides[middleware_api._get_business_logic] = BusinessLogicMock

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
    body = r.json()
    assert body["client_id"] == "TestClient"
    assert isinstance(body["arcs"], list)
    assert body["arcs"][0]["status"] == arc_status.value
    if arc_status == ArcStatus.CREATED:
        assert r.headers.get("Location", "") != ""

    middleware_api.app.dependency_overrides.clear()


def test_create_or_update_arcs_invalid_json_semantic(
    client: TestClient,
    cert: str,
    middleware_api: Api,
) -> None:
    """Test error handling in the /v1/arcs endpoint."""

    class BusinessLogicMock:  # pylint: disable=too-few-public-methods
        """Service that always returns a created ARC."""

        async def create_or_update_arcs(self, rdi: str, _arcs: list[Any], client_id: str) -> CreateOrUpdateArcsResponse:
            """Mock create_or_update_arcs method."""
            raise InvalidJsonSemanticError("invalid JSON semantic")

    middleware_api.app.dependency_overrides[middleware_api._get_business_logic] = BusinessLogicMock

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
    assert r.status_code == 422  # InvalidJSONSemantic by BusinessLogic

    middleware_api.app.dependency_overrides.clear()


def test_create_or_update_arcs_invalid_body(client: TestClient, cert: str, middleware_api: Api) -> None:
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
    assert r.status_code == 422  # unprocessable entity by FastAPI


def test_create_or_update_arcs_invalid_accept(client: TestClient, cert: str, middleware_api: Api) -> None:
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
    assert r.status_code == 406


def test_create_or_update_arcs_no_cert(client: TestClient, middleware_api: Api) -> None:
    """Test the /v1/arcs endpoint without a client certificate."""
    r = client.post(
        "/v1/arcs",
        headers={
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == 401


@pytest.mark.parametrize(
    "client_verify, expected_status",
    [
        ("FAILED", 401),
        ("NONE", 401),
    ],
)
def test_create_or_update_arcs_cert_verification_state(
    cert: str, client: TestClient, client_verify: str, expected_status: int, middleware_api: Api
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
    assert r.status_code == 400


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
    assert r.status_code == 403


# -------------------------------------------------------------------
# ACCESSIBLE RDIS COMPUTATION
# -------------------------------------------------------------------


def test_whoami_accessible_rdis_intersection(client: TestClient, middleware_api: Api, known_rdis: list[str]) -> None:
    """Test that accessible_rdis is the intersection of allowed_rdis and known_rdis."""
    # Create certificate with RDIs that partially overlap with known_rdis
    # known_rdis fixture has ["rdi-1", "rdi-2"]
    # Let's create a cert with ["rdi-1", "rdi-3"] - only rdi-1 should be accessible
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
    assert r.status_code == 200
    # Only rdi-1 should be in the intersection
    assert set(r.json()["accessible_rdis"]) == {"rdi-1"}

    # Cleanup
    middleware_api.app.dependency_overrides.clear()


def test_whoami_accessible_rdis_no_overlap(client: TestClient, middleware_api: Api) -> None:
    """Test that accessible_rdis is empty when there's no overlap between allowed and known RDIs."""
    # Create certificate with RDIs that don't overlap with known_rdis
    # known_rdis has ["rdi-1", "rdi-2"], create cert with ["rdi-3", "rdi-4"]
    middleware_api.app.dependency_overrides[middleware_api._validate_client_id] = lambda: "TestClient"
    middleware_api.app.dependency_overrides[middleware_api._get_authorized_rdis] = lambda: ["rdi-3", "rdi-4"]
    middleware_api.app.dependency_overrides[middleware_api._get_known_rdis] = lambda: ["rdi-1", "rdi-2"]

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": "dummy-cert", "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == 200
    # No overlap, should be empty
    assert r.json()["accessible_rdis"] == []

    # Cleanup
    middleware_api.app.dependency_overrides.clear()


def test_whoami_accessible_rdis_complete_overlap(client: TestClient, middleware_api: Api) -> None:
    """Test that accessible_rdis contains all RDIs when there's complete overlap."""
    # Create certificate with same RDIs as known_rdis
    middleware_api.app.dependency_overrides[middleware_api._validate_client_id] = lambda: "TestClient"
    middleware_api.app.dependency_overrides[middleware_api._get_authorized_rdis] = lambda: ["rdi-1", "rdi-2"]
    middleware_api.app.dependency_overrides[middleware_api._get_known_rdis] = lambda: ["rdi-1", "rdi-2"]

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": "dummy-cert", "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == 200
    # Complete overlap
    assert set(r.json()["accessible_rdis"]) == {"rdi-1", "rdi-2"}

    # Cleanup
    middleware_api.app.dependency_overrides.clear()


def test_whoami_accessible_rdis_superset_in_cert(client: TestClient, middleware_api: Api) -> None:
    """Test accessible_rdis when certificate contains more RDIs than known_rdis."""
    # Certificate has ["rdi-1", "rdi-2", "rdi-3", "rdi-4"]
    # known_rdis has ["rdi-1", "rdi-2"]
    # Result should be ["rdi-1", "rdi-2"]
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
    assert r.status_code == 200
    # Only the intersection should be returned
    assert set(r.json()["accessible_rdis"]) == {"rdi-1", "rdi-2"}

    # Cleanup
    middleware_api.app.dependency_overrides.clear()
