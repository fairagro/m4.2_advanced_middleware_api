
import pytest
from typing import Any
from arctrl import ARC, ArcInvestigation, ArcStudy, ArcAssay, Person, Publication
from middleware.sql_to_arc.main import build_single_arc_task

@pytest.fixture
def sample_investigation() -> dict[str, Any]:
    return {
        "identifier": "inv1",
        "title": "Inv Title",
        "description_text": "Inv Desc",
        "submission_date": None,
        "public_release_date": None,
    }

@pytest.fixture
def sample_studies() -> list[dict[str, Any]]:
    return [{
        "identifier": "sty1",
        "investigation_ref": "inv1",
        "title": "Study Title",
        "description_text": "Study Desc",
        "submission_date": None,
        "public_release_date": None,
    }]

@pytest.fixture
def sample_assays() -> list[dict[str, Any]]:
    return [{
        "identifier": "asy1",
        "investigation_ref": "inv1",
        "measurement_type_term": "MType",
        "measurement_type_uri": "http://mtype",
        "technology_type_term": "TType",
        "technology_type_uri": "http://ttype",
        # Link to study sty1
        "study_ref": '["sty1"]', 
        "technology_platform": "Platform",
    }]

@pytest.fixture
def sample_contacts() -> list[dict[str, Any]]:
    return [
        {
            "last_name": "Doe",
            "first_name": "John",
            "investigation_ref": "inv1",
            "target_type": "investigation",
            "target_ref": None,
        },
        {
            "last_name": "Smith",
            "first_name": "Jane",
            "investigation_ref": "inv1",
            "target_type": "study",
            "target_ref": "sty1",
        }
    ]

@pytest.fixture
def sample_publications() -> list[dict[str, Any]]:
    return [
        {
            "title": "Inv Pub",
            "investigation_ref": "inv1",
            "target_type": "investigation",
            "target_ref": None,
        },
        {
            "title": "Study Pub",
            "investigation_ref": "inv1",
            "target_type": "study",
            "target_ref": "sty1",
        }
    ]

def test_build_simple_arc(sample_investigation: dict[str, Any]) -> None:
    arc = build_single_arc_task(sample_investigation, [], [], [], [], [])
    assert isinstance(arc, ARC)
    assert arc.Identifier == "inv1"

def test_build_arc_with_study_and_assay(
    sample_investigation: dict[str, Any],
    sample_studies: list[dict[str, Any]],
    sample_assays: list[dict[str, Any]]
) -> None:
    arc = build_single_arc_task(
        sample_investigation,
        sample_studies,
        sample_assays,
        [], [], []
    )
    
    assert len(arc.RegisteredStudies) == 1
    # Assays are linked to studies, or present in the ARC assays list if not linked?
    # ARCtrl logic: RegisteredAssays usually refers to assays in the ARC.
    # But let's check Assays count on ARC.
    assert len(arc.Assays) == 1
    
    study = arc.RegisteredStudies[0]
    assert study.Identifier == "sty1"
    
    # Check linkage: Assay should be registered in Study
    assert len(study.RegisteredAssays) == 1
    assert study.RegisteredAssays[0].Identifier == "asy1"

def test_build_arc_with_contacts_and_pubs(
    sample_investigation: dict[str, Any],
    sample_studies: list[dict[str, Any]],
    sample_contacts: list[dict[str, Any]],
    sample_publications: list[dict[str, Any]]
) -> None:
    arc = build_single_arc_task(
        sample_investigation,
        sample_studies,
        [],
        sample_contacts,
        sample_publications,
        []
    )
    
    # Inv contacts
    assert len(arc.Contacts) == 1
    assert arc.Contacts[0].LastName == "Doe"
    
    # Study contacts
    study = arc.RegisteredStudies[0]
    assert len(study.Contacts) == 1
    assert study.Contacts[0].LastName == "Smith"
    
    # Inv pubs
    assert len(arc.Publications) == 1
    assert arc.Publications[0].Title == "Inv Pub"
    
    # Study pubs
    assert len(study.Publications) == 1
    assert study.Publications[0].Title == "Study Pub"

def test_build_ignores_irrelevant_data(
    sample_investigation: dict[str, Any]
) -> None:
    # Data for other investigation
    other_study = {"identifier": "styX", "investigation_ref": "inv2"}
    
    arc = build_single_arc_task(
        sample_investigation,
        [other_study],
        [], [], [], []
    )
    
    assert len(arc.RegisteredStudies) == 0

