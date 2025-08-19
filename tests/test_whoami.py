from .prepare_tests import client, test_cert


def test_authenticated():
    response = client.get(
        "/v1/whoami",
        headers={
            "X-Client-Cert": test_cert,
            "Accept": "application/json"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == "TestClient"


def test_no_cert_header():
    response = client.get(
        "/v1/whoami",
        headers={
            "Accept": "application/json"
        }
    )
    assert response.status_code == 401


def test_whoami_invalid_cert():
    response = client.get(
        "/v1/whoami",
        headers={
            "X-Client-Cert": "invalid_client_certificate",
            "Accept": "application/json"
        }
    )
    assert response.status_code == 400


def test_invalid_accept_header():
    response = client.get(
        "/v1/whoami",
        headers={
            "X-Client-Cert": test_cert,
            "Accept": "application/xml"
        }
    )
    assert response.status_code == 406
