"""Content-hash helpers for RO-Crate change detection."""

from __future__ import annotations

import hashlib
import json

# JSON shapes produced by ``json.loads`` / consumed by ``json.dumps``.
type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]

# Top-level RO-Crate document stored in CouchDB (``@context``, ``@graph``, …).
type RoCrateContent = dict[str, JsonValue]

# Serialization / harvest timestamps that change without semantic ARC edits.
# ISA RO-Crate profile: Submission Date → dateCreated, Public Release Date → datePublished.
# arctrl ToROCrateJsonString() may also refresh datePublished / sdDatePublished / dateModified.
_VOLATILE_ROCRATE_FIELDS = frozenset({
    "dateCreated",
    "datePublished",
    "sdDatePublished",
    "dateModified",
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


def _canonicalize_json_for_hash(node: JsonValue) -> JsonValue:
    """Canonicalize RO-Crate JSON for stable hashing.

    In addition to excluding volatile timestamp fields (done upstream),
    this normalizes deterministic ordering for certain RO-Crate structures:

    - ``@graph`` nodes remain handled by the caller (see ``canonicalize_rocrate_for_hash``).
    - For other lists: if every element is a dict with a string ``@id``, sort deterministically by it.
    """
    if isinstance(node, dict):
        canonical: dict[str, JsonValue] = {}
        for key, item in node.items():
            if key == "@graph" and isinstance(item, list):
                # Keep graph ordering handling in the caller: we only canonicalize nodes.
                canonical[key] = [_canonicalize_json_for_hash(n) for n in item]
                continue
            canonical[key] = _canonicalize_json_for_hash(item)
        return canonical

    if isinstance(node, list):
        canonical_elems = [_canonicalize_json_for_hash(elem) for elem in node]

        # Heuristic: sort lists of RO-Crate reference objects deterministically.
        # This addresses non-semantic list permutations like ``hasPart`` ordering.
        if all(isinstance(elem, dict) and isinstance(elem.get("@id"), str) for elem in canonical_elems):
            return sorted(
                canonical_elems,  # type: ignore[arg-type]
                key=lambda elem: (
                    elem["@id"],  # type: ignore[index]
                    json.dumps(elem, sort_keys=True),
                ),
            )

        return canonical_elems

    return node


def canonicalize_rocrate_for_hash(value: RoCrateContent) -> RoCrateContent:
    """Strip volatile fields and make RO-Crate JSON order-deterministic for hashing."""
    stripped = strip_volatile_rocrate_fields(value)

    # First normalize list ordering for all nested structures (except @graph, which we
    # keep in its special handling path to avoid changing prior expectations).
    def _canonicalize_root(node: RoCrateContent) -> RoCrateContent:
        canonical: dict[str, JsonValue] = {}
        for key, item in node.items():
            if key == "@graph" and isinstance(item, list):
                canonical_nodes = [_canonicalize_json_for_hash(n) for n in item]
                canonical[key] = sorted(canonical_nodes, key=_graph_sort_key)
            else:
                canonical[key] = _canonicalize_json_for_hash(item)
        return canonical  # type: ignore[return-value]

    return _canonicalize_root(stripped)


def calculate_arc_content_hash(arc_content: RoCrateContent) -> str:
    """SHA-256 of normalized RO-Crate JSON (volatile timestamps excluded)."""
    normalized = canonicalize_rocrate_for_hash(arc_content)
    json_str = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
