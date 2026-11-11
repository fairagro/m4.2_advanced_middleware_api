"""Unit tests for catalog JSON-LD expand/compact and vendored schema.org context."""

from __future__ import annotations

from typing import cast

import pytest

from middleware.api.arc_store.consolidated_git.catalog_jsonld import (
    CATALOG_JSONLD_COMPACT_BASE_IRI,
    SCHEMA_ORG_CONTEXT_IRI,
    build_catalog_compact_context,
    build_catalog_emitted_context,
    compact_catalog_dataset,
    normalize_catalog_datasets,
    normalize_catalog_datasets_best_effort,
)
from middleware.api.arc_store.consolidated_git.catalog_jsonld_dump_shape import CATALOG_DUMP_SHAPE_CONTEXT
from middleware.api.arc_store.consolidated_git.catalog_jsonld_extensions import ARC_BIOSCHEMAS_EXTENSION_CONTEXT
from middleware.api.arc_store.consolidated_git.catalog_materialize import materialize_catalog_dataset
from middleware.api.arc_store.consolidated_git.catalog_serialize import extract_catalog_dataset
from middleware.api.arc_store.consolidated_git.schema_org_context import load_schema_org_context
from middleware.shared.json_types import CatalogDatasetRecord, JsonObject, RoCrateContent


def _expected_emitted_context() -> list[object]:
    return [
        SCHEMA_ORG_CONTEXT_IRI,
        dict(ARC_BIOSCHEMAS_EXTENSION_CONTEXT),
        dict(CATALOG_DUMP_SHAPE_CONTEXT),
    ]


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


def _json_contains_compact_base(value: object) -> bool:
    """Return True if dummy compact base IRI appears in Dataset data."""
    if isinstance(value, str):
        return CATALOG_JSONLD_COMPACT_BASE_IRI in value
    if isinstance(value, dict):
        return any(_json_contains_compact_base(item) for item in value.values())
    if isinstance(value, list):
        return any(_json_contains_compact_base(item) for item in value)
    return False


def _arctrl_shaped_arc() -> RoCrateContent:
    """RO-Crate with graph nodes backing ARCtrl-shaped root references."""
    return cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "#LICENSE",
                    "@type": "CreativeWork",
                    "text": "ALL RIGHTS RESERVED",
                },
                {
                    "@id": "#Person_1",
                    "@type": "Person",
                    "givenName": "Ada",
                    "name": "Ada",
                    "sameAs": {"@id": "https://orcid.org/0000-0002-1825-0097"},
                },
                {
                    "@id": "#LDComment_1",
                    "@type": "Comment",
                    "name": "Notes",
                    "text": "note",
                },
                {
                    "@id": "#citation_1",
                    "@type": "ScholarlyArticle",
                    "headline": "Paper",
                },
                {
                    "@id": "assays/assay-a/",
                    "@type": "Dataset",
                    "additionalType": "Assay",
                    "identifier": "assay-a",
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-ARCTRL",
                    "name": "ARCtrl-shaped dataset",
                    "license": {"@id": "#LICENSE"},
                    "creator": {"@id": "#Person_1"},
                    "hasPart": {"@id": "assays/assay-a/", "@type": "Dataset"},
                    "comment": {"@id": "#LDComment_1", "text": "note"},
                    "citation": {"@id": "#citation_1"},
                    "url": {"@id": "https://doi.org/10.1234/example"},
                },
            ],
        },
    )


def _arctrl_shaped_dataset() -> CatalogDatasetRecord:
    """Materialized ARCtrl-shaped catalog Dataset (post graph resolution)."""
    arc = _arctrl_shaped_arc()
    return materialize_catalog_dataset(extract_catalog_dataset(arc), arc)


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
    """Compact with vendored document; emit schema.org + ARC/Bioschemas + dump shape."""
    dataset = extract_catalog_dataset(_arc_with_rocrate_and_extension())
    compact_ctx = build_catalog_compact_context(load_schema_org_context())
    emitted_ctx = build_catalog_emitted_context()
    assert emitted_ctx == _expected_emitted_context()
    assert isinstance(compact_ctx, list)
    compact_parts = cast(list[object], compact_ctx)
    assert dict(ARC_BIOSCHEMAS_EXTENSION_CONTEXT) in compact_parts
    assert dict(CATALOG_DUMP_SHAPE_CONTEXT) in compact_parts

    compacted = compact_catalog_dataset(dataset, compact_ctx, emitted_context=emitted_ctx)
    assert compacted["@context"] == emitted_ctx
    assert compacted.get("name") == "Example dataset"
    assert compacted.get("identifier") == "DS-1"
    assert compacted.get("id") == "./"
    assert not _json_contains_compact_base(compacted)
    assert "https://example.org/unknownProp" in compacted


def test_emitted_context_is_schema_org_iri_plus_extensions() -> None:
    """Published @context is schema.org IRI plus ARC/Bioschemas and dump-shape maps."""
    emitted = build_catalog_emitted_context()
    assert emitted == _expected_emitted_context()


@pytest.mark.asyncio
async def test_normalize_byte_stable_with_vendored_context() -> None:
    """Two normalizes with the vendored pin yield identical Dataset bytes."""
    dataset = extract_catalog_dataset(_arc_with_rocrate_and_extension())
    first = await normalize_catalog_datasets([dataset])
    second = await normalize_catalog_datasets([dataset])
    assert first == second


