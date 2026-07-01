"""Content-hash helpers for RO-Crate change detection."""

from __future__ import annotations

import hashlib
import json

# JSON shapes produced by ``json.loads`` / consumed by ``json.dumps``.
type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list[JsonValue] | dict[str, JsonValue]

# Top-level RO-Crate document stored in CouchDB (``@context``, ``@graph``, …).
type RoCrateContent = dict[str, JsonValue]

# arctrl ToROCrateJsonString() refreshes these on every serialization even when
# semantic ARC content is unchanged (see arctrl round-trip behaviour).
_VOLATILE_ROCRATE_FIELDS = frozenset({"datePublished", "sdDatePublished", "dateModified"})


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


def calculate_arc_content_hash(arc_content: RoCrateContent) -> str:
    """SHA-256 of normalized RO-Crate JSON (volatile timestamp fields excluded)."""
    normalized = strip_volatile_rocrate_fields(arc_content)
    json_str = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
