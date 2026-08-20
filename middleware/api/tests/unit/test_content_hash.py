"""Unit tests for RO-Crate content-hash normalization."""

import hashlib
import json

from middleware.api.document_store.content_hash import (
    RoCrateContent,
    calculate_arc_content_hash,
    canonicalize_rocrate_for_hash,
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
                "dateCreated": "2026-01-01",
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

    graph = stripped.get("@graph")
    assert isinstance(graph, list)
    root = graph[0]
    study = graph[1]
    assert isinstance(root, dict)
    assert isinstance(study, dict)

    assert "dateCreated" not in root
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
                "dateCreated": "2024-01-15",
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
                "dateCreated": "2026-08-11",
                "datePublished": "2026-07-01T11:19:33.494",
                "sdDatePublished": "2026-07-01T11:19:33.557",
            },
            {"@id": "#study", "dateModified": "2026-07-01T11:19:33.522", "name": "Study"},
        ],
    }

    assert calculate_arc_content_hash(base) == calculate_arc_content_hash(refreshed)


def test_calculate_arc_content_hash_ignores_date_modified_only_differences() -> None:
    """Only ``dateModified`` differences must not change the ARC content hash."""
    base: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "dateCreated": "2024-01-15",
                "datePublished": "2026-01-01T10:00:00.111",
                "sdDatePublished": "2026-01-01T10:00:00.112",
                "nested": {"dateModified": "2026-01-01T10:00:00.200"},
            },
            {"@id": "#study", "name": "Study", "dateModified": "2026-01-01T10:00:00.201"},
        ],
    }
    changed: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "dateCreated": "2024-01-15",
                "datePublished": "2026-01-01T10:00:00.111",
                "sdDatePublished": "2026-01-01T10:00:00.112",
                "nested": {"dateModified": "2026-01-02T11:11:11.222"},
            },
            {"@id": "#study", "name": "Study", "dateModified": "2026-01-02T11:11:11.333"},
        ],
    }

    assert calculate_arc_content_hash(base) == calculate_arc_content_hash(changed)


def test_calculate_arc_content_hash_ignores_haspart_list_order() -> None:
    """Permuting RO-Crate reference lists (e.g. ``hasPart``) must not change the hash."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "hasPart": [{"@id": "#assay-a"}, {"@id": "#assay-b"}],
            },
            {"@id": "#assay-a", "name": "Assay A"},
            {"@id": "#assay-b", "name": "Assay B"},
        ],
    }

    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "hasPart": [{"@id": "#assay-b"}, {"@id": "#assay-a"}],
            },
            {"@id": "#assay-a", "name": "Assay A"},
            {"@id": "#assay-b", "name": "Assay B"},
        ],
    }

    assert calculate_arc_content_hash(arc_a) == calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_preserves_non_allowlisted_list_order() -> None:
    """Non-allowlisted reference-list properties must keep their original order semantics."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "creator": [{"@id": "#person-a"}, {"@id": "#person-b"}],
            },
            {"@id": "#person-a", "name": "Person A"},
            {"@id": "#person-b", "name": "Person B"},
        ],
    }

    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "creator": [{"@id": "#person-b"}, {"@id": "#person-a"}],
            },
            {"@id": "#person-a", "name": "Person A"},
            {"@id": "#person-b", "name": "Person B"},
        ],
    }

    assert calculate_arc_content_hash(arc_a) != calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_ignores_graph_order() -> None:
    """``@graph`` node order must not affect the content hash."""
    first: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {"@id": "./", "identifier": "arc-1"},
            {"@id": "#study", "name": "Study"},
        ],
    }
    reordered: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {"@id": "#study", "name": "Study"},
            {"@id": "./", "identifier": "arc-1"},
        ],
    }

    assert calculate_arc_content_hash(first) == calculate_arc_content_hash(reordered)
    assert calculate_arc_content_hash(first) == calculate_arc_content_hash(canonicalize_rocrate_for_hash(reordered))


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


def test_calculate_arc_content_hash_ignores_keywords_join_order() -> None:
    """Permuting Schema.org keyword joins must not change the ARC content hash.

    Harvesters may emit the same keyword *set* in different RDF object orders.
    That changes Investigation Comment / Data-Collection ParameterValue strings and
    the arctrl ``@id``s derived from them (``#LDComment_Keywords_…``,
    ``#ParameterValue_Keywords_…``) without a semantic content change.
    """
    keywords_a = "DEPTH, water, Longitude of event, Trawling time, Event label"
    keywords_b = "Longitude of event, Event label, DEPTH, water, Trawling time"
    expected_sorted = "DEPTH, Event label, Longitude of event, Trawling time, water"

    def _arc_with_keywords(joined: str) -> RoCrateContent:
        comment_id = f"#LDComment_Keywords_{joined.replace(' ', '_')}"
        param_id = f"#ParameterValue_Keywords_{joined.replace(' ', '_')}"
        return {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "identifier": "10.1594/PANGAEA.874745",
                    "comment": {"@id": comment_id},
                },
                {
                    "@id": comment_id,
                    "@type": "Comment",
                    "name": "Keywords",
                    "text": joined,
                },
                {
                    "@id": param_id,
                    "@type": "PropertyValue",
                    "additionalType": "ParameterValue",
                    "name": "Keywords",
                    "value": joined,
                },
                {
                    "@id": "#Process_Data_Collection",
                    "parameterValue": {"@id": param_id},
                },
            ],
        }

    arc_a = _arc_with_keywords(keywords_a)
    arc_b = _arc_with_keywords(keywords_b)

    assert calculate_arc_content_hash(arc_a) == calculate_arc_content_hash(arc_b)

    canonical = canonicalize_rocrate_for_hash(arc_a)
    graph = canonical.get("@graph")
    assert isinstance(graph, list)
    by_id = {item["@id"]: item for item in graph if isinstance(item, dict) and isinstance(item.get("@id"), str)}
    comment = by_id[f"#LDComment_Keywords_{expected_sorted.replace(' ', '_')}"]
    param = by_id[f"#ParameterValue_Keywords_{expected_sorted.replace(' ', '_')}"]
    assert isinstance(comment, dict)
    assert isinstance(param, dict)
    assert comment["text"] == expected_sorted
    assert param["value"] == expected_sorted
    root = by_id["./"]
    assert isinstance(root, dict)
    assert root["comment"] == {"@id": comment["@id"]}


def test_calculate_arc_content_hash_detects_different_keyword_sets() -> None:
    """Different keyword membership must still change the hash."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "#LDComment_Keywords_DEPTH,_water",
                "@type": "Comment",
                "name": "Keywords",
                "text": "DEPTH, water",
            },
        ],
    }
    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "#LDComment_Keywords_DEPTH,_salinity",
                "@type": "Comment",
                "name": "Keywords",
                "text": "DEPTH, salinity",
            },
        ],
    }

    assert calculate_arc_content_hash(arc_a) != calculate_arc_content_hash(arc_b)
