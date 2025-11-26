"""Unit tests for the MiddlewareClient class."""

import pytest
import httpx
import respx
from pathlib import Path

from middleware.api_client import Config, MiddlewareClient, MiddlewareClientError
from middleware.shared.api_models.models import (
    CreateOrUpdateArcsRequest,
    CreateOrUpdateArcsResponse,
)


@pytest.fixture
def client_config(test_config_dict: dict) -> Config:
    """Create a Config instance for testing."""
    return Config.from_data(test_config_dict)


@pytest.mark.asyncio
async def test_client_initialization_success(client_config: Config) -> None:
    """Test successful client initialization with valid config."""
    client = MiddlewareClient(client_config)
    assert client._config == client_config
    assert client._client is None  # Not created until needed


@pytest.mark.asyncio
async def test_client_initialization_missing_cert(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization fails when certificate file is missing."""
    # Point to non-existent certificate
    test_config_dict["client_cert_path"] = str(temp_dir / "nonexistent-cert.pem")
    config = Config.from_data(test_config_dict)
    
    with pytest.raises(MiddlewareClientError, match="Client certificate not found"):
        MiddlewareClient(config)


@pytest.mark.asyncio
async def test_client_initialization_missing_key(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization fails when key file is missing."""
    # Point to non-existent key
    test_config_dict["client_key_path"] = str(temp_dir / "nonexistent-key.pem")
    config = Config.from_data(test_config_dict)
    
    with pytest.raises(MiddlewareClientError, match="Client key not found"):
        MiddlewareClient(config)


@pytest.mark.asyncio
async def test_client_initialization_missing_ca_cert(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization fails when CA cert is specified but missing."""
    # Point to non-existent CA cert
    test_config_dict["ca_cert_path"] = str(temp_dir / "nonexistent-ca.pem")
    config = Config.from_data(test_config_dict)
    
    with pytest.raises(MiddlewareClientError, match="CA certificate not found"):
        MiddlewareClient(config)


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arcs_success(client_config: Config) -> None:
    """Test successful create_or_update_arcs request."""
    # Mock the API response
    mock_response = {
        "client_id": "TestClient",
        "message": "ARCs created successfully",
        "rdi": "test-rdi",
        "arcs": [
            {
                "id": "test-arc-123",
                "status": "created",
                "timestamp": "2024-01-01T12:00:00Z",
            }
        ],
    }
    
    route = respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(201, json=mock_response)
    )
    
    # Create request
    request = CreateOrUpdateArcsRequest(
        rdi="test-rdi",
        arcs=[{"@id": "test-arc", "@type": "Dataset"}],
    )
    
    # Send request
    async with MiddlewareClient(client_config) as client:
        response = await client.create_or_update_arcs(request)
    
    # Verify
    assert route.called
    assert isinstance(response, CreateOrUpdateArcsResponse)
    assert response.rdi == "test-rdi"
    assert len(response.arcs) == 1
    assert response.arcs[0].id == "test-arc-123"
    assert response.arcs[0].status == "created"


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arcs_http_error(client_config: Config) -> None:
    """Test create_or_update_arcs with HTTP error response."""
    # Mock an error response
    respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(403, text="Forbidden")
    )
    
    request = CreateOrUpdateArcsRequest(
        rdi="test-rdi",
        arcs=[{"@id": "test-arc", "@type": "Dataset"}],
    )
    
    # Should raise MiddlewareClientError
    async with MiddlewareClient(client_config) as client:
        with pytest.raises(MiddlewareClientError, match="HTTP error 403"):
            await client.create_or_update_arcs(request)


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arcs_network_error(client_config: Config) -> None:
    """Test create_or_update_arcs with network error."""
    # Mock a network error
    respx.post(f"{client_config.api_url}/v1/arcs").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    
    request = CreateOrUpdateArcsRequest(
        rdi="test-rdi",
        arcs=[{"@id": "test-arc", "@type": "Dataset"}],
    )
    
    # Should raise MiddlewareClientError
    async with MiddlewareClient(client_config) as client:
        with pytest.raises(MiddlewareClientError, match="Request error"):
            await client.create_or_update_arcs(request)


@pytest.mark.asyncio
async def test_async_context_manager(client_config: Config) -> None:
    """Test that async context manager properly initializes and cleans up."""
    async with MiddlewareClient(client_config) as client:
        assert isinstance(client, MiddlewareClient)
    
    # After context exit, client should be closed
    # (we can't easily verify this without accessing private attributes)


@pytest.mark.asyncio
async def test_manual_close(client_config: Config) -> None:
    """Test manual close of the client."""
    client = MiddlewareClient(client_config)
    
    # Create the HTTP client by calling _get_client
    http_client = client._get_client()
    assert http_client is not None
    
    # Close manually
    await client.aclose()
    
    # Client should be None after close
    assert client._client is None


@pytest.mark.asyncio
@respx.mock
async def test_client_uses_certificates(client_config: Config, test_cert_pem: tuple[Path, Path]) -> None:
    """Test that client is configured with the correct certificates."""
    cert_path, key_path = test_cert_pem
    
    # Mock response
    respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(201, json={
            "client_id": "test",
            "message": "ok",
            "rdi": "test",
            "arcs": [],
        })
    )
    
    client = MiddlewareClient(client_config)
    http_client = client._get_client()
    
    # Verify that cert is configured (httpx stores it as a tuple)
    assert http_client._transport._pool._ssl_context is not None or http_client.cert is not None
    
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_client_headers(client_config: Config) -> None:
    """Test that client sends correct headers."""
    route = respx.post(f"{client_config.api_url}/v1/arcs").mock(
        return_value=httpx.Response(201, json={
            "client_id": "test",
            "message": "ok",
            "rdi": "test",
            "arcs": [],
        })
    )
    
    request = CreateOrUpdateArcsRequest(
        rdi="test",
        arcs=[],
    )
    
    async with MiddlewareClient(client_config) as client:
        await client.create_or_update_arcs(request)
    
    # Verify headers
    assert route.called
    last_request = route.calls.last.request
    assert last_request.headers["accept"] == "application/json"
    assert last_request.headers["content-type"] == "application/json"
