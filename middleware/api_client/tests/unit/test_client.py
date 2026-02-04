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
from middleware.shared.api_models.models import ArcOperationResult


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
async def test_create_or_update_arc_success(client_config: Config) -> None:
    """Test successful create_or_update_arc request."""
    # Mock the API response
    # Mock the API response (Task submission)
    task_response = {"task_id": "task-123", "status": "PENDING"}

    # Mock the Task Status response
    status_response = {
        "status": "SUCCESS",
        "result": {
            "client_id": "TestClient",
            "message": "ARC created successfully",
            "rdi": "test-rdi",
            "arc": {
                "id": "test-arc-123",
                "status": "created",
                "timestamp": "2024-01-01T12:00:00Z",
            },
        },
    }

    route_post = respx.post(f"{client_config.api_url}v2/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.ACCEPTED, json=task_response)
    )

    route_get = respx.get(f"{client_config.api_url}v2/tasks/task-123").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=status_response)
    )

    # Send request with ARC object
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test-arc", title="Test ARC"))
    async with ApiClient(client_config) as client:
        response = await client.create_or_update_arc(
            rdi="test-rdi",
            arc=arc,
        )

    # Verify
    assert route_post.called
    assert route_get.called
    assert isinstance(response, ArcOperationResult)
    assert response.rdi == "test-rdi"
    assert response.arc.id == "test-arc-123"
    assert response.arc.status == "created"


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_http_error(client_config: Config) -> None:
    """Test create_or_update_arc with HTTP error response."""
    # Mock an error response
    respx.post(f"{client_config.api_url}v2/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.FORBIDDEN, text="Forbidden")
    )

    # Should raise ApiClientError
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match=f"HTTP error {http.HTTPStatus.FORBIDDEN.value}"):
            await client.create_or_update_arc(
                rdi="test-rdi",
                arc=arc,
            )


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_network_error(client_config: Config) -> None:
    """Test create_or_update_arc with network error."""
    # Mock a network error
    respx.post(f"{client_config.api_url}v2/arcs").mock(side_effect=httpx.ConnectError("Connection refused"))

    # Should raise ApiClientError
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Request error"):
            await client.create_or_update_arc(
                rdi="test-rdi",
                arc=arc,
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
    task_response = {"task_id": "task-headers", "status": "PENDING"}
    status_response = {
        "status": "SUCCESS",
        "result": {
            "client_id": "test",
            "message": "ok",
            "rdi": "test",
            "arc": {"id": "arc-1", "status": "created", "timestamp": "2024-01-01T00:00:00Z"},
        },
    }

    route_post = respx.post(f"{client_config.api_url}v2/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.ACCEPTED, json=task_response)
    )

    respx.get(f"{client_config.api_url}v2/tasks/task-headers").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=status_response)
    )

    async with ApiClient(client_config) as client:
        # Use a dict so it's treated as pre-serialized, avoiding JSON serialization issues with Mock
        await client.create_or_update_arc(rdi="test", arc={"id": "mock-arc"})

    # Verify headers
    assert route_post.called
    last_request = route_post.calls.last.request
    assert last_request.headers["accept"] == "application/json"
    assert last_request.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_client_verify_ssl_false(test_config_dict: dict) -> None:
    """Test client initialization with verify_ssl=False."""
    test_config_dict["verify_ssl"] = "false"
    config = Config.from_data(test_config_dict)
    client = ApiClient(config)

    with patch("httpx.AsyncClient") as mock_client:
        client._get_client()  # pylint: disable=protected-access
        mock_client.assert_called_once()
        _, kwargs = mock_client.call_args
        assert kwargs["verify"] is False


