
from fastapi.testclient import TestClient
import pytest


@pytest.mark.asyncio
async def test_whoami_with_client_cert(client: TestClient, cert: str):
    # Optional Base64 encodieren, falls dein Code das erwartet
    cert_with_linebreaks = cert.replace("\\n", "\n")

    headers = {
        "X-Client-Cert": cert_with_linebreaks,
        "accept": "application/json"
    }

    response = client.get("/v1/whoami", headers=headers)

    assert response.status_code == 200 # nosec
    body = response.json()
    assert body["client_id"] == "TestClient" # nosec

