"""Unit tests for the ApiClient class (v3 API)."""

from __future__ import annotations

import asyncio
import http
import json
import ssl
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]
from client_test_support import ARC_RESPONSE, HARVEST_RESPONSE, rocrate_dict

from middleware.api_client import (
    ApiClient,
    ApiClientError,
    ArcResult,
    Config,
    HarvestResult,
)

# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_initialization_success(client_config: Config) -> None:
    """Test successful client initialization with valid config."""
    client = ApiClient(client_config)
    assert client._config == client_config  # noqa: SLF001
    assert client._client is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_client_initialization_missing_cert(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization fails when certificate file is missing."""
    test_config_dict["client_cert_path"] = str(temp_dir / "nonexistent-cert.pem")
    config = Config.from_data(test_config_dict)
    with pytest.raises(ApiClientError, match="Client certificate not found"):
        ApiClient(config)


@pytest.mark.asyncio
async def test_client_initialization_missing_key(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization fails when key file is missing."""
    test_config_dict["client_key_path"] = str(temp_dir / "nonexistent-key.pem")
    config = Config.from_data(test_config_dict)
    with pytest.raises(ApiClientError, match="Client key not found"):
        ApiClient(config)


@pytest.mark.asyncio
async def test_client_initialization_missing_ca_cert(test_config_dict: dict, temp_dir: Path) -> None:
    """Test client initialization fails when CA cert is specified but missing."""
    test_config_dict["ca_cert_path"] = str(temp_dir / "nonexistent-ca.pem")
    config = Config.from_data(test_config_dict)
    with pytest.raises(ApiClientError, match="CA certificate not found"):
        ApiClient(config)


# ---------------------------------------------------------------------------
# SSL / certificate wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_uses_certificates(test_config_dict: dict, test_cert_pem: tuple[Path, Path]) -> None:
    """Test that the client is configured with the correct certificates."""
    cert_path, key_path = test_cert_pem
    test_config_dict["client_cert_path"] = str(cert_path)
    test_config_dict["client_key_path"] = str(key_path)
    config = Config.from_data(test_config_dict)

    with patch("middleware.api_client.api_client.httpx.AsyncClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_client_class.return_value = mock_instance
        client = ApiClient(config)
        client._get_client()  # noqa: SLF001
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args.kwargs
        assert "verify" in call_kwargs
        assert isinstance(call_kwargs["verify"], ssl.SSLContext)
        await client.aclose()


@pytest.mark.asyncio
async def test_client_verify_ssl_false(test_config_dict: dict) -> None:
    """Test client initialization with verify_ssl=False."""
    test_config_dict["verify_ssl"] = "false"
    config = Config.from_data(test_config_dict)
    client = ApiClient(config)
    with patch("httpx.AsyncClient") as mock_client:
        client._get_client()  # noqa: SLF001
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
        client._get_client()  # noqa: SLF001
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
        client._get_client()  # noqa: SLF001
        mock_ssl.assert_called_once_with(cafile=str(ca_cert))
        mock_ctx.load_cert_chain.assert_called_once_with(str(cert_path), str(key_path))
        _, kwargs = mock_client.call_args
        assert kwargs["verify"] == mock_ctx


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_context_manager(client_config: Config) -> None:
    """Test that async context manager works correctly."""
    async with ApiClient(client_config) as client:
        assert isinstance(client, ApiClient)


@pytest.mark.asyncio
async def test_manual_close(client_config: Config) -> None:
    """Test manual close of the client."""
    client = ApiClient(client_config)
    http_client = client._get_client()  # noqa: SLF001
    assert http_client is not None
    await client.aclose()
    assert client._client is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# create_or_update_arc  (POST v3/arcs)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_success(client_config: Config) -> None:
    """Test successful create_or_update_arc with v3 endpoint."""
    route = respx.post(f"{client_config.api_url}v3/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )

    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test-arc", title="Test ARC"))
    async with ApiClient(client_config) as client:
        response = await client.create_or_update_arc(rdi="test-rdi", arc=arc)

    assert route.called
    assert isinstance(response, ArcResult)
    assert response.arc_id == "arc-123"
    assert response.status == "created"


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_with_dict(client_config: Config) -> None:
    """Test create_or_update_arc with a pre-serialised dict."""
    respx.post(f"{client_config.api_url}v3/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        response = await client.create_or_update_arc(rdi="test-rdi", arc=rocrate_dict())
    assert isinstance(response, ArcResult)


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_with_json_string(client_config: Config) -> None:
    """Test create_or_update_arc with a JSON string."""
    route = respx.post(f"{client_config.api_url}v3/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        response = await client.create_or_update_arc(rdi="test-rdi", arc=json.dumps(rocrate_dict()))
    assert route.called
    assert isinstance(response, ArcResult)
    assert response.arc_id == "arc-123"


@pytest.mark.asyncio
async def test_create_or_update_arc_with_invalid_json_string(client_config: Config) -> None:
    """Test create_or_update_arc with an invalid JSON string."""
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Invalid JSON string provided for ARC"):
            await client.create_or_update_arc(rdi="test-rdi", arc='{"@context":')


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_http_error(client_config: Config) -> None:
    """Test create_or_update_arc with an HTTP error response."""
    respx.post(f"{client_config.api_url}v3/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.FORBIDDEN, text="Forbidden")
    )
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match=f"HTTP error {http.HTTPStatus.FORBIDDEN.value}"):
            await client.create_or_update_arc(rdi="test-rdi", arc=arc)


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_retries_on_connect_error(client_config: Config) -> None:
    """ARC POST is server-idempotent: ConnectError is retried then succeeds."""
    client_config.retry_backoff_factor = 0.01
    client_config.max_retries = 2
    route = respx.post(f"{client_config.api_url}v3/arcs").mock(
        side_effect=[
            httpx.ConnectError("Connection refused"),
            httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE),
        ]
    )
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        result = await client.create_or_update_arc(rdi="test-rdi", arc=arc)
    assert result.arc_id == ARC_RESPONSE["arc_id"]
    assert route.call_count == 2  # noqa: PLR2004


@pytest.mark.asyncio
@respx.mock
async def test_create_harvest_network_error_not_retried(client_config: Config) -> None:
    """Non-ARC POSTs (create harvest) must not retry ConnectError."""
    client_config.retry_backoff_factor = 0.01
    route = respx.post(f"{client_config.api_url}v3/harvests").mock(side_effect=httpx.ConnectError("Connection refused"))
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Request failed: Connection refused"):
            await client.create_harvest(rdi="test-rdi")
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_invalid_response(client_config: Config) -> None:
    """Test create_or_update_arc raises when the server returns unexpected JSON."""
    respx.post(f"{client_config.api_url}v3/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json={"unexpected": "data"})
    )
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Invalid ARC response"):
            await client.create_or_update_arc(rdi="test-rdi", arc=rocrate_dict("mock"))


@pytest.mark.asyncio
async def test_create_or_update_arc_invalid_rocrate(client_config: Config) -> None:
    """Test create_or_update_arc rejects structurally invalid RO-Crate JSON."""
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Invalid RO-Crate JSON"):
            await client.create_or_update_arc(rdi="test-rdi", arc={"id": "mock"})


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_sends_correct_headers(client_config: Config) -> None:
    """Test that the correct Content-Type and Accept headers are sent."""
    route = respx.post(f"{client_config.api_url}v3/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        await client.create_or_update_arc(rdi="test", arc=rocrate_dict())

    assert route.called
    req = route.calls.last.request
    assert req.headers["accept"] == "application/json"
    assert req.headers["content-type"] == "application/json"


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_serializes_rocrate_wire_aliases(client_config: Config) -> None:
    """ARC upload JSON must use @context and @graph, not Python field names."""
    route = respx.post(f"{client_config.api_url}v3/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        await client.create_or_update_arc(rdi="test-rdi", arc=rocrate_dict())

    body = json.loads(route.calls.last.request.content.decode())
    assert "@context" in body["arc"]
    assert "@graph" in body["arc"]
    assert "context" not in body["arc"]
    assert "graph" not in body["arc"]


@pytest.mark.asyncio
@respx.mock
async def test_submit_arc_in_harvest_serializes_rocrate_wire_aliases(client_config: Config) -> None:
    """Harvest ARC upload JSON must use @context and @graph wire aliases."""
    route = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        await client.submit_arc_in_harvest("harvest-456", arc=rocrate_dict())

    body = json.loads(route.calls.last.request.content.decode())
    assert "@context" in body["arc"]
    assert "@graph" in body["arc"]
    assert "context" not in body["arc"]
    assert "graph" not in body["arc"]


# ---------------------------------------------------------------------------
# Generic _get / error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_get_http_error(client_config: Config) -> None:
    """Test _get with an HTTP error."""
    respx.get(f"{client_config.api_url}v3/harvests/missing").mock(
        return_value=httpx.Response(http.HTTPStatus.NOT_FOUND)
    )
    client = ApiClient(client_config)
    with pytest.raises(ApiClientError, match="HTTP error 404"):
        await client._get("v3/harvests/missing")  # noqa: SLF001


@pytest.mark.asyncio
@respx.mock
async def test_get_network_error(client_config: Config) -> None:
    """Test _get with a network error."""
    client_config.retry_backoff_factor = 0.01
    respx.get(f"{client_config.api_url}v3/harvests").mock(side_effect=httpx.RequestError("Network error"))
    client = ApiClient(client_config)
    with pytest.raises(ApiClientError, match="Request failed after 3 retries: Network error"):
        await client._get("v3/harvests")  # noqa: SLF001


@pytest.mark.asyncio
@respx.mock
async def test_get_timeout_not_retried(client_config: Config) -> None:
    """Timeouts are not retried, even for GET requests."""
    route = respx.get(f"{client_config.api_url}v3/harvests").mock(side_effect=httpx.TimeoutException("Timed out"))
    client = ApiClient(client_config)
    with pytest.raises(ApiClientError, match="Request failed: Timed out"):
        await client._get("v3/harvests")  # noqa: SLF001
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_global_max_concurrency_limits_parallel_requests(client_config: Config) -> None:
    """ApiClient enforces a package-wide max number of concurrent API requests."""
    client_config.max_concurrency = 2

    in_flight = 0
    peak_in_flight = 0
    counter_lock = asyncio.Lock()

    async def slow_response(_: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak_in_flight
        async with counter_lock:
            in_flight += 1
            peak_in_flight = max(peak_in_flight, in_flight)
        await asyncio.sleep(0.02)
        async with counter_lock:
            in_flight -= 1
        return httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)

    route = respx.get(f"{client_config.api_url}v3/harvests/harvest-456").mock(side_effect=slow_response)

    async with ApiClient(client_config) as client:
        await asyncio.gather(*(client.get_harvest("harvest-456") for _ in range(6)))

    assert route.call_count == 6  # noqa: PLR2004
    assert peak_in_flight <= 2  # noqa: PLR2004


@pytest.mark.asyncio
@respx.mock
async def test_get_invalid_json_wrapped(client_config: Config) -> None:
    """Invalid JSON body is surfaced as ApiClientError."""
    respx.get(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, text="not-json")
    )
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Invalid JSON response from API"):
            await client.get_harvest("harvest-456")


# ---------------------------------------------------------------------------
# Harvest endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_harvest_success(client_config: Config) -> None:
    """Test successful harvest creation."""
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        harvest = await client.create_harvest(rdi="test-rdi", expected_datasets=10)
    assert isinstance(harvest, HarvestResult)
    assert harvest.harvest_id == "harvest-456"
    assert harvest.rdi == "test-rdi"


@pytest.mark.asyncio
@respx.mock
async def test_create_harvest_without_expected_datasets(client_config: Config) -> None:
    """Test harvest creation without expected_datasets."""
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        harvest = await client.create_harvest(rdi="test-rdi")
    assert isinstance(harvest, HarvestResult)


@pytest.mark.asyncio
@respx.mock
async def test_create_harvest_503_not_retried(client_config: Config) -> None:
    """POST create_harvest is not retried on transient server errors."""
    route = respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.SERVICE_UNAVAILABLE, text="Busy")
    )
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="HTTP error 503"):
            await client.create_harvest(rdi="test-rdi")
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_get_harvest(client_config: Config) -> None:
    """Test getting a single harvest run."""
    respx.get(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=HARVEST_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        harvest = await client.get_harvest("harvest-456")
    assert isinstance(harvest, HarvestResult)
    assert harvest.harvest_id == "harvest-456"


@pytest.mark.asyncio
@respx.mock
async def test_complete_harvest(client_config: Config) -> None:
    """Test completing a harvest run."""
    completed_response = {**HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )
    async with ApiClient(client_config) as client:
        harvest = await client.complete_harvest("harvest-456")
    assert isinstance(harvest, HarvestResult)
    assert harvest.status == "COMPLETED"
    assert harvest.completed_at is not None


@pytest.mark.asyncio
@respx.mock
async def test_cancel_harvest(client_config: Config) -> None:
    """Test cancelling a harvest run via PATCH."""
    cancelled_response = {**HARVEST_RESPONSE, "status": "CANCELLED"}
    route = respx.patch(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=cancelled_response)
    )
    async with ApiClient(client_config) as client:
        result = await client.cancel_harvest("harvest-456")
    assert route.called
    assert isinstance(result, HarvestResult)
    assert result.status == "CANCELLED"


@pytest.mark.asyncio
@respx.mock
async def test_fail_harvest(client_config: Config) -> None:
    """Test marking a harvest run as failed via PATCH."""
    failed_response = {**HARVEST_RESPONSE, "status": "FAILED"}
    route = respx.patch(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=failed_response)
    )
    async with ApiClient(client_config) as client:
        result = await client.fail_harvest("harvest-456")
    assert route.called
    assert isinstance(result, HarvestResult)
    assert result.status == "FAILED"


