"""Unit tests for investigation population helpers."""

from typing import Any

from middleware.sql_to_arc.main import build_single_arc_task


def _sample_investigation() -> dict[str, Any]:
    return {
        "id": 1,
        "title": "Test Investigation",
        "description": "Desc",
        "submission_time": None,
        "release_time": None,
    }


def _sample_studies() -> list[dict[str, Any]]:
    return [
        {
            "id": 10,
            "investigation_id": 1,
            "title": "Study 1",
            "description": "Desc 1",
            "submission_time": None,
            "release_time": None,
        },
        {
            "id": 11,
            "investigation_id": 1,
            "title": "Study 2",
            "description": "Desc 2",
            "submission_time": None,
            "release_time": None,
        },
    ]


def test_build_single_arc_task_populates_studies_and_assays() -> None:
    """The helper should build an investigation with studies and assays."""
    assays_by_study = {
        10: [
            {"id": 100, "study_id": 10, "measurement_type": "Metabolomics", "technology_type": "MS"},
            {"id": 101, "study_id": 10, "measurement_type": "Proteomics", "technology_type": "MS"},
        ],
        11: [
            {"id": 102, "study_id": 11, "measurement_type": "Genomics", "technology_type": "Sequencing"},
        ],
    }

    arc = build_single_arc_task(
        _sample_investigation(),
        _sample_studies(),
        assays_by_study,
    )

    assert arc.Identifier == "1"
    assert len(arc.RegisteredStudies) == 2
    study1 = next(study for study in arc.RegisteredStudies if study.Identifier == "10")
    study2 = next(study for study in arc.RegisteredStudies if study.Identifier == "11")

    assert len(study1.RegisteredAssays) == 2
    assert len(study2.RegisteredAssays) == 1


def test_build_single_arc_task_handles_empty_assays() -> None:
    """The helper should handle studies without assays."""
    arc = build_single_arc_task(
        _sample_investigation(),
        _sample_studies(),
        {},
    )

    assert len(arc.RegisteredStudies) == 2
    for study in arc.RegisteredStudies:
        assert len(study.RegisteredAssays) == 0
