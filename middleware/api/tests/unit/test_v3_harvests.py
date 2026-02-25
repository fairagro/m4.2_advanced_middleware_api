"""Unit tests for the v3/harvests endpoint."""

import http
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from middleware.api.api.fastapi_app import Api
from middleware.api.schemas import HarvestDocument, HarvestStatistics, HarvestStatus
from middleware.shared.api_models import ArcOperationResult, ArcResponse, ArcStatus


@pytest.mark.unit
def test_create_harvest_success(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test starting a new harvest."""
    harvest_id = "harvest-123"

    with (
        patch.object(
            middleware_api.business_logic.harvest_manager, "create_harvest", new_callable=AsyncMock
        ) as mock_create,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
    ):
        mock_create.return_value = harvest_id
        mock_auth.return_value = ["rdi-1"]
        mock_get.return_value = HarvestDocument(
            doc_id="harvest-123",
            rdi="rdi-1",
            client_id="test-client-cn",
            status=HarvestStatus.RUNNING,
            started_at=datetime.now(UTC),
            statistics=HarvestStatistics(),  # Replace with an appropriate HarvestStatistics instance
        )

        r = client.post(
            "/v3/harvests",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"rdi": "rdi-1"},
        )

        assert r.status_code == http.HTTPStatus.OK
        body = r.json()
        assert body["harvest_id"] == harvest_id
        assert body["status"] == "RUNNING"


@pytest.mark.unit
def test_submit_arc_in_harvest_success(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test submitting an ARC within a harvest context."""
    harvest_id = "harvest-123"

    mock_harvest = HarvestDocument(
        doc_id=harvest_id,
        rdi="rdi-1",
        client_id="test-client-cn",
        status=HarvestStatus.RUNNING,
        started_at=datetime.now(UTC),
        statistics=HarvestStatistics(),  # Replace with an appropriate HarvestStatistics instance
    )

    mock_result = ArcOperationResult(
        client_id="test-client-cn",
        rdi="rdi-1",
        arc=ArcResponse(
            id="arc-123",
            status=ArcStatus.CREATED,
            timestamp="2024-01-01T00:00:00Z",
        ),
    )

    now = datetime.now(UTC)
    mock_metadata = MagicMock()
    mock_metadata.arc_hash = "fake-hash"
    mock_metadata.status = "ACTIVE"
    mock_metadata.first_seen = now
    mock_metadata.last_seen = now
    mock_metadata.events = []

    rocrate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "ARC-001"}],
    }

    with (
        patch.object(
            middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock
        ) as mock_get_harvest,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(middleware_api.business_logic, "create_or_update_arc", new_callable=AsyncMock) as mock_create_arc,
        patch.object(middleware_api.business_logic, "get_metadata", new_callable=AsyncMock) as mock_get_metadata,
    ):
        mock_get_harvest.return_value = mock_harvest
        mock_auth.return_value = ["rdi-1"]
        mock_create_arc.return_value = mock_result
        mock_get_metadata.return_value = mock_metadata

        r = client.post(
            f"/v3/harvests/{harvest_id}/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"arc": rocrate},
        )

        assert r.status_code == http.HTTPStatus.OK
        body = r.json()
        assert body["arc_id"] == "arc-123"
        # Check that harvest_id was passed if possible, but at least verify success
        mock_create_arc.assert_called_once()
        assert mock_create_arc.call_args[1]["harvest_id"] == harvest_id
