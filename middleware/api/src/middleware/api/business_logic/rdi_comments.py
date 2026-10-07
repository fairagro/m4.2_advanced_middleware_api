"""Embed authorized source RDI as ISA Investigation Comments in RO-Crate JSON.

ARCtrl 3.2.x ``ARC.Write`` fails when **one** Comment holder (Investigation, Study,
Assay, or Person) has two Comments with the same ``name`` — Python surfaces this as
``TypeError: Object is not iterable`` (https://github.com/nfdi4plants/ARCtrl/issues/641).
Same names on **different** holders (Investigation ``Comment[RDI]`` plus Study
``Comment[RDI]``) are valid. This module therefore upserts only Investigation
Comments linked from the root dataset ``./`` and must not leave two Investigation
Comments with names ``RDI`` / ``RDI Description`` / ``RDI URL``.

A separate ARCtrl bug duplicates Investigation ``dateModified`` Comments on
RO-Crate read (https://github.com/nfdi4plants/ARCtrl/issues/642); the harvester
documents workarounds in
https://github.com/fairagro/m4.2_middleware_harvester/pull/446. That is out of
scope here.
"""

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

    existing_rdi = _find_investigation_comment_text(graph, COMMENT_NAME_RDI)
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


def _comment_ref_ids(existing_refs: JsonValue | None) -> set[str]:
    ids: set[str] = set()
    for ref in _iter_comment_refs(existing_refs):
        ref_id = _ref_id(ref)
        if ref_id is not None:
            ids.add(ref_id)
    return ids


def _nodes_by_id(graph: list[JsonValue]) -> dict[str, RoCrateGraphNode]:
    by_id: dict[str, RoCrateGraphNode] = {}
    for item in graph:
        if not isinstance(item, dict):
            continue
        node_id = item.get("@id")
        if isinstance(node_id, str):
            by_id[node_id] = item
    return by_id


def _find_investigation_comment_text(graph: list[JsonValue], name: str) -> str | None:
    """Read a Comment linked from the root dataset only (not Study/Assay comments)."""
    root = _root_dataset(graph)
    by_id = _nodes_by_id(graph)
    for ref_id in _comment_ref_ids(root.get("comment")):
        node = by_id.get(ref_id)
        if node is None:
            continue
        if _is_comment_node(node) and _comment_name(node) == name:
            return _comment_text(node)
    return None


def _non_root_comment_ref_ids(graph: list[JsonValue]) -> set[str]:
    referenced: set[str] = set()
    for item in graph:
        if not isinstance(item, dict) or item.get("@id") == "./":
            continue
        referenced.update(_comment_ref_ids(item.get("comment")))
    return referenced


def _investigation_rdi_comment_ids(graph: list[JsonValue], root: RoCrateGraphNode) -> set[str]:
    """Root-linked Comment ``@id``s whose name is one of the RDI Investigation Comments."""
    by_id = _nodes_by_id(graph)
    matched: set[str] = set()
    for ref_id in _comment_ref_ids(root.get("comment")):
        node = by_id.get(ref_id)
        if node is None:
            continue
        if _is_comment_node(node) and _comment_name(node) in _RDI_COMMENT_NAMES:
            matched.add(ref_id)
    return matched


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


def _iter_comment_refs(existing_refs: JsonValue | None) -> list[JsonValue]:
    if isinstance(existing_refs, list):
        return list(existing_refs)
    if isinstance(existing_refs, dict):
        return [existing_refs]
    return []


def _retained_comment_refs(existing_refs: JsonValue | None, drop_ids: set[str]) -> list[JsonObject]:
    """Keep non-RDI comment links from the root dataset."""
    retained: list[JsonObject] = []
    stable_ids = set(_STABLE_COMMENT_IDS.values())
    for ref in _iter_comment_refs(existing_refs):
        ref_id = _ref_id(ref)
        if ref_id is None:
            if isinstance(ref, dict):
                retained.append(ref)
            continue
        if ref_id in drop_ids or ref_id in stable_ids:
            continue
        retained.append({"@id": ref_id})
    return retained


def _strip_unshared_investigation_rdi_nodes(
    graph: list[JsonValue],
    *,
    root_rdi_ids: set[str],
    shared_ids: set[str],
) -> list[JsonValue]:
    """Drop Investigation RDI Comment nodes that no other entity still references."""
    keep: list[JsonValue] = []
    for item in graph:
        if not isinstance(item, dict):
            keep.append(item)
            continue
        node_id = item.get("@id")
        if isinstance(node_id, str) and node_id in root_rdi_ids and node_id not in shared_ids:
            continue
        keep.append(item)
    return keep


def _upsert_comments(graph: list[JsonValue], values: dict[str, str]) -> None:
    root = _root_dataset(graph)
    root_rdi_ids = _investigation_rdi_comment_ids(graph, root)
    shared_ids = root_rdi_ids & _non_root_comment_ref_ids(graph)
    keep = _strip_unshared_investigation_rdi_nodes(
        graph,
        root_rdi_ids=root_rdi_ids,
        shared_ids=shared_ids,
    )

    keep_ids: set[str] = set()
    for item in keep:
        if isinstance(item, dict):
            item_id = item.get("@id")
            if isinstance(item_id, str):
                keep_ids.add(item_id)
    new_comment_ids: list[str] = []
    for name, text in values.items():
        comment_id = _STABLE_COMMENT_IDS[name]
        if comment_id not in keep_ids:
            keep.append({
                "@id": comment_id,
                "@type": "Comment",
                "name": name,
                "text": text,
            })
            keep_ids.add(comment_id)
        new_comment_ids.append(comment_id)

    retained_refs = _retained_comment_refs(root.get("comment"), root_rdi_ids)
    new_refs: list[JsonObject] = [{"@id": cid} for cid in new_comment_ids]
    root["comment"] = [*retained_refs, *new_refs]
    graph[:] = keep
