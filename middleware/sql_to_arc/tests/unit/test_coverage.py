"""Additional tests to increase coverage for sql_to_arc/main.py."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from arctrl import ARC # type: ignore[import-untyped]

from middleware.sql_to_arc.main import (
    DatasetContext,
    ProcessingStats,
    WorkerContext,
    build_arc_for_investigation,
    process_single_dataset,
    stream_investigation_datasets,
)


def test_processing_stats_to_jsonld() -> None:
    """Test ProcessingStats.to_jsonld conversion."""
    stats = ProcessingStats(
        found_datasets=2,
        total_studies=4,
        total_assays=10,
        failed_datasets=1,
        failed_ids=["error-1"],
        duration_seconds=12.5,
    )
    jsonld_str = stats.to_jsonld(rdi_identifier="test-rdi", rdi_url="https://test-rdi.org")
    data = json.loads(jsonld_str)

    assert data["@type"] == ["prov:Activity", "schema:CreateAction"]
    assert data["found_datasets"] == 2
    assert data["status"] == "schema:FailedActionStatus"
    assert data["duration"] == "PT12.50S"
    assert data["prov:used"]["schema:identifier"] == "test-rdi"


@pytest.mark.asyncio
async def test_stream_investigation_datasets() -> None:
    """Test stream_investigation_datasets with mocked cursor."""
    mock_cur = AsyncMock()
    mock_cur.fetchmany.side_effect = [
        [{"id": 1, "title": "Inv 1"}],
        []  # End of stream
    ]
    
    # Mock studies and assays
    mock_detail_cur = AsyncMock()
    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__aenter__.return_value = mock_detail_cur
    mock_cursor_cm.__aexit__.return_value = False
    
    # mock_conn.cursor() should return the context manager
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor_cm
    mock_cur.connection = mock_conn
    
    # Detail fetches (Studies, then Assays)
    mock_detail_cur.fetchall.side_effect = [
        [{"id": 10, "investigation_id": 1, "title": "Study 1"}], # Studies
        [{"id": 100, "study_id": 10, "measurement_type": "MT"}] # Assays
    ]

    results = []
    async for item in stream_investigation_datasets(mock_cur, batch_size=1):
        results.append(item)

    assert len(results) == 1
    inv_row, studies, assays = results[0]
    assert inv_row["id"] == 1
    assert len(studies) == 1
    assert studies[0]["id"] == 10
    assert 10 in assays


def test_build_arc_for_investigation() -> None:
    """Test build_arc_for_investigation direct call."""
    inv_row = {"id": 1, "title": "Inv"}
    studies = [{"id": 10, "title": "Study"}]
    assays_by_study = {10: [{"id": 100, "measurement_type": "M"}]}

    with patch("middleware.sql_to_arc.main.map_investigation") as mock_map_inv, \
         patch("middleware.sql_to_arc.main.map_study") as mock_map_study, \
         patch("middleware.sql_to_arc.main.map_assay") as mock_map_assay, \
         patch("arctrl.ARC.from_arc_investigation") as mock_arc_from_inv:
        
        mock_inv = MagicMock()
        mock_map_inv.return_value = mock_inv
        mock_study = MagicMock()
        mock_map_study.return_value = mock_study
        mock_assay = MagicMock()
        mock_map_assay.return_value = mock_assay
        
        mock_arc = MagicMock()
        mock_arc.ToROCrateJsonString.return_value = '{"fake": "arc"}'
        mock_arc_from_inv.return_value = mock_arc

        result = build_arc_for_investigation(inv_row, studies, assays_by_study)
        assert result == '{"fake": "arc"}'


@pytest.mark.asyncio
async def test_process_single_dataset_limits_exceeded() -> None:
    """Test process_single_dataset when limits are exceeded."""
    ctx = WorkerContext(
        client=AsyncMock(),
        rdi="test",
        executor=MagicMock(),
        max_studies=1,
        max_assays=1,
        arc_generation_timeout_minutes=1,
    )
    
    # 2 studies exceeds limit of 1
    dataset_ctx = DatasetContext(
        investigation_row={"id": "err1"},
        studies=[{"id": 1}, {"id": 2}],
        assays_by_study={}
    )
    
    stats = ProcessingStats()
    semaphore = asyncio.Semaphore(1)
    
    await process_single_dataset(ctx, dataset_ctx, semaphore, stats)
    assert stats.failed_datasets == 1
    assert "err1" in stats.failed_ids


@pytest.mark.asyncio
async def test_process_single_dataset_timeout() -> None:
    """Test process_single_dataset when build times out."""
    ctx = WorkerContext(
        client=AsyncMock(),
        rdi="test",
        executor=MagicMock(),
        max_studies=10,
        max_assays=10,
        arc_generation_timeout_minutes=1,
    )
    
    dataset_ctx = DatasetContext(
        investigation_row={"id": "timeout1"},
        studies=[],
        assays_by_study={}
    )
    
    stats = ProcessingStats()
    semaphore = asyncio.Semaphore(1)
    
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
        await process_single_dataset(ctx, dataset_ctx, semaphore, stats)
    
    assert stats.failed_datasets == 1
    assert "timeout1" in stats.failed_ids
