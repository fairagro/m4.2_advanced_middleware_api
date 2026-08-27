"""Offline JSON-LD document loader for vendored RO-Crate contexts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from pyld.documentloader.base import RemoteDocument  # type: ignore[import-untyped]
from pyld.options import DocumentLoaderCallable  # type: ignore[import-untyped]

from middleware.shared.json_types import JsonObject

_CONTEXTS_DIR = Path(__file__).resolve().parent / "jsonld_contexts"

# Map remote context URLs (as used in ARC fixtures/production) to vendored files.
_VENDOR_CONTEXT_FILES: dict[str, str] = {
    "https://w3id.org/ro/crate/1.1/context": "ro-crate-1.1-context.json",
    "http://w3id.org/ro/crate/1.1/context": "ro-crate-1.1-context.json",
    "https://w3id.org/ro/crate/1.2/context": "ro-crate-1.2-context.json",
    "http://w3id.org/ro/crate/1.2/context": "ro-crate-1.2-context.json",
}


@lru_cache(maxsize=8)
def _load_vendor_document(filename: str) -> JsonObject:
    path = _CONTEXTS_DIR / filename
    with path.open(encoding="utf-8") as handle:
        loaded: object = json.load(handle)
    if not isinstance(loaded, dict):
        msg = f"Vendored JSON-LD context {filename} must be a JSON object"
        raise TypeError(msg)
    return cast(JsonObject, loaded)


def create_offline_document_loader() -> DocumentLoaderCallable:
    """Return a pyld documentLoader that serves only vendored RO-Crate contexts."""

    def document_loader(url: str, _options: dict[str, Any]) -> RemoteDocument:
        filename = _VENDOR_CONTEXT_FILES.get(url)
        if filename is None:
            msg = f"Refusing network fetch for unknown JSON-LD context URL: {url}"
            raise ValueError(msg)
        document = _load_vendor_document(filename)
        return {
            "contentType": "application/ld+json",
            "contextUrl": None,
            "documentUrl": url,
            "document": document,
        }

    return document_loader
