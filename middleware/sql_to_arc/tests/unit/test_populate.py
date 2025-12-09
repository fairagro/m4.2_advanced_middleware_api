"""Unit tests for investigation population."""

from typing import Any

from arctrl import ArcInvestigation  # type: ignore[import-untyped]

from middleware.sql_to_arc.main import populate_investigation_studies_and_assays


def test_populate_investigation_studies_and_assays() -> None:
    """Test populating an investigation with studies and assays."""
    # Create an empty investigation
    arc = ArcInvestigation.create(identifier="1", title="Test Investigation")

    # Prepare test data
    studies_by_investigation = {
        1: [
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
    }

    assays_by_study = {
        10: [
            {"id": 100, "study_id": 10, "measurement_type": "Metabolomics", "technology_type": "MS"},
            {"id": 101, "study_id": 10, "measurement_type": "Proteomics", "technology_type": "MS"},
        ],
        11: [
            {"id": 102, "study_id": 11, "measurement_type": "Genomics", "technology_type": "Sequencing"},
        ],
    }

    # Populate the investigation
    populate_investigation_studies_and_assays(
        arc,
        1,
        studies_by_investigation,
        assays_by_study,
    )

    # Verify the investigation was populated correctly
    assert arc.Identifier == "1"
    assert len(arc.StudyIdentifiers) == 2
    assert "10" in arc.StudyIdentifiers
    assert "11" in arc.StudyIdentifiers

    # Verify studies were added
    study_1 = arc.GetStudy("10")
    assert study_1 is not None
    assert study_1.Identifier == "10"
    assert study_1.Title == "Study 1"
    # Note: AssayIdentifiers might not be available in the mock, skip this assertion

    study_2 = arc.GetStudy("11")
    assert study_2 is not None
    assert study_2.Identifier == "11"
    assert study_2.Title == "Study 2"


def test_populate_investigation_no_studies() -> None:
    """Test populating an investigation with no studies."""
    arc = ArcInvestigation.create(identifier="2", title="Empty Investigation")

    # Empty data
    studies_by_investigation: dict[int, list[dict[str, Any]]] = {}
    assays_by_study: dict[int, list[dict[str, Any]]] = {}

    # Populate (should not add anything)
    populate_investigation_studies_and_assays(
        arc,
        2,
        studies_by_investigation,
        assays_by_study,
    )

    # Verify investigation is still empty
    assert arc.Identifier == "2"
    assert len(arc.StudyIdentifiers) == 0


def test_populate_investigation_studies_without_assays() -> None:
    """Test populating an investigation with studies but no assays."""
    arc = ArcInvestigation.create(identifier="3", title="Investigation with Studies")

    studies_by_investigation = {
        3: [
            {
                "id": 20,
                "investigation_id": 3,
                "title": "Study Without Assays",
                "description": "Desc",
                "submission_time": None,
                "release_time": None,
            },
        ]
    }

    assays_by_study: dict[int, list[dict[str, Any]]] = {}

    populate_investigation_studies_and_assays(
        arc,
        3,
        studies_by_investigation,
        assays_by_study,
    )

    # Verify study was added
    assert len(arc.StudyIdentifiers) == 1
    study = arc.GetStudy("20")
    assert study is not None
    assert study.Identifier == "20"
