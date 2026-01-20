"""Mapper module to convert database rows to ARCTRL objects."""

import json
from datetime import datetime
from typing import Any, cast

from arctrl import (
    ARC,
    ArcAssay,
    ArcInvestigation,
    ArcStudy,
    OntologyAnnotation,
    Person,
    Publication,
)


def _create_ontology_annotation(term: str | None, uri: str | None, version: str | None) -> OntologyAnnotation:
    """Create an OntologyAnnotation object."""
    if not term and not uri:
        # If both are empty, return empty annotation
        return OntologyAnnotation()
    
    # If term is empty but URI is present, we still create it (spec says name without ontology reference means unknown ref, 
    # omitting name means no ref. But here we have URI without name? 
    # Spec: "Omitting the name field means 'there is no ontology reference at all', the other two fields will be disregarded"
    # So if term is None, we return empty.
    if not term:
        return OntologyAnnotation()

    return OntologyAnnotation(
        tan=uri or "",
        tsr=term or "",
        name=term or ""
    )

# Correction: Arctrl OntologyAnnotation (from previous knowledge/standard) usually has:
# Name, TermAccessionNumber, TermSourceREF.
# In ARC/ISA:
# Name -> The term name (e.g. "Homo sapiens")
# TermAccessionNumber -> URI or Accession (e.g. http://...)
# TermSourceREF -> Ontology Name (e.g. NCBITaxon) - Wait, the spec says "status_version".
# The spec says: "Triple from xxx_term, xxx_uri and xxx_version were als OntologyAnnotations behandelt"
# xxx_term -> Name
# xxx_uri -> Term Accession / URI
# xxx_version -> Version (Where does this go? TermSourceREF usually holds ontology name, not version. Maybe comments?)

# Let's check how ARCTRL expects it. 
# For now, I will map:
# term -> Name
# uri -> TermAccessionNumber
# version -> (Comments?) or if ARCTRL has version support.
# As a safe bet:
# Name = term
# TermAccessionNumber = uri
# Comments = {"Ontology Version": version} if version else {}

def _make_oa(term: str | None, uri: str | None, version: str | None) -> OntologyAnnotation:
    if not term:
        return OntologyAnnotation()
    
    # name=term, tan=uri (TermAccessionNumber), tsr="" (TermSourceREF - we don't have it, maybe version?)
    # Spec says version is used. If we don't have TSR, we can leave it empty.
    return OntologyAnnotation(
        name=term,
        tan=uri or "",
        tsr="" 
    )


def map_investigation(row: dict[str, Any]) -> ArcInvestigation:
    """Map a database row to an ArcInvestigation object."""
    # Handle potential None values for dates
    submission_date = row.get("submission_date")
    public_release_date = row.get("public_release_date")
    
    # helper for dates
    def format_date(d: Any) -> str | None:
        if isinstance(d, datetime):
            return d.isoformat()
        if isinstance(d, str):
            return d
        return None

    identifier = str(row["identifier"]) if row.get("identifier") is not None else ""
    if not identifier.strip():
        # It's a required field
        # But we might start empty
        pass 

    inv = ArcInvestigation.create(
        identifier=identifier,
        title=row.get("title", ""),
        description=row.get("description_text", ""),
        submission_date=format_date(submission_date),
        public_release_date=format_date(public_release_date),
    )
    return inv


def map_study(row: dict[str, Any]) -> ArcStudy:
    """Map a database row to an ArcStudy object."""
    submission_date = row.get("submission_date")
    public_release_date = row.get("public_release_date")
    
    def format_date(d: Any) -> str | None:
        if isinstance(d, datetime):
            return d.isoformat()
        if isinstance(d, str):
            return d
        return None

    return ArcStudy.create(
        identifier=str(row["identifier"]),
        title=row.get("title", ""),
        description=row.get("description_text", ""),
        submission_date=format_date(submission_date),
        public_release_date=format_date(public_release_date),
    )


def map_assay(row: dict[str, Any]) -> ArcAssay:
    """Map a database row to an ArcAssay object."""
    
    assay = ArcAssay.create(
        identifier=str(row["identifier"]),
        measurement_type=_make_oa(
            row.get("measurement_type_term"),
            row.get("measurement_type_uri"),
            row.get("measurement_type_version")
        ),
        technology_type=_make_oa(
            row.get("technology_type_term"),
            row.get("technology_type_uri"),
            row.get("technology_type_version")
        ),
        technology_platform=_make_oa(
            row.get("technology_platform"), # Spec says platform is text but mapping to OA is allowed
            None,
            None
        ) if row.get("technology_platform") else None
    )
    
    return assay


def map_publication(row: dict[str, Any]) -> Publication:
    """Map a database row to a Publication object."""
    # Publication(doi, pubMedID, authors, title, status)
    
    status = _make_oa(
        row.get("status_term"),
        row.get("status_uri"),
        row.get("status_version")
    )
    
    return Publication(
        doi=row.get("doi", ""),
        pub_med_id=row.get("pubmed_id", ""),
        authors=row.get("authors", ""),
        title=row.get("title", ""),
        status=status
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
            pass # Logger?

    return Person(
        last_name=row.get("last_name", ""),
        first_name=row.get("first_name", ""),
        mid_initials=row.get("mid_initials", ""),
        email=row.get("email", ""),
        phone=row.get("phone", ""),
        fax=row.get("fax", ""),
        address=row.get("postal_address", ""),
        affiliation=row.get("affiliation", ""),
        roles=roles
    )

def map_annotation(row: dict[str, Any]) -> dict[str, Any]:
    """Return raw dict for annotation processing."""
    return row
