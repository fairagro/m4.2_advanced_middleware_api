"""Unit tests for the FastAPI middleware API endpoints."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from middleware_api.api import Api
from middleware_api.business_logic import InvalidJsonSemanticError
from tests.conftest import create_test_cert


class DummyArc:  # pylint: disable=too-few-public-methods
    """Helper object that mimics an ArcResponse model."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize the DummyArc with data from a dictionary."""
        self.__dict__.update(data)


class DummyResponse:  # pylint: disable=too-few-public-methods
    """Helper object that mimics a BusinessLogicResponse model."""

    def __init__(self, payload: dict[str, Any]) -> None:
        """Initialize the DummyResponse with data from a dictionary."""
        self._payload = payload
        self.client_id = payload.get("client_id")
        self.message = payload.get("message")
        # arcs als Liste von Objekten, nicht Dictionaries
        self.arcs = [DummyArc(arc) for arc in payload.get("arcs", [])]

    def model_dump(self) -> dict:
        """Return the payload as a dictionary."""
        return self._payload


def override_service(api: Api, obj: Any) -> None:
    """Helfer zum Überschreiben der get_service-Dependency."""
    api.app.dependency_overrides[api.get_business_logic] = lambda: obj


# -------------------------------------------------------------------
# WHOAMI
# -------------------------------------------------------------------


def test_whoami_success(client: TestClient, middleware_api: Api, cert: str) -> None:
    """Test the /v1/whoami endpoint with a valid certificate and accept header."""

    class Svc:  # pylint: disable=too-few-public-methods
        """Service that always returns a successful response."""

        async def whoami(self, client_id: str, accessible_rdis: list[str]) -> DummyResponse:
            """Mock whoami method."""
            return DummyResponse({"client_id": client_id, "accessible_rdis": accessible_rdis, "message": "ok"})

    override_service(middleware_api, Svc())

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert, "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == 200  # nosec
    body = r.json()
    assert body["client_id"] == "TestClient"  # nosec
    assert body["message"] == "ok"  # nosec


def test_whoami_invalid_accept(client: TestClient, cert: str) -> None:
    """Test the /v1/whoami endpoint with an invalid accept header."""
    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert, "ssl-client-verify": "SUCCESS", "accept": "application/xml"},
    )
    assert r.status_code == 406  # nosec


def test_whoami_no_cert(client: TestClient) -> None:
    """Test the /v1/whoami endpoint without a client certificate."""
    r = client.get(
        "/v1/whoami",
        headers={"accept": "application/json"},
    )
    assert r.status_code == 401  # nosec


def test_whoami_invalid_cert(client: TestClient) -> None:
    """Test the /v1/whoami endpoint with an invalid client certificate."""
    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": "dumy cert", "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == 400  # nosec


# -------------------------------------------------------------------
# CREATE / UPDATE ARCS
# -------------------------------------------------------------------


def test_create_or_update_arcs_created(client: TestClient, middleware_api: Api, cert: str) -> None:
    """Test creating a new ARC via the /v1/arcs endpoint."""

    class SvcOK:  # pylint: disable=too-few-public-methods
        """Service that always returns a created ARC."""

        async def create_or_update_arcs(self, rdi: str, _data: list[Any], client_id: str) -> DummyResponse:
            """Mock create_or_update_arcs method."""
            return DummyResponse(
                {
                    "rdi": rdi,
                    "client_id": client_id,
                    "message": "ok",
                    "arcs": [
                        {
                            "id": "abc123",
                            "status": "created",
                            "timestamp": "2025-01-01T00:00:00Z",
                        }
                    ],
                }
            )

    override_service(middleware_api, SvcOK())

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
    assert r.status_code == 201  # nosec
    body = r.json()
    assert body["client_id"] == "TestClient"  # nosec
    assert isinstance(body["arcs"], list)  # nosec
    assert body["arcs"][0]["status"] == "created"  # nosec
    # Location-Header gesetzt?
    assert r.headers.get("Location", "") != ""  # nosec


