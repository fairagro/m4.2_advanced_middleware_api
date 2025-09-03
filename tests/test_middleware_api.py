# nosec

import pytest

# Importiere die echte FastAPI-App und die echte get_service-Factory
from app.middleware_api import MiddlewareAPI

# Nur die Exception-Typen importieren, damit wir das HTTP-Mapping testen können
from app.middleware_logic import (
    InvalidJsonSemanticError,
    InvalidJsonSyntaxError,
)


class DummyArc:
    def __init__(self, data: dict):
        self.__dict__.update(data)

class DummyResponse:
    """Kleines Hilfsobjekt, das wie ein Pydantic-Model wirkt."""
    def __init__(self, payload: dict):
        self._payload = payload
        self.client_id = payload.get("client_id")
        self.message = payload.get("message")
        # arcs als Liste von Objekten, nicht Dictionaries
        self.arcs = [DummyArc(arc) for arc in payload.get("arcs", [])]

    def model_dump(self) -> dict:
        return self._payload


def override_service(api: MiddlewareAPI, obj):
    """Helfer zum Überschreiben der get_service-Dependency."""
    api.app.dependency_overrides[api.get_service] = lambda: obj

# -------------------------------------------------------------------
# WHOAMI
# -------------------------------------------------------------------

def test_whoami_success(client, middleware_api, cert):
    class Svc:
        async def whoami(self, client_id):
            return DummyResponse({"client_id": client_id, "message": "ok"})

    override_service(middleware_api, Svc())

    r = client.get(
        "/v1/whoami",
        headers={"X-Client-Cert": cert, "accept": "application/json"},
    )
    assert r.status_code == 200 # nosec
    body = r.json()
    assert body["client_id"] == "TestClient" # nosec
    assert body["message"] == "ok" # nosec

def test_whoami_invalid_accept(client, cert):
    r = client.get(
        "/v1/whoami",
        headers={"X-Client-Cert": cert, "accept": "application/xml"},
    )
    assert r.status_code == 406 # nosec

def test_whoami_no_cert(client):
    r = client.get(
        "/v1/whoami",
        headers={"accept": "application/json"},
    )
    assert r.status_code == 401 # nosec

def test_whoami_invalid_cert(client):
    r = client.get(
        "/v1/whoami",
        headers={"X-Client-Cert": "dumy cert", "accept": "application/json"},
    )
    assert r.status_code == 400 # nosec


# -------------------------------------------------------------------
# CREATE / UPDATE ARCS
# -------------------------------------------------------------------

def test_create_or_update_arcs_created(client, middleware_api, cert):
    class SvcOK:
        async def create_or_update_arcs(self, data, client_id):
            return DummyResponse(
                {
                    "client_id": client_id,
                    "message": "ok",
                    "arcs": [
                        {"id": "abc123", "status": "created", "timestamp": "2025-01-01T00:00:00Z"}
                    ],
                }
            )

    override_service(middleware_api, SvcOK())

    r = client.post(
        "/v1/arcs",
        headers={
            "X-Client-Cert": cert,
            "content-type": "application/ro-crate+json",
            "accept": "application/json",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == 201 # nosec
    body = r.json()
    assert body["client_id"] == "TestClient" # nosec
    assert isinstance(body["arcs"], list) # nosec
    assert body["arcs"][0]["status"] == "created" # nosec
    # Location-Header gesetzt?
    assert r.headers.get("Location", "") != "" # nosec


def test_create_or_update_arcs_updated(client, middleware_api, cert):
    class SvcOK:
        async def create_or_update_arcs(self, data, client_id):
            return DummyResponse(
                {
                    "client_id": client_id,
                    "message": "ok",
                    "arcs": [
                        {"id": "abc123", "status": "updated", "timestamp": "2025-01-01T00:00:00Z"}
                    ],
                }
            )

    override_service(middleware_api, SvcOK())

    r = client.post(
        "/v1/arcs",
        headers={
            "X-Client-Cert": cert,
            "content-type": "application/ro-crate+json",
            "accept": "application/json",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == 200  # nosec
    body = r.json()
    assert body["arcs"][0]["status"] == "updated" # nosec


@pytest.mark.parametrize(
    "exc, expected",
    [
        (InvalidJsonSyntaxError("bad json"), 400),
        (InvalidJsonSemanticError("bad crate"), 422),
    ],
)
def test_create_or_update_arcs_invalid_json(client, middleware_api, cert, exc, expected):
    class SvcFail:
        async def create_or_update_arcs(self, data, client_id):
            raise exc

    override_service(middleware_api, SvcFail())

    r = client.post(
        "/v1/arcs",
        headers={
            "X-Client-Cert": cert,
            "content-type": "application/ro-crate+json",
            "accept": "application/json",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == expected # nosec

def test_create_or_update_arcs_invalid_accept(client, cert):
    r = client.post(
        "/v1/arcs",
        headers={
            "X-Client-Cert": cert,
            "content-type": "application/ro-crate+json",
            "accept": "application/xml",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == 406 # nosec

def test_create_or_update_arcs_no_cert(client):
    r = client.post(
        "/v1/arcs",
        headers={
            "content-type": "application/ro-crate+json",
            "accept": "application/json",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == 401 # nosec

def test_create_or_update_arcs_invalid_cert(client):

    r = client.post(
        "/v1/arcs",
        headers={
            "X-Client-Cert": "dummy cert",
            "content-type": "application/ro-crate+json",
            "accept": "application/xml",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == 400 # nosec