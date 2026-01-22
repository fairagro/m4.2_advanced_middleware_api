"""Tests for sql_to_arc main module."""

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg
import pytest

from middleware.sql_to_arc.main import (
    ProcessingStats,
    WorkerContext,
    parse_args,
    process_investigations,
    process_single_dataset,
    stream_investigation_datasets,
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
        executor=mock_executor,
    )
    
    semaphore = asyncio.Semaphore(1)
    stats = ProcessingStats()
    
    # Pass individual studies and assays separately now
    await process_single_dataset(
        ctx, investigation, studies_by_investigation[1], assays_by_study, semaphore, stats
    )
    
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
        executor=mock_executor,
    )
    
    semaphore = asyncio.Semaphore(1)
    stats = ProcessingStats()
    
    investigation = {"id": 1}
    await process_single_dataset(ctx, investigation, [], {}, semaphore, stats)
    
    assert not mock_client.create_or_update_arc.called
    assert stats.failed_datasets == 1
    assert "1" in stats.failed_ids


@pytest.mark.asyncio
async def test_process_investigations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test full process_investigations flow."""
    mock_cursor = AsyncMock()
    mock_client = AsyncMock()
    mock_config = MagicMock(max_concurrent_arc_builds=2, rdi="test")

    # Mock stream_investigation_datasets
    async def mock_stream(*_args: Any) -> AsyncGenerator[tuple[dict, list, dict], None]:
        yield ({"id": 1}, [{"id": 10}], {10: []})
        yield ({"id": 2}, [], {})
        yield ({"id": 3}, [], {})

    monkeypatch.setattr("middleware.sql_to_arc.main.stream_investigation_datasets", mock_stream)

    # Mock process_single_dataset to avoid checking the whole flow details here
    async def mock_process_single(
        _ctx: WorkerContext,
        _row: dict,
        _studies: list,
        _assays: dict,
        _sem: asyncio.Semaphore,
        _stats: ProcessingStats,
    ) -> None:
         # Simulate success
         return

    monkeypatch.setattr("middleware.sql_to_arc.main.process_single_dataset", mock_process_single)

    stats = await process_investigations(mock_cursor, mock_client, mock_config)

    assert stats.found_datasets == 3  # noqa: PLR2004
