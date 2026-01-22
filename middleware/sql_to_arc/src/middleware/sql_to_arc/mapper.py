"""Mapper module to convert database rows to ARCTRL objects."""

import json
from datetime import datetime
from typing import Any

from arctrl import (  # type: ignore
    ArcAssay,
    ArcInvestigation,
    ArcStudy,
    OntologyAnnotation,
    Person,
    Publication,
)

# name=term, tan=uri (TermAccessionNumber), tsr="" (TermSourceREF - we don't have it, maybe version?)
# Spec says version is used. If we don't have TSR, we can leave it empty.


def _make_oa(term: str | None, uri: str | None, _version: str | None) -> OntologyAnnotation:
    if not term:
        return OntologyAnnotation()

    # name=term, tan=uri (TermAccessionNumber), tsr="" (TermSourceREF - we don't have it, maybe version?)
    # Spec says version is used. If we don't have TSR, we can leave it empty.
    return OntologyAnnotation(name=term, tan=uri or "", tsr="")


def _format_date(d: Any) -> str | None:
    """Format dates as ISO strings."""
    if isinstance(d, datetime):
        return d.isoformat()
    if isinstance(d, str):
        return d
    return None


def map_investigation(row: dict[str, Any]) -> ArcInvestigation:
    """Map a database row to an ArcInvestigation object."""
    # Handle potential None values for dates
    submission_date = row.get("submission_date")
    public_release_date = row.get("public_release_date")

    identifier = str(row["identifier"]) if row.get("identifier") is not None else ""
    if not identifier.strip():
        # It's a required field
        # But we might start empty
        pass

    # TODO: the database view spec requires title and description_text to be NOT NULL.
    # But how would we validate that in general -- not necessarily here?
    inv = ArcInvestigation.create(
        identifier=identifier,
        title=row.get("title", ""),
        description=row.get("description_text", ""),
        submission_date=_format_date(submission_date),
        public_release_date=_format_date(public_release_date),
    )
    return inv


def map_study(row: dict[str, Any]) -> ArcStudy:
    """Map a database row to an ArcStudy object."""
    submission_date = row.get("submission_date")
    public_release_date = row.get("public_release_date")

    return ArcStudy.create(
        identifier=str(row["identifier"]),
        title=row.get("title", ""),
        description=row.get("description_text", ""),
        submission_date=_format_date(submission_date),
        public_release_date=_format_date(public_release_date),
    )


def map_assay(row: dict[str, Any]) -> ArcAssay:
    """Map a database row to an ArcAssay object."""
    assay = ArcAssay.create(
        identifier=str(row["identifier"]),
        measurement_type=_make_oa(
            row.get("measurement_type_term"), row.get("measurement_type_uri"), row.get("measurement_type_version")
        ),
        technology_type=_make_oa(
            row.get("technology_type_term"), row.get("technology_type_uri"), row.get("technology_type_version")
        ),
        technology_platform=_make_oa(
            row.get("technology_platform"),  # Spec says platform is text but mapping to OA is allowed
            None,
            None,
        )
        if row.get("technology_platform")
        else None,
    )

    return assay


def map_publication(row: dict[str, Any]) -> Publication:
    """Map a database row to a Publication object."""
    # Publication(doi, pubMedID, authors, title, status)

    status = _make_oa(row.get("status_term"), row.get("status_uri"), row.get("status_version"))

    return Publication(
        doi=row.get("doi", ""),
        pub_med_id=row.get("pubmed_id", ""),
        authors=row.get("authors", ""),
        title=row.get("title", ""),
        status=status,
    )


def map_contact(row: dict[str, Any]) -> Person:
    """Map a database row to a Person object."""
    # Person(lastName, firstName, midInitials, email, phone, fax, address, affiliation, roles)

    # Parse roles JSON
    roles_json = row.get("roles")
    roles = []
    if roles_json:
        try:
            roles_list = json.loads(roles_json)
            if isinstance(roles_list, list):
                for r in roles_list:
                    roles.append(_make_oa(r.get("term"), r.get("uri"), r.get("version")))
        except json.JSONDecodeError:
            pass  # Logger?

    return Person(
        last_name=row.get("last_name", ""),
        first_name=row.get("first_name", ""),
        mid_initials=row.get("mid_initials", ""),
        email=row.get("email", ""),
        phone=row.get("phone", ""),
        fax=row.get("fax", ""),
        address=row.get("postal_address", ""),
        affiliation=row.get("affiliation", ""),
        roles=roles,
    )


def map_annotation(row: dict[str, Any]) -> dict[str, Any]:
    """Return raw dict for annotation processing."""
    return row
