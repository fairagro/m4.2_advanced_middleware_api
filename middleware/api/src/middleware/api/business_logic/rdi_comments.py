"""Embed authorized source RDI as ISA Investigation Comments in RO-Crate JSON."""

from __future__ import annotations

from typing import Final

from middleware.api.business_logic.exceptions import InvalidJsonSemanticError
from middleware.shared.json_types import JsonObject, JsonValue, RoCrateContent, RoCrateGraphNode

COMMENT_NAME_RDI: Final = "RDI"
COMMENT_NAME_DESCRIPTION: Final = "RDI Description"
COMMENT_NAME_URL: Final = "RDI URL"

_STABLE_COMMENT_IDS: Final[dict[str, str]] = {
    COMMENT_NAME_RDI: "#Comment_RDI",
    COMMENT_NAME_DESCRIPTION: "#Comment_RDI_Description",
    COMMENT_NAME_URL: "#Comment_RDI_URL",
}

_RDI_COMMENT_NAMES: Final[frozenset[str]] = frozenset(_STABLE_COMMENT_IDS)


def enrich_investigation_rdi_comments(
    arc_content: RoCrateContent,
    *,
    rdi: str,
    description: str = "",
    url: str = "",
) -> RoCrateContent:
    """Upsert Investigation RDI Comments on ``arc_content`` (mutates and returns it).

    Raises:
        InvalidJsonSemanticError: When a non-empty ``Comment[RDI]`` disagrees with ``rdi``.
    """
    graph = arc_content.get("@graph")
    if not isinstance(graph, list):
        msg = "RO-Crate @graph must be a list"
        raise InvalidJsonSemanticError(msg)

    existing_rdi = _find_comment_text(graph, COMMENT_NAME_RDI)
    if existing_rdi is not None:
        trimmed = existing_rdi.strip()
        if trimmed and trimmed != rdi:
            msg = f"Investigation Comment[RDI] value '{trimmed}' conflicts with authorized RDI '{rdi}'"
            raise InvalidJsonSemanticError(msg)

    values = {
        COMMENT_NAME_RDI: rdi,
        COMMENT_NAME_DESCRIPTION: description,
        COMMENT_NAME_URL: url,
    }
    _upsert_comments(graph, values)
    return arc_content


def _node_types(node: RoCrateGraphNode) -> set[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    return set()


def _is_comment_node(node: RoCrateGraphNode) -> bool:
    return "Comment" in _node_types(node)


def _comment_name(node: RoCrateGraphNode) -> str | None:
    name = node.get("name")
    return name if isinstance(name, str) else None


def _comment_text(node: RoCrateGraphNode) -> str | None:
    text = node.get("text")
    if isinstance(text, str):
        return text
    # Some producers use "value"; accept for conflict detection only.
    value = node.get("value")
    return value if isinstance(value, str) else None


def _find_comment_text(graph: list[JsonValue], name: str) -> str | None:
    for item in graph:
        if not isinstance(item, dict):
            continue
        node: RoCrateGraphNode = item
        if _is_comment_node(node) and _comment_name(node) == name:
            return _comment_text(node)
    return None


def _root_dataset(graph: list[JsonValue]) -> RoCrateGraphNode:
    for item in graph:
        if isinstance(item, dict) and item.get("@id") == "./":
            return item
    msg = "RO-Crate @graph must contain a root data entity with @id './'"
    raise InvalidJsonSemanticError(msg)


def _ref_id(ref: JsonValue) -> str | None:
    if isinstance(ref, dict):
        ref_id = ref.get("@id")
        return ref_id if isinstance(ref_id, str) else None
    return None


def _strip_rdi_comment_nodes(graph: list[JsonValue]) -> tuple[list[JsonValue], set[str]]:
    """Remove RDI Comment nodes; return remaining graph nodes and removed ``@id``s."""
    removed_ids: set[str] = set()
    keep: list[JsonValue] = []
    for item in graph:
        if not isinstance(item, dict):
            keep.append(item)
            continue
        node: RoCrateGraphNode = item
        if _is_comment_node(node) and _comment_name(node) in _RDI_COMMENT_NAMES:
            node_id = node.get("@id")
            if isinstance(node_id, str):
                removed_ids.add(node_id)
            continue
        keep.append(item)
    return keep, removed_ids


def _iter_comment_refs(existing_refs: JsonValue) -> list[JsonValue]:
    if isinstance(existing_refs, list):
        return list(existing_refs)
    if isinstance(existing_refs, dict):
        return [existing_refs]
    return []


def _retained_comment_refs(existing_refs: JsonValue, removed_ids: set[str]) -> list[JsonObject]:
    """Keep non-RDI comment links from the root dataset."""
    retained: list[JsonObject] = []
    stable_ids = set(_STABLE_COMMENT_IDS.values())
    for ref in _iter_comment_refs(existing_refs):
        ref_id = _ref_id(ref)
        if ref_id is None:
            if isinstance(ref, dict):
                retained.append(ref)
            continue
        if ref_id in removed_ids or ref_id in stable_ids:
            continue
        retained.append({"@id": ref_id})
    return retained


def _upsert_comments(graph: list[JsonValue], values: dict[str, str]) -> None:
    root = _root_dataset(graph)
    keep, removed_ids = _strip_rdi_comment_nodes(graph)

    new_comment_ids: list[str] = []
    for name, text in values.items():
        comment_id = _STABLE_COMMENT_IDS[name]
        keep.append({
            "@id": comment_id,
            "@type": "Comment",
            "name": name,
            "text": text,
        })
        new_comment_ids.append(comment_id)

    retained_refs = _retained_comment_refs(root.get("comment"), removed_ids)
    new_refs: list[JsonObject] = [{"@id": cid} for cid in new_comment_ids]
    root["comment"] = [*retained_refs, *new_refs]
    graph[:] = keep
