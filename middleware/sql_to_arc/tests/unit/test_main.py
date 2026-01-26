"""Tests for sql_to_arc main module."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.sql_to_arc.main import (
    DatasetContext,
    ProcessingStats,
    WorkerContext,
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


# TestFetchAllInvestigations and other bulk fetchers removed as they are integrated into stream


# Bulk fetch classes removed


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
    loop_mock = MagicMock()

    # Only ONE call now: build_arc_for_investigation returns JSON string directly
    future: asyncio.Future[str] = asyncio.Future()
    future.set_result('{"id": "arc-1", "Identifier": "1"}')

    loop_mock.run_in_executor.return_value = future

    monkeypatch.setattr("asyncio.get_event_loop", lambda: loop_mock)

    ctx = WorkerContext(
        client=mock_client,
        rdi="test_rdi",
        executor=mock_executor,
    )

    stats = ProcessingStats()

    dataset_ctx = DatasetContext(
        investigation_row=investigation,
        studies=studies_by_investigation[1],
        assays_by_study=assays_by_study,
    )
    semaphore = asyncio.Semaphore(1)
    await process_single_dataset(ctx, dataset_ctx, semaphore, stats)

    assert mock_client.create_or_update_arc.called
    # Check that parsed JSON was passed
    call_kwargs = mock_client.create_or_update_arc.call_args.kwargs
    assert call_kwargs["rdi"] == "test_rdi"
    assert call_kwargs["arc"] == {"id": "arc-1", "Identifier": "1"}
    assert stats.failed_datasets == 0


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
        executor=mock_executor,
    )

    semaphore = asyncio.Semaphore(1)
    stats = ProcessingStats()

    investigation = {"id": 1}
    dataset_ctx = DatasetContext(investigation_row=investigation, studies=[], assays_by_study={})
    await process_single_dataset(ctx, dataset_ctx, semaphore, stats)

    assert not mock_client.create_or_update_arc.called
    assert stats.failed_datasets == 1
    assert "1" in stats.failed_ids


@pytest.mark.asyncio
async def test_process_investigations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test full process_investigations flow."""
    mock_cursor = AsyncMock()
    mock_client = AsyncMock()
    mock_config = MagicMock(max_concurrent_arc_builds=2, rdi="test", db_batch_size=100)

    # Mock stream_investigation_datasets
    async def mock_stream(*_args: Any, **_kwargs: Any) -> AsyncGenerator[tuple[dict, list, dict], None]:
        yield ({"id": 1}, [{"id": 10}], {10: []})
        yield ({"id": 2}, [], {})
        yield ({"id": 3}, [], {})

    monkeypatch.setattr("middleware.sql_to_arc.main.stream_investigation_datasets", mock_stream)

    # Mock process_single_dataset to avoid checking the whole flow details here
    async def mock_process_single(
        _ctx: WorkerContext,
        _dataset_ctx: DatasetContext,
        _sem: asyncio.Semaphore,
        _stats: ProcessingStats,
    ) -> None:
        # Simulate success
        return

    monkeypatch.setattr("middleware.sql_to_arc.main.process_single_dataset", mock_process_single)

    stats = await process_investigations(mock_cursor, mock_client, mock_config)

    assert stats.found_datasets == 3  # noqa: PLR2004
