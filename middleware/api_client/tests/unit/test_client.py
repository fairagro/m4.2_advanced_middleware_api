"""Unit tests for the ApiClient class."""

import http
import ssl
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]

from middleware.api_client import ApiClient, ApiClientError, Config
from middleware.shared.api_models.models import CreateOrUpdateArcsResponse


@pytest.fixture
def client_config(test_config_dict: dict) -> Config:
    """Create a Config instance for testing."""
    return Config.from_data(test_config_dict)


@pytest.mark.asyncio
async def test_client_initialization_success(client_config: Config) -> None:
    """Test successful client initialization with valid config."""
    client = ApiClient(client_config)
    assert client._config == client_config  # pylint: disable=protected-access
    assert client._client is None  # pylint: disable=protected-access


@pytest.mark.asyncio
async def test_client_initialization_missing_cert(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization fails when certificate file is missing."""
    # Point to non-existent certificate
    test_config_dict["client_cert_path"] = str(temp_dir / "nonexistent-cert.pem")
    config = Config.from_data(test_config_dict)

    with pytest.raises(ApiClientError, match="Client certificate not found"):
        ApiClient(config)


@pytest.mark.asyncio
async def test_client_initialization_missing_key(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization fails when key file is missing."""
    # Point to non-existent key
    test_config_dict["client_key_path"] = str(temp_dir / "nonexistent-key.pem")
    config = Config.from_data(test_config_dict)

    with pytest.raises(ApiClientError, match="Client key not found"):
        ApiClient(config)


@pytest.mark.asyncio
async def test_client_initialization_missing_ca_cert(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization fails when CA cert is specified but missing."""
    # Point to non-existent CA cert
    test_config_dict["ca_cert_path"] = str(temp_dir / "nonexistent-ca.pem")
    config = Config.from_data(test_config_dict)

    with pytest.raises(ApiClientError, match="CA certificate not found"):
        ApiClient(config)


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arcs_success(client_config: Config) -> None:
    """Test successful create_or_update_arcs request."""
    # Mock the API response
    # Mock the API response (Task submission)
    task_response = {"task_id": "task-123", "status": "processing"}

    # Mock the Task Status response
    status_response = {
        "task_id": "task-123",
        "status": "SUCCESS",
        "result": {
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
        },
    }

    route_post = respx.post(f"{client_config.api_url}v1/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.ACCEPTED, json=task_response)
    )

    route_get = respx.get(f"{client_config.api_url}v1/tasks/task-123").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=status_response)
    )

    # Send request with ARC object
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test-arc", title="Test ARC"))
    async with ApiClient(client_config) as client:
        response = await client.create_or_update_arcs(
            rdi="test-rdi",
            arcs=[arc],
        )

    # Verify
    assert route_post.called
    assert route_get.called
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
    respx.post(f"{client_config.api_url}v1/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.FORBIDDEN, text="Forbidden")
    )

    # Should raise ApiClientError
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match=f"HTTP error {http.HTTPStatus.FORBIDDEN.value}"):
            await client.create_or_update_arcs(
                rdi="test-rdi",
                arcs=[arc],
            )


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arcs_network_error(client_config: Config) -> None:
    """Test create_or_update_arcs with network error."""
    # Mock a network error
    respx.post(f"{client_config.api_url}v1/arcs").mock(side_effect=httpx.ConnectError("Connection refused"))

    # Should raise ApiClientError
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Request error"):
            await client.create_or_update_arcs(
                rdi="test-rdi",
                arcs=[arc],
            )


@pytest.mark.asyncio
async def test_async_context_manager(client_config: Config) -> None:
    """Test that async context manager properly initializes and cleans up."""
    async with ApiClient(client_config) as client:
        assert isinstance(client, ApiClient)

    # After context exit, client should be closed
    # (we can't easily verify this without accessing private attributes)


@pytest.mark.asyncio
async def test_manual_close(client_config: Config) -> None:
    """Test manual close of the client."""
    client = ApiClient(client_config)

    # Create the HTTP client by calling _get_client
    http_client = client._get_client()  # pylint: disable=protected-access
    assert http_client is not None

    # Close manually
    await client.aclose()

    # Client should be None after close
    assert client._client is None  # pylint: disable=protected-access


@pytest.mark.asyncio
async def test_client_uses_certificates(test_config_dict: dict, test_cert_pem: tuple[Path, Path]) -> None:
    """Test that client is configured with the correct certificates."""
    cert_path, key_path = test_cert_pem

    # Update config to use the test certificates
    test_config_dict["client_cert_path"] = str(cert_path)
    test_config_dict["client_key_path"] = str(key_path)
    config = Config.from_data(test_config_dict)

    # Patch httpx.AsyncClient to capture the cert argument
    with patch("middleware.api_client.api_client.httpx.AsyncClient") as mock_client_class:
        # Configure the mock to return an AsyncMock instance with an async aclose method
        mock_instance = AsyncMock()
        mock_client_class.return_value = mock_instance

        client = ApiClient(config)
        client._get_client()  # pylint: disable=protected-access

        # Verify AsyncClient was called with the correct verify parameter
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args.kwargs

        # httpx now expects verify as an ssl.SSLContext with loaded cert chain
        assert "verify" in call_kwargs
        verify_param = call_kwargs["verify"]
        assert isinstance(verify_param, ssl.SSLContext)

        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_client_headers(client_config: Config) -> None:
    """Test that client sends correct headers."""
    task_response = {"task_id": "task-headers", "status": "processing"}
    status_response = {
        "task_id": "task-headers",
        "status": "SUCCESS",
        "result": {
            "client_id": "test",
            "message": "ok",
            "rdi": "test",
            "arcs": [],
        },
    }

    route_post = respx.post(f"{client_config.api_url}v1/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.ACCEPTED, json=task_response)
    )

    respx.get(f"{client_config.api_url}v1/tasks/task-headers").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=status_response)
    )

    async with ApiClient(client_config) as client:
        await client.create_or_update_arcs(rdi="test", arcs=[])

    # Verify headers
    assert route_post.called
    last_request = route_post.calls.last.request
    assert last_request.headers["accept"] == "application/json"
    assert last_request.headers["content-type"] == "application/json"
