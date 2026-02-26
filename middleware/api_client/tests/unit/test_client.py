"""Unit tests for the ApiClient class (v3 API)."""

import http
import ssl
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]

from middleware.api_client import ApiClient, ApiClientError, ArcResult, Config, HarvestResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ARC_RESPONSE = {
    "client_id": "test-client",
    "message": "ARC processed successfully",
    "arc_id": "arc-123",
    "status": "created",
    "metadata": {
        "arc_hash": "abc123",
        "status": "ACTIVE",
        "first_seen": "2024-01-01T00:00:00Z",
        "last_seen": "2024-01-01T00:00:00Z",
    },
    "events": [],
}

_HARVEST_RESPONSE: dict[str, str | None | dict] = {
    "client_id": "test-client",
    "message": "Harvest created",
    "harvest_id": "harvest-456",
    "rdi": "test-rdi",
    "status": "RUNNING",
    "started_at": "2024-01-01T00:00:00Z",
    "completed_at": None,
    "statistics": {},
}


@pytest.fixture
def client_config(test_config_dict: dict) -> Config:
    """Create a Config instance for testing."""
    return Config.from_data(test_config_dict)


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
        return_value=httpx.Response(http.HTTPStatus.OK, json=_ARC_RESPONSE)
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
        return_value=httpx.Response(http.HTTPStatus.OK, json=_ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        response = await client.create_or_update_arc(rdi="test-rdi", arc={"id": "mock-arc"})
    assert isinstance(response, ArcResult)


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
async def test_create_or_update_arc_network_error(client_config: Config) -> None:
    """Test create_or_update_arc with a network error."""
    client_config.retry_backoff_factor = 0.01
    respx.post(f"{client_config.api_url}v3/arcs").mock(side_effect=httpx.ConnectError("Connection refused"))
    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Request failed after 3 retries"):
            await client.create_or_update_arc(rdi="test-rdi", arc=arc)


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_invalid_response(client_config: Config) -> None:
    """Test create_or_update_arc raises when the server returns unexpected JSON."""
    respx.post(f"{client_config.api_url}v3/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json={"unexpected": "data"})
    )
    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="Invalid ARC response"):
            await client.create_or_update_arc(rdi="test-rdi", arc={"id": "mock"})


@pytest.mark.asyncio
@respx.mock
async def test_create_or_update_arc_sends_correct_headers(client_config: Config) -> None:
    """Test that the correct Content-Type and Accept headers are sent."""
    route = respx.post(f"{client_config.api_url}v3/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        await client.create_or_update_arc(rdi="test", arc={"id": "mock-arc"})

    assert route.called
    req = route.calls.last.request
    assert req.headers["accept"] == "application/json"
    assert req.headers["content-type"] == "application/json"


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


# ---------------------------------------------------------------------------
# Harvest endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_harvest_success(client_config: Config) -> None:
    """Test successful harvest creation."""
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_HARVEST_RESPONSE)
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
        return_value=httpx.Response(http.HTTPStatus.OK, json=_HARVEST_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        harvest = await client.create_harvest(rdi="test-rdi")
    assert isinstance(harvest, HarvestResult)


@pytest.mark.asyncio
@respx.mock
async def test_list_harvests(client_config: Config) -> None:
    """Test listing harvest runs."""
    respx.get(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=[_HARVEST_RESPONSE, _HARVEST_RESPONSE])
    )
    async with ApiClient(client_config) as client:
        harvests = await client.list_harvests()
    assert len(harvests) == 2  # noqa: PLR2004
    assert all(isinstance(h, HarvestResult) for h in harvests)


@pytest.mark.asyncio
@respx.mock
async def test_list_harvests_with_rdi_filter(client_config: Config) -> None:
    """Test listing harvest runs filtered by RDI."""
    route = respx.get(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=[_HARVEST_RESPONSE])
    )
    async with ApiClient(client_config) as client:
        await client.list_harvests(rdi="test-rdi")
    assert "rdi=test-rdi" in str(route.calls.last.request.url)


