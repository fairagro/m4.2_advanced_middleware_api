"""Resolve RO-Crate @graph references into inline catalog Dataset fields."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from middleware.shared.json_types import CatalogDatasetRecord, JsonObject, JsonValue, RoCrateContent

logger = logging.getLogger(__name__)

_PERSON_PROPERTIES = ("creator", "author", "contributor")
_PERSON_FIELDS = ("givenName", "familyName", "name", "email", "sameAs", "identifier", "affiliation")
# ARCtrl puts every Investigation contact under Dataset.creator and encodes the ARC role
# as Person.jobTitle → DefinedTerm.name. Author-like roles stay on creator; any other
# role (including contributor) goes to contributor. Dual roles → both lists (#594).
# Comparison is alphanumeric-casefold so "Principal Investigator" matches.
_AUTHOR_ROLE_NAMES = frozenset({
    "author",
    "creator",
    "principalinvestigator",
    "investigator",
    "coauthor",
})
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
_CREATOR_ORGANIZATION_COMMENT = "creator organization"
_CREATOR_ORGANIZATION_URL_COMMENT = "creator organization url"
_LANDING_PAGE_COMMENT = "landing page"


@dataclass
class _CreatorOrgBuffers:
    names: list[str]
    urls: list[str]


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

    _materialize_person_properties_by_role(result, graph_index, warn)
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


def _materialize_person_identifier(value: JsonValue) -> JsonValue:
    """Pass through Person ``identifier``; flatten HTTP ``@id`` refs to plain URL strings."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        ref_id = _extract_ref_id(value)
        if isinstance(ref_id, str) and (ref_id.startswith("http://") or ref_id.startswith("https://")):
            return ref_id
        return value
    return value


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
    items = value if isinstance(value, list) else [value]
    people = [person for item in items if (person := _materialize_single_person(item, graph_index, warn)) is not None]
    if not people:
        return None
    return cast(JsonValue, people)


def _person_list_value(people: list[JsonObject]) -> JsonValue | None:
    """Return person slots as a JSON array so single-author records stay iterable."""
    if not people:
        return None
    return cast(JsonValue, people)


def _job_title_role_names(source: JsonObject, graph_index: dict[str, JsonObject]) -> list[str]:
    """Resolve Person.jobTitle (string, DefinedTerm ref, or list) to role name strings."""
    job_title = source.get("jobTitle")
    if job_title is None:
        return []
    items = job_title if isinstance(job_title, list) else [job_title]
    names: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            names.append(item.strip())
            continue
        if not isinstance(item, dict):
            continue
        inline_name = item.get("name")
        if isinstance(inline_name, str) and inline_name.strip():
            names.append(inline_name.strip())
            continue
        ref_id = _extract_ref_id(item)
        if ref_id is None:
            continue
        node = graph_index.get(ref_id)
        if node is None:
            continue
        term_name = node.get("name")
        if isinstance(term_name, str) and term_name.strip():
            names.append(term_name.strip())
    return names


def _normalize_role_key(role_name: str) -> str:
    return "".join(character for character in role_name.casefold() if character.isalnum())


def _role_flags(role_names: list[str], *, source_property: str) -> tuple[bool, bool]:
    """Return ``(author_like, contributor_like)`` for catalog slot assignment."""
    role_keys = {_normalize_role_key(name) for name in role_names if _normalize_role_key(name)}
    if role_keys:
        author_like = bool(role_keys & _AUTHOR_ROLE_NAMES)
        contributor_like = bool(role_keys - _AUTHOR_ROLE_NAMES)
        return author_like, contributor_like
    # No jobTitle: honour the RO-Crate property the Person was listed under.
    if source_property == "contributor":
        return False, True
    if source_property == "author":
        return True, False
    return True, False


def _set_person_slot(record: dict[str, JsonValue], key: str, people: list[JsonObject]) -> None:
    value = _person_list_value(people)
    if value is not None:
        record[key] = value


def _materialize_person_properties_by_role(
    record: dict[str, JsonValue],
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
) -> None:
    """Materialize creator/author/contributor and split ARCtrl jobTitle roles (#594)."""
    collected: list[tuple[JsonValue, str]] = []
    for key in _PERSON_PROPERTIES:
        if key not in record:
            continue
        value = record.pop(key)
        items = value if isinstance(value, list) else [value]
        collected.extend((item, key) for item in items)

    creators: list[JsonObject] = []
    authors: list[JsonObject] = []
    contributors: list[JsonObject] = []
    for item, source_property in collected:
        source = _resolve_person_source(item, graph_index, warn)
        if source is None:
            continue
        person = _materialize_single_person(item, graph_index, warn)
        if person is None:
            continue
        author_like, contributor_like = _role_flags(
            _job_title_role_names(source, graph_index),
            source_property=source_property,
        )
        if author_like:
            if source_property == "author":
                authors.append(person)
            else:
                creators.append(person)
        if contributor_like:
            # Shallow copy when also author-like so the two slots do not share one dict.
            contributors.append(dict(person) if author_like else person)

    _set_person_slot(record, "creator", creators)
    _set_person_slot(record, "author", authors)
    _set_person_slot(record, "contributor", contributors)


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
        elif field == "identifier":
            # schema.org identifier is not @type:@id; emit plain HTTP strings so compact
            # keeps a URL string (not {"id": …}). PropertyValue objects pass through (#551).
            person[field] = _materialize_person_identifier(field_value)
        else:
            person[field] = field_value
    _strip_fragment_ids(person)
    return person


