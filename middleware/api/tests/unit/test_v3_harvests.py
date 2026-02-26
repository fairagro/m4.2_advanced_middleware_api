"""Unit tests for the v3/harvests endpoint."""

import http
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from middleware.api.api.fastapi_app import Api
from middleware.api.business_logic import InvalidJsonSemanticError
from middleware.api.document_store.harvest_document import HarvestDocument, HarvestStatistics
from middleware.shared.api_models import ArcOperationResult, ArcResponse, ArcStatus
from middleware.shared.api_models.common.models import HarvestStatus


@pytest.mark.unit
def test_create_harvest_success(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test starting a new harvest."""
    harvest_id = "harvest-123"

    with (
        patch.object(
            middleware_api.business_logic.harvest_manager, "create_harvest", new_callable=AsyncMock
        ) as mock_create,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
    ):
        mock_create.return_value = harvest_id
        mock_auth.return_value = ["rdi-1"]
        mock_get.return_value = HarvestDocument(
            doc_id="harvest-123",
            rdi="rdi-1",
            client_id="test-client-cn",
            status=HarvestStatus.RUNNING,
            started_at=datetime.now(UTC),
            statistics=HarvestStatistics(),  # Replace with an appropriate HarvestStatistics instance
        )

        r = client.post(
            "/v3/harvests",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"rdi": "rdi-1"},
        )

        assert r.status_code == http.HTTPStatus.OK
        body = r.json()
        assert body["harvest_id"] == harvest_id
        assert body["status"] == "RUNNING"


@pytest.mark.unit
def test_submit_arc_in_harvest_success(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test submitting an ARC within a harvest context."""
    harvest_id = "harvest-123"

    mock_harvest = HarvestDocument(
        doc_id=harvest_id,
        rdi="rdi-1",
        client_id="test-client-cn",
        status=HarvestStatus.RUNNING,
        started_at=datetime.now(UTC),
        statistics=HarvestStatistics(),  # Replace with an appropriate HarvestStatistics instance
    )

    mock_result = ArcOperationResult(
        client_id="test-client-cn",
        rdi="rdi-1",
        arc=ArcResponse(
            id="arc-123",
            status=ArcStatus.CREATED,
            timestamp="2024-01-01T00:00:00Z",
        ),
    )

    now = datetime.now(UTC)
    mock_metadata = MagicMock()
    mock_metadata.arc_hash = "fake-hash"
    mock_metadata.status = "ACTIVE"
    mock_metadata.first_seen = now
    mock_metadata.last_seen = now
    mock_metadata.events = []

    rocrate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "ARC-001"}],
    }

    with (
        patch.object(
            middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock
        ) as mock_get_harvest,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(middleware_api.business_logic, "create_or_update_arc", new_callable=AsyncMock) as mock_create_arc,
        patch.object(middleware_api.business_logic, "get_metadata", new_callable=AsyncMock) as mock_get_metadata,
    ):
        mock_get_harvest.return_value = mock_harvest
        mock_auth.return_value = ["rdi-1"]
        mock_create_arc.return_value = mock_result
        mock_get_metadata.return_value = mock_metadata

        r = client.post(
            f"/v3/harvests/{harvest_id}/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"arc": rocrate},
        )

        assert r.status_code == http.HTTPStatus.OK
        body = r.json()
        assert body["arc_id"] == "arc-123"
        # Check that harvest_id was passed if possible, but at least verify success
        mock_create_arc.assert_called_once()
        assert mock_create_arc.call_args[1]["harvest_id"] == harvest_id


