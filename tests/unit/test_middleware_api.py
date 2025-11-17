"""Unit tests for the FastAPI middleware API endpoints."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from middleware_api.api import Api
from middleware_api.business_logic import InvalidJsonSemanticError


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
            "content-type": "application/ro-crate+json",
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
            "content-type": "application/ro-crate+json",
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
            "content-type": "application/ro-crate+json",
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
            "content-type": "application/ro-crate+json",
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
            "content-type": "application/ro-crate+json",
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
            "content-type": "application/ro-crate+json",
            "accept": "application/xml",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == 400  # nosec
