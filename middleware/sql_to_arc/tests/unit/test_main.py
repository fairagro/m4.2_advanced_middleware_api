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
    process_worker_investigations,
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
async def test_process_worker_investigations_empty() -> None:
    """Test worker investigations processing with empty list returns early."""
    mock_client = AsyncMock()
    investigations: list[dict[str, Any]] = []
    mock_executor = MagicMock()

    ctx = WorkerContext(
        client=mock_client,
        rdi="test_rdi",
        studies_by_investigation={},  # studies_by_investigation
        assays_by_study={},  # assays_by_study
        batch_size=2,
        worker_id=1,
        total_workers=1,
        executor=mock_executor,
    )
    await process_worker_investigations(ctx, investigations)
    mock_client.create_or_update_arcs.assert_not_called()


@pytest.mark.asyncio
async def test_process_worker_investigations_builds_and_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    """process_worker_investigations should build ARCs via executor and upload them."""
    mock_client = AsyncMock()
    mock_client.create_or_update_arcs.return_value = MagicMock(arcs=[1])

    investigations = [
        {"id": 1, "title": "Inv", "description": "Desc", "submission_time": None, "release_time": None},
    ]
    studies_by_investigation = {
        1: [
            {
                "id": 10,
                "investigation_id": 1,
                "title": "Study",
                "description": "Desc",
                "submission_time": None,
                "release_time": None,
            }
        ]
    }
    assays_by_study = {10: [{"id": 100, "study_id": 10, "measurement_type": "Type", "technology_type": "Tech"}]}

    # Mock the loop.run_in_executor to return an ARC directly
    loop_future: asyncio.Future[MagicMock] = asyncio.Future()
    arc_object = MagicMock(name="ARCObject")
    loop_future.set_result(arc_object)

    loop_mock = MagicMock()
    loop_mock.run_in_executor.return_value = loop_future
    monkeypatch.setattr("asyncio.get_event_loop", MagicMock(return_value=loop_mock))

    executor = MagicMock(spec=concurrent.futures.ProcessPoolExecutor)

    ctx = WorkerContext(
        client=mock_client,
        rdi="test_rdi",
        studies_by_investigation=studies_by_investigation,
        assays_by_study=assays_by_study,
        batch_size=2,
        worker_id=1,
        total_workers=1,
        executor=executor,
    )
    await process_worker_investigations(ctx, investigations)

    loop_mock.run_in_executor.assert_called_once()
    mock_client.create_or_update_arcs.assert_called_once_with(rdi="test_rdi", arcs=[arc_object])


@pytest.mark.asyncio
async def test_process_investigations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test full process_investigations flow."""
    mock_cursor = AsyncMock()
    mock_client = AsyncMock()
    mock_config = MagicMock(max_concurrent_arc_builds=2, batch_size=2, rdi="test")

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

    # Mock process_worker_investigations
    async def mock_process_worker_inv(_ctx: WorkerContext, invs: list[dict[str, Any]]) -> ProcessingStats:
        return ProcessingStats(found_datasets=len(invs))

    monkeypatch.setattr("middleware.sql_to_arc.main.process_worker_investigations", mock_process_worker_inv)

    stats = await process_investigations(mock_cursor, mock_client, mock_config)

    assert stats.found_datasets == 3  # noqa: PLR2004