# ---------------------------------------------------------------------------
# create_harvest — internal server error (get_harvest returns None after create)
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_create_harvest_internal_error(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test that create_harvest raises 500 when get_harvest returns None after creation."""
    with (
        patch.object(
            middleware_api.business_logic.harvest_manager, "create_harvest", new_callable=AsyncMock
        ) as mock_create,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
    ):
        mock_create.return_value = "harvest-xyz"
        mock_auth.return_value = ["rdi-1"]
        mock_get.return_value = None  # Simulate DB failure after creation

        r = client.post(
            "/v3/harvests",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"rdi": "rdi-1"},
        )

        assert r.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# list_harvests — all & with rdi filter
# ---------------------------------------------------------------------------
def _make_harvest_doc(
    harvest_id: str = "h-1",
    rdi: str = "rdi-1",
    status: HarvestStatus = HarvestStatus.RUNNING,
) -> HarvestDocument:
    return HarvestDocument(
        doc_id=harvest_id,
        rdi=rdi,
        client_id="test-cn",
        status=status,
        started_at=datetime.now(UTC),
        statistics=HarvestStatistics(),
    )


@pytest.mark.unit
def test_list_harvests_no_filter(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test listing all harvests without rdi filter."""
    harvests = [_make_harvest_doc("h-1"), _make_harvest_doc("h-2")]

    with patch.object(
        middleware_api.business_logic.harvest_manager, "list_harvests", new_callable=AsyncMock
    ) as mock_list:
        mock_list.return_value = harvests

        r = client.get(
            "/v3/harvests",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "accept": "application/json",
            },
        )

        assert r.status_code == http.HTTPStatus.OK
        assert len(r.json()) == 2  # noqa: PLR2004


@pytest.mark.unit
def test_list_harvests_with_rdi_filter(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test listing harvests filtered by rdi."""
    harvests = [_make_harvest_doc()]

    with (
        patch.object(
            middleware_api.business_logic.harvest_manager, "list_harvests", new_callable=AsyncMock
        ) as mock_list,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
    ):
        mock_list.return_value = harvests
        mock_auth.return_value = ["rdi-1"]

        r = client.get(
            "/v3/harvests?rdi=rdi-1",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "accept": "application/json",
            },
        )

        assert r.status_code == http.HTTPStatus.OK
        mock_list.assert_called_once_with("rdi-1")


# ---------------------------------------------------------------------------
# get_harvest
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_get_harvest_success(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test retrieving a harvest by id."""
    harvest = _make_harvest_doc()

    with (
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
    ):
        mock_get.return_value = harvest
        mock_auth.return_value = ["rdi-1"]

        r = client.get(
            "/v3/harvests/h-1",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "accept": "application/json",
            },
        )

        assert r.status_code == http.HTTPStatus.OK
        assert r.json()["harvest_id"] == "h-1"


@pytest.mark.unit
def test_get_harvest_not_found(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test 404 when harvest does not exist."""
    with patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        r = client.get(
            "/v3/harvests/no-such-harvest",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "accept": "application/json",
            },
        )

        assert r.status_code == http.HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# complete_harvest
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_complete_harvest_success(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test completing a harvest."""
    harvest = _make_harvest_doc(status=HarvestStatus.RUNNING)
    completed = _make_harvest_doc(status=HarvestStatus.COMPLETED)
    completed.completed_at = datetime.now(UTC)

    with (
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(
            middleware_api.business_logic.harvest_manager, "complete_harvest", new_callable=AsyncMock
        ) as mock_complete,
    ):
        mock_get.return_value = harvest
        mock_auth.return_value = ["rdi-1"]
        mock_complete.return_value = completed

        r = client.post(
            "/v3/harvests/h-1/complete",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "accept": "application/json",
            },
        )

        assert r.status_code == http.HTTPStatus.OK
        assert r.json()["status"] == "COMPLETED"


@pytest.mark.unit
def test_complete_harvest_not_found(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test 404 when completing a non-existent harvest."""
    with patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        r = client.post(
            "/v3/harvests/no-such/complete",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "accept": "application/json",
            },
        )

        assert r.status_code == http.HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# cancel_harvest
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_cancel_harvest_success(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test cancelling a harvest."""
    harvest = _make_harvest_doc()

    with (
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(
            middleware_api.business_logic.harvest_manager, "cancel_harvest", new_callable=AsyncMock
        ) as mock_cancel,
    ):
        mock_get.return_value = harvest
        mock_auth.return_value = ["rdi-1"]
        mock_cancel.return_value = None

        r = client.delete(
            "/v3/harvests/h-1",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
            },
        )

        assert r.status_code == http.HTTPStatus.NO_CONTENT


