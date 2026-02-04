"""System tests for the /v1/whoami endpoint."""

import http

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
@pytest.mark.system
async def test_whoami_with_client_cert(client: TestClient, cert: str) -> None:
    """Test the /v1/whoami endpoint with a client certificate."""
    cert_with_linebreaks = cert.replace("\\n", "\n")

    headers = {"ssl-client-cert": cert_with_linebreaks, "ssl-client-verify": "SUCCESS", "accept": "application/json"}

    response = client.get("/v1/whoami", headers=headers)

    assert response.status_code == http.HTTPStatus.OK  # nosec
    body = response.json()
    assert body["client_id"] == "TestClient"  # nosec
