"""Schema.org Dataset extraction and byte-stable catalog serialization."""

from __future__ import annotations

import json
from collections import Counter

from middleware.shared.api_models.common.rocrate import extract_identifier
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

    extract_identifier(chosen)

    # Keep a self-contained record: copy node and attach top-level @context when present.
    record = chosen.copy()
    context = arc_content.get("@context")
    if context is not None and "@context" not in record:
        record["@context"] = context
    return record


def catalog_dataset_identifier(dataset: CatalogDatasetRecord) -> str:
    """Return normalized Dataset ``identifier`` (same rules as RO-Crate root entity)."""
    try:
        return extract_identifier(dataset)
    except ValueError:
        return ""


def _dataset_sort_key(
    dataset: CatalogDatasetRecord,
    *,
    identifier: str,
    identifier_counts: Counter[str],
) -> tuple[str, str]:
    """Primary ``identifier``; canonical JSON only for missing/duplicate identifiers."""
    if not identifier or identifier_counts[identifier] > 1:
        tie = json.dumps(dataset, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    else:
        tie = ""
    return (identifier, tie)


def serialize_catalog_file(datasets: list[CatalogDatasetRecord]) -> bytes:
    """Serialize Dataset list to byte-stable JSON (UTF-8, sorted keys, stable separators)."""
    identifiers = [catalog_dataset_identifier(dataset) for dataset in datasets]
    identifier_counts = Counter(identifiers)
    indexed = list(zip(datasets, identifiers, strict=True))
    ordered = [
        dataset
        for dataset, _identifier in sorted(
            indexed,
            key=lambda item: _dataset_sort_key(
                item[0],
                identifier=item[1],
                identifier_counts=identifier_counts,
            ),
        )
    ]
    text = json.dumps(ordered, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")
