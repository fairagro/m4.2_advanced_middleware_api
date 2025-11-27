"""Integration tests for the SQL-to-ARC workflow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from arctrl import ArcInvestigation  # type: ignore[import-untyped]

from middleware.api_client import ApiClient
from middleware.shared.api_models.models import CreateOrUpdateArcsResponse
from middleware.sql_to_arc.main import main, process_batch


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
async def test_process_batch(mock_api_client: AsyncMock) -> None:
    """Test batch processing."""
    batch = [
        ArcInvestigation.create(identifier="1", title="Test 1"),
        ArcInvestigation.create(identifier="2", title="Test 2"),
    ]

    await process_batch(mock_api_client, batch)

    assert mock_api_client.create_or_update_arcs.called
    call_args = mock_api_client.create_or_update_arcs.call_args
    # Check keyword arguments
    assert call_args.kwargs["rdi"] == "edaphobase"
    assert len(call_args.kwargs["arcs"]) == 2
    assert call_args.kwargs["arcs"][0].Identifier == "1"
    assert call_args.kwargs["arcs"][1].Identifier == "2"


@pytest.mark.asyncio
async def test_main_workflow(
    mocker: MagicMock,
    mock_db_connection: AsyncMock,
    mock_db_cursor: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test the main workflow with mocked DB and API."""
    # Mock psycopg connection
    mocker.patch(
        "psycopg.AsyncConnection.connect",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_db_connection)),
    )

    # Mock ApiClient context manager
    mocker.patch(
        "middleware.sql_to_arc.main.ApiClient",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_api_client)),
    )

    # Setup DB data
    # 1. Investigations
    investigations = [
        {"id": 1, "title": "Inv 1", "description": "Desc 1", "submission_time": None, "release_time": None},
        {"id": 2, "title": "Inv 2", "description": "Desc 2", "submission_time": None, "release_time": None},
    ]

    # 2. Studies (for Inv 1)
    studies_1 = [
        {
            "id": 10,
            "investigation_id": 1,
            "title": "Study 1",
            "description": "Desc S1",
            "submission_time": None,
            "release_time": None,
        },
    ]

    # 3. Assays (for Study 1)
    assays_1 = [
        {"id": 100, "study_id": 10, "measurement_type": "Metabolomics", "technology_type": "MS"},
    ]

    # Configure cursor behavior
    # The cursor is used in a loop for investigations, and then fetchall for studies/assays

    # Mocking __aiter__ for the main investigation loop
    mock_db_cursor.__aiter__.return_value = iter(investigations)

    # Mocking fetchall for studies and assays
    # We need to handle different queries.
    # This is a bit tricky with a single mock object for multiple queries.
    # We can use side_effect on execute to switch the return value of fetchall,
    # but fetchall is called AFTER execute.

    async def fetchall_side_effect() -> list[dict[str, Any]]:
        # Check the last executed query to decide what to return
        last_query = mock_db_cursor.execute.call_args[0][0]
        if 'FROM "ARC_Study"' in last_query:
            # Check investigation_id param
            inv_id = mock_db_cursor.execute.call_args[0][1][0]
            if inv_id == 1:
                return studies_1
            return []
        elif 'FROM "ARC_Assay"' in last_query:
            study_id = mock_db_cursor.execute.call_args[0][1][0]
            if study_id == 10:
                return assays_1
            return []
        return []

    mock_db_cursor.fetchall.side_effect = fetchall_side_effect

    # Run main
    await main()

    # Verify interactions
    # Should have connected to DB
    assert mock_db_connection.cursor.called

    # Should have executed investigation query
    assert mock_db_cursor.execute.call_count >= 1

    # Should have uploaded batch (2 investigations, default batch size is 10, so 1 upload)
    assert mock_api_client.create_or_update_arcs.called
    call_args = mock_api_client.create_or_update_arcs.call_args
    assert len(call_args.kwargs["arcs"]) == 2

    # Verify content of uploaded ARCs
    # Inv 1 should have 1 study with 1 assay
    # We can't easily check the internal structure of the dummy payload without parsing,
    # but we can check the IDs
    assert call_args.kwargs["arcs"][0].Identifier == "1"
    assert call_args.kwargs["arcs"][1].Identifier == "2"
