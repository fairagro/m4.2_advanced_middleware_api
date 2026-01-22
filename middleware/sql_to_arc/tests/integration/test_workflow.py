"""Integration tests for the SQL-to-ARC workflow."""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from middleware.api_client import ApiClient
from middleware.shared.api_models.models import CreateOrUpdateArcsResponse
from middleware.shared.config.config_base import OtelConfig
from middleware.sql_to_arc.main import WorkerContext, main, process_worker_investigations


@pytest.fixture
def mock_db_cursor() -> AsyncMock:
    """Mock database cursor."""
    cursor = AsyncMock()
    # Setup default behavior for fetchall/aiter
    cursor.fetchall.return_value = []
    cursor.__aiter__.return_value = []
    return cursor


@pytest.fixture
def mock_db_connection(mock_db_cursor: AsyncMock) -> AsyncMock:
    """Mock database connection."""
    conn = AsyncMock()
    # conn.cursor is synchronous, returns an async context manager
    conn.cursor = MagicMock()
    conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_db_cursor)
    conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Mock API client."""
    client = AsyncMock(spec=ApiClient)
    client.create_or_update_arcs.return_value = CreateOrUpdateArcsResponse(
        client_id="test",
        message="success",
        rdi="test",
        arcs=[],
    )
    return client


@pytest.mark.asyncio
async def test_process_worker_investigations(mock_api_client: AsyncMock) -> None:
    """Test worker investigations processing."""
    investigation_rows: list[dict[str, Any]] = [
        {"identifier": 1, "title": "Test 1", "description": "Desc 1", "submission_time": None, "release_time": None},
        {"identifier": 2, "title": "Test 2", "description": "Desc 2", "submission_time": None, "release_time": None},
    ]
    studies_by_investigation: dict[str, list[dict[str, Any]]] = {"1": [], "2": []}
    assays_by_study: dict[str, list[dict[str, Any]]] = {}

    mp_context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=5, mp_context=mp_context) as executor:
        ctx = WorkerContext(
            client=mock_api_client,
            rdi="edaphobase",
            studies_by_inv=studies_by_investigation,
            assays_by_inv=assays_by_study,
            contacts_by_inv={},
            pubs_by_inv={},
            anns_by_inv={},
            worker_id=1,
            total_workers=1,
            executor=executor,
        )
        await process_worker_investigations(ctx, investigation_rows)

    assert mock_api_client.create_or_update_arcs.called
    # There should be two calls, each with one ARC (since batch size is always 1)
    assert mock_api_client.create_or_update_arcs.call_count == 2  # noqa: PLR2004
    for call in mock_api_client.create_or_update_arcs.call_args_list:
        assert call.kwargs["rdi"] == "edaphobase"
        assert len(call.kwargs["arcs"]) == 1


@pytest.mark.asyncio
# TODO: fix this test. Neither ChatGPT 4.1 nor me is able to.
async def test_main_workflow(
    mocker: MagicMock,
    mock_db_connection: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test the main workflow with mocked DB and API."""
    # Patch Database to prevent real DB operations and ensure to_jsonld returns valid JSON
    mock_db_instance = MagicMock()
    mock_db_instance.to_jsonld.return_value = "{}"
    # Patch bulk fetch methods to return test data
    mock_db_instance.fetch_investigations_bulk.return_value = [
        {"identifier": 1, "title": "Inv 1", "description": "Desc 1", "submission_time": None, "release_time": None},
        {"identifier": 2, "title": "Inv 2", "description": "Desc 2", "submission_time": None, "release_time": None},
    ]
    mock_db_instance.fetch_studies_bulk.return_value = [
        {
            "id": 10,
            "investigation_id": 1,
            "title": "Study 1",
            "description": "Desc S1",
            "submission_time": None,
            "release_time": None,
        },
        {
            "id": 11,
            "investigation_id": 2,
            "title": "Study 2",
            "description": "Desc S2",
            "submission_time": None,
            "release_time": None,
        },
    ]
    mock_db_instance.fetch_assays_bulk.return_value = [
        {"id": 100, "study_id": 10},
        {"id": 101, "study_id": 11},
    ]
    mocker.patch(
        "middleware.sql_to_arc.main.Database",
        return_value=mock_db_instance,
    )
    # Prevent real engine creation and ValueError by mocking create_async_engine
    mocker.patch(
        "sqlalchemy.ext.asyncio.create_async_engine",
        return_value=MagicMock(),
    )
    mocker.patch(
        "sqlalchemy.ext.asyncio.AsyncSession",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_db_connection)),
    )

    # Mock ApiClient context manager
    mocker.patch(
        "middleware.sql_to_arc.main.ApiClient",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_api_client)),
    )

    # Mock ConfigWrapper and Config
    mock_config = MagicMock()
    mock_config.db_name = "test_db"
    mock_config.db_user = "test_user"
    mock_config.db_password.get_secret_value.return_value = "test_password"
    mock_config.db_host = "localhost"
    mock_config.db_port = 5432
    mock_config.rdi = "edaphobase"
    mock_config.max_concurrent_arc_builds = 5
    mock_config.api_client = MagicMock()
    mock_config.log_level = "INFO"
    mock_config.otel = OtelConfig(endpoint=None, log_console_spans=False, log_level="INFO")
    # Add mock connection_string with get_secret_value
    mock_connection_string = MagicMock()
    mock_connection_string.get_secret_value.return_value = "sqlite+aiosqlite:///:memory:"
    mock_config.connection_string = mock_connection_string

    mock_wrapper = MagicMock()
    mocker.patch(
        "middleware.sql_to_arc.main.ConfigWrapper.from_yaml_file",
        return_value=mock_wrapper,
    )
    mocker.patch(
        "middleware.sql_to_arc.main.Config.from_config_wrapper",
        return_value=mock_config,
    )

    # Mock configure_logging to avoid log config issues
    mocker.patch("middleware.sql_to_arc.main.configure_logging")

    # Run main
    await main()

    # Verify interactions
    # Should have executed DB queries via SQLAlchemy session

    # Should have uploaded ARCs (2 investigations distributed across workers)
    # With max_concurrent_arc_builds=5, both investigations
    # will be assigned to worker 1 and uploaded in a single batch
    assert mock_api_client.create_or_update_arcs.called

    # The new architecture may split into multiple batches depending on worker assignment
    # Collect all uploaded ARCs from all calls
    all_arcs = []
    for call in mock_api_client.create_or_update_arcs.call_args_list:
        all_arcs.extend(call.kwargs["arcs"])

    # Should have uploaded 2 ARCs in total
    assert len(all_arcs) == 2  # noqa: PLR2004

    # Verify content of uploaded ARCs
    identifiers = {arc.Identifier for arc in all_arcs}
    assert identifiers == {"1", "2"}
