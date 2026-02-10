"""
Unit tests for retry logic in the ApiClient.

This module contains tests to verify the retry behavior of the ApiClient
when handling HTTP 503 responses and network errors.
"""

import httpx
import pytest
import respx

from middleware.api_client import ApiClient, ApiClientError, Config


@pytest.mark.asyncio
async def test_client_retries_on_503_then_success() -> None:
    """Test that the client retries on 503 and eventually succeeds."""
    config = Config(
        api_url="http://api.local/",
        max_retries=2,
        retry_backoff_factor=0.1,  # small delay for tests
    )

    async with ApiClient(config) as client:
        with respx.mock:
            # First two calls return 503, third succeeds
            route = respx.get("http://api.local/v2/tasks/123")
            route.side_effect = [
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(
                    200, json={"status": "SUCCESS", "result": {"id": "arc1", "status": "CREATED", "timestamp": "now"}}
                ),
            ]

            result = await client._get("v2/tasks/123")  # pylint: disable=protected-access
            assert result["status"] == "SUCCESS"
            max_retries_plus_one = config.max_retries + 1
            assert route.call_count == max_retries_plus_one


@pytest.mark.asyncio
async def test_client_fails_after_max_retries() -> None:
    """Test that the client fails after exceeding max retries."""
    config = Config(api_url="http://api.local/", max_retries=2, retry_backoff_factor=0.1)
    max_retries_plus_one = config.max_retries + 1  # Named constant for clarity

    async with ApiClient(config) as client:
        with respx.mock:
            route = respx.get("http://api.local/v2/tasks/123")
            route.return_value = httpx.Response(503)

            with pytest.raises(ApiClientError, match="Request failed after 2 retries"):
                await client._get("v2/tasks/123")  # pylint: disable=protected-access

            assert route.call_count == max_retries_plus_one


@pytest.mark.asyncio
async def test_client_retries_on_network_error() -> None:
    """Test that the client retries on network errors."""
    config = Config(api_url="http://api.local/", max_retries=1, retry_backoff_factor=0.1)
    max_retries_plus_one = config.max_retries + 1  # Named constant for clarity

    async with ApiClient(config) as client:
        with respx.mock:
            route = respx.get("http://api.local/v2/tasks/123")
            route.side_effect = [
                httpx.ConnectError("Connection failed"),
                httpx.Response(
                    200, json={"status": "SUCCESS", "result": {"id": "arc1", "status": "CREATED", "timestamp": "now"}}
                ),
            ]

            result = await client._get("v2/tasks/123")  # pylint: disable=protected-access
            assert result["status"] == "SUCCESS"
            assert route.call_count == max_retries_plus_one
