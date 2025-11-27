"""Unit tests for the mapper module."""

import datetime
from typing import Any

from arctrl import ArcAssay, ArcInvestigation, ArcStudy  # type: ignore[import-untyped]

from middleware.sql_to_arc.mapper import map_assay, map_investigation, map_study


def test_map_investigation() -> None:
    """Test mapping of investigation data."""
    now = datetime.datetime.now()
    row: dict[str, Any] = {
        "id": 123,
        "title": "Test Investigation",
        "description": "Test Description",
        "submission_time": now,
        "release_time": now,
    }

    arc = map_investigation(row)

    assert isinstance(arc, ArcInvestigation)
    assert arc.Identifier == "123"
    assert arc.Title == "Test Investigation"
    assert arc.Description == "Test Description"
    assert arc.SubmissionDate == now.isoformat()
    assert arc.PublicReleaseDate == now.isoformat()


def test_map_investigation_defaults() -> None:
    """Test mapping of investigation data with missing optional fields."""
    row: dict[str, Any] = {
        "id": 456,
    }

    arc = map_investigation(row)

    assert arc.Identifier == "456"
    assert arc.Title == ""
    assert arc.Description == ""
    assert arc.SubmissionDate is None
    assert arc.PublicReleaseDate is None


def test_map_study() -> None:
    """Test mapping of study data."""
    now = datetime.datetime.now()
    row: dict[str, Any] = {
        "id": 1,
        "title": "Test Study",
        "description": "Study Description",
        "submission_time": now,
        "release_time": now,
    }

    study = map_study(row)

    assert isinstance(study, ArcStudy)
    assert study.Identifier == "1"
    assert study.Title == "Test Study"
    assert study.Description == "Study Description"
    assert study.SubmissionDate == now.isoformat()
    assert study.PublicReleaseDate == now.isoformat()


def test_map_assay() -> None:
    """Test mapping of assay data."""
    row: dict[str, Any] = {
        "id": 1,
        "measurement_type": "Proteomics",
        "technology_type": "Mass Spectrometry",
    }

    assay = map_assay(row)

    assert isinstance(assay, ArcAssay)
    assert assay.Identifier == "1"
    assert str(assay.MeasurementType) == "Proteomics"
    assert str(assay.TechnologyType) == "Mass Spectrometry"
