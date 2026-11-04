"""System tests for the /v1/whoami and /v3/whoami endpoints."""

import http

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize("path", ["/v1/whoami", "/v3/whoami"])
async def test_whoami_with_client_cert(client: TestClient, cert: str, path: str) -> None:
    """Test whoami with a client certificate on v1 and v3."""
    cert_with_linebreaks = cert.replace("\\n", "\n")

    headers = {"ssl-client-cert": cert_with_linebreaks, "ssl-client-verify": "SUCCESS", "accept": "application/json"}

    response = client.get(path, headers=headers)

    assert response.status_code == http.HTTPStatus.OK  # nosec
    body = response.json()
    assert body["client_id"] == "TestClient"  # nosec
