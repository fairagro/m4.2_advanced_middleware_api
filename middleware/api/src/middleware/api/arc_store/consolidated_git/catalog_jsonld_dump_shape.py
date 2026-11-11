"""Transitional catalog dump shape overrides for AggregatedArcStore JSON-LD.

Not AgriSchemas. schema.org remains the vocabulary; this fragment only overrides
term *writing* rules for Search Hub–stable basic-layout dumps until ARC→AgriSchemas
lands. Kept separate from ``ARC_BIOSCHEMAS_EXTENSION_CONTEXT`` (Lab/Sample/ISA aliases).

``@id`` values use ``http://schema.org/`` to match the vendored schema.org 30.0
``@vocab`` / ``schema:`` prefix (https and http are not interchangeable in JSON-LD).
"""

from __future__ import annotations

# Match schemaorg-30.0-context.jsonld (@vocab / schema: prefix).
_SCHEMA = "http://schema.org"


def _schema_term(name: str) -> str:
    return f"{_SCHEMA}/{name}"


def _date_term(name: str) -> dict[str, str]:
    # Drop schema.org ``@type: Date`` so untyped ARCtrl strings compact to the short name.
    return {"@id": _schema_term(name)}


def _set_term(name: str) -> dict[str, str]:
    return {"@id": _schema_term(name), "@container": "@set"}


# Appended after schema.org (+ ARC/Bioschemas) so these definitions win on compact/expand.
CATALOG_DUMP_SHAPE_CONTEXT: dict[str, str | dict[str, str]] = {
    "schema": f"{_SCHEMA}/",
    "dateCreated": _date_term("dateCreated"),
    "dateModified": _date_term("dateModified"),
    "datePublished": _date_term("datePublished"),
    "sdDatePublished": _date_term("sdDatePublished"),
    "author": _set_term("author"),
    "citation": _set_term("citation"),
    "comment": _set_term("comment"),
    "contributor": _set_term("contributor"),
    "creator": _set_term("creator"),
    "hasPart": _set_term("hasPart"),
    "keywords": _set_term("keywords"),
}
