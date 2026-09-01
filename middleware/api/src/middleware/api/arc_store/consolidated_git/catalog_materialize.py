"""Resolve RO-Crate @graph references into inline catalog Dataset fields."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast

from middleware.shared.json_types import CatalogDatasetRecord, JsonObject, JsonValue, RoCrateContent

logger = logging.getLogger(__name__)

_PERSON_PROPERTIES = ("creator", "author", "contributor")
_PERSON_FIELDS = ("givenName", "familyName", "name", "email", "sameAs", "affiliation")
_DATASET_PART_FIELDS = (
    "additionalType",
    "identifier",
    "name",
    "description",
    "datePublished",
    "dateModified",
)
_CITATION_FIELDS = ("headline", "name", "identifier", "url", "sameAs", "datePublished")
_CITATION_TYPES = ("ScholarlyArticle", "CreativeWork")
_CITATION_IRI_FIELDS = frozenset({"url", "sameAs"})
_ID_KEYS = frozenset({"@id", "id"})
_MAX_HAS_PART_DEPTH = 2
_LDComment_NAME_MAP = {
    "keywords": "keywords",
    "language": "inLanguage",
}


def build_graph_index(arc_content: RoCrateContent) -> dict[str, JsonObject]:
    """Index ``@graph`` nodes by ``@id`` for reference lookup."""
    graph = arc_content.get("@graph")
    if not isinstance(graph, list):
        return {}
    index: dict[str, JsonObject] = {}
    for node in graph:
        if not isinstance(node, dict):
            continue
        node_id = node.get("@id")
        if isinstance(node_id, str):
            index[node_id] = node
    return index


def materialize_catalog_dataset(
    record: CatalogDatasetRecord,
    arc_content: RoCrateContent,
    *,
    arc_id: str | None = None,
) -> CatalogDatasetRecord:
    """Inline selected RO-Crate references from ``@graph`` into a catalog Dataset."""
    graph_index = build_graph_index(arc_content)
    result: dict[str, JsonValue] = dict(record)
    arc_label = f" for ARC {arc_id}" if arc_id else ""

    def warn(message: str) -> None:
        logger.warning("Catalog materialize%s: %s", arc_label, message)

    _replace_or_delete(result, _PERSON_PROPERTIES, graph_index, warn, _materialize_person_value)
    _replace_or_delete(result, ("license",), graph_index, warn, _materialize_license)
    if "comment" in result:
        _materialize_dataset_comments(result, graph_index, warn)
    _replace_or_delete(result, ("citation",), graph_index, warn, _materialize_citation)
    _replace_or_delete(
        result,
        ("hasPart",),
        graph_index,
        warn,
        lambda value, index, warn_fn: _materialize_has_part(value, index, depth=1, warn=warn_fn),
    )
    return cast(CatalogDatasetRecord, result)


def _replace_or_delete(
    record: dict[str, JsonValue],
    keys: tuple[str, ...],
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
    materializer: Callable[[JsonValue, dict[str, JsonObject], Callable[[str], None]], JsonValue | None],
) -> None:
    for key in keys:
        if key not in record:
            continue
        materialized = materializer(record[key], graph_index, warn)
        if materialized is None:
            del record[key]
        else:
            record[key] = materialized


def _extract_ref_id(value: JsonValue | None) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        node_id = value.get("@id")
        if isinstance(node_id, str):
            return node_id
        alt_id = value.get("id")
        if isinstance(alt_id, str):
            return alt_id
    return None


def _node_has_type(node: JsonObject, type_name: str) -> bool:
    node_type = node.get("@type")
    if isinstance(node_type, str):
        return node_type == type_name or node_type.endswith(f"/{type_name}")
    if isinstance(node_type, list):
        return any(
            isinstance(item, str) and (item == type_name or item.endswith(f"/{type_name}")) for item in node_type
        )
    return False


def _is_fragment_id(node_id: str) -> bool:
    return node_id.startswith("#")


def _strip_fragment_ids(node: JsonObject) -> None:
    node_id = node.get("@id")
    if isinstance(node_id, str) and _is_fragment_id(node_id):
        del node["@id"]
    alt_id = node.get("id")
    if isinstance(alt_id, str) and _is_fragment_id(alt_id):
        del node["id"]


def _materialize_same_as(value: JsonValue, graph_index: dict[str, JsonObject]) -> JsonValue:
    r"""Preserve ``{"@id": "https://…"}`` shape so compact keeps the ``sameAs`` term."""
    if isinstance(value, str) and (value.startswith("http://") or value.startswith("https://")):
        return {"@id": value}
    if isinstance(value, dict):
        ref_id = _extract_ref_id(value)
        if isinstance(ref_id, str) and (ref_id.startswith("http://") or ref_id.startswith("https://")):
            return {"@id": ref_id}
    return _materialize_iri_value(value, graph_index)


def _materialize_iri_value(value: JsonValue, graph_index: dict[str, JsonObject]) -> JsonValue:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return value
    ref_id = _extract_ref_id(value)
    if ref_id is None:
        return value
    if ref_id.startswith("http://") or ref_id.startswith("https://"):
        return ref_id
    referenced = graph_index.get(ref_id)
    if referenced is None:
        return value
    name = referenced.get("name")
    return name if isinstance(name, str) else value


def _materialize_person_value(
    value: JsonValue,
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
) -> JsonValue | None:
    if isinstance(value, list):
        people = [
            person for item in value if (person := _materialize_single_person(item, graph_index, warn)) is not None
        ]
        if not people:
            return None
        return cast(JsonValue, people)
    return cast(JsonValue | None, _materialize_single_person(value, graph_index, warn))


def _resolve_person_source(
    value: JsonValue,
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
) -> JsonObject | None:
    ref_id = _extract_ref_id(value)
    if ref_id is not None:
        node = graph_index.get(ref_id)
        if node is None:
            warn(f"missing Person reference {ref_id}")
            return None
        if not _node_has_type(node, "Person"):
            warn(f"reference {ref_id} is not a Person node")
            return None
        source = dict(node)
        if isinstance(value, dict):
            for key, item in value.items():
                if key not in _ID_KEYS:
                    source[key] = item
        return source
    if isinstance(value, dict) and _node_has_type(value, "Person"):
        return dict(value)
    return None


def _materialize_single_person(
    value: JsonValue,
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
) -> JsonObject | None:
    source = _resolve_person_source(value, graph_index, warn)
    if source is None:
        return None
    person: JsonObject = {"@type": "Person"}
    for field in _PERSON_FIELDS:
        if field not in source:
            continue
        field_value = source[field]
        if field == "affiliation":
            person[field] = _materialize_iri_value(field_value, graph_index)
        elif field == "sameAs":
            person[field] = _materialize_same_as(field_value, graph_index)
        else:
            person[field] = field_value
    _strip_fragment_ids(person)
    return person


def _license_from_node(license_node: JsonObject) -> JsonObject | None:
    url_value = license_node.get("url")
    if isinstance(url_value, str):
        return {"@type": "CreativeWork", "url": url_value}
    if isinstance(url_value, dict):
        url_ref = _extract_ref_id(url_value)
        if isinstance(url_ref, str) and (url_ref.startswith("http://") or url_ref.startswith("https://")):
            return {"@type": "CreativeWork", "url": url_ref}
    text_value = license_node.get("text")
    if isinstance(text_value, str):
        return {"@type": "CreativeWork", "text": text_value}
    return None


def _materialize_license(
    value: JsonValue,
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
) -> JsonValue | None:
    if isinstance(value, str):
        return value
    ref_id = _extract_ref_id(value)
    if ref_id != "#LICENSE":
        return value
    license_node = graph_index.get("#LICENSE")
    if license_node is None:
        warn("missing #LICENSE node")
        return None
    resolved = _license_from_node(license_node)
    if resolved is None:
        warn("#LICENSE node has no url or text")
    return resolved


def _append_keywords(record: dict[str, JsonValue], text: str) -> None:
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        return
    existing = record.get("keywords")
    if existing is None:
        record["keywords"] = cast(JsonValue, parts if len(parts) > 1 else parts[0])
        return
    if isinstance(existing, list):
        record["keywords"] = cast(JsonValue, [*existing, *parts])
        return
    record["keywords"] = cast(JsonValue, [existing, *parts])


def _materialize_single_comment(
    item: JsonValue,
    record: dict[str, JsonValue],
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
) -> JsonObject | None:
    ref_id = _extract_ref_id(item)
    if ref_id is None:
        return None
    node = graph_index.get(ref_id)
    if node is None:
        warn(f"missing Comment reference {ref_id}")
        return None
    if not _node_has_type(node, "Comment"):
        warn(f"reference {ref_id} is not a Comment node")
        return None
    name = node.get("name")
    text = node.get("text")
    name_str = name if isinstance(name, str) else ""
    text_str = text if isinstance(text, str) else ""
    mapped = _LDComment_NAME_MAP.get(name_str.casefold())
    if mapped == "keywords":
        _append_keywords(record, text_str)
        return None
    if mapped == "inLanguage":
        record["inLanguage"] = text_str
        return None
    comment: JsonObject = {"@type": "Comment"}
    if name_str:
        comment["name"] = name
    if text_str:
        comment["text"] = text
    _strip_fragment_ids(comment)
    return comment


def _materialize_dataset_comments(
    record: dict[str, JsonValue],
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
) -> None:
    comment_value = record.pop("comment", None)
    if comment_value is None:
        return
    items = comment_value if isinstance(comment_value, list) else [comment_value]
    inline_comments = [
        comment
        for item in items
        if (comment := _materialize_single_comment(item, record, graph_index, warn)) is not None
    ]
    if inline_comments:
        record["comment"] = cast(
            JsonValue,
            inline_comments if len(inline_comments) > 1 else inline_comments[0],
        )


def _materialize_citation(
    value: JsonValue,
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
) -> JsonObject | None:
    ref_id = _extract_ref_id(value)
    if ref_id is None:
        return None
    node = graph_index.get(ref_id)
    if node is None:
        warn(f"missing citation reference {ref_id}")
        return None
    if not any(_node_has_type(node, type_name) for type_name in _CITATION_TYPES):
        warn(f"reference {ref_id} is not a ScholarlyArticle or CreativeWork node")
        return None
    citation: JsonObject = {}
    node_type = node.get("@type")
    if isinstance(node_type, str | list):
        citation["@type"] = node_type
    for field in _CITATION_FIELDS:
        if field not in node:
            continue
        field_value = node[field]
        citation[field] = (
            _materialize_iri_value(field_value, graph_index) if field in _CITATION_IRI_FIELDS else field_value
        )
    _strip_fragment_ids(citation)
    return citation if citation else None


def _materialize_has_part(
    value: JsonValue,
    graph_index: dict[str, JsonObject],
    *,
    depth: int,
    warn: Callable[[str], None],
) -> JsonValue | None:
    if depth > _MAX_HAS_PART_DEPTH:
        return None
    if isinstance(value, list):
        parts = [
            part
            for item in value
            if (part := _materialize_has_part_item(item, graph_index, depth=depth, warn=warn)) is not None
        ]
        if not parts:
            return None
        return cast(JsonValue, parts)
    if isinstance(value, dict):
        return _materialize_has_part_item(value, graph_index, depth=depth, warn=warn)
    return None


def _copy_dataset_part_fields(part: JsonObject, node: JsonObject) -> None:
    for field in _DATASET_PART_FIELDS:
        if field in node:
            part[field] = node[field]


def _materialize_has_part_item(
    value: JsonValue,
    graph_index: dict[str, JsonObject],
    *,
    depth: int,
    warn: Callable[[str], None],
) -> JsonObject | None:
    ref_id = _extract_ref_id(value)
    if ref_id is None:
        return None
    node = graph_index.get(ref_id)
    if node is None:
        warn(f"missing hasPart reference {ref_id}")
        return None
    if not _node_has_type(node, "Dataset"):
        warn(f"reference {ref_id} is not a Dataset node")
        return None

    part: JsonObject = {"@id": ref_id, "@type": "Dataset"}
    _copy_dataset_part_fields(part, node)
    for prop in _PERSON_PROPERTIES:
        if prop not in node:
            continue
        materialized = _materialize_person_value(node[prop], graph_index, warn)
        if materialized is not None:
            part[prop] = materialized

    nested_has_part = node.get("hasPart")
    if depth < _MAX_HAS_PART_DEPTH and node.get("additionalType") == "Study" and nested_has_part is not None:
        materialized_nested = _materialize_has_part(
            nested_has_part,
            graph_index,
            depth=depth + 1,
            warn=warn,
        )
        if materialized_nested is not None:
            part["hasPart"] = materialized_nested
    return part
