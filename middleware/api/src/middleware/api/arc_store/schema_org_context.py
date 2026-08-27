"""Vendored schema.org JSON-LD context for catalog compact (offline)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import cast

from middleware.shared.json_types import JsonObject

# Release copied into the repo (same pin formerly fetched at runtime). Bump the
# filename when upgrading the pinned schema.org release used for catalog compact.
_SCHEMA_ORG_CONTEXT_FILENAME = "schemaorg-30.0-context.jsonld"
_CONTEXTS_DIR = Path(__file__).resolve().parent / "jsonld_contexts"


@lru_cache(maxsize=1)
def load_schema_org_context() -> JsonObject:
    """Load the vendored schema.org release context document."""
    path = _CONTEXTS_DIR / _SCHEMA_ORG_CONTEXT_FILENAME
    with path.open(encoding="utf-8") as handle:
        loaded: object = json.load(handle)
    if not isinstance(loaded, dict):
        msg = f"Vendored schema.org context {_SCHEMA_ORG_CONTEXT_FILENAME} must be a JSON object"
        raise TypeError(msg)
    return cast(JsonObject, loaded)
