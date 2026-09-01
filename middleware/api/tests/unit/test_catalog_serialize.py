"""Tests for consolidated catalog Dataset extraction and serialization."""

from typing import cast

from rocrate_fixtures import minimal_rocrate_dict

from middleware.api.arc_store.consolidated_git.catalog_serialize import (
    catalog_dataset_identifier,
    extract_catalog_dataset,
    serialize_catalog_file,
)
from middleware.shared.json_types import CatalogDatasetRecord, RoCrateContent


def test_extract_root_dataset_prefers_id_dot_slash() -> None:
    """Root Dataset (``@id`` ``./``) is extracted for the catalog."""
    arc = minimal_rocrate_dict("DS-1", name="Example dataset")
    dataset = extract_catalog_dataset(arc)
    assert dataset["@id"] == "./"
    assert dataset["identifier"] == "DS-1"
    assert dataset["@context"] == arc["@context"]


def test_extract_first_dataset_when_no_root() -> None:
    """When no root Dataset, the first Dataset node in ``@graph`` is used."""
    arc = cast(
        RoCrateContent,
        {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {"@id": "./", "@type": "CreativeWork", "name": "not a dataset"},
                {"@id": "https://example.org/ds/1", "@type": "Dataset", "name": "Catalog record"},
            ],
        },
    )
    dataset = extract_catalog_dataset(arc)
    assert dataset["@id"] == "https://example.org/ds/1"


def test_serialize_catalog_file_byte_stable_order() -> None:
    """Dataset array order is stable by ``identifier`` and bytes are deterministic."""
    ds_a = cast(CatalogDatasetRecord, {"identifier": "https://b.example/ds", "name": "B"})
    ds_b = cast(CatalogDatasetRecord, {"identifier": "https://a.example/ds", "name": "A"})
    first = serialize_catalog_file([ds_a, ds_b])
    second = serialize_catalog_file([ds_b, ds_a])
    assert first == second
    assert first.startswith(b"[")
    assert first.index(b"https://a.example/ds") < first.index(b"https://b.example/ds")


def test_serialize_catalog_file_orders_by_identifier_after_compact() -> None:
    """Post-compact records with shared ``id`` sort by normalized ``identifier``."""
    ds_b = cast(
        CatalogDatasetRecord,
        {"id": "./", "identifier": "DS-B", "name": "B"},
    )
    ds_a = cast(
        CatalogDatasetRecord,
        {"id": "./", "identifier": "DS-A", "name": "A"},
    )
    payload = serialize_catalog_file([ds_b, ds_a])
    assert payload.index(b"DS-A") < payload.index(b"DS-B")


def test_serialize_catalog_file_jsonld_identifier_value_object() -> None:
    """JSON-LD ``identifier`` value objects normalize like RO-Crate root entity."""
    ds = cast(
        CatalogDatasetRecord,
        {"id": "./", "identifier": {"@value": "DS-JSONLD"}, "name": "Example"},
    )
    assert catalog_dataset_identifier(ds) == "DS-JSONLD"


def test_serialize_catalog_file_non_ascii_stable() -> None:
    """Duplicate ``identifier`` tie-break uses canonical JSON with ensure_ascii=False."""
    ds_a = cast(CatalogDatasetRecord, {"identifier": "https://example.org/ds", "name": "Äpfel"})
    ds_b = cast(CatalogDatasetRecord, {"identifier": "https://example.org/ds", "name": "Öl"})
    first = serialize_catalog_file([ds_a, ds_b])
    second = serialize_catalog_file([ds_b, ds_a])
    assert first == second
    assert "Äpfel".encode() in first
    assert b"\\u" not in first
