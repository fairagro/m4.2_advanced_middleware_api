"""Mapper module to convert database rows to ARCTRL objects."""

from typing import Any

from arctrl import ArcAssay, ArcInvestigation, ArcStudy  # type: ignore[import-untyped]


def map_investigation(row: dict[str, Any]) -> ArcInvestigation:
    """Map a database row to an ArcInvestigation object.

    Args:
        row: Dictionary containing investigation data from DB

    Returns:
        ArcInvestigation object
    """
    # Handle potential None values for dates
    submission_date = row.get("submission_time")
    public_release_date = row.get("release_time")

    # Ensure dates are properly formatted if they are datetime objects
    # arctrl might expect strings or specific formats, but let's pass what we have for now
    # or convert to ISO format string if needed.

    return ArcInvestigation.create(
        identifier=str(row["id"]),
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
    submission_date = row.get("submission_time")
    public_release_date = row.get("release_time")

    return ArcStudy.create(
        identifier=str(row["title"]),  # Using title as identifier for now as ID is int
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
    """
    return ArcAssay.create(
        identifier=str(row["measurement_type"]),  # Using measurement_type as identifier? Or generate one?
        measurement_type=row.get("measurement_type", ""),
        technology_type=row.get("technology_type", ""),
    )
