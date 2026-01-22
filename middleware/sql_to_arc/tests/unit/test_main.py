"""Tests for sql_to_arc main module."""

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg
import pytest

from middleware.sql_to_arc.main import (
    ProcessingStats,
    WorkerContext,
    fetch_all_investigations,
    fetch_assays_bulk,
    fetch_studies_bulk,
    parse_args,
    process_investigations,
    process_single_dataset,
)


class TestParseArgs:
    """Test suite for parse_args function."""

    def test_parse_args_default(self) -> None:
        """Test parse_args with default config."""
        with patch("sys.argv", ["prog"]):
            args = parse_args()
            assert args.config == Path("config.yaml")

    def test_parse_args_custom_config(self) -> None:
        """Test parse_args with custom config file."""
        with patch("sys.argv", ["prog", "-c", "/path/to/config.yaml"]):
            args = parse_args()
            assert args.config == Path("/path/to/config.yaml")

    def test_parse_args_long_form(self) -> None:
        """Test parse_args with long form --config."""
        with patch("sys.argv", ["prog", "--config", "/custom/config.yaml"]):
            args = parse_args()
            assert args.config == Path("/custom/config.yaml")

    def test_parse_args_ignores_unknown_args(self) -> None:
        """Test parse_args ignores pytest and other unknown arguments."""
        with patch("sys.argv", ["prog", "-c", "config.yaml", "-v", "--tb=short"]):
            args = parse_args()
            assert args.config == Path("config.yaml")


class TestFetchAllInvestigations:
    """Test suite for fetch_all_investigations function."""

    @pytest.mark.asyncio
    async def test_fetch_all_investigations_success(self) -> None:
        """Test successful fetch of all investigations."""
        mock_cursor = AsyncMock(spec=psycopg.AsyncCursor)
        test_data = [
            {"id": 1, "title": "Test 1", "description": "Desc 1", "submission_time": None, "release_time": None},
            {"id": 2, "title": "Test 2", "description": "Desc 2", "submission_time": None, "release_time": None},
        ]
        mock_cursor.fetchall.return_value = test_data

        result = await fetch_all_investigations(mock_cursor)

        assert result == test_data
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_all_investigations_empty(self) -> None:
        """Test fetch when no investigations exist."""
        mock_cursor = AsyncMock(spec=psycopg.AsyncCursor)
        mock_cursor.fetchall.return_value = []

        result = await fetch_all_investigations(mock_cursor)

        assert result == []


class TestFetchStudiesBulk:
    """Test suite for fetch_studies_bulk function."""

    @pytest.mark.asyncio
    async def test_fetch_studies_bulk_success(self) -> None:
        """Test successful bulk fetch of studies."""
        mock_cursor = AsyncMock(spec=psycopg.AsyncCursor)
        test_data = [
            {
                "id": 1,
                "investigation_id": 1,
                "title": "Study 1",
                "description": "Desc",
                "submission_time": None,
                "release_time": None,
            },
            {
                "id": 2,
                "investigation_id": 1,
                "title": "Study 2",
                "description": "Desc",
                "submission_time": None,
                "release_time": None,
            },
            {
                "id": 3,
                "investigation_id": 2,
                "title": "Study 3",
                "description": "Desc",
                "submission_time": None,
                "release_time": None,
            },
        ]
        mock_cursor.fetchall.return_value = test_data

        result = await fetch_studies_bulk(mock_cursor, [1, 2])

        assert len(result) == 2  # noqa: PLR2004
        assert len(result[1]) == 2  # noqa: PLR2004
        assert len(result[2]) == 1

    @pytest.mark.asyncio
    async def test_fetch_studies_bulk_empty_ids(self) -> None:
        """Test fetch with empty investigation IDs."""
        mock_cursor = AsyncMock(spec=psycopg.AsyncCursor)

        result = await fetch_studies_bulk(mock_cursor, [])

        assert result == {}
        mock_cursor.execute.assert_not_called()


