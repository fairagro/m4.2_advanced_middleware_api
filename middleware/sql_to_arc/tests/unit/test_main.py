"""Unit tests for the sql_to_arc main module.

This module contains tests for argument parsing, investigation processing,
and worker investigation handling in the sql_to_arc pipeline.
"""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.sql_to_arc.main import (
    ProcessingStats,
    WorkerContext,
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


@pytest.mark.asyncio
async def test_process_worker_investigations_empty() -> None:
    """Test worker investigations processing with empty list returns early."""
    mock_client = AsyncMock()
    investigations: list[dict[str, Any]] = []
    mock_executor = MagicMock()

    ctx = WorkerContext(
        client=mock_client,
        rdi="test_rdi",
        studies_by_inv={},
        assays_by_inv={},
        contacts_by_inv={},
        pubs_by_inv={},
        anns_by_inv={},
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
    mock_client.create_or_update_arcs.return_value = MagicMock(arcs=[MagicMock(id="1")])

    investigations = [
        {"identifier": "1", "title": "Inv", "description_text": "Desc"},
    ]
    studies = {"1": [{"identifier": "10", "investigation_ref": "1", "title": "Study"}]}

    # Mock the loop.run_in_executor to return an ARC directly
    loop_future: asyncio.Future[MagicMock] = asyncio.Future()
    arc_object = MagicMock(name="ARCObject")
    arc_object.Identifier = "1"
    loop_future.set_result(arc_object)

    loop_mock = MagicMock()
    loop_mock.run_in_executor.return_value = loop_future
    monkeypatch.setattr("asyncio.get_event_loop", MagicMock(return_value=loop_mock))

    executor = MagicMock()

    ctx = WorkerContext(
        client=mock_client,
        rdi="test_rdi",
        studies_by_inv=studies,
        assays_by_inv={},
        contacts_by_inv={},
        pubs_by_inv={},
        anns_by_inv={},
        worker_id=1,
        total_workers=1,
        executor=executor,
    )
    await process_worker_investigations(ctx, investigations)

    loop_mock.run_in_executor.assert_called_once()
    mock_client.create_or_update_arcs.assert_called_once()


@pytest.mark.asyncio
async def test_process_investigations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test full process_investigations flow."""
    mock_db = MagicMock()

    # Mock DB stream methods
    async def mock_gen(data: list[dict[str, Any]]) -> AsyncGenerator[dict[str, Any], None]:
        for item in data:
            yield item

    mock_db.stream_investigations.side_effect = lambda limit=None: mock_gen([{"identifier": "1"}, {"identifier": "2"}])  # noqa: ARG005
    mock_db.stream_studies.side_effect = lambda investigation_ids: mock_gen(  # noqa: ARG005
        [{"identifier": "10", "investigation_ref": "1"}]
    )
    mock_db.stream_assays.side_effect = lambda investigation_ids: mock_gen([])  # noqa: ARG005
    mock_db.stream_contacts.side_effect = lambda investigation_ids: mock_gen([])  # noqa: ARG005
    mock_db.stream_publications.side_effect = lambda investigation_ids: mock_gen([])  # noqa: ARG005
    mock_db.stream_annotation_tables.side_effect = lambda investigation_ids: mock_gen([])  # noqa: ARG005

    mock_client = AsyncMock()
    mock_config = MagicMock(max_concurrent_arc_builds=2, rdi="test", debug_limit=10)

    # Mock process_worker_investigations to simplify
    async def mock_process_worker_inv(_ctx: WorkerContext, _invs: list[dict[str, Any]]) -> ProcessingStats:
        return ProcessingStats(found_datasets=0)

    monkeypatch.setattr("middleware.sql_to_arc.main.process_worker_investigations", mock_process_worker_inv)

    stats = await process_investigations(mock_db, mock_client, mock_config)

    assert stats.found_datasets == 2  # noqa: PLR2004
    assert stats.total_studies == 1
    mock_db.stream_investigations.assert_called_with(limit=10)
