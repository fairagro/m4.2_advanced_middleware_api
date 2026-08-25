"""Tests for consolidated catalog Dataset extraction and serialization."""

from typing import cast

from rocrate_fixtures import minimal_rocrate_dict

from middleware.api.arc_store.catalog_serialize import extract_catalog_dataset, serialize_catalog_file
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
    """Dataset array order is stable by ``@id`` and bytes are deterministic."""
    ds_a = cast(CatalogDatasetRecord, {"@id": "https://b.example/ds", "name": "B"})
    ds_b = cast(CatalogDatasetRecord, {"@id": "https://a.example/ds", "name": "A"})
    first = serialize_catalog_file([ds_a, ds_b])
    second = serialize_catalog_file([ds_b, ds_a])
    assert first == second
    assert first.startswith(b"[")


def test_serialize_catalog_file_non_ascii_stable() -> None:
    """Sort-key and payload both use ensure_ascii=False for non-ASCII content."""
    ds_a = cast(CatalogDatasetRecord, {"@id": "https://example.org/ds", "name": "Äpfel"})
    ds_b = cast(CatalogDatasetRecord, {"@id": "https://example.org/ds", "name": "Öl"})
    first = serialize_catalog_file([ds_a, ds_b])
    second = serialize_catalog_file([ds_b, ds_a])
    assert first == second
    assert "Äpfel".encode() in first
    assert b"\\u" not in first
