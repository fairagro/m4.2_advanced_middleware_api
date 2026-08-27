"""Unit tests for catalog JSON-LD expand/compact and vendored schema.org context."""

from __future__ import annotations

from typing import cast

import pytest

from middleware.api.arc_store.consolidated_git.catalog_jsonld import (
    SCHEMA_ORG_CONTEXT_IRI,
    build_catalog_compact_context,
    build_catalog_emitted_context,
    compact_catalog_dataset,
    normalize_catalog_datasets,
)
from middleware.api.arc_store.consolidated_git.catalog_jsonld_extensions import ARC_BIOSCHEMAS_EXTENSION_CONTEXT
from middleware.api.arc_store.consolidated_git.catalog_serialize import extract_catalog_dataset
from middleware.api.arc_store.consolidated_git.schema_org_context import load_schema_org_context
from middleware.shared.json_types import CatalogDatasetRecord, JsonObject, RoCrateContent


def _arc_with_rocrate_and_extension(identifier: str = "DS-1") -> RoCrateContent:
    return cast(
        RoCrateContent,
        {
            "@context": [
                "https://w3id.org/ro/crate/1.1/context",
                {
                    "LabProcess": "https://bioschemas.org/LabProcess",
                    "columnIndex": "https://w3id.org/ro/terms/arc#columnIndex",
                },
            ],
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": identifier,
                    "name": "Example dataset",
                    "https://example.org/unknownProp": "keep-me",
                },
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"},
                },
            ],
        },
    )


def test_extract_preserves_source_context_for_ingest_semantics() -> None:
    """Extraction still attaches source @context (API ingest path unchanged)."""
    arc = _arc_with_rocrate_and_extension()
    dataset = extract_catalog_dataset(arc)
    assert dataset["@context"] == arc["@context"]


def test_vendored_schema_org_context_loads() -> None:
    """Vendored release context is a JSON object with @context."""
    document = load_schema_org_context()
    assert isinstance(document.get("@context"), dict | list | str)


def test_compact_uses_schema_org_and_extension_map() -> None:
    """Compact with vendored document; emit https://schema.org + ARC/Bioschemas map."""
    dataset = extract_catalog_dataset(_arc_with_rocrate_and_extension())
    compact_ctx = build_catalog_compact_context(load_schema_org_context())
    emitted_ctx = build_catalog_emitted_context()
    assert emitted_ctx == [SCHEMA_ORG_CONTEXT_IRI, dict(ARC_BIOSCHEMAS_EXTENSION_CONTEXT)]
    assert isinstance(compact_ctx, list)
    compact_parts = cast(list[object], compact_ctx)
    assert dict(ARC_BIOSCHEMAS_EXTENSION_CONTEXT) in compact_parts

    compacted = compact_catalog_dataset(dataset, compact_ctx, emitted_context=emitted_ctx)
    assert compacted["@context"] == emitted_ctx
    assert compacted.get("name") == "Example dataset"
    assert compacted.get("identifier") == "DS-1"
    assert "https://example.org/unknownProp" in compacted


def test_emitted_context_is_schema_org_iri_plus_extensions() -> None:
    """Published @context is the conventional schema.org IRI, not an inline release map."""
    emitted = build_catalog_emitted_context()
    assert emitted == [SCHEMA_ORG_CONTEXT_IRI, dict(ARC_BIOSCHEMAS_EXTENSION_CONTEXT)]


@pytest.mark.asyncio
async def test_normalize_byte_stable_with_vendored_context() -> None:
    """Two normalizes with the vendored pin yield identical Dataset bytes."""
    dataset = extract_catalog_dataset(_arc_with_rocrate_and_extension())
    first = await normalize_catalog_datasets([dataset])
    second = await normalize_catalog_datasets([dataset])
    assert first == second


@pytest.mark.asyncio
async def test_normalize_optional_injected_document() -> None:
    """Injected schema.org document overrides the vendored file (offline tests)."""
    dataset = cast(CatalogDatasetRecord, extract_catalog_dataset(_arc_with_rocrate_and_extension()))
    minimal: JsonObject = {
        "@context": {
            "@vocab": "http://schema.org/",
            "Dataset": "http://schema.org/Dataset",
            "name": "http://schema.org/name",
            "identifier": "http://schema.org/identifier",
        }
    }
    result = await normalize_catalog_datasets([dataset], schema_org_document=minimal)
    assert result[0]["@context"] == build_catalog_emitted_context()
    assert result[0].get("name") == "Example dataset"
