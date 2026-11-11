"""Auth ordering checks for shared v3 harvest lifecycle routes."""

import http
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from middleware.api.api.fastapi_app import Api


@pytest.mark.unit
def test_complete_harvest_requires_client_cert_before_lookup(client: TestClient, middleware_api: Api) -> None:
    """Missing client cert must 401 before harvest lookup (no existence leak)."""
    with patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        r = client.post(
            "/v3/harvests/no-such/complete",
            headers={"accept": "application/json"},
        )

        assert r.status_code == http.HTTPStatus.UNAUTHORIZED
        mock_get.assert_not_awaited()
