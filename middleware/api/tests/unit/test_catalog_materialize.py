"""Unit tests for catalog Dataset reference materialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from middleware.api.arc_store.consolidated_git.catalog_jsonld import (
    CATALOG_JSONLD_COMPACT_BASE_IRI,
    build_catalog_compact_context,
    build_catalog_emitted_context,
    compact_catalog_dataset,
    normalize_catalog_datasets,
)
from middleware.api.arc_store.consolidated_git.catalog_materialize import materialize_catalog_dataset
from middleware.api.arc_store.consolidated_git.catalog_serialize import extract_catalog_dataset
from middleware.api.arc_store.consolidated_git.schema_org_context import load_schema_org_context
from middleware.shared.json_types import RoCrateContent

_REPO_ROOT = Path(__file__).resolve().parents[4]
_RO_CRATES = _REPO_ROOT / "ro_crates"


def _load_rocrate(name: str) -> RoCrateContent:
    return cast(RoCrateContent, json.loads((_RO_CRATES / name).read_text(encoding="utf-8")))


def _dangling_ref_arc() -> RoCrateContent:
    """Production-style root with graph-backed Person/Comment refs only on root."""
    return cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "#Person_Kevin_Urbasch",
                    "@type": "Person",
                    "givenName": "Kevin",
                    "familyName": "Urbasch",
                },
                {
                    "@id": "#LDComment_Language_eng",
                    "@type": "Comment",
                    "name": "Language",
                    "text": "eng",
                },
                {
                    "@id": "#LDComment_Keywords_soil,field",
                    "@type": "Comment",
                    "name": "Keywords",
                    "text": "soil, field",
                },
                {
                    "@id": "#LDComment_Notes",
                    "@type": "Comment",
                    "name": "Notes",
                    "text": "fallback comment",
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-DANGLING",
                    "name": "Dangling refs",
                    "creator": {"@id": "#Person_Kevin_Urbasch"},
                    "comment": [
                        {"@id": "#LDComment_Language_eng"},
                        {"@id": "#LDComment_Keywords_soil,field"},
                        {"@id": "#LDComment_Notes"},
                    ],
                },
            ],
        },
    )


def _json_contains_compact_base(value: object) -> bool:
    if isinstance(value, str):
        return CATALOG_JSONLD_COMPACT_BASE_IRI in value
    if isinstance(value, dict):
        return any(_json_contains_compact_base(item) for item in value.values())
    if isinstance(value, list):
        return any(_json_contains_compact_base(item) for item in value)
    return False


def test_materialize_person_inline_without_fragment_id() -> None:
    """Person refs resolve to givenName/familyName without fragment @id."""
    arc = _dangling_ref_arc()
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    creator = record.get("creator")
    assert isinstance(creator, dict)
    assert creator.get("givenName") == "Kevin"
    assert creator.get("familyName") == "Urbasch"
    assert "@id" not in creator
    assert "id" not in creator


def test_materialize_ldcomment_maps_keywords_and_language() -> None:
    """LDComment Keywords/Language become schema.org properties."""
    arc = _dangling_ref_arc()
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    assert record.get("inLanguage") == "eng"
    assert record.get("keywords") == ["soil", "field"]
    comment = record.get("comment")
    assert isinstance(comment, dict)
    assert comment.get("name") == "Notes"
    assert comment.get("text") == "fallback comment"
    assert "@id" not in comment


def test_materialize_license_text_from_edaphobase_pattern() -> None:
    """#LICENSE CreativeWork text becomes inline CreativeWork license."""
    arc = _load_rocrate("edaphobase.json")
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    license_value = record.get("license")
    assert isinstance(license_value, dict)
    assert license_value.get("@type") == "CreativeWork"
    assert license_value.get("text") == "ALL RIGHTS RESERVED BY THE AUTHORS"


