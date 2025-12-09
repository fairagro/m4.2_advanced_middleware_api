"""Unit tests for bulk fetch functions."""

from unittest.mock import AsyncMock

import pytest

from middleware.sql_to_arc.main import fetch_all_investigations, fetch_assays_bulk, fetch_studies_bulk


@pytest.mark.asyncio
async def test_fetch_all_investigations() -> None:
    """Test fetching all investigations."""
    mock_cursor = AsyncMock()
    expected_investigations = [
        {"id": 1, "title": "Inv 1", "description": "Desc 1", "submission_time": None, "release_time": None},
        {"id": 2, "title": "Inv 2", "description": "Desc 2", "submission_time": None, "release_time": None},
    ]
    mock_cursor.fetchall.return_value = expected_investigations

    result = await fetch_all_investigations(mock_cursor)

    assert result == expected_investigations
    assert mock_cursor.execute.called
    # Verify the correct query was executed
    call_args = mock_cursor.execute.call_args[0][0]
    assert 'FROM "ARC_Investigation"' in call_args


@pytest.mark.asyncio
async def test_fetch_studies_bulk() -> None:
    """Test bulk fetching studies for multiple investigations."""
    mock_cursor = AsyncMock()
    studies_data = [
        {
            "id": 10,
            "investigation_id": 1,
            "title": "Study 1",
            "description": "Desc",
            "submission_time": None,
            "release_time": None,
        },
        {
            "id": 11,
            "investigation_id": 1,
            "title": "Study 2",
            "description": "Desc",
            "submission_time": None,
            "release_time": None,
        },
        {
            "id": 12,
            "investigation_id": 2,
            "title": "Study 3",
            "description": "Desc",
            "submission_time": None,
            "release_time": None,
        },
    ]
    mock_cursor.fetchall.return_value = studies_data

    investigation_ids = [1, 2]
    result = await fetch_studies_bulk(mock_cursor, investigation_ids)

    # Verify the query was executed with ANY clause
    assert mock_cursor.execute.called
    call_args = mock_cursor.execute.call_args[0]
    assert 'FROM "ARC_Study"' in call_args[0]
    assert "ANY" in call_args[0]
    assert call_args[1] == (investigation_ids,)

    # Verify the results are grouped by investigation_id
    assert 1 in result
    assert 2 in result
    assert len(result[1]) == 2  # Investigation 1 has 2 studies
    assert len(result[2]) == 1  # Investigation 2 has 1 study
    assert result[1][0]["id"] == 10
    assert result[1][1]["id"] == 11
    assert result[2][0]["id"] == 12


@pytest.mark.asyncio
async def test_fetch_studies_bulk_empty() -> None:
    """Test bulk fetching studies with empty investigation list."""
    mock_cursor = AsyncMock()

    result = await fetch_studies_bulk(mock_cursor, [])

    # Should return empty dict without executing query
    assert result == {}
    assert not mock_cursor.execute.called


@pytest.mark.asyncio
async def test_fetch_assays_bulk() -> None:
    """Test bulk fetching assays for multiple studies."""
    mock_cursor = AsyncMock()
    assays_data = [
        {"id": 100, "study_id": 10, "measurement_type": "Metabolomics", "technology_type": "MS"},
        {"id": 101, "study_id": 10, "measurement_type": "Proteomics", "technology_type": "MS"},
        {"id": 102, "study_id": 11, "measurement_type": "Genomics", "technology_type": "Sequencing"},
    ]
    mock_cursor.fetchall.return_value = assays_data

    study_ids = [10, 11]
    result = await fetch_assays_bulk(mock_cursor, study_ids)

    # Verify the query was executed with ANY clause
    assert mock_cursor.execute.called
    call_args = mock_cursor.execute.call_args[0]
    assert 'FROM "ARC_Assay"' in call_args[0]
    assert "ANY" in call_args[0]
    assert call_args[1] == (study_ids,)

    # Verify the results are grouped by study_id
    assert 10 in result
    assert 11 in result
    assert len(result[10]) == 2  # Study 10 has 2 assays
    assert len(result[11]) == 1  # Study 11 has 1 assay
    assert result[10][0]["id"] == 100
    assert result[10][1]["id"] == 101
    assert result[11][0]["id"] == 102


@pytest.mark.asyncio
async def test_fetch_assays_bulk_empty() -> None:
    """Test bulk fetching assays with empty study list."""
    mock_cursor = AsyncMock()

    result = await fetch_assays_bulk(mock_cursor, [])

    # Should return empty dict without executing query
    assert result == {}
    assert not mock_cursor.execute.called
