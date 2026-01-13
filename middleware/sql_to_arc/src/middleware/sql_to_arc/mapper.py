"""Mapper module to convert database rows to ARCTRL objects."""

from datetime import datetime
from typing import Any, cast

from arctrl import ArcAssay, ArcInvestigation, ArcStudy  # type: ignore[import-untyped]


def map_investigation(row: dict[str, Any]) -> ArcInvestigation:
    """Map a database row to an ArcInvestigation object.

    Args:
        row: Dictionary containing investigation data from DB

    Returns:
        ArcInvestigation object
    """
    # Handle potential None values for dates
    submission_date = cast(datetime, row.get("submission_time")).isoformat() if row.get("submission_time") else None
    public_release_date = cast(datetime, row.get("release_time")).isoformat() if row.get("release_time") else None

    # Validate ID (mandatory per DB view spec, but we enforce it here to be safe)
    identifier = str(row["id"]) if row.get("id") is not None else ""
    if not identifier.strip():
        raise ValueError(f"Investigation ID cannot be empty (row={row})")

    return ArcInvestigation.create(
        identifier=identifier,
        title=row.get("title", ""),
        description=row.get("description", ""),
        submission_date=submission_date,
        public_release_date=public_release_date,
    )


def map_study(row: dict[str, Any]) -> ArcStudy:
    """Map a database row to an ArcStudy object.

    Args:
        row: Dictionary containing study data from DB

    Returns:
        ArcStudy object
    """
    # Handle potential None values for dates
    submission_date = cast(datetime, row.get("submission_time")).isoformat() if row.get("submission_time") else None
    public_release_date = cast(datetime, row.get("release_time")).isoformat() if row.get("release_time") else None

    return ArcStudy.create(
        identifier=str(row["id"]),
        title=row.get("title", ""),
        description=row.get("description", ""),
        submission_date=submission_date,
        public_release_date=public_release_date,
    )


def map_assay(row: dict[str, Any]) -> ArcAssay:
    """Map a database row to an ArcAssay object.

    Args:
        row: Dictionary containing assay data from DB

    Returns:
        ArcAssay object

    Note:
        TODO: Currently measurement_type and technology_type from DB are simple strings,
        but ArcAssay expects OntologyTerm objects. Once the database schema is updated to
        provide full ontology information (term accession, ontology name, etc.), these
        should be converted to proper OntologyTerm objects instead of being omitted.
    """
    # TODO: Convert measurement_type and technology_type to OntologyTerms
    # once the database provides the necessary ontology information
    return ArcAssay.create(
        identifier=str(row["id"]),
    )