def test_create_or_update_arcs_updated(client: TestClient, middleware_api: Api, cert: str) -> None:
    """Test updating an existing ARC via the /v1/arcs endpoint."""

    class SvcOK:  # pylint: disable=too-few-public-methods
        """Service that always returns an updated ARC."""

        async def create_or_update_arcs(self, rdi: str, arcs: list[Any], client_id: str) -> DummyResponse:
            """Mock create_or_update_arcs method."""
            return DummyResponse(
                {
                    "client_id": client_id,
                    "message": "ok",
                    "arcs": [
                        {
                            "id": "abc123",
                            "status": "updated",
                            "timestamp": "2025-01-01T00:00:00Z",
                        }
                    ],
                }
            )

    override_service(middleware_api, SvcOK())

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
    assert r.status_code == 200  # nosec
    body = r.json()
    assert body["arcs"][0]["status"] == "updated"  # nosec


@pytest.mark.parametrize(
    "exc, expected",
    [
        (InvalidJsonSemanticError("bad crate"), 422),
    ],
)
def test_create_or_update_arcs_invalid_json(
    client: TestClient, middleware_api: Api, cert: str, exc: Exception, expected: int
) -> None:
    """Test error handling in the /v1/arcs endpoint."""

    class SvcFail:  # pylint: disable=too-few-public-methods
        """Service that always raises an exception."""

        async def create_or_update_arcs(self, _rdi: str, _arcs: list[Any], _client_id: str) -> None:
            """Mock create_or_update_arcs method that raises an exception."""
            raise exc

    override_service(middleware_api, SvcFail())

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
    assert r.status_code == expected  # nosec


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
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == 406  # nosec


