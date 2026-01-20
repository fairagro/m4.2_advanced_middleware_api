"""Unit tests for the mapper module."""

import datetime
from typing import Any

from arctrl import ArcAssay, ArcInvestigation, ArcStudy, Person, Publication

from middleware.sql_to_arc.mapper import (
    map_assay,
    map_contact,
    map_investigation,
    map_publication,
    map_study,
)


def test_map_investigation() -> None:
    """Test mapping of investigation data."""
    now = datetime.datetime.now()
    row: dict[str, Any] = {
        "identifier": "123",
        "title": "Test Investigation",
        "description_text": "Test Description",
        "submission_date": now,
        "public_release_date": now,
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
        "identifier": "456",
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
        "identifier": "1",
        "title": "Test Study",
        "description_text": "Study Description",
        "submission_date": now,
        "public_release_date": now,
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
        "identifier": "1",
        "measurement_type_term": "Proteomics",
        "measurement_type_uri": "http://example.org/prot",
        "technology_type_term": "Mass Spectrometry",
        "technology_type_uri": "http://example.org/ms",
    }

    assay = map_assay(row)

    assert isinstance(assay, ArcAssay)
    assert assay.Identifier == "1"
    # Check OntologyAnnotations
    assert assay.MeasurementType.Name == "Proteomics"
    assert assay.MeasurementType.TermAccessionNumber == "http://example.org/prot"
    assert assay.TechnologyType.Name == "Mass Spectrometry"
    assert assay.TechnologyType.TermAccessionNumber == "http://example.org/ms"


def test_map_publication() -> None:
    """Test mapping of publication data."""
    row: dict[str, Any] = {
        "pubmed_id": "12345",
        "doi": "10.1234/5678",
        "authors": "Doe J, Smith A",
        "title": "A Great Paper",
        "status_term": "Published",
    }

    pub = map_publication(row)

    assert isinstance(pub, Publication)
    assert pub.PubMedID == "12345"
    assert pub.DOI == "10.1234/5678"
    assert pub.Authors == "Doe J, Smith A"
    assert pub.Title == "A Great Paper"
    assert pub.Status.Name == "Published"


def test_map_contact() -> None:
    """Test mapping of contact data."""
    row: dict[str, Any] = {
        "last_name": "Doe",
        "first_name": "John",
        "email": "john@example.com",
        "roles": '[{"term": "Principal Investigator", "uri": "http://roles", "version": "1.0"}]',
    }

    person = map_contact(row)

    assert isinstance(person, Person)
    assert person.LastName == "Doe"
    assert person.FirstName == "John"
    assert person.EMail == "john@example.com"
    assert len(person.Roles) == 1
    assert person.Roles[0].Name == "Principal Investigator"
    assert person.Roles[0].TermAccessionNumber == "http://roles"
