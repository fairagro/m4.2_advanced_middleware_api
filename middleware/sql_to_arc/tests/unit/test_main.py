"""Tests for sql_to_arc main module."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg
import pytest
from arctrl import ArcInvestigation  # type: ignore[import-untyped]

from middleware.sql_to_arc.main import (
    fetch_all_investigations,
    fetch_assays_bulk,
    fetch_studies_bulk,
    parse_args,
    populate_investigation_studies_and_assays,
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


class TestPopulateInvestigation:
    """Test suite for populate_investigation_studies_and_assays function."""

    def test_populate_investigation_no_studies(self) -> None:
        """Test populate with no studies."""
        arc = MagicMock(spec=ArcInvestigation)
        populate_investigation_studies_and_assays(arc, 1, {}, {})
        arc.AddRegisteredStudy.assert_not_called()

    def test_populate_investigation_with_studies_and_assays(self) -> None:
        """Test populate with studies and assays."""
        arc = MagicMock(spec=ArcInvestigation)
        study_mock = MagicMock()
        arc.AddRegisteredStudy.return_value = study_mock

        studies_by_investigation = {
            1: [{"id": 1, "title": "Study 1", "description": "Desc", "submission_time": None, "release_time": None}]
        }
        assays_by_study = {1: [{"id": 1, "study_id": 1, "measurement_type": "Type", "technology_type": "Tech"}]}

        with (
            patch("middleware.sql_to_arc.main.map_study") as mock_map_study,
            patch("middleware.sql_to_arc.main.map_assay") as mock_map_assay,
        ):
            mock_map_study.return_value = study_mock
            mock_map_assay.return_value = MagicMock()

            populate_investigation_studies_and_assays(arc, 1, studies_by_investigation, assays_by_study)

            mock_map_study.assert_called_once()
            mock_map_assay.assert_called_once()


@pytest.mark.asyncio
async def test_process_batch_empty() -> None:
    """Test batch processing with empty batch returns early."""
    mock_client = AsyncMock()
    batch: list[dict[str, Any]] = []

    await process_batch(
        mock_client,
        batch,
        "test_rdi",
        {},  # studies_by_investigation
        {},  # assays_by_study
        max_concurrent_builds=5,
    )
    mock_client.create_or_update_arcs.assert_not_called()