def test_materialize_license_url() -> None:
    """#LICENSE node url becomes inline CreativeWork license with url."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "#LICENSE",
                    "@type": "CreativeWork",
                    "url": "https://creativecommons.org/licenses/by/4.0/",
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-LIC",
                    "license": {"@id": "#LICENSE"},
                },
            ],
        },
    )
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    license_value = record.get("license")
    assert isinstance(license_value, dict)
    assert license_value.get("url") == "https://creativecommons.org/licenses/by/4.0/"


def test_materialize_has_part_study_and_assay_from_sample() -> None:
    """Root hasPart resolves Study/Assay Dataset nodes from sample RO-Crate."""
    arc = _load_rocrate("sample.json")
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    has_part = record.get("hasPart")
    assert isinstance(has_part, list)
    by_id = {cast(str, part.get("@id")): part for part in has_part if isinstance(part, dict)}
    study = by_id["studies/AthalianaColdStress/"]
    assert study.get("additionalType") == "Study"
    assert study.get("identifier") == "AthalianaColdStress"
    creators = study.get("creator")
    assert isinstance(creators, list)
    first_creator = creators[0]
    assert isinstance(first_creator, dict)
    assert first_creator.get("givenName") == "Jasmine"
    assay = by_id["assays/Proteomics_MS/"]
    assert assay.get("additionalType") == "Assay"
    assert assay.get("identifier") == "Proteomics_MS"


def test_materialize_citation_without_nested_comment() -> None:
    """Citation resolves ScholarlyArticle fields; nested Comment is omitted."""
    arc = _load_rocrate("sample.json")
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    citation = record.get("citation")
    assert isinstance(citation, dict)
    assert citation.get("headline") == "test"
    assert "comment" not in citation
    assert "creativeWorkStatus" not in citation


def test_materialize_missing_reference_is_omitted() -> None:
    """Missing @graph targets drop the property instead of failing."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-MISSING",
                    "creator": {"@id": "#Person_Missing"},
                },
            ],
        },
    )
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    assert "creator" not in record


@pytest.mark.asyncio
async def test_materialize_then_normalize_emits_schema_org_context() -> None:
    """Materialize + normalize keeps schema.org @context and avoids example.org."""
    arc = _dangling_ref_arc()
    materialized = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    normalized = await normalize_catalog_datasets([materialized])
    compacted = normalized[0]
    assert compacted["@context"] == build_catalog_emitted_context()
    data_without_context = {key: value for key, value in compacted.items() if key != "@context"}
    assert not _json_contains_compact_base(data_without_context)
    creator = compacted.get("creator")
    assert isinstance(creator, dict)
    assert creator.get("givenName") == "Kevin"
    assert creator.get("familyName") == "Urbasch"
    assert creator.get("id") is None
    assert creator.get("@id") is None


def test_materialize_author_and_contributor() -> None:
    """Author and contributor use the same Person materialization rules."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {"@id": "#Person_A", "@type": "Person", "givenName": "Ann"},
                {"@id": "#Person_B", "@type": "Person", "givenName": "Bob"},
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-ROLES",
                    "author": {"@id": "#Person_A"},
                    "contributor": {"@id": "#Person_B"},
                },
            ],
        },
    )
    record = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    author = record.get("author")
    contributor = record.get("contributor")
    assert isinstance(author, dict)
    assert isinstance(contributor, dict)
    assert author.get("givenName") == "Ann"
    assert contributor.get("givenName") == "Bob"


def _materialized_arctrl_arc() -> RoCrateContent:
    return cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "#LICENSE",
                    "@type": "CreativeWork",
                    "text": "CC-BY 4.0",
                },
                {
                    "@id": "#Person_1",
                    "@type": "Person",
                    "givenName": "Ada",
                    "familyName": "Lovelace",
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
                    "headline": "Example paper",
                },
                {
                    "@id": "assays/assay-a/",
                    "@type": "Dataset",
                    "additionalType": "Assay",
                    "identifier": "assay-a",
                    "name": "Assay A",
                },
                {
                    "@id": "./",
                    "@type": "Dataset",
                    "identifier": "DS-ARCTRL",
                    "name": "ARCtrl-shaped dataset",
                    "license": {"@id": "#LICENSE"},
                    "creator": {"@id": "#Person_1"},
                    "hasPart": {"@id": "assays/assay-a/"},
                    "comment": {"@id": "#LDComment_1"},
                    "citation": {"@id": "#citation_1"},
                    "url": {"@id": "https://doi.org/10.1234/example"},
                },
            ],
        },
    )


def test_materialized_compact_pipeline() -> None:
    """After materialize, compact emits inline data and relative path ids."""
    arc = _materialized_arctrl_arc()
    materialized = materialize_catalog_dataset(extract_catalog_dataset(arc), arc)
    compact_ctx = build_catalog_compact_context(load_schema_org_context())
    compacted = compact_catalog_dataset(
        materialized,
        compact_ctx,
        emitted_context=build_catalog_emitted_context(),
    )
    creator = compacted.get("creator")
    has_part = compacted.get("hasPart")
    citation = compacted.get("citation")
    assert compacted.get("license") == {"type": "CreativeWork", "text": "CC-BY 4.0"}
    assert isinstance(creator, dict)
    assert creator.get("givenName") == "Ada"
    assert "id" not in creator
    assert creator.get("sameAs") == "https://orcid.org/0000-0002-1825-0097"
    assert isinstance(has_part, dict)
    assert has_part.get("id") == "assays/assay-a/"
    assert isinstance(citation, dict)
    assert citation.get("headline") == "Example paper"
    assert "comment" not in citation