class TestFetchAssaysBulk:
    """Test suite for fetch_assays_bulk function."""

    @pytest.mark.asyncio
    async def test_fetch_assays_bulk_success(self) -> None:
        """Test successful bulk fetch of assays."""
        mock_cursor = AsyncMock(spec=psycopg.AsyncCursor)
        test_data = [
            {"id": 1, "study_id": 1, "measurement_type": "Type1", "technology_type": "Tech1"},
            {"id": 2, "study_id": 1, "measurement_type": "Type2", "technology_type": "Tech2"},
            {"id": 3, "study_id": 2, "measurement_type": "Type3", "technology_type": "Tech3"},
        ]
        mock_cursor.fetchall.return_value = test_data

        result = await fetch_assays_bulk(mock_cursor, [1, 2])

        assert len(result) == 2  # noqa: PLR2004
        assert len(result[1]) == 2  # noqa: PLR2004
        assert len(result[2]) == 1

    @pytest.mark.asyncio
    async def test_fetch_assays_bulk_empty_ids(self) -> None:
        """Test fetch with empty study IDs."""
        mock_cursor = AsyncMock(spec=psycopg.AsyncCursor)

        result = await fetch_assays_bulk(mock_cursor, [])

        assert result == {}
        mock_cursor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_process_single_dataset_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful single dataset processing."""
    mock_client = AsyncMock()
    # Mock create_or_update_arc response
    mock_client.create_or_update_arc.return_value = MagicMock(arcs=[MagicMock(id="arc-1")])
    
    investigation = {"id": 1, "title": "Inv", "description": "Desc"}
    studies_by_investigation: dict[int, list[dict[str, Any]]] = {1: [{"id": 10}]}
    assays_by_study: dict[int, list[dict[str, Any]]] = {10: []}
    
    mock_executor = MagicMock()
    
    # Mock loop and executor behavior
    loop_future: asyncio.Future[MagicMock] = asyncio.Future()
    arc_object = MagicMock()
    arc_object.ToROCrateJsonString.return_value = '{"id": "arc-1", "Identifier": "1"}'
    loop_future.set_result(arc_object)
    
    # We need to mock serialization too (run_in_executor call 2)
    # The first call builds ARC (returns arc_object)
    # The second call serializes (returns string)
    
    # Let's simplify by using side_effect for run_in_executor
    async def side_effect(func: Any, *args: Any) -> Any:
        if func == arc_object.ToROCrateJsonString:
            return '{"id": "arc-1", "Identifier": "1"}'
        # Otherwise it's the build function
        return arc_object

    # But process_single_dataset calls `loop.run_in_executor(ctx.executor, ...)` for build
    # and `loop.run_in_executor(None, ...)` for serialization.
    # We need to mock the loop.
    
    loop_mock = MagicMock()
    # Configure run_in_executor to handle both calls
    # Call 1: build -> returns Future(arc_object)
    # Call 2: serialize -> returns Future(json_str)
    
    future1: asyncio.Future[MagicMock] = asyncio.Future()
    future1.set_result(arc_object)
    future2: asyncio.Future[str] = asyncio.Future()
    future2.set_result('{"id": "arc-1", "Identifier": "1"}')
    
    loop_mock.run_in_executor.side_effect = [future1, future2]
    
    monkeypatch.setattr("asyncio.get_event_loop", lambda: loop_mock)

    ctx = WorkerContext(
        client=mock_client,
        rdi="test_rdi",
        studies_by_investigation=studies_by_investigation,
        assays_by_study=assays_by_study,
        worker_id=1,
        total_workers=1,
        executor=mock_executor,
    )
    
    semaphore = asyncio.Semaphore(1)
    stats = ProcessingStats()
    
    await process_single_dataset(ctx, investigation, semaphore, stats)
    
    assert mock_client.create_or_update_arc.called
    # Check that parsed JSON was passed
    call_kwargs = mock_client.create_or_update_arc.call_args.kwargs
    assert call_kwargs["rdi"] == "test_rdi"
    assert call_kwargs["arc"] == {"id": "arc-1", "Identifier": "1"}
    assert stats.failed_datasets == 0


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_process_single_dataset_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test single dataset processing failure."""
    mock_client = AsyncMock()
    mock_executor = MagicMock()
    
    # Mock build failure (returns None)
    loop_future: asyncio.Future[None] = asyncio.Future()
    loop_future.set_result(None)
    
    loop_mock = MagicMock()
    loop_mock.run_in_executor.return_value = loop_future
    monkeypatch.setattr("asyncio.get_event_loop", lambda: loop_mock)

    ctx = WorkerContext(
        client=mock_client,
        rdi="test_rdi",
        studies_by_investigation={},
        assays_by_study={},
        worker_id=1,
        total_workers=1,
        executor=mock_executor,
    )
    
    semaphore = asyncio.Semaphore(1)
    stats = ProcessingStats()
    
    investigation = {"id": 1}
    await process_single_dataset(ctx, investigation, semaphore, stats)
    
    assert not mock_client.create_or_update_arc.called
    assert stats.failed_datasets == 1
    assert "1" in stats.failed_ids


@pytest.mark.asyncio
async def test_process_investigations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test full process_investigations flow."""
    mock_cursor = AsyncMock()
    mock_client = AsyncMock()
    mock_config = MagicMock(max_concurrent_arc_builds=2, rdi="test")

    # Mock fetchers
    async def mock_fetch_inv(*_args: Any) -> list[dict[str, Any]]:
        return [{"id": 1}, {"id": 2}, {"id": 3}]

    async def mock_fetch_studies(*_args: Any) -> dict[int, list[dict[str, Any]]]:
        return {1: [{"id": 10}], 2: [], 3: []}

    async def mock_fetch_assays(*_args: Any) -> dict[int, list[dict[str, Any]]]:
        return {10: []}

    monkeypatch.setattr("middleware.sql_to_arc.main.fetch_all_investigations", mock_fetch_inv)
    monkeypatch.setattr("middleware.sql_to_arc.main.fetch_studies_bulk", mock_fetch_studies)
    monkeypatch.setattr("middleware.sql_to_arc.main.fetch_assays_bulk", mock_fetch_assays)

    # Mock process_single_dataset to avoid checking the whole flow details here
    async def mock_process_single(_ctx: WorkerContext, _row: dict, _sem: asyncio.Semaphore, _stats: ProcessingStats) -> None:
         # Simulate success
         return

    monkeypatch.setattr("middleware.sql_to_arc.main.process_single_dataset", mock_process_single)

    stats = await process_investigations(mock_cursor, mock_client, mock_config)

    assert stats.found_datasets == 3  # noqa: PLR2004
