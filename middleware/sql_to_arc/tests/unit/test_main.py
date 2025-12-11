"""Tests for sql_to_arc main module."""

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg
import pytest

from middleware.sql_to_arc.main import (
    fetch_all_investigations,
    fetch_assays_bulk,
    fetch_studies_bulk,
    parse_args,
    process_batch,
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

        assert len(result) == 2
        assert len(result[1]) == 2
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

        assert len(result) == 2
        assert len(result[1]) == 2
        assert len(result[2]) == 1

    @pytest.mark.asyncio
    async def test_fetch_assays_bulk_empty_ids(self) -> None:
        """Test fetch with empty study IDs."""
        mock_cursor = AsyncMock(spec=psycopg.AsyncCursor)

        result = await fetch_assays_bulk(mock_cursor, [])

        assert result == {}
        mock_cursor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_process_batch_empty() -> None:
    """Test batch processing with empty batch returns early."""
    mock_client = AsyncMock()
    batch: list[dict[str, Any]] = []
    mock_executor = MagicMock()

    await process_batch(
        mock_client,
        batch,
        "test_rdi",
        {},  # studies_by_investigation
        {},  # assays_by_study
        executor=mock_executor,
    )
    mock_client.create_or_update_arcs.assert_not_called()


@pytest.mark.asyncio
async def test_process_batch_builds_and_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    """process_batch should build ARCs via executor and upload them."""
    mock_client = AsyncMock()
    mock_client.create_or_update_arcs.return_value = MagicMock(arcs=[1])

    batch = [
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

    loop_future: asyncio.Future[MagicMock] = asyncio.Future()
    arc_investigation = MagicMock(name="ArcInvestigation")
    loop_future.set_result(arc_investigation)

    loop_mock = MagicMock()
    loop_mock.run_in_executor.return_value = loop_future
    monkeypatch.setattr("asyncio.get_running_loop", MagicMock(return_value=loop_mock))

    with patch("middleware.sql_to_arc.main.ARC") as mock_arc_class:
        arc_wrapper = MagicMock(name="ARCObject")
        mock_arc_class.from_arc_investigation.return_value = arc_wrapper

        executor = MagicMock(spec=concurrent.futures.ProcessPoolExecutor)

        await process_batch(
            mock_client,
            batch,
            "test_rdi",
            studies_by_investigation,
            assays_by_study,
            executor=executor,
            batch_num=1,
            total_batches=1,
        )

    loop_mock.run_in_executor.assert_called_once()
    mock_arc_class.from_arc_investigation.assert_called_once_with(arc_investigation)
    mock_client.create_or_update_arcs.assert_called_once_with(rdi="test_rdi", arcs=[arc_wrapper])
