"""Unit tests for the v2/arcs endpoint."""

import http
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from middleware.api.api import Api


@pytest.mark.unit
@pytest.mark.parametrize(
    "expected_http_status",
    [
        (http.HTTPStatus.ACCEPTED),
    ],
)
def test_create_or_update_arc_success(client: TestClient, cert: str, expected_http_status: int) -> None:
    """Test creating a new ARC via the /v2/arcs endpoint."""
    # Mock the Celery task
    mock_task = MagicMock()
    mock_task.id = "task-123"

    with pytest.MonkeyPatch.context() as mp:
        mock_process_arc = MagicMock()
        mock_process_arc.delay.return_value = mock_task
        mp.setattr("middleware.api.api.process_arc", mock_process_arc)

        r = client.post(
            "/v2/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"rdi": "rdi-1", "arc": {"dummy": "crate"}},
        )
        assert r.status_code == expected_http_status
        body = r.json()
        assert body["task_id"] == "task-123"
        assert body["status"] == "processing"


@pytest.mark.unit
def test_create_or_update_arc_validation_error(client: TestClient, cert: str) -> None:
    """Test validation error for /v2/arcs endpoint (missing 'arc')."""
    r = client.post(
        "/v2/arcs",
        headers={
            "ssl-client-cert": cert,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-1", "arcs": [{"dummy": "crate"}]},  # Wrong field name
    )
    assert r.status_code == http.HTTPStatus.UNPROCESSABLE_ENTITY

@pytest.mark.unit
def test_create_or_update_arc_rdi_not_known(client: TestClient, cert: str) -> None:
    """Test that requesting an unknown RDI returns 400."""
    r = client.post(
        "/v2/arcs",
        headers={
            "ssl-client-cert": cert,
            "ssl-client-verify": "SUCCESS",
            "content-type": "application/json",
            "accept": "application/json",
        },
        json={"rdi": "rdi-unknown", "arc": {"dummy": "crate"}},
    )
    assert r.status_code == http.HTTPStatus.BAD_REQUEST


@pytest.mark.unit
def test_get_task_status_v2(client: TestClient) -> None:
    """Test getting task status via /v2/tasks endpoint."""
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.ready.return_value = True
    mock_result.successful.return_value = True
    mock_result.failed.return_value = False
    # Mock return value from worker (singular)
    mock_result.result = {
        "client_id": "test",
        "message": "ok",
        "rdi": "rdi-1",
        "arc": {"id": "arc-1", "status": "created", "timestamp": "2024-01-01T00:00:00Z"},
    }

    with pytest.MonkeyPatch.context() as mp:
        mock_async_result = MagicMock(return_value=mock_result)
        mp.setattr("middleware.api.api.celery_app.AsyncResult", mock_async_result)

        r = client.get(
            "/v2/tasks/task-123",
            headers={"accept": "application/json"},
        )
        assert r.status_code == http.HTTPStatus.OK
        body = r.json()
        assert body["task_id"] == "task-123"
        assert body["status"] == "SUCCESS"
        assert body["result"]["message"] == "ok"
        assert body["result"]["arc"]["id"] == "arc-1"

