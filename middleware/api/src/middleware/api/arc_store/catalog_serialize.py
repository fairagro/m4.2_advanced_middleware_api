"""Schema.org Dataset extraction and byte-stable catalog serialization."""

from __future__ import annotations

import json

from middleware.shared.json_types import CatalogDatasetRecord, JsonValue, RoCrateContent


def _type_includes_dataset(node_type: JsonValue | None) -> bool:
    if isinstance(node_type, str):
        return node_type == "Dataset" or node_type.endswith("/Dataset")
    if isinstance(node_type, list):
        return any(_type_includes_dataset(item) for item in node_type)
    return False


def extract_catalog_dataset(arc_content: RoCrateContent) -> CatalogDatasetRecord:
    """Extract the catalog Schema.org Dataset from an ARC RO-Crate document.

    Prefers the root entity (``@id`` ``./``) when it is a Dataset; otherwise the
    first ``@graph`` node typed as Dataset.
    """
    graph = arc_content.get("@graph")
    if not isinstance(graph, list):
        msg = "RO-Crate content missing @graph list"
        raise ValueError(msg)

    datasets: list[CatalogDatasetRecord] = []
    root_dataset: CatalogDatasetRecord | None = None
    for node in graph:
        if not isinstance(node, dict):
            continue
        if not _type_includes_dataset(node.get("@type")):
            continue
        datasets.append(node)
        node_id = node.get("@id")
        if node_id == "./":
            root_dataset = node

    chosen = root_dataset or (datasets[0] if datasets else None)
    if chosen is None:
        msg = "RO-Crate @graph has no Dataset node for catalog extraction"
        raise ValueError(msg)

    # Keep a self-contained record: copy node and attach top-level @context when present.
    record: CatalogDatasetRecord = dict(chosen)
    context = arc_content.get("@context")
    if context is not None and "@context" not in record:
        record["@context"] = context
    return record


def _dataset_sort_key(dataset: CatalogDatasetRecord) -> tuple[str, str]:
    node_id = dataset.get("@id")
    id_part = node_id if isinstance(node_id, str) else ""
    return (id_part, json.dumps(dataset, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def serialize_catalog_file(datasets: list[CatalogDatasetRecord]) -> bytes:
    """Serialize Dataset list to byte-stable JSON (UTF-8, sorted keys, stable separators)."""
    ordered = sorted(datasets, key=_dataset_sort_key)
    text = json.dumps(ordered, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")