def test_create_or_update_arcs_no_cert(client: TestClient) -> None:
    """Test the /v1/arcs endpoint without a client certificate."""
    r = client.post(
        "/v1/arcs",
        headers={
            "content-type": "application/json",
            "accept": "application/json",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == 401  # nosec


def test_create_or_update_arcs_invalid_cert(client: TestClient) -> None:
    """Test the /v1/arcs endpoint with an invalid client certificate."""
    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": "dummy cert",
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/xml",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == 400  # nosec


# -------------------------------------------------------------------
# RDI AUTHORIZATION IN CREATE_OR_UPDATE_ARCS
# -------------------------------------------------------------------


def test_create_or_update_arcs_rdi_not_known(client: TestClient, middleware_api: Api) -> None:
    """Test that requesting an unknown RDI returns 400."""
    # Create certificate with RDI that is not in known_rdis
    # known_rdis has ["rdi-1", "rdi-2"]
    cert_with_unknown_rdi = create_test_cert(middleware_api._config.client_auth_oid, ["rdi-unknown"])

    class Svc:  # pylint: disable=too-few-public-methods
        """Mock service - should not be called."""

        async def create_or_update_arcs(self, rdi: str, arcs: list[Any], client_id: str) -> DummyResponse:
            """Raise assertion error - service should not be invoked."""
            raise AssertionError("Service should not be called for unknown RDI")

    override_service(middleware_api, Svc())

    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": cert_with_unknown_rdi,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-unknown", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == 400  # nosec
    assert "not recognized" in r.json()["detail"]  # nosec


def test_create_or_update_arcs_rdi_not_allowed(client: TestClient, middleware_api: Api) -> None:
    """Test that requesting an RDI not in client certificate returns 403."""
    # Create certificate with RDI "rdi-1" only
    # Client tries to access "rdi-2" which is known but not in their cert
    cert_with_rdi1_only = create_test_cert(middleware_api._config.client_auth_oid, ["rdi-1"])

    class Svc:  # pylint: disable=too-few-public-methods
        """Mock service - should not be called."""

        async def create_or_update_arcs(self, rdi: str, arcs: list[Any], client_id: str) -> DummyResponse:
            """Raise assertion error - service should not be invoked."""
            raise AssertionError("Service should not be called for unauthorized RDI")

    override_service(middleware_api, Svc())

    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": cert_with_rdi1_only,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-2", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == 403  # nosec
    assert "not authorized" in r.json()["detail"]  # nosec


def test_create_or_update_arcs_rdi_authorized(client: TestClient, middleware_api: Api) -> None:
    """Test that a properly authorized RDI request succeeds."""
    # Create certificate with both RDIs
    cert_with_both_rdis = create_test_cert(middleware_api._config.client_auth_oid, ["rdi-1", "rdi-2"])

    class Svc:  # pylint: disable=too-few-public-methods
        """Mock service that verifies the RDI was passed correctly."""

        async def create_or_update_arcs(self, rdi: str, arcs: list[Any], client_id: str) -> DummyResponse:
            """Mock create_or_update_arcs that captures the RDI."""
            return DummyResponse(
                {
                    "client_id": client_id,
                    "rdi": rdi,
                    "message": "ok",
                    "arcs": [
                        {
                            "id": "test-arc-id",
                            "status": "created",
                            "timestamp": "2025-01-01T00:00:00Z",
                        }
                    ],
                }
            )

    service = Svc()
    override_service(middleware_api, service)

    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": cert_with_both_rdis,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == 201  # nosec - created
    assert r.json()["rdi"] == "rdi-1"  # nosec


def test_create_or_update_arcs_rdi_edge_case_cert_has_extra(client: TestClient, middleware_api: Api) -> None:
    """Test that client can access RDI if it's in both cert and known_rdis, even if cert has extras."""
    # Certificate has ["rdi-1", "rdi-2", "rdi-extra"]
    # known_rdis has ["rdi-1", "rdi-2"]
    # Client requests "rdi-1" - should succeed
    cert_with_extra = create_test_cert(middleware_api._config.client_auth_oid, ["rdi-1", "rdi-2", "rdi-extra"])

    class Svc:  # pylint: disable=too-few-public-methods
        """Mock service that verifies the RDI was passed correctly."""

        async def create_or_update_arcs(self, rdi: str, arcs: list[Any], client_id: str) -> DummyResponse:
            """Mock create_or_update_arcs that captures the RDI."""
            return DummyResponse(
                {
                    "client_id": client_id,
                    "rdi": rdi,
                    "message": "ok",
                    "arcs": [
                        {
                            "id": "test-arc-id",
                            "status": "updated",
                            "timestamp": "2025-01-01T00:00:00Z",
                        }
                    ],
                }
            )

    service = Svc()
    override_service(middleware_api, service)

    r = client.post(
        "/v1/arcs",
        headers={
            "ssl-client-cert": cert_with_extra,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},
    )
    assert r.status_code == 200  # nosec - updated
    assert r.json()["rdi"] == "rdi-1"  # nosec


# -------------------------------------------------------------------
# ACCESSIBLE RDIS COMPUTATION
# -------------------------------------------------------------------


def test_whoami_accessible_rdis_intersection(client: TestClient, middleware_api: Api, known_rdis: list[str]) -> None:
    """Test that accessible_rdis is the intersection of allowed_rdis and known_rdis."""
    # Create certificate with RDIs that partially overlap with known_rdis
    # known_rdis fixture has ["rdi-1", "rdi-2"]
    # Let's create a cert with ["rdi-1", "rdi-3"] - only rdi-1 should be accessible
    cert_with_partial_overlap = create_test_cert(middleware_api._config.client_auth_oid, ["rdi-1", "rdi-3"])

    class Svc:  # pylint: disable=too-few-public-methods
        """Service that captures the accessible_rdis passed to it."""

        async def whoami(self, client_id: str, accessible_rdis: list[str]) -> DummyResponse:
            """Mock whoami method that captures accessible_rdis."""
            return DummyResponse({"client_id": client_id, "accessible_rdis": accessible_rdis, "message": "ok"})

    service = Svc()
    override_service(middleware_api, service)

    r = client.get(
        "/v1/whoami",
        headers={
            "ssl-client-cert": cert_with_partial_overlap,
            "ssl-client-verify": "SUCCESS",
            "accept": "application/json",
        },
    )
    assert r.status_code == 200  # nosec
    # Only rdi-1 should be in the intersection
    assert set(r.json()["accessible_rdis"]) == {"rdi-1"}  # nosec


def test_whoami_accessible_rdis_no_overlap(client: TestClient, middleware_api: Api) -> None:
    """Test that accessible_rdis is empty when there's no overlap between allowed and known RDIs."""
    # Create certificate with RDIs that don't overlap with known_rdis
    # known_rdis has ["rdi-1", "rdi-2"], create cert with ["rdi-3", "rdi-4"]
    cert_no_overlap = create_test_cert(middleware_api._config.client_auth_oid, ["rdi-3", "rdi-4"])

    class Svc:  # pylint: disable=too-few-public-methods
        """Service that captures the accessible_rdis passed to it."""

        async def whoami(self, client_id: str, accessible_rdis: list[str]) -> DummyResponse:
            """Mock whoami method that captures accessible_rdis."""
            return DummyResponse({"client_id": client_id, "accessible_rdis": accessible_rdis, "message": "ok"})

    service = Svc()
    override_service(middleware_api, service)

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert_no_overlap, "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == 200  # nosec
    # No overlap, should be empty
    assert r.json()["accessible_rdis"] == []  # nosec


def test_whoami_accessible_rdis_complete_overlap(client: TestClient, middleware_api: Api) -> None:
    """Test that accessible_rdis contains all RDIs when there's complete overlap."""
    # Create certificate with same RDIs as known_rdis
    cert_complete = create_test_cert(middleware_api._config.client_auth_oid, ["rdi-1", "rdi-2"])

    class Svc:  # pylint: disable=too-few-public-methods
        """Service that captures the accessible_rdis passed to it."""

        async def whoami(self, client_id: str, accessible_rdis: list[str]) -> DummyResponse:
            """Mock whoami method that captures accessible_rdis."""
            return DummyResponse({"client_id": client_id, "accessible_rdis": accessible_rdis, "message": "ok"})

    service = Svc()
    override_service(middleware_api, service)

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert_complete, "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == 200  # nosec
    # Complete overlap
    assert set(r.json()["accessible_rdis"]) == {"rdi-1", "rdi-2"}  # nosec


def test_whoami_accessible_rdis_superset_in_cert(client: TestClient, middleware_api: Api) -> None:
    """Test accessible_rdis when certificate contains more RDIs than known_rdis."""
    # Certificate has ["rdi-1", "rdi-2", "rdi-3", "rdi-4"]
    # known_rdis has ["rdi-1", "rdi-2"]
    # Result should be ["rdi-1", "rdi-2"]
    cert_superset = create_test_cert(middleware_api._config.client_auth_oid, ["rdi-1", "rdi-2", "rdi-3", "rdi-4"])

    class Svc:  # pylint: disable=too-few-public-methods
        """Service that captures the accessible_rdis passed to it."""

        captured_accessible_rdis: list[str] = []

        async def whoami(self, client_id: str, accessible_rdis: list[str]) -> DummyResponse:
            """Mock whoami method that captures accessible_rdis."""
            Svc.captured_accessible_rdis = accessible_rdis
            return DummyResponse({"client_id": client_id, "accessible_rdis": accessible_rdis, "message": "ok"})

    service = Svc()
    override_service(middleware_api, service)

    r = client.get(
        "/v1/whoami",
        headers={"ssl-client-cert": cert_superset, "ssl-client-verify": "SUCCESS", "accept": "application/json"},
    )
    assert r.status_code == 200  # nosec
    # Only the intersection should be returned
    assert set(service.captured_accessible_rdis) == {"rdi-1", "rdi-2"}  # nosec
