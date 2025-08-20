from fastapi.testclient import TestClient


def test_authenticated(client: TestClient, cert: str):
    response = client.get(
        "/v1/whoami",
        headers={
            "X-Client-Cert": cert,
            "Accept": "application/json"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "TestClient"


def test_no_cert_header(client: TestClient):
    response = client.get(
        "/v1/whoami",
        headers={
            "Accept": "application/json"
        }
    )
    assert response.status_code == 401


def test_whoami_invalid_cert(client: TestClient):
    response = client.get(
        "/v1/whoami",
        headers={
            "X-Client-Cert": "invalid_client_certificate",
            "Accept": "application/json"
        }
    )
    assert response.status_code == 400


def test_invalid_accept_header(client: TestClient, cert: str):
    response = client.get(
        "/v1/whoami",
        headers={
            "X-Client-Cert": cert,
            "Accept": "application/xml"
        }
    )
    assert response.status_code == 406
