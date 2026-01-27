"""Integration tests for the SQL-to-ARC workflow."""

import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from middleware.api_client import ApiClient
from middleware.shared.api_models.models import CreateOrUpdateArcsResponse
from middleware.shared.config.config_base import OtelConfig
from middleware.sql_to_arc.main import DatasetContext, ProcessingStats, WorkerContext, main, process_single_dataset


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
    client.create_or_update_arc.return_value = CreateOrUpdateArcsResponse(
        client_id="test",
        message="success",
        rdi="test",
        arcs=[],
    )
    return client


@pytest.mark.asyncio
async def test_process_single_dataset(mock_api_client: AsyncMock) -> None:
    """Test single dataset processing."""
    investigation_rows: list[dict[str, Any]] = [
        {"id": 1, "title": "Test 1", "description": "Desc 1", "submission_time": None, "release_time": None},
        {"id": 2, "title": "Test 2", "description": "Desc 2", "submission_time": None, "release_time": None},
    ]
    studies_by_investigation: dict[int, list[dict[str, Any]]] = {1: [], 2: []}
    assays_by_study: dict[int, list[dict[str, Any]]] = {}

    mp_context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=5, mp_context=mp_context) as executor:
        ctx = WorkerContext(
            client=mock_api_client,
            rdi="edaphobase",
            executor=executor,
            max_studies=5000,
            max_assays=10000,
            arc_generation_timeout_minutes=60,
        )
        semaphore = asyncio.Semaphore(1)
        stats = ProcessingStats()

        for inv in investigation_rows:
            # Build a minimal DatasetContext as expected by process_single_dataset
            dataset_context = DatasetContext(
                investigation_row=inv,
                studies=studies_by_investigation.get(inv["id"], []),
                assays_by_study=assays_by_study,
            )
            # Call with correct arguments: ctx, dataset_context, semaphore, stats
            await process_single_dataset(ctx, dataset_context, semaphore, stats)

    assert mock_api_client.create_or_update_arc.called
    assert mock_api_client.create_or_update_arc.call_count == 2  # noqa: PLR2004
    for call in mock_api_client.create_or_update_arc.call_args_list:
        assert call.kwargs["rdi"] == "edaphobase"
        # Each call sends one ARC as dict or ARC object
        assert "arc" in call.kwargs


@pytest.fixture
def mock_main_config(mocker: MagicMock) -> MagicMock:
    """Mock configuration for main workflow."""
    config = MagicMock()
    config.db_name = "test_db"
    config.db_user = "test_user"
    config.db_password.get_secret_value.return_value = "test_password"
    config.db_host = "localhost"
    config.db_port = 5432
    config.rdi = "edaphobase"
    config.max_concurrent_arc_builds = 5
    config.max_concurrent_tasks = 10
    config.db_batch_size = 100
    config.api_client = MagicMock()
    config.log_level = "INFO"
    config.otel = OtelConfig(endpoint=None, log_console_spans=False, log_level="INFO")
    config.max_studies = 5000
    config.max_assays = 10000
    config.arc_generation_timeout_minutes = 60
    config.rdi_url = "https://example.com"  # Real string for JSON serialization

    mocker.patch("middleware.sql_to_arc.main.ConfigWrapper.from_yaml_file")
    mocker.patch("middleware.sql_to_arc.main.Config.from_config_wrapper", return_value=config)
    mocker.patch("middleware.sql_to_arc.main.configure_logging")
    mocker.patch("middleware.sql_to_arc.main.initialize_tracing", return_value=(MagicMock(), MagicMock()))
    return config


def _setup_cursor_side_effects(
    mock_db_cursor: AsyncMock, investigations: list[dict], studies: list[dict], assays: list[dict]
) -> AsyncMock:
    """Set up cursor behavior for bulk fetch strategy."""
    mock_detail_cursor = AsyncMock()
    mock_detail_cursor.fetchall.return_value = []
    mock_db_cursor.connection = MagicMock()
    mock_db_cursor.connection.cursor.return_value.__aenter__.return_value = mock_detail_cursor

    async def detail_fetchall_side_effect() -> list[dict[str, Any]]:
        if not mock_detail_cursor.execute.call_args:
            return []
        last_query = mock_detail_cursor.execute.call_args[0][0]
        if 'FROM "ARC_Study"' in last_query:
            return studies
        if 'FROM "ARC_Assay"' in last_query:
            return assays
        return []

    mock_detail_cursor.fetchall.side_effect = detail_fetchall_side_effect
    fetchmany_done: list[bool] = []

    async def fetchmany_side_effect(_size: int = 100) -> list[dict[str, Any]]:
        _ = _size
        last_query = mock_db_cursor.execute.call_args[0][0]
        if 'FROM "ARC_Investigation"' in last_query and not fetchmany_done:
            fetchmany_done.append(True)
            return investigations
        return []

    mock_db_cursor.fetchall.side_effect = AsyncMock(return_value=[])
    mock_db_cursor.fetchmany.side_effect = fetchmany_side_effect
    return mock_detail_cursor


@pytest.mark.asyncio
async def test_main_workflow(
    mocker: MagicMock,
    mock_db_connection: AsyncMock,
    mock_db_cursor: AsyncMock,
    mock_api_client: AsyncMock,
    mock_main_config: MagicMock,
) -> None:
    """Test the main workflow with mocked DB and API."""
    _ = mock_main_config
    mocker.patch(
        "psycopg.AsyncConnection.connect",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_db_connection)),
    )
    mocker.patch(
        "middleware.sql_to_arc.main.ApiClient",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_api_client)),
    )

    # Setup DB data
    invs = [
        {"id": 1, "title": "I1", "description": "D1", "submission_time": None, "release_time": None},
        {"id": 2, "title": "I2", "description": "D2", "submission_time": None, "release_time": None},
    ]
    sts = [
        {
            "id": 10,
            "investigation_id": 1,
            "title": "S1",
            "description": "D1",
            "submission_time": None,
            "release_time": None,
        },
        {
            "id": 11,
            "investigation_id": 2,
            "title": "S2",
            "description": "D2",
            "submission_time": None,
            "release_time": None,
        },
    ]
    ass = [{"id": 100, "study_id": 10}, {"id": 101, "study_id": 11}]

    # Configure cursor behavior using helper
    mock_detail_cursor = _setup_cursor_side_effects(mock_db_cursor, invs, sts, ass)

    await main()

    # Verify interactions
    assert mock_db_connection.cursor.called
    assert mock_db_cursor.execute.call_count == 1
    assert mock_detail_cursor.execute.call_count == 2  # noqa: PLR2004
    assert mock_api_client.create_or_update_arc.called

    all_arcs = [call.kwargs["arc"] for call in mock_api_client.create_or_update_arc.call_args_list]
    assert len(all_arcs) == 2  # noqa: PLR2004

    # Verify content of uploaded ARCs (Identifiers from invs list)
    identifiers = set()
    for arc in all_arcs:
        # Find the investigation node in @graph
        investigation_node = next(
            (node for node in arc.get("@graph", []) 
             if "Investigation" in node.get("additionalType", "")),
            None
        )
        if investigation_node:
            identifiers.add(investigation_node.get("identifier"))

    assert identifiers == {"1", "2"}
