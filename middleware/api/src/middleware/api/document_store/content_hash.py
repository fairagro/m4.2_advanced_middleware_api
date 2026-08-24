"""Content-hash helpers for RO-Crate change detection."""

from __future__ import annotations

import hashlib
import json
from typing import cast

from middleware.shared.json_types import JsonValue, RoCrateContent

# Serialization / harvest timestamps that change without semantic ARC edits.
# ISA RO-Crate profile: Submission Date → dateCreated, Public Release Date → datePublished.
# arctrl ToROCrateJsonString() may also refresh datePublished / sdDatePublished / dateModified.
_VOLATILE_ROCRATE_FIELDS = frozenset({
    "dateCreated",
    "datePublished",
    "sdDatePublished",
    "dateModified",
})

# RO-Crate properties that behave like unordered reference sets for hashing.
# Only applied when every list element is a dict with a string ``@id`` (safe heuristic).
# Domain-specific payload noise (keyword join order, blank-node comment text, DE/EN
# description choice) is intentionally NOT normalized here — fix those in harvesters.
_ORDER_INSENSITIVE_REFERENCE_LIST_FIELDS = frozenset({
    "hasPart",
    "creator",
    "author",
    "contributor",
    # Investigation/root often links Comments via ``[{"@id": …}, …]``; order is not semantic.
    "comment",
})


def strip_volatile_rocrate_fields(value: RoCrateContent) -> RoCrateContent:
    """Return a copy of RO-Crate JSON with serialization timestamps removed."""

    def _strip(node: JsonValue) -> JsonValue:
        if isinstance(node, dict):
            return {key: _strip(item) for key, item in node.items() if key not in _VOLATILE_ROCRATE_FIELDS}
        if isinstance(node, list):
            return [_strip(item) for item in node]
        return node

    stripped = _strip(value)
    if not isinstance(stripped, dict):
        msg = "RO-Crate content must be a JSON object"
        raise TypeError(msg)
    return stripped


def _graph_sort_key(node: JsonValue) -> tuple[str, str]:
    """Stable sort key for ``@graph`` nodes (order must not affect the content hash)."""
    if isinstance(node, dict):
        node_id = node.get("@id")
        id_part = node_id if isinstance(node_id, str) else ""
        return (id_part, json.dumps(node, sort_keys=True))
    return ("", json.dumps(node, sort_keys=True))


def _canonicalize_json_for_hash(node: JsonValue, *, parent_key: str | None = None) -> JsonValue:
    """Canonicalize RO-Crate JSON for stable hashing.

    In addition to excluding volatile timestamp fields (done upstream),
    this normalizes deterministic ordering for certain RO-Crate structures:

    - ``@graph`` nodes remain handled by the caller (see ``canonicalize_rocrate_for_hash``).
    - For allowlisted reference-list properties (``hasPart``, ``creator``, …): if every
      element is a dict with a string ``@id``, sort deterministically by it.
    """
    if isinstance(node, dict):
        canonical: dict[str, JsonValue] = {}
        for key, item in node.items():
            if key == "@graph" and isinstance(item, list):
                # Keep graph ordering handling in the caller: we only canonicalize nodes.
                canonical[key] = [_canonicalize_json_for_hash(n) for n in item]
                continue
            canonical[key] = _canonicalize_json_for_hash(item, parent_key=key)
        return canonical

    if isinstance(node, list):
        canonical_elems = [_canonicalize_json_for_hash(elem) for elem in node]

        # Only canonicalize list order for explicitly allowlisted reference properties.
        if parent_key in _ORDER_INSENSITIVE_REFERENCE_LIST_FIELDS and all(
            isinstance(elem, dict) and isinstance(elem.get("@id"), str) for elem in canonical_elems
        ):
            reference_elems: list[dict[str, JsonValue]] = [cast(dict[str, JsonValue], elem) for elem in canonical_elems]

            def _reference_sort_key(elem: dict[str, JsonValue]) -> tuple[str, str]:
                id_part = cast(str, elem["@id"])
                return (id_part, json.dumps(elem, sort_keys=True))

            decorated = [(_reference_sort_key(elem), elem) for elem in reference_elems]
            decorated.sort(key=lambda pair: pair[0])
            return [elem for _, elem in decorated]

        return canonical_elems

    return node


def canonicalize_rocrate_for_hash(value: RoCrateContent) -> RoCrateContent:
    """Strip volatile fields and make RO-Crate JSON order-deterministic for hashing."""
    stripped = strip_volatile_rocrate_fields(value)

    canonical: RoCrateContent = {}
    for key, item in stripped.items():
        if key == "@graph" and isinstance(item, list):
            canonical_nodes = [_canonicalize_json_for_hash(n) for n in item]
            canonical[key] = sorted(canonical_nodes, key=_graph_sort_key)
        else:
            canonical[key] = _canonicalize_json_for_hash(item)
    return canonical


def calculate_arc_content_hash(arc_content: RoCrateContent) -> str:
    """SHA-256 of normalized RO-Crate JSON (volatile timestamps excluded)."""
    normalized = canonicalize_rocrate_for_hash(arc_content)
    json_str = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
