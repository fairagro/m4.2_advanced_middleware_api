"""Unit tests for the v3/arcs endpoint."""

import http
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from middleware.api.api.common.dependencies import get_client_id
from middleware.api.api.fastapi_app import Api
from middleware.api.document_store.arc_document import ArcEvent, ArcMetadata
from middleware.shared.api_models import ArcOperationResult, ArcResponse, ArcStatus
from middleware.shared.api_models.common.models import ArcEventType, ArcLifecycleStatus


@pytest.mark.unit
def test_create_or_update_arc_v3_success(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test creating a new ARC via the /v3/arcs endpoint."""
    # Mock the BusinessLogic response
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
    mock_metadata = ArcMetadata(
        arc_hash="fake-hash",
        status=ArcLifecycleStatus.ACTIVE,
        first_seen=now,
        last_seen=now,
        events=[ArcEvent(timestamp=now, type=ArcEventType.ARC_CREATED, message="ARC first seen")],
    )

    rocrate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "identifier": "ARC-001",
            }
        ],
    }

    with (
        patch.object(middleware_api.business_logic, "create_or_update_arc", new_callable=AsyncMock) as mock_create,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(
            middleware_api.business_logic._doc_store,  # noqa: SLF001
            "get_metadata",
            new_callable=AsyncMock,
        ) as mock_get_metadata,
    ):
        mock_create.return_value = mock_result
        mock_auth.return_value = ["rdi-1"]
        mock_get_metadata.return_value = mock_metadata

        r = client.post(
            "/v3/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"rdi": "rdi-1", "arc": rocrate},
        )

        assert r.status_code == http.HTTPStatus.OK
        body = r.json()
        assert body["arc_id"] == "arc-123"
        assert body["status"] == "created"
        assert body["metadata"]["arc_hash"] == "fake-hash"
        assert len(body["events"]) == 1
        assert body["events"][0]["type"] == "ARC_CREATED"
        # Verify it doesn't return a task_id
        assert "task_id" not in body


@pytest.mark.unit
def test_create_or_update_arc_v3_rdi_not_authorized(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test that requesting an unauthorized RDI returns 403."""
    # Use an RDI that is known (rdi-1 is in known_rdis) but mock auth to return empty
    middleware_api.app.dependency_overrides[get_client_id] = lambda: "TestClient"

    with patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = []

        r = client.post(
            "/v3/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"rdi": "rdi-1", "arc": {"dummy": "crate"}},
        )
        assert r.status_code == http.HTTPStatus.FORBIDDEN

    middleware_api.app.dependency_overrides.clear()
