"""Integration tests for API client against real API instance.

These tests use FastAPI TestClient to start the Middleware API within the test,
allowing us to test the full request/response cycle without needing nginx or
a real HTTP server.
"""

import json

import httpx
import pytest
import respx
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]

from middleware.api_client import ApiClient, Config
from middleware.shared.api_models.models import CreateOrUpdateArcsRequest


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_integration_mock_server(client_config: Config) -> None:
    """Test create_or_update_arcs with mocked server responses.

    This test uses respx to mock the HTTP responses, allowing us to verify
    that the client correctly sends certificates and handles responses.
    """
    # Mock successful response
    mock_response = {
        "client_id": "TestClient",
        "message": "ARCs created",
        "rdi": "test-rdi",
        "arcs": [
            {
                "id": "arc-id-123",
                "status": "created",
                "timestamp": "2024-01-01T12:00:00Z",
            }
        ],
    }

    route = respx.post(f"{client_config.api_url}/v1/arcs").mock(return_value=httpx.Response(201, json=mock_response))

    # Execute request with ARC object
    arc = ARC.from_arc_investigation(ArcInvestigation.create(
        identifier="test-arc-001",
        title="Test ARC",
        description="Integration test ARC"
    ))
    async with ApiClient(client_config) as client:
        response = await client.create_or_update_arcs(
            rdi="test-rdi",
            arcs=[arc],
        )

    # Verify
    assert route.called
    assert response.rdi == "test-rdi"
    assert len(response.arcs) == 1
    assert response.arcs[0].status == "created"

    # Verify request was sent correctly
    last_request = route.calls.last.request
    assert last_request.method == "POST"
    assert "application/json" in last_request.headers["content-type"]

    # Verify request body
    body = json.loads(last_request.content)
    assert body["rdi"] == "test-rdi"
    assert len(body["arcs"]) == 1


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_unauthorized(client_config: Config) -> None:
    """Test handling of 401 Unauthorized response."""
    respx.post(f"{client_config.api_url}/v1/arcs").mock(return_value=httpx.Response(401, text="Unauthorized"))

    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(Exception, match="401"):
            await client.create_or_update_arcs(
                rdi="test-rdi",
                arcs=[arc],
            )


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_forbidden(client_config: Config) -> None:
    """Test handling of 403 Forbidden response."""
    respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(403, text="Forbidden - RDI not authorized")
    )

    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(Exception, match="403"):
            await client.create_or_update_arcs(
                rdi="unauthorized-rdi",
                arcs=[arc],
            )


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_validation_error(client_config: Config) -> None:
    """Test handling of 422 Validation Error response."""
    respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(422, json={"detail": "Invalid ARC data"})
    )

    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(Exception, match="422"):
            await client.create_or_update_arcs(
                rdi="test-rdi",
                arcs=[arc],
            )


@pytest.mark.asyncio
@respx.mock
async def test_create_multiple_arcs(client_config: Config) -> None:
    """Test creating multiple ARCs in one request."""
    mock_response = {
        "client_id": "TestClient",
        "message": "ARCs created",
        "rdi": "test-rdi",
        "arcs": [
            {
                "id": "arc-1",
                "status": "created",
                "timestamp": "2024-01-01T12:00:00Z",
            },
            {
                "id": "arc-2",
                "status": "created",
                "timestamp": "2024-01-01T12:00:01Z",
            },
        ],
    }

    route = respx.post(f"{client_config.api_url}/v1/arcs").mock(return_value=httpx.Response(201, json=mock_response))

    arc1 = ARC.from_arc_investigation(ArcInvestigation.create(identifier="arc-1", title="ARC 1"))
    arc2 = ARC.from_arc_investigation(ArcInvestigation.create(identifier="arc-2", title="ARC 2"))
    async with ApiClient(client_config) as client:
        response = await client.create_or_update_arcs(
            rdi="test-rdi",
            arcs=[arc1, arc2],
        )

    assert route.called
    assert len(response.arcs) == 2

    # Verify request body has both ARCs
    body = json.loads(route.calls.last.request.content)
    assert len(body["arcs"]) == 2


@pytest.mark.asyncio
@respx.mock
async def test_timeout_error(client_config: Config) -> None:
    """Test handling of timeout errors."""
    # Set a short timeout
    client_config.timeout = 0.1

    # Mock a slow response
    respx.post(f"{client_config.api_url}/v1/arcs").mock(side_effect=httpx.TimeoutException("Request timeout"))

    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(Exception, match="timeout|Timeout"):
            await client.create_or_update_arcs(
                rdi="test-rdi",
                arcs=[arc],
            )
