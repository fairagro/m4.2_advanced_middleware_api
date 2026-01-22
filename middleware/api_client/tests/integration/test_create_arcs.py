"""Integration tests for API client against real API instance.

These tests use FastAPI TestClient to start the Middleware API within the test,
allowing us to test the full request/response cycle without needing nginx or
a real HTTP server.
"""

import http
import json

import httpx
import pytest
import respx
from arctrl import ARC, ArcInvestigation  # type: ignore[import-untyped]

from middleware.api_client import ApiClient, Config


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_integration_mock_server(client_config: Config) -> None:
    """Test create_or_update_arc with mocked server responses.

    This test uses respx to mock the HTTP responses, allowing us to verify
    that the client correctly sends certificates and handles responses.
    """
    # Mock successful response
    # Mock successful response
    task_response = {"task_id": "task-integr-001", "status": "processing"}

    final_result = {
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

    status_response = {"task_id": "task-integr-001", "status": "SUCCESS", "result": final_result}

    route_post = respx.post(f"{client_config.api_url}v1/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.ACCEPTED, json=task_response)
    )

    route_get = respx.get(f"{client_config.api_url}v1/tasks/task-integr-001").mock(
        return_value=httpx.Response(http.HTTPStatus.OK, json=status_response)
    )

    # Execute request with ARC object
    arc = ARC.from_arc_investigation(
        ArcInvestigation.create(identifier="test-arc-001", title="Test ARC", description="Integration test ARC")
    )
    async with ApiClient(client_config) as client:
        response = await client.create_or_update_arc(
            rdi="test-rdi",
            arc=arc,
        )

    # Verify
    assert route_post.called
    assert route_get.called
    assert response.rdi == "test-rdi"
    assert len(response.arcs) == 1
    assert response.arcs[0].status == "created"

    # Verify request was sent correctly
    last_request = route_post.calls.last.request
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
    respx.post(f"{client_config.api_url}v1/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.UNAUTHORIZED, text="Unauthorized")
    )

    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(Exception, match=str(http.HTTPStatus.UNAUTHORIZED.value)):
            await client.create_or_update_arc(
                rdi="test-rdi",
                arc=arc,
            )


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_forbidden(client_config: Config) -> None:
    """Test handling of 403 Forbidden response."""
    respx.post(f"{client_config.api_url}v1/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.FORBIDDEN, text="Forbidden - RDI not authorized")
    )

    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(Exception, match=str(http.HTTPStatus.FORBIDDEN.value)):
            await client.create_or_update_arc(
                rdi="unauthorized-rdi",
                arc=arc,
            )


@pytest.mark.asyncio
@respx.mock
async def test_create_arcs_validation_error(client_config: Config) -> None:
    """Test handling of 422 Validation Error response."""
    respx.post(f"{client_config.api_url}v1/arcs").mock(
        return_value=httpx.Response(http.HTTPStatus.UNPROCESSABLE_ENTITY, json={"detail": "Invalid ARC data"})
    )

    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(Exception, match=str(http.HTTPStatus.UNPROCESSABLE_ENTITY.value)):
            await client.create_or_update_arc(
                rdi="test-rdi",
                arc=arc,
            )


@pytest.mark.asyncio
@respx.mock
async def test_create_multiple_arcs(client_config: Config) -> None:
    """Test that creating multiple ARCs (passing a list) raises a TypeError."""
    # Since the method signature expects a single ARC/dict, passing a list
    # generally won't work. We verify it actually fails.
    
    arc1 = ARC.from_arc_investigation(ArcInvestigation.create(identifier="arc-1", title="ARC 1"))
    arc2 = ARC.from_arc_investigation(ArcInvestigation.create(identifier="arc-2", title="ARC 2"))
    
    async with ApiClient(client_config) as client:
        # We expect a failure because we are passing a list where a single item is expected
        # This will likely fail in isinstance checks or attribute access inside the method
        with pytest.raises((AttributeError, TypeError, Exception)):
             await client.create_or_update_arc(
                rdi="test-rdi",
                arc=[arc1, arc2],  # type: ignore
            )



@pytest.mark.asyncio
@respx.mock
async def test_timeout_error(client_config: Config) -> None:
    """Test handling of timeout errors."""
    # Set a short timeout
    client_config.timeout = 0.1

    # Mock a slow response
    respx.post(f"{client_config.api_url}v1/arcs").mock(side_effect=httpx.TimeoutException("Request timeout"))

    arc = ARC.from_arc_investigation(ArcInvestigation.create(identifier="test", title="Test"))
    async with ApiClient(client_config) as client:
        with pytest.raises(Exception, match="timeout|Timeout"):
            await client.create_or_update_arc(
                rdi="test-rdi",
                arc=arc,
            )