@pytest.mark.asyncio
async def test_normalize_best_effort_preserves_order_with_batched_concurrency() -> None:
    """Batched gather keeps successful Dataset order when concurrency < item count."""
    datasets = [
        cast(CatalogDatasetRecord, extract_catalog_dataset(_arc_with_rocrate_and_extension(f"DS-{index}")))
        for index in range(5)
    ]
    labeled = [(f"arc-{index}", dataset) for index, dataset in enumerate(datasets)]
    outcome = await normalize_catalog_datasets_best_effort(labeled, concurrency=2)
    assert outcome.skipped == []
    assert [item.get("identifier") for item in outcome.datasets] == [f"DS-{index}" for index in range(5)]


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
    assert result[0].get("id", result[0].get("@id")) == "./"


def _compact_arctrl_shaped() -> CatalogDatasetRecord:
    dataset = _arctrl_shaped_dataset()
    compact_ctx = build_catalog_compact_context(load_schema_org_context())
    return compact_catalog_dataset(dataset, compact_ctx, emitted_context=build_catalog_emitted_context())


def test_compact_restores_arctrl_relative_ids() -> None:
    """B1: path @ids stay relative; inlined Person/Comment omit fragment ids."""
    compacted = _compact_arctrl_shaped()
    creators = compacted.get("creator")
    has_parts = compacted.get("hasPart")
    comments = compacted.get("comment")
    citations = compacted.get("citation")
    assert compacted.get("id") == "./"
    assert compacted.get("@id", "./") == "./"
    assert compacted.get("license") == {"type": "CreativeWork", "text": "ALL RIGHTS RESERVED"}
    assert isinstance(creators, list) and len(creators) == 1
    creator = creators[0]
    assert isinstance(creator, dict)
    assert creator.get("givenName") == "Ada"
    assert "id" not in creator
    assert isinstance(has_parts, list) and len(has_parts) == 1
    has_part = has_parts[0]
    assert isinstance(has_part, dict)
    assert has_part.get("id") == "assays/assay-a/"
    assert isinstance(comments, list) and len(comments) == 1
    comment = comments[0]
    assert isinstance(comment, dict)
    assert comment.get("name") == "Notes"
    assert "id" not in comment
    assert isinstance(citations, list) and len(citations) == 1
    citation = citations[0]
    assert isinstance(citation, dict)
    assert citation.get("headline") == "Paper"
    assert "id" not in citation
    data_without_context = {key: value for key, value in compacted.items() if key != "@context"}
    assert not _json_contains_compact_base(data_without_context)


def test_compact_emitted_context_has_no_base() -> None:
    """Public @context stays schema.org + extensions; no @base and no example.org."""
    compacted = _compact_arctrl_shaped()
    emitted = compacted["@context"]
    assert emitted == build_catalog_emitted_context()
    assert emitted == _expected_emitted_context()
    assert "@base" not in str(emitted)
    assert "example.org" not in str(emitted).lower()


def test_compact_preserves_identifier_and_absolute_iris() -> None:
    """Keep identifier and already-absolute HTTP(S) IRIs; keep schema.org short names."""
    compacted = _compact_arctrl_shaped()
    creators = compacted.get("creator")
    assert compacted.get("identifier") == "DS-ARCTRL"
    assert compacted.get("name") == "ARCtrl-shaped dataset"
    assert compacted.get("url") == "https://doi.org/10.1234/example"
    assert isinstance(creators, list) and len(creators) == 1
    creator = creators[0]
    assert isinstance(creator, dict)
    assert creator.get("sameAs") == "https://orcid.org/0000-0002-1825-0097"


def test_compact_dump_shape_unprefixed_dates_and_set_arrays() -> None:
    """Dump-shape context: plain date* keys and @set arrays for single values (#595)."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "#Person_1",
                    "@type": "Person",
                    "givenName": "Ada",
                    "familyName": "Lovelace",
                },
                {
                    "@id": "#LDComment_Keywords_soil",
                    "@type": "Comment",
                    "name": "Keywords",
                    "text": "soil",
                },
                {
                    "@id": "#LDComment_Notes",
                    "@type": "Comment",
                    "name": "Notes",
                    "text": "one note",
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-SHAPE",
                    "name": "Shape fixture",
                    "datePublished": "2024-06-01",
                    "dateCreated": "2024-01-01",
                    "dateModified": "2024-06-02",
                    "sdDatePublished": "2024-06-03",
                    "creator": {"@id": "#Person_1"},
                    "comment": [
                        {"@id": "#LDComment_Keywords_soil"},
                        {"@id": "#LDComment_Notes"},
                    ],
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
    assert compacted.get("datePublished") == "2024-06-01"
    assert compacted.get("dateCreated") == "2024-01-01"
    assert compacted.get("dateModified") == "2024-06-02"
    assert compacted.get("sdDatePublished") == "2024-06-03"
    assert "schema:datePublished" not in compacted
    creators = compacted.get("creator")
    keywords = compacted.get("keywords")
    comments = compacted.get("comment")
    assert isinstance(creators, list) and len(creators) == 1
    assert isinstance(keywords, list) and keywords == ["soil"]
    assert isinstance(comments, list) and len(comments) == 1
    assert isinstance(creators[0], dict)
    assert creators[0].get("givenName") == "Ada"
    assert isinstance(comments[0], dict)
    assert comments[0].get("name") == "Notes"
