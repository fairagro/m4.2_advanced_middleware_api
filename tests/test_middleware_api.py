# nosec

import pytest

# Importiere die echte FastAPI-App und die echte get_service-Factory
from app.middleware_api import MiddlewareAPI

# Nur die Exception-Typen importieren, damit wir das HTTP-Mapping testen können
from app.middleware_service import (
    ClientCertMissingError,
    ClientCertParsingError,
    InvalidAcceptTypeError,
    InvalidContentTypeError,
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
    get_service = api.get_service
    api.app.dependency_overrides[get_service] = lambda: obj

# -------------------------------------------------------------------
# WHOAMI
# -------------------------------------------------------------------

def test_whoami_success(client, middleware_api):
    class SvcOK:
        async def whoami(self, client_cert, accept_type):
            return DummyResponse({"client_id": "TestClient", "message": "ok"})

    override_service(middleware_api, SvcOK())

    r = client.get(
        "/v1/whoami",
        headers={"X-Client-Cert": "dummy", "accept": "application/json"},
    )
    assert r.status_code == 200 # nosec
    body = r.json()
    assert body["client_id"] == "TestClient" # nosec
    assert body["message"] == "ok" # nosec


@pytest.mark.parametrize(
    "exc, expected",
    [
        (ClientCertMissingError("missing"), 401),
        (ClientCertParsingError("bad cert"), 400),
        (InvalidAcceptTypeError("bad accept"), 406),
    ],
)
def test_whoami_exception_mapping(client, middleware_api, exc, expected):
    class SvcFail:
        async def whoami(self, *args, **kwargs):
            raise exc

    override_service(middleware_api, SvcFail())

    r = client.get(
        "/v1/whoami",
        headers={"X-Client-Cert": "dummy", "accept": "application/json"},
    )
    assert r.status_code == expected # nosec


# -------------------------------------------------------------------
# CREATE / UPDATE ARCS
# -------------------------------------------------------------------

def test_create_or_update_arcs_created(client, middleware_api):
    class SvcOK:
        async def create_or_update_arcs(self, data, client_cert, content_type, accept_type):
            return DummyResponse(
                {
                    "client_id": "TestClient",
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
            "X-Client-Cert": "dummy",
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


def test_create_or_update_arcs_updated(client, middleware_api):
    class SvcOK:
        async def create_or_update_arcs(self, data, client_cert, content_type, accept_type):
            return DummyResponse(
                {
                    "client_id": "TestClient",
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
            "X-Client-Cert": "dummy",
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
        (ClientCertMissingError("missing"), 401),
        (ClientCertParsingError("bad cert"), 400),
        (InvalidAcceptTypeError("bad accept"), 406),
        (InvalidContentTypeError("bad content-type"), 415),
        (InvalidJsonSyntaxError("bad json"), 400),
        (InvalidJsonSemanticError("bad crate"), 422),
    ],
)
def test_create_or_update_arcs_exception_mapping(client, middleware_api, exc, expected):
    class SvcFail:
        async def create_or_update_arcs(self, *args, **kwargs):
            raise exc

    override_service(middleware_api, SvcFail())

    r = client.post(
        "/v1/arcs",
        headers={
            "X-Client-Cert": "dummy",
            "content-type": "application/ro-crate+json",
            "accept": "application/json",
        },
        json=[{"dummy": "crate"}],
    )
    assert r.status_code == expected # nosec
