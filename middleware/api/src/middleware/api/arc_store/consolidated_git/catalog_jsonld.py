"""Expand/compact catalog Datasets to schema.org + ARC/Bioschemas context."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import cast

from pyld.jsonld import (  # type: ignore[import-untyped]
    DEFAULT_BASE_IRI,
    CompactOptions,
    Context,
    ExpandOptions,
    compact,
    expand,
)
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

# Internal compact/expand base only (B1). Same IRI pyld uses when none is set,
# so ARCtrl-relative IDs re-relativize. Must not appear in emitted @context.
CATALOG_JSONLD_COMPACT_BASE_IRI = DEFAULT_BASE_IRI


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
    expand_options: ExpandOptions = {
        "documentLoader": loader,
        "base": CATALOG_JSONLD_COMPACT_BASE_IRI,
    }
    compact_options: CompactOptions = {
        "documentLoader": loader,
        "base": CATALOG_JSONLD_COMPACT_BASE_IRI,
    }
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

    Raises:
        ArcStoreError: If any Dataset fails expand/compact (fail-closed).
    """
    if not datasets:
        return []

    labeled = [(str(index), dataset) for index, dataset in enumerate(datasets)]
    outcome = await normalize_catalog_datasets_best_effort(
        labeled,
        concurrency=concurrency,
        schema_org_document=schema_org_document,
    )
    if outcome.skipped:
        # First failure reason; strict callers expect a single exception.
        _arc_id, reason = outcome.skipped[0]
        raise ArcStoreError(reason)
    return outcome.datasets


@dataclass(frozen=True, slots=True)
class CatalogNormalizeOutcome:
    """Result of best-effort catalog Dataset normalize (partial push)."""

    datasets: list[CatalogDatasetRecord]
    skipped: list[tuple[str, str]]
    """``(arc_id, error_message)`` for Datasets that failed extract-independent normalize."""


async def normalize_catalog_datasets_best_effort(
    items: list[tuple[str, CatalogDatasetRecord]],
    *,
    concurrency: int = _DEFAULT_NORMALIZE_CONCURRENCY,
    schema_org_document: JsonObject | None = None,
) -> CatalogNormalizeOutcome:
    """Expand/compact Datasets concurrently; skip failures instead of aborting.

    Successful Datasets keep input order. Used by consolidated finalize for
    interim partial push (no last-good retention yet — see issue #356).
    """
    if not items:
        return CatalogNormalizeOutcome(datasets=[], skipped=[])

    document = schema_org_document if schema_org_document is not None else load_schema_org_context()
    compact_context = build_catalog_compact_context(document)
    emitted_context = build_catalog_emitted_context()
    loader = create_offline_document_loader()
    semaphore = asyncio.Semaphore(max(1, concurrency))
    loop = asyncio.get_running_loop()

    async def _one(arc_id: str, dataset: CatalogDatasetRecord) -> CatalogDatasetRecord | tuple[str, str]:
        async with semaphore:
            try:
                return await loop.run_in_executor(
                    None,
                    lambda: compact_catalog_dataset(
                        dataset,
                        compact_context,
                        emitted_context=emitted_context,
                        document_loader=loader,
                    ),
                )
            except Exception as exc:  # noqa: BLE001 — per-ARC isolate for partial push
                return (arc_id, f"JSON-LD expand/compact failed for ARC {arc_id}: {exc}")

    results = await asyncio.gather(*(_one(arc_id, dataset) for arc_id, dataset in items))
    datasets: list[CatalogDatasetRecord] = []
    skipped: list[tuple[str, str]] = []
    for result in results:
        if isinstance(result, tuple):
            skipped.append(result)
        else:
            datasets.append(result)
    return CatalogNormalizeOutcome(datasets=datasets, skipped=skipped)
