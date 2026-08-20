"""Content-hash helpers for RO-Crate change detection."""

from __future__ import annotations

import hashlib
import json
from typing import cast

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

# RO-Crate properties that behave like unordered reference sets for hashing.
_ORDER_INSENSITIVE_REFERENCE_LIST_FIELDS = frozenset({
    "hasPart",
})

# Schema.org / OpenAgrar mappers join unordered keyword sets with this separator.
# Permuting the join changes Comment/ParameterValue payloads and arctrl-derived ``@id``s.
_KEYWORDS_JOIN_SEP = ", "
_KEYWORDS_NAME = "Keywords"
_KEYWORDS_ID_MARKER = "_Keywords_"
_KEYWORDS_PAYLOAD_FIELDS = ("text", "value")


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


def _join_keywords_sorted(payload: str) -> str:
    """Return a lexicographically sorted ``", "``-joined keyword string."""
    parts = [part.strip() for part in payload.split(_KEYWORDS_JOIN_SEP) if part.strip()]
    return _KEYWORDS_JOIN_SEP.join(sorted(parts))


def _encode_keywords_for_arc_id(joined: str) -> str:
    """Match arctrl-style ``@id`` encoding for keyword joins (spaces → underscores)."""
    return joined.replace(" ", "_")


def _normalize_keywords_node(node: dict[str, JsonValue]) -> dict[str, str]:
    """Sort Keywords payloads in *node*; return ``{old_@id: new_@id}`` remaps."""
    if node.get("name") != _KEYWORDS_NAME:
        return {}

    payload_key: str | None = None
    for key in _KEYWORDS_PAYLOAD_FIELDS:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            payload_key = key
            break
    if payload_key is None:
        return {}

    old_payload = cast(str, node[payload_key])
    new_payload = _join_keywords_sorted(old_payload)
    node[payload_key] = new_payload

    remaps: dict[str, str] = {}
    old_id = node.get("@id")
    if not isinstance(old_id, str) or _KEYWORDS_ID_MARKER not in old_id:
        return remaps

    prefix, _, _old_suffix = old_id.partition(_KEYWORDS_ID_MARKER)
    new_id = f"{prefix}{_KEYWORDS_ID_MARKER}{_encode_keywords_for_arc_id(new_payload)}"
    if new_id != old_id:
        remaps[old_id] = new_id
        node["@id"] = new_id
    return remaps


def _apply_id_remaps(node: JsonValue, remaps: dict[str, str]) -> JsonValue:
    """Rewrite ``@id`` values that point at remapped Keywords nodes."""
    if not remaps:
        return node
    if isinstance(node, dict):
        rewritten: dict[str, JsonValue] = {}
        for key, item in node.items():
            if key == "@id" and isinstance(item, str) and item in remaps:
                rewritten[key] = remaps[item]
            else:
                rewritten[key] = _apply_id_remaps(item, remaps)
        return rewritten
    if isinstance(node, list):
        return [_apply_id_remaps(elem, remaps) for elem in node]
    return node


def _canonicalize_json_for_hash(
    node: JsonValue,
    *,
    parent_key: str | None = None,
    id_remaps: dict[str, str] | None = None,
) -> JsonValue:
    """Canonicalize RO-Crate JSON for stable hashing.

    In addition to excluding volatile timestamp fields (done upstream),
    this normalizes deterministic ordering for certain RO-Crate structures:

    - ``@graph`` nodes remain handled by the caller (see ``canonicalize_rocrate_for_hash``).
    - For allowlisted reference-list properties such as ``hasPart``: if every element is a
      dict with a string ``@id``, sort deterministically by it.
    - Nodes named ``Keywords`` get a sorted join string (and stable ``@id``) so RDF object
      order from harvesters does not churn the content hash.
    """
    if isinstance(node, dict):
        canonical: dict[str, JsonValue] = {}
        for key, item in node.items():
            if key == "@graph" and isinstance(item, list):
                # Keep graph ordering handling in the caller: we only canonicalize nodes.
                canonical[key] = [_canonicalize_json_for_hash(n, id_remaps=id_remaps) for n in item]
                continue
            canonical[key] = _canonicalize_json_for_hash(item, parent_key=key, id_remaps=id_remaps)
        if id_remaps is not None:
            id_remaps.update(_normalize_keywords_node(canonical))
        return canonical

    if isinstance(node, list):
        canonical_elems = [_canonicalize_json_for_hash(elem, id_remaps=id_remaps) for elem in node]

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
    id_remaps: dict[str, str] = {}

    canonical: RoCrateContent = {}
    for key, item in stripped.items():
        if key == "@graph" and isinstance(item, list):
            canonical_nodes = [_canonicalize_json_for_hash(n, id_remaps=id_remaps) for n in item]
            canonical[key] = sorted(canonical_nodes, key=_graph_sort_key)
        else:
            canonical[key] = _canonicalize_json_for_hash(item, id_remaps=id_remaps)

    if not id_remaps:
        return canonical

    remapped = _apply_id_remaps(canonical, id_remaps)
    if not isinstance(remapped, dict):
        msg = "RO-Crate content must be a JSON object"
        raise TypeError(msg)

    graph = remapped.get("@graph")
    if isinstance(graph, list):
        remapped["@graph"] = sorted(graph, key=_graph_sort_key)
    return cast(RoCrateContent, remapped)


def calculate_arc_content_hash(arc_content: RoCrateContent) -> str:
    """SHA-256 of normalized RO-Crate JSON (volatile timestamps excluded)."""
    normalized = canonicalize_rocrate_for_hash(arc_content)
    json_str = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
