"""Expand/compact catalog Datasets to schema.org + ARC/Bioschemas context."""

from __future__ import annotations

import asyncio
from typing import cast

from pyld.jsonld import CompactOptions, Context, ExpandOptions, compact, expand  # type: ignore[import-untyped]
from pyld.options import ContextObject, DocumentLoaderCallable  # type: ignore[import-untyped]

from middleware.api.arc_store import ArcStoreError
from middleware.api.arc_store.consolidated_git.catalog_jsonld_extensions import (
    ARC_BIOSCHEMAS_EXTENSION_CONTEXT,
)
from middleware.api.arc_store.consolidated_git.jsonld_document_loader import create_offline_document_loader
from middleware.api.arc_store.consolidated_git.schema_org_context import load_schema_org_context
from middleware.shared.json_types import CatalogDatasetRecord, JsonObject, JsonValue

_DEFAULT_NORMALIZE_CONCURRENCY = 8

# Published catalog @context uses the conventional schema.org IRI (not an inline
# dump of the vendored release). Compact still uses the vendored document.
SCHEMA_ORG_CONTEXT_IRI = "https://schema.org"


def build_catalog_emitted_context() -> Context:
    """Public @context written into each catalog Dataset (URL + ARC/Bioschemas)."""
    return [SCHEMA_ORG_CONTEXT_IRI, cast(ContextObject, dict(ARC_BIOSCHEMAS_EXTENSION_CONTEXT))]


def build_catalog_compact_context(schema_org_document: JsonObject) -> Context:
    """Build pyld compact context from vendored schema.org document + extensions."""
    extension = cast(ContextObject, dict(ARC_BIOSCHEMAS_EXTENSION_CONTEXT))
    nested = schema_org_document.get("@context")
    if nested is None:
        return [cast(ContextObject, schema_org_document), extension]
    if isinstance(nested, str):
        return [nested, extension]
    if isinstance(nested, dict):
        return [cast(ContextObject, nested), extension]
    if isinstance(nested, list):
        return [*cast(list[str | ContextObject], nested), extension]
    raise ArcStoreError("schema.org document @context must be a string, object, or array")


def compact_catalog_dataset(
    dataset: CatalogDatasetRecord,
    compact_context: Context,
    *,
    emitted_context: Context | None = None,
    document_loader: DocumentLoaderCallable | None = None,
) -> CatalogDatasetRecord:
    """JSON-LD expand then compact a single Dataset record (sync; run off event loop)."""
    loader = document_loader or create_offline_document_loader()
    expand_options: ExpandOptions = {"documentLoader": loader}
    compact_options: CompactOptions = {"documentLoader": loader}
    try:
        expanded = expand(dataset, expand_options)
        compacted: object = compact(expanded, compact_context, compact_options)
    except Exception as exc:
        raise ArcStoreError(f"JSON-LD expand/compact failed for catalog Dataset: {exc}") from exc

    if not isinstance(compacted, dict):
        raise ArcStoreError("JSON-LD compact did not return a Dataset object")

    result: CatalogDatasetRecord = cast(CatalogDatasetRecord, dict(compacted))
    result["@context"] = cast(JsonValue, emitted_context or build_catalog_emitted_context())
    return result


async def normalize_catalog_datasets(
    datasets: list[CatalogDatasetRecord],
    *,
    concurrency: int = _DEFAULT_NORMALIZE_CONCURRENCY,
    schema_org_document: JsonObject | None = None,
) -> list[CatalogDatasetRecord]:
    """Expand/compact Datasets concurrently using the vendored schema.org context.

    Ordering of the returned list matches ``datasets`` input order; callers that
    need ``@id`` sort should serialize via ``serialize_catalog_file``.
    """
    if not datasets:
        return []

    document = schema_org_document if schema_org_document is not None else load_schema_org_context()
    compact_context = build_catalog_compact_context(document)
    emitted_context = build_catalog_emitted_context()
    loader = create_offline_document_loader()
    semaphore = asyncio.Semaphore(max(1, concurrency))
    loop = asyncio.get_running_loop()

    async def _one(dataset: CatalogDatasetRecord) -> CatalogDatasetRecord:
        async with semaphore:
            return await loop.run_in_executor(
                None,
                lambda: compact_catalog_dataset(
                    dataset,
                    compact_context,
                    emitted_context=emitted_context,
                    document_loader=loader,
                ),
            )

    return list(await asyncio.gather(*(_one(dataset) for dataset in datasets)))
