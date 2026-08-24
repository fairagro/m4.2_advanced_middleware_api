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


def _arc_with_person_refs(field: str, person_ids: list[str]) -> RoCrateContent:
    return {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                field: [{"@id": pid} for pid in person_ids],
            },
            {"@id": "#person-a", "name": "Person A"},
            {"@id": "#person-b", "name": "Person B"},
        ],
    }


def test_calculate_arc_content_hash_ignores_creator_list_order() -> None:
    """Permuting ``creator`` ``@id`` refs must not change the hash."""
    arc_a = _arc_with_person_refs("creator", ["#person-a", "#person-b"])
    arc_b = _arc_with_person_refs("creator", ["#person-b", "#person-a"])
    assert calculate_arc_content_hash(arc_a) == calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_ignores_author_list_order() -> None:
    """Permuting ``author`` ``@id`` refs must not change the hash."""
    arc_a = _arc_with_person_refs("author", ["#person-a", "#person-b"])
    arc_b = _arc_with_person_refs("author", ["#person-b", "#person-a"])
    assert calculate_arc_content_hash(arc_a) == calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_ignores_contributor_list_order() -> None:
    """Permuting ``contributor`` ``@id`` refs must not change the hash."""
    arc_a = _arc_with_person_refs("contributor", ["#person-a", "#person-b"])
    arc_b = _arc_with_person_refs("contributor", ["#person-b", "#person-a"])
    assert calculate_arc_content_hash(arc_a) == calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_ignores_comment_ref_list_order() -> None:
    """Permuting ``comment`` ``@id`` refs must not change the hash."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "comment": [{"@id": "#c-a"}, {"@id": "#c-b"}],
            },
            {"@id": "#c-a", "@type": "Comment", "name": "License", "text": "CC-BY"},
            {"@id": "#c-b", "@type": "Comment", "name": "Publisher", "text": "Zenodo"},
        ],
    }
    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "comment": [{"@id": "#c-b"}, {"@id": "#c-a"}],
            },
            {"@id": "#c-a", "@type": "Comment", "name": "License", "text": "CC-BY"},
            {"@id": "#c-b", "@type": "Comment", "name": "Publisher", "text": "Zenodo"},
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
                "editor": [{"@id": "#person-a"}, {"@id": "#person-b"}],
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
                "editor": [{"@id": "#person-b"}, {"@id": "#person-a"}],
            },
            {"@id": "#person-a", "name": "Person A"},
            {"@id": "#person-b", "name": "Person B"},
        ],
    }

    assert calculate_arc_content_hash(arc_a) != calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_preserves_order_when_list_lacks_uniform_id_refs() -> None:
    """Allowlisted fields stay order-sensitive when elements are not all ``{@id}`` dicts."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "creator": ["Alice", "Bob"],
            },
        ],
    }
    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "creator": ["Bob", "Alice"],
            },
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


def test_calculate_arc_content_hash_ignores_keyword_join_permutation() -> None:
    """Keywords comment token order (and join-derived ``@id``s) must not change the hash."""
    keywords_a = "DEPTH, water, Longitude of event"
    keywords_b = "Longitude of event, DEPTH, water"

    def _arc_with_keywords(joined: str) -> RoCrateContent:
        comment_id = f"#LDComment_Keywords_{joined.replace(' ', '_')}"
        param_id = f"#ParameterValue_Keywords_{joined.replace(' ', '_')}"
        return {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "./",
                    "identifier": "arc-1",
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
                    "name": "Keywords",
                    "value": joined,
                },
            ],
        }

    assert calculate_arc_content_hash(_arc_with_keywords(keywords_a)) == calculate_arc_content_hash(
        _arc_with_keywords(keywords_b)
    )


def test_calculate_arc_content_hash_ignores_keyword_casefold_tie_order() -> None:
    """Tokens that casefold equal must still canonicalize to a total order."""
    keywords_a = "Depth, DEPTH, water"
    keywords_b = "DEPTH, water, Depth"

    def _arc_with_keywords(joined: str) -> RoCrateContent:
        comment_id = f"#LDComment_Keywords_{joined.replace(' ', '_')}"
        return {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {"@id": "./", "identifier": "arc-1", "comment": {"@id": comment_id}},
                {
                    "@id": comment_id,
                    "@type": "Comment",
                    "name": "Keywords",
                    "text": joined,
                },
            ],
        }

    assert calculate_arc_content_hash(_arc_with_keywords(keywords_a)) == calculate_arc_content_hash(
        _arc_with_keywords(keywords_b)
    )


def test_calculate_arc_content_hash_ignores_keywords_array_casefold_tie_order() -> None:
    """Homogeneous keywords arrays with casefold ties must not depend on input order."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc-1", "keywords": ["Depth", "water", "DEPTH"]}],
    }
    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc-1", "keywords": ["DEPTH", "Depth", "water"]}],
    }
    assert calculate_arc_content_hash(arc_a) == calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_preserves_untyped_keywords_named_node_order() -> None:
    """Nodes named Keywords without a known payload ``@type`` stay order-sensitive."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "#other",
                "name": "Keywords",
                "text": "DEPTH, water",
            },
        ],
    }
    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "#other",
                "name": "Keywords",
                "text": "water, DEPTH",
            },
        ],
    }
    assert calculate_arc_content_hash(arc_a) != calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_detects_keyword_set_change() -> None:
    """A real Keywords token membership change must change the hash."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "#LDComment_Keywords_a",
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
                "@id": "#LDComment_Keywords_b",
                "@type": "Comment",
                "name": "Keywords",
                "text": "DEPTH, soil",
            },
        ],
    }
    assert calculate_arc_content_hash(arc_a) != calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_ignores_keywords_array_order() -> None:
    """Homogeneous string ``keywords`` arrays are order-insensitive for hashing."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc-1", "keywords": ["water", "DEPTH", "soil"]}],
    }
    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc-1", "keywords": ["soil", "water", "DEPTH"]}],
    }
    assert calculate_arc_content_hash(arc_a) == calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_preserves_mixed_keywords_array_order() -> None:
    """Mixed-type ``keywords`` arrays must remain order-sensitive."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "keywords": ["water", {"@id": "#kw"}],
            },
        ],
    }
    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "identifier": "arc-1",
                "keywords": [{"@id": "#kw"}, "water"],
            },
        ],
    }
    assert calculate_arc_content_hash(arc_a) != calculate_arc_content_hash(arc_b)


def test_calculate_arc_content_hash_treats_description_language_swap_as_change() -> None:
    """Different description literals must change the hash (not normalized away)."""
    arc_de: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc-1", "description": "Deutscher Text"}],
    }
    arc_en: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [{"@id": "./", "identifier": "arc-1", "description": "English text"}],
    }
    assert calculate_arc_content_hash(arc_de) != calculate_arc_content_hash(arc_en)


def test_calculate_arc_content_hash_treats_blank_node_comment_text_as_change() -> None:
    """Blank-node label comment text remains a hash change (Harvester must not persist it)."""
    arc_a: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "#LDComment_contributorOrder_Nad019e26cbb748fc8af372d30f5d9946",
                "@type": "Comment",
                "name": "contributorOrder",
                "text": "Nad019e26cbb748fc8af372d30f5d9946",
            },
        ],
    }
    arc_b: RoCrateContent = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "#LDComment_contributorOrder_N47faa23a0594409ea973e49159e269a7",
                "@type": "Comment",
                "name": "contributorOrder",
                "text": "N47faa23a0594409ea973e49159e269a7",
            },
        ],
    }
    assert calculate_arc_content_hash(arc_a) != calculate_arc_content_hash(arc_b)
