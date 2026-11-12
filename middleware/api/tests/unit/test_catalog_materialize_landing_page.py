"""Unit tests for Landing Page → Dataset url materialization."""

from __future__ import annotations

from typing import cast

from middleware.api.arc_store.consolidated_git.catalog_jsonld import (
    build_catalog_compact_context,
    build_catalog_emitted_context,
    compact_catalog_dataset,
)
from middleware.api.arc_store.consolidated_git.catalog_materialize import materialize_catalog_dataset
from middleware.api.arc_store.consolidated_git.catalog_serialize import extract_catalog_dataset
from middleware.api.arc_store.consolidated_git.schema_org_context import load_schema_org_context
from middleware.shared.json_types import RoCrateContent


def test_materialize_landing_page_comment_sets_url() -> None:
    """Landing Page Comment becomes Dataset url (@id shape) and is consumed."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "#LDComment_Landing_Page",
                    "@type": "Comment",
                    "name": "Landing Page",
                    "text": "  https://example.org/landing\n",
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-LANDING",
                    "name": "Landing dataset",
                    "comment": {"@id": "#LDComment_Landing_Page"},
                },
            ],
        },
    )
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    assert record.get("url") == {"@id": "https://example.org/landing"}
    assert "comment" not in record


def test_materialize_landing_page_does_not_overwrite_existing_url() -> None:
    """Existing Dataset url wins; Landing Page Comment is still consumed."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "#LDComment_Landing_Page",
                    "@type": "Comment",
                    "name": "Landing Page",
                    "text": "https://example.org/landing",
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-LANDING-KEEP",
                    "name": "Has url",
                    "url": {"@id": "https://doi.org/10.1234/example"},
                    "comment": {"@id": "#LDComment_Landing_Page"},
                },
            ],
        },
    )
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    assert record.get("url") == {"@id": "https://doi.org/10.1234/example"}
    assert "comment" not in record


def test_materialize_without_landing_page_leaves_url_unset() -> None:
    """No Landing Page Comment → materialize does not invent url."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-NO-LANDING",
                    "name": "No landing",
                },
            ],
        },
    )
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    assert "url" not in record


def test_materialize_landing_page_url_survives_compact() -> None:
    """Landing Page url @id shape compactifies to the url term (not schema:url)."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "#LDComment_Landing_Page",
                    "@type": "Comment",
                    "name": "Landing Page",
                    "text": "https://example.org/landing",
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-LANDING-COMPACT",
                    "name": "Landing compact",
                    "comment": {"@id": "#LDComment_Landing_Page"},
                },
            ],
        },
    )
    materialized = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    compacted = compact_catalog_dataset(
        materialized,
        build_catalog_compact_context(load_schema_org_context()),
        emitted_context=build_catalog_emitted_context(),
    )
    assert compacted.get("url") == "https://example.org/landing"
    assert "schema:url" not in compacted