@pytest.mark.unit
def test_cancel_harvest_not_found(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test 404 when cancelling a non-existent harvest."""
    with patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        r = client.delete(
            "/v3/harvests/no-such",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
            },
        )

        assert r.status_code == http.HTTPStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# submit_arc_in_harvest — error paths
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_submit_arc_harvest_not_found(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test 404 when harvest does not exist during ARC submission."""
    rocrate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "ARC-001"}],
    }

    with patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        r = client.post(
            "/v3/harvests/no-such/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"arc": rocrate},
        )

        assert r.status_code == http.HTTPStatus.NOT_FOUND


@pytest.mark.unit
def test_submit_arc_metadata_not_found(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test 500 when metadata cannot be retrieved after ARC creation."""
    harvest = _make_harvest_doc()
    mock_result = ArcOperationResult(
        client_id="test-client-cn",
        rdi="rdi-1",
        arc=ArcResponse(id="arc-123", status=ArcStatus.CREATED, timestamp="2024-01-01T00:00:00Z"),
    )
    rocrate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "ARC-001"}],
    }

    with (
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(middleware_api.business_logic, "create_or_update_arc", new_callable=AsyncMock) as mock_create,
        patch.object(middleware_api.business_logic, "get_metadata", new_callable=AsyncMock) as mock_meta,
    ):
        mock_get.return_value = harvest
        mock_auth.return_value = ["rdi-1"]
        mock_create.return_value = mock_result
        mock_meta.return_value = None  # Simulate missing metadata

        r = client.post(
            "/v3/harvests/h-1/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"arc": rocrate},
        )

        assert r.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.unit
def test_submit_arc_invalid_json_semantic(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test 422 when arc JSON has semantic errors."""
    harvest = _make_harvest_doc()
    rocrate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "ARC-001"}],
    }

    with (
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(middleware_api.business_logic, "create_or_update_arc", new_callable=AsyncMock) as mock_create,
    ):
        mock_get.return_value = harvest
        mock_auth.return_value = ["rdi-1"]
        mock_create.side_effect = InvalidJsonSemanticError("bad arc")

        r = client.post(
            "/v3/harvests/h-1/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"arc": rocrate},
        )

        assert r.status_code == http.HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.unit
def test_submit_arc_generic_exception(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test 500 when an unexpected error occurs during ARC submission."""
    harvest = _make_harvest_doc()
    rocrate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "ARC-001"}],
    }

    with (
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(middleware_api.business_logic, "create_or_update_arc", new_callable=AsyncMock) as mock_create,
    ):
        mock_get.return_value = harvest
        mock_auth.return_value = ["rdi-1"]
        mock_create.side_effect = RuntimeError("unexpected")

        r = client.post(
            "/v3/harvests/h-1/arcs",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"arc": rocrate},
        )

        assert r.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# _map_harvest — completed_at branch
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_create_harvest_with_completed_at(client: TestClient, cert: str, middleware_api: Api) -> None:
    """Test that completed_at is correctly serialised in response."""
    harvest_id = "harvest-done"
    completed_doc = HarvestDocument(
        doc_id=harvest_id,
        rdi="rdi-1",
        client_id="test-client-cn",
        status=HarvestStatus.COMPLETED,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        statistics=HarvestStatistics(),
    )

    with (
        patch.object(
            middleware_api.business_logic.harvest_manager, "create_harvest", new_callable=AsyncMock
        ) as mock_create,
        patch.object(middleware_api.app.state.common_deps, "get_authorized_rdis", new_callable=AsyncMock) as mock_auth,
        patch.object(middleware_api.business_logic.harvest_manager, "get_harvest", new_callable=AsyncMock) as mock_get,
    ):
        mock_create.return_value = harvest_id
        mock_auth.return_value = ["rdi-1"]
        mock_get.return_value = completed_doc

        r = client.post(
            "/v3/harvests",
            headers={
                "ssl-client-cert": cert,
                "ssl-client-verify": "SUCCESS",
                "content-type": "application/json",
                "accept": "application/json",
            },
            json={"rdi": "rdi-1"},
        )

        assert r.status_code == http.HTTPStatus.OK
        body = r.json()
        assert body["completed_at"] is not None