@pytest.mark.asyncio
@respx.mock
async def test_submit_arc_in_harvest_retries_on_connect_error(client_config: Config) -> None:
    """Harvest ARC POST is server-idempotent: ConnectError is retried then succeeds."""
    client_config.retry_backoff_factor = 0.01
    client_config.max_retries = 2
    route = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        side_effect=[
            httpx.ConnectError("Connection refused"),
            httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE),
        ]
    )
    async with ApiClient(client_config) as client:
        result = await client.submit_arc_in_harvest("harvest-456", arc=rocrate_dict())
    assert result.arc_id == ARC_RESPONSE["arc_id"]
    assert route.call_count == 2  # noqa: PLR2004


@pytest.mark.asyncio
@respx.mock
async def test_submit_arc_in_harvest(client_config: Config) -> None:
    """Test submitting an ARC within a harvest run."""
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        response = await client.submit_arc_in_harvest("harvest-456", arc=rocrate_dict())
    assert isinstance(response, ArcResult)
    assert response.arc_id == "arc-123"


@pytest.mark.asyncio
@respx.mock
async def test_submit_arc_in_harvest_invalid_response(client_config: Config) -> None:
    """Test submit_arc_in_harvest raises on unexpected JSON."""
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json={"bad": "response"})
    )
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Invalid ARC response"):
            await client.submit_arc_in_harvest("harvest-456", arc=rocrate_dict("mock"))


@pytest.mark.asyncio
async def test_submit_arc_in_harvest_invalid_rocrate(client_config: Config) -> None:
    """Test submit_arc_in_harvest rejects structurally invalid RO-Crate JSON."""
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Invalid RO-Crate JSON"):
            await client.submit_arc_in_harvest("harvest-456", arc={"id": "mock"})


@pytest.mark.asyncio
@respx.mock
async def test_submit_arc_in_harvest_with_json_string(client_config: Config) -> None:
    """Test submit_arc_in_harvest with a JSON string."""
    route = respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        response = await client.submit_arc_in_harvest("harvest-456", arc=json.dumps(rocrate_dict()))
    assert route.called
    assert isinstance(response, ArcResult)
    assert response.arc_id == "arc-123"


@pytest.mark.asyncio
async def test_submit_arc_in_harvest_with_invalid_json_string(client_config: Config) -> None:
    """Test submit_arc_in_harvest with an invalid JSON string."""
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Invalid JSON string provided for ARC"):
            await client.submit_arc_in_harvest("harvest-456", arc='{"@context":')