def _is_http_iri(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _license_from_node(license_node: JsonObject) -> JsonObject | None:
    url_value = license_node.get("url")
    if isinstance(url_value, str):
        return {"@type": "CreativeWork", "url": url_value}
    if isinstance(url_value, dict):
        url_ref = _extract_ref_id(url_value)
        if isinstance(url_ref, str) and _is_http_iri(url_ref):
            return {"@type": "CreativeWork", "url": url_ref}
    text_value = license_node.get("text")
    if isinstance(text_value, str):
        # ARCtrl often stores the licence IRI in ``text`` (harvester ≥ 3.2.0).
        if _is_http_iri(text_value):
            return {"@type": "CreativeWork", "url": text_value}
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
    if ref_id is None:
        return value
    license_node = graph_index.get(ref_id)
    if license_node is None:
        # Direct schema.org license IRIs may have no CreativeWork node in @graph.
        if _is_http_iri(ref_id):
            return {"@type": "CreativeWork", "url": ref_id}
        warn(f"missing license reference {ref_id}")
        return None
    resolved = _license_from_node(license_node)
    if resolved is None:
        warn(f"license node {ref_id} has no url or text")
    return resolved


def _append_keywords(record: dict[str, JsonValue], text: str) -> None:
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        return
    existing = record.get("keywords")
    if existing is None:
        record["keywords"] = cast(JsonValue, parts)
        return
    if isinstance(existing, list):
        record["keywords"] = cast(JsonValue, [*existing, *parts])
        return
    record["keywords"] = cast(JsonValue, [existing, *parts])


def _split_semicolon_list(text: str) -> list[str]:
    return [part.strip() for part in text.split(";") if part.strip()]


def _build_creator_organizations(names: list[str], urls: list[str]) -> list[JsonObject]:
    organizations: list[JsonObject] = []
    for index, name in enumerate(names):
        organization: JsonObject = {"@type": "Organization", "name": name}
        if index < len(urls):
            # IRI as ``{"@id": …}`` so catalog compact keeps the ``url`` term (not ``schema:url``).
            organization["url"] = {"@id": urls[index]}
        organizations.append(organization)
    return organizations


def _append_organization_creators(record: dict[str, JsonValue], organizations: list[JsonObject]) -> None:
    if not organizations:
        return
    existing = record.get("creator")
    if existing is None:
        record["creator"] = cast(JsonValue, organizations)
        return
    if isinstance(existing, list):
        record["creator"] = cast(JsonValue, [*existing, *organizations])
        return
    record["creator"] = cast(JsonValue, [existing, *organizations])


def _resolve_comment_node(
    item: JsonValue,
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
    return node


def _consume_mapped_comment(
    name_key: str,
    text_str: str,
    record: dict[str, JsonValue],
    creator_orgs: _CreatorOrgBuffers,
) -> bool:
    """Apply first-class Comment mappings; return True when the Comment is consumed."""
    if name_key == _CREATOR_ORGANIZATION_COMMENT:
        creator_orgs.names.extend(_split_semicolon_list(text_str))
        return True
    if name_key == _CREATOR_ORGANIZATION_URL_COMMENT:
        creator_orgs.urls.extend(_split_semicolon_list(text_str))
        return True
    if name_key == _LANDING_PAGE_COMMENT:
        # IRI as ``{"@id": …}`` so catalog compact keeps the ``url`` term (not ``schema:url``).
        landing_url = text_str.strip()
        if "url" not in record and landing_url:
            record["url"] = {"@id": landing_url}
        return True
    mapped = _LDComment_NAME_MAP.get(name_key)
    if mapped == "keywords":
        _append_keywords(record, text_str)
        return True
    if mapped == "inLanguage":
        record["inLanguage"] = text_str
        return True
    return False


def _materialize_single_comment(
    item: JsonValue,
    record: dict[str, JsonValue],
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
    creator_orgs: _CreatorOrgBuffers,
) -> JsonObject | None:
    node = _resolve_comment_node(item, graph_index, warn)
    if node is None:
        return None
    name = node.get("name")
    text = node.get("text")
    name_str = name if isinstance(name, str) else ""
    text_str = text if isinstance(text, str) else ""
    if _consume_mapped_comment(name_str.casefold(), text_str, record, creator_orgs):
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
    creator_orgs = _CreatorOrgBuffers(names=[], urls=[])
    inline_comments = [
        comment
        for item in items
        if (comment := _materialize_single_comment(item, record, graph_index, warn, creator_orgs)) is not None
    ]
    if inline_comments:
        record["comment"] = cast(JsonValue, inline_comments)
    _append_organization_creators(
        record,
        _build_creator_organizations(creator_orgs.names, creator_orgs.urls),
    )


def _materialize_citation(
    value: JsonValue,
    graph_index: dict[str, JsonObject],
    warn: Callable[[str], None],
) -> JsonValue | None:
    items = value if isinstance(value, list) else [value]
    citations = [
        citation for item in items if (citation := _materialize_single_citation(item, graph_index, warn)) is not None
    ]
    if not citations:
        return None
    return cast(JsonValue, citations)


def _materialize_single_citation(
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
    items: list[JsonValue]
    if isinstance(value, list):
        items = value
    elif isinstance(value, str | dict):
        items = [value]
    else:
        return None
    parts = [
        part
        for item in items
        if (part := _materialize_has_part_item(item, graph_index, depth=depth, warn=warn)) is not None
    ]
    if not parts:
        return None
    return cast(JsonValue, parts)


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
        if prop in node:
            part[prop] = node[prop]
    _materialize_person_properties_by_role(part, graph_index, warn)

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
