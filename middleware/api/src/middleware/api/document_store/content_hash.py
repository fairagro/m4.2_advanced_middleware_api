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
# Only applied when every list element is a dict with a string ``@id`` (safe heuristic).
# Language preference and blank-node comment text are intentionally NOT normalized here.
_ORDER_INSENSITIVE_REFERENCE_LIST_FIELDS = frozenset({
    "hasPart",
    "creator",
    "author",
    "contributor",
    # Investigation/root often links Comments via ``[{"@id": …}, …]``; order is not semantic.
    "comment",
})

# Comment ``name`` whose textual payload is treated as an unordered keyword multiset.
_KEYWORDS_COMMENT_NAME = "Keywords"
_KEYWORDS_TEXT_FIELDS = ("text", "value")


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


def _canonicalize_keyword_join(text: str) -> str:
    """Comma-split, strip, drop empties, casefold-sort, rejoin with comma-space."""
    tokens = [part.strip() for part in text.split(",")]
    tokens = [token for token in tokens if token]
    tokens.sort(key=str.casefold)
    return ", ".join(tokens)


def _canonicalize_keywords_comments(content: RoCrateContent) -> dict[str, str]:
    """Canonicalize Keywords comment text/value; return old→new join replacements."""
    replacements: dict[str, str] = {}
    graph = content.get("@graph")
    if not isinstance(graph, list):
        return replacements

    for node in graph:
        if not isinstance(node, dict):
            continue
        if node.get("name") != _KEYWORDS_COMMENT_NAME:
            continue
        for field in _KEYWORDS_TEXT_FIELDS:
            value = node.get(field)
            if not isinstance(value, str):
                continue
            canonical = _canonicalize_keyword_join(value)
            if canonical != value:
                replacements[value] = canonical
            node[field] = canonical
    return replacements


def _rewrite_id_string(id_value: str, replacements: dict[str, str]) -> str:
    """Apply keyword-join replacements inside an ``@id`` (raw and space→underscore forms)."""
    result = id_value
    for old, new in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if old in result:
            result = result.replace(old, new)
        old_underscore = old.replace(" ", "_")
        new_underscore = new.replace(" ", "_")
        if old_underscore != old and old_underscore in result:
            result = result.replace(old_underscore, new_underscore)
    return result


def _rewrite_ids_for_keyword_joins(node: JsonValue, replacements: dict[str, str]) -> JsonValue:
    """Rewrite ``@id`` strings (and nested structures) using keyword-join replacements."""
    if isinstance(node, dict):
        rewritten: dict[str, JsonValue] = {}
        for key, item in node.items():
            if key == "@id" and isinstance(item, str):
                rewritten[key] = _rewrite_id_string(item, replacements)
            else:
                rewritten[key] = _rewrite_ids_for_keyword_joins(item, replacements)
        return rewritten
    if isinstance(node, list):
        return [_rewrite_ids_for_keyword_joins(item, replacements) for item in node]
    return node


def _graph_sort_key(node: JsonValue) -> tuple[str, str]:
    """Stable sort key for ``@graph`` nodes (order must not affect the content hash)."""
    if isinstance(node, dict):
        node_id = node.get("@id")
        id_part = node_id if isinstance(node_id, str) else ""
        return (id_part, json.dumps(node, sort_keys=True))
    return ("", json.dumps(node, sort_keys=True))


def _canonicalize_json_for_hash(node: JsonValue, *, parent_key: str | None = None) -> JsonValue:
    """Canonicalize RO-Crate JSON for stable hashing.

    In addition to excluding volatile timestamp fields and Keywords joins (done upstream),
    this normalizes deterministic ordering for certain RO-Crate structures:

    - ``@graph`` nodes remain handled by the caller (see ``canonicalize_rocrate_for_hash``).
    - For allowlisted reference-list properties (``hasPart``, ``creator``, …): if every
      element is a dict with a string ``@id``, sort deterministically by it.
    - Homogeneous string ``keywords`` arrays are sorted casefold.
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

        # Schema.org-style keywords arrays: unordered string multisets.
        if parent_key == "keywords" and all(isinstance(elem, str) for elem in canonical_elems):
            string_elems = cast(list[str], canonical_elems)
            return cast(
                JsonValue,
                sorted(string_elems, key=lambda item: item.casefold()),
            )

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
    replacements = _canonicalize_keywords_comments(stripped)
    if replacements:
        rewritten = _rewrite_ids_for_keyword_joins(stripped, replacements)
        if not isinstance(rewritten, dict):
            msg = "RO-Crate content must be a JSON object"
            raise TypeError(msg)
        stripped = rewritten

    canonical: RoCrateContent = {}
    for key, item in stripped.items():
        if key == "@graph" and isinstance(item, list):
            canonical_nodes = [_canonicalize_json_for_hash(n) for n in item]
            canonical[key] = sorted(canonical_nodes, key=_graph_sort_key)
        else:
            canonical[key] = _canonicalize_json_for_hash(item)
    return canonical


def calculate_arc_content_hash(arc_content: RoCrateContent) -> str:
    """SHA-256 of normalized RO-Crate JSON (volatile timestamps / order noise excluded)."""
    normalized = canonicalize_rocrate_for_hash(arc_content)
    json_str = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