@pytest.mark.asyncio
@respx.mock
async def test_get_harvest(client_config: Config) -> None:
    """Test getting a single harvest run."""
    respx.get(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_HARVEST_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        harvest = await client.get_harvest("harvest-456")
    assert isinstance(harvest, HarvestResult)
    assert harvest.harvest_id == "harvest-456"


@pytest.mark.asyncio
@respx.mock
async def test_complete_harvest(client_config: Config) -> None:
    """Test completing a harvest run."""
    completed_response = {**_HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
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
    """Test cancelling a harvest run."""
    route = respx.delete(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.NO_CONTENT)
    )
    async with ApiClient(client_config) as client:
        await client.cancel_harvest("harvest-456")
    assert route.called
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_submit_arc_in_harvest(client_config: Config) -> None:
    """Test submitting an ARC within a harvest run."""
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_ARC_RESPONSE)
    )
    async with ApiClient(client_config) as client:
        response = await client.submit_arc_in_harvest("harvest-456", arc={"id": "mock-arc"})
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
            await client.submit_arc_in_harvest("harvest-456", arc={"id": "mock"})


# ---------------------------------------------------------------------------
# harvest_arcs
# ---------------------------------------------------------------------------


async def _arc_gen(*arcs: "dict[str, Any]") -> AsyncGenerator["dict[str, Any]", None]:
    """Yield the provided arc dicts as an async generator."""
    for arc in arcs:
        yield arc


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_success(client_config: Config) -> None:
    """harvest_arcs creates a harvest, submits all ARCs, then completes it."""
    completed_response = {**_HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_ARC_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    arcs = _arc_gen({"id": "arc-1"}, {"id": "arc-2"}, {"id": "arc-3"})
    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs("test-rdi", arcs, expected_datasets=3)

    assert isinstance(result, HarvestResult)
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_empty_generator(client_config: Config) -> None:
    """harvest_arcs with an empty generator creates and immediately completes the harvest."""
    completed_response = {**_HARVEST_RESPONSE, "status": "COMPLETED", "completed_at": "2024-01-01T01:00:00Z"}
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/complete").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=completed_response)
    )

    async with ApiClient(client_config) as client:
        result = await client.harvest_arcs("test-rdi", _arc_gen())

    assert isinstance(result, HarvestResult)
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_cancels_on_error(client_config: Config) -> None:
    """harvest_arcs cancels the harvest when ARC submission fails."""
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.INTERNAL_SERVER_ERROR, text="server error")
    )
    cancel_route = respx.delete(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.NO_CONTENT)
    )

    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError):
            await client.harvest_arcs("test-rdi", _arc_gen({"id": "arc-1"}), cancel_on_error=True)

    assert cancel_route.called


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_no_cancel_on_error(client_config: Config) -> None:
    """harvest_arcs does NOT cancel the harvest when cancel_on_error=False."""
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.INTERNAL_SERVER_ERROR, text="server error")
    )
    cancel_route = respx.delete(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.NO_CONTENT)
    )

    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError):
            await client.harvest_arcs("test-rdi", _arc_gen({"id": "arc-1"}), cancel_on_error=False)

    assert not cancel_route.called


@pytest.mark.asyncio
@respx.mock
async def test_harvest_arcs_cancel_failure_does_not_mask_original_error(client_config: Config) -> None:
    """If cancel itself raises, the original submission error is still propagated."""
    respx.post(f"{client_config.api_url}v3/harvests").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=_HARVEST_RESPONSE)
    )
    respx.post(f"{client_config.api_url}v3/harvests/harvest-456/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.INTERNAL_SERVER_ERROR, text="arc error")
    )
    # Also make the cancel fail
    respx.delete(f"{client_config.api_url}v3/harvests/harvest-456").mock(
        return_value=httpx.Response(http.HTTPStatus.INTERNAL_SERVER_ERROR, text="cancel error")
    )

    async with ApiClient(client_config) as client:
        with pytest.raises(ApiClientError, match="HTTP error 500"):
            await client.harvest_arcs("test-rdi", _arc_gen({"id": "arc-1"}))