@pytest.mark.asyncio
async def test_client_with_ca_cert(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization with a CA certificate."""
    ca_cert = temp_dir / "ca.pem"
    ca_cert.write_text("fake-ca-cert")
    test_config_dict["ca_cert_path"] = str(ca_cert)
    config = Config.from_data(test_config_dict)
    client = ApiClient(config)

    with patch("httpx.AsyncClient") as mock_client, patch("ssl.create_default_context") as mock_ssl:
        mock_ctx = mock_ssl.return_value
        client._get_client()  # pylint: disable=protected-access
        mock_ssl.assert_called_once_with(cafile=str(ca_cert))
        _, kwargs = mock_client.call_args
        assert kwargs["verify"] == mock_ctx


@pytest.mark.asyncio
async def test_client_with_ca_and_mtls_cert(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization with both CA and mTLS certificates."""
    ca_cert = temp_dir / "ca.pem"
    ca_cert.write_text("fake-ca-cert")
    cert_path = temp_dir / "client.crt"
    cert_path.write_text("fake-cert")
    key_path = temp_dir / "client.key"
    key_path.write_text("fake-key")

    test_config_dict["ca_cert_path"] = str(ca_cert)
    test_config_dict["client_cert_path"] = str(cert_path)
    test_config_dict["client_key_path"] = str(key_path)

    config = Config.from_data(test_config_dict)
    client = ApiClient(config)

    with patch("httpx.AsyncClient") as mock_client, patch("ssl.create_default_context") as mock_ssl:
        mock_ctx = mock_ssl.return_value
        client._get_client()  # pylint: disable=protected-access
        mock_ssl.assert_called_once_with(cafile=str(ca_cert))
        mock_ctx.load_cert_chain.assert_called_once_with(str(cert_path), str(key_path))
        _, kwargs = mock_client.call_args
        assert kwargs["verify"] == mock_ctx


@pytest.mark.asyncio
@respx.mock
async def test_get_http_error(client_config: Config) -> None:
    """Test _get with an HTTP error."""
    respx.get(f"{client_config.api_url}v2/test").mock(return_value=httpx.Response(http.HTTPStatus.NOT_FOUND))
    client = ApiClient(client_config)
    with pytest.raises(ApiClientError, match="HTTP error 404"):
        await client._get("v2/test")  # pylint: disable=protected-access


@pytest.mark.asyncio
@respx.mock
async def test_get_network_error(client_config: Config) -> None:
    """Test _get with a network error."""
    respx.get(f"{client_config.api_url}v2/test").mock(side_effect=httpx.RequestError("Network error"))
    client = ApiClient(client_config)
    with pytest.raises(ApiClientError, match="Request error: Network error"):
        await client._get("v2/test")  # pylint: disable=protected-access


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_no_task_id(client_config: Config) -> None:
    """Test create_or_update_arc when API returns no task_id."""
    respx.post(f"{client_config.api_url}v2/arcs").mock(return_value=httpx.Response(http.HTTPStatus.ACCEPTED, json={}))
    client = ApiClient(client_config)
    with pytest.raises(ApiClientError, match="Invalid response from API during submission"):
        await client.create_or_update_arc(rdi="test", arc={"id": "mock-arc"})


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_task_failure(client_config: Config) -> None:
    """Test create_or_update_arc when poll returns FAILURE."""
    task_response = {"task_id": "failed-task", "status": "PENDING"}
    status_response = {
        "status": "FAILURE",
        "message": "Something went wrong",
    }

    respx.post(f"{client_config.api_url}v2/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.ACCEPTED, json=task_response)
    )
    respx.get(f"{client_config.api_url}v2/tasks/failed-task").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=status_response)
    )

    client = ApiClient(client_config)
    with (
        patch("asyncio.sleep", return_value=None),
        pytest.raises(ApiClientError, match="Task FAILURE: Something went wrong"),
    ):
        await client.create_or_update_arc(rdi="test", arc={"id": "mock-arc"})


@pytest.mark.asyncio
@respx.mock
async def test_poll_for_result_timeout(client_config: Config) -> None:
    """Test that _poll_for_result raises ApiClientError on timeout."""
    # Set a short timeout for the test (in minutes)
    client_config.polling_timeout = 0.01  # 0.6 seconds
    client_config.polling_initial_delay = 0.2

    # Mock the Task Status response to stay PENDING
    status_response = {"status": "PENDING"}

    respx.get(f"{client_config.api_url}v2/tasks/task-timeout").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=status_response)
    )

    async with ApiClient(client_config) as client:
        # We mock asyncio.sleep to avoid waiting during the test
        # but the logic still increments time_waited based on 'delay'
        with patch("asyncio.sleep", return_value=None) as mock_sleep:
            with pytest.raises(ApiClientError, match="timed out after 0.01 minutes"):
                await client._poll_for_result("task-timeout")  # pylint: disable=protected-access
            assert mock_sleep.called
