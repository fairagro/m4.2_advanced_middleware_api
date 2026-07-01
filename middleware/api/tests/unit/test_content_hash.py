"""Unit tests for RO-Crate content-hash normalization."""

import hashlib
import json

from middleware.api.document_store.content_hash import (
    RoCrateContent,
    calculate_arc_content_hash,
    strip_volatile_rocrate_fields,
)


def test_strip_volatile_rocrate_fields_removes_timestamps_recursively() -> None:
    """Volatile fields anywhere in the RO-Crate tree are excluded from hashing."""
    arc: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "datePublished": "2026-01-01T00:00:00.000",
                "sdDatePublished": "2026-01-01T00:00:00.001",
            },
            {
                "@id": "#study",
                "dateModified": "2026-01-02T00:00:00.000",
                "name": "Study",
            },
        ],
    }

    stripped = strip_volatile_rocrate_fields(arc)

    graph = stripped["@graph"]
    assert isinstance(graph, list)
    root = graph[0]
    study = graph[1]
    assert isinstance(root, dict)
    assert isinstance(study, dict)

    assert "datePublished" not in root
    assert "sdDatePublished" not in root
    assert "dateModified" not in study
    assert study["name"] == "Study"


def test_calculate_arc_content_hash_ignores_timestamp_only_differences() -> None:
    """arctrl-style timestamp refresh must not count as a content change."""
    base: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "datePublished": "2026-01-01T10:00:00.111",
                "sdDatePublished": "2026-01-01T10:00:00.112",
            },
            {"@id": "#study", "dateModified": "2026-01-01T10:00:00.200", "name": "Study"},
        ],
    }
    refreshed: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "datePublished": "2026-07-01T11:19:33.494",
                "sdDatePublished": "2026-07-01T11:19:33.557",
            },
            {"@id": "#study", "dateModified": "2026-07-01T11:19:33.522", "name": "Study"},
        ],
    }

    assert calculate_arc_content_hash(base) == calculate_arc_content_hash(refreshed)


def test_calculate_arc_content_hash_detects_real_content_changes() -> None:
    """Semantic differences must still produce a different hash."""
    unchanged: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc-1", "name": "Original"}],
    }
    changed: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc-1", "name": "Updated"}],
    }

    assert calculate_arc_content_hash(unchanged) != calculate_arc_content_hash(changed)


def test_calculate_arc_content_hash_differs_from_legacy_full_json_hash() -> None:
    """Documents stored before normalization used the full JSON hash."""
    arc: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc-1", "datePublished": "2026-01-01T00:00:00.000"}],
    }
    legacy_hash = hashlib.sha256(json.dumps(arc, sort_keys=True).encode("utf-8")).hexdigest()

    assert calculate_arc_content_hash(arc) != legacy_hash
