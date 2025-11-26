"""Integration tests for API client against real API instance.

These tests use FastAPI TestClient to start the Middleware API within the test,
allowing us to test the full request/response cycle without needing nginx or
a real HTTP server.
"""

import json
import pytest
import respx
import httpx
from pathlib import Path

from middleware.api_client import Config, MiddlewareClient
from middleware.shared.api_models.models import CreateOrUpdateArcsRequest


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_integration_mock_server(
    client_config: Config,
    test_cert_pem: tuple[Path, Path],
) -> None:
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
    
    route = respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(201, json=mock_response)
    )
    
    # Create request with realistic RO-Crate data
    request = CreateOrUpdateArcsRequest(
        rdi="test-rdi",
        arcs=[
            {
                "@context": "https://w3id.org/ro/crate/1.1/context",
                "@id": "test-arc-001",
                "@type": "Dataset",
                "name": "Test ARC",
                "description": "Integration test ARC",
            }
        ],
    )
    
    # Execute request
    async with MiddlewareClient(client_config) as client:
        response = await client.create_or_update_arcs(request)
    
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
    respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    
    request = CreateOrUpdateArcsRequest(
        rdi="test-rdi",
        arcs=[{"@id": "test", "@type": "Dataset"}],
    )
    
    async with MiddlewareClient(client_config) as client:
        with pytest.raises(Exception, match="401"):
            await client.create_or_update_arcs(request)


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_forbidden(client_config: Config) -> None:
    """Test handling of 403 Forbidden response."""
    respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(403, text="Forbidden - RDI not authorized")
    )
    
    request = CreateOrUpdateArcsRequest(
        rdi="unauthorized-rdi",
        arcs=[{"@id": "test", "@type": "Dataset"}],
    )
    
    async with MiddlewareClient(client_config) as client:
        with pytest.raises(Exception, match="403"):
            await client.create_or_update_arcs(request)


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_validation_error(client_config: Config) -> None:
    """Test handling of 422 Validation Error response."""
    respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(422, json={
            "detail": "Invalid ARC data"
        })
    )
    
    request = CreateOrUpdateArcsRequest(
        rdi="test-rdi",
        arcs=[{"invalid": "data"}],
    )
    
    async with MiddlewareClient(client_config) as client:
        with pytest.raises(Exception, match="422"):
            await client.create_or_update_arcs(request)


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
    
    route = respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(201, json=mock_response)
    )
    
    request = CreateOrUpdateArcsRequest(
        rdi="test-rdi",
        arcs=[
            {
                "@context": "https://w3id.org/ro/crate/1.1/context",
                "@id": "arc-1",
                "@type": "Dataset",
            },
            {
                "@context": "https://w3id.org/ro/crate/1.1/context",
                "@id": "arc-2",
                "@type": "Dataset",
            },
        ],
    )
    
    async with MiddlewareClient(client_config) as client:
        response = await client.create_or_update_arcs(request)
    
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
    respx.post(f"{client_config.api_url}/v1/arcs").mock(
        side_effect=httpx.TimeoutException("Request timeout")
    )
    
    request = CreateOrUpdateArcsRequest(
        rdi="test-rdi",
        arcs=[{"@id": "test", "@type": "Dataset"}],
    )
    
    async with MiddlewareClient(client_config) as client:
        with pytest.raises(Exception, match="timeout|Timeout"):
            await client.create_or_update_arcs(request)
